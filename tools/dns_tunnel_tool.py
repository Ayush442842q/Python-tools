#!/usr/bin/env python3
"""
DNS Tunneling Client & Server Daemon Simulator

A utility to simulate tunneling data (text or files) over DNS queries.
Encodes payloads using Base32 (DNS-safe) and encapsulates them in standard DNS 
request packets. The simulator runs either as a client sending queries, or as 
a mock DNS server receiving and decoding queries.
"""

import argparse
import base64
import os
import socket
import sys
from typing import Tuple, Optional, Dict

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def log_success(msg: str):
    print(color_text("[+] " + msg, COLOR_GREEN))

def log_info(msg: str):
    print(color_text("[*] " + msg, COLOR_CYAN))

def log_warning(msg: str):
    print(color_text("[!] " + msg, COLOR_YELLOW))

def log_error(msg: str):
    print(color_text("[-] ERROR: " + msg, COLOR_RED), file=sys.stderr)

# --- DNS Protocol Raw Serialization ---

def build_dns_query(domain: str, transaction_id: int = 0x1234) -> bytes:
    """Builds a raw DNS query UDP packet for QTYPE=TXT, QCLASS=IN."""
    # Header Section
    header = bytearray()
    header.extend(transaction_id.to_bytes(2, byteorder='big'))  # Transaction ID
    header.extend((0x0100).to_bytes(2, byteorder='big'))        # Flags: Standard Query
    header.extend((1).to_bytes(2, byteorder='big'))             # Questions count
    header.extend((0).to_bytes(2, byteorder='big'))             # Answer RRs
    header.extend((0).to_bytes(2, byteorder='big'))             # Authority RRs
    header.extend((0).to_bytes(2, byteorder='big'))             # Additional RRs

    # Question Section
    question = bytearray()
    for part in domain.split('.'):
        if not part:
            continue
        part_bytes = part.encode('utf-8')
        question.append(len(part_bytes))
        question.extend(part_bytes)
    question.append(0)  # Terminating zero byte

    question.extend((16).to_bytes(2, byteorder='big'))  # QTYPE: TXT (16)
    question.extend((1).to_bytes(2, byteorder='big'))   # QCLASS: IN (1)

    return bytes(header + question)

def parse_dns_query(data: bytes) -> Tuple[int, str]:
    """Parses a raw DNS query UDP packet, extracting transaction ID and query domain name."""
    if len(data) < 12:
        raise ValueError("Packet too short to be a valid DNS header")
        
    transaction_id = int.from_bytes(data[:2], byteorder='big')
    # Parse domain name in question section starting at byte 12
    idx = 12
    labels = []
    while idx < len(data):
        length = data[idx]
        if length == 0:
            idx += 1
            break
        # Pointer check (DNS compression, not expected in query but safe to check)
        if (length & 0xC0) == 0xC0:
            # We don't support compression in incoming queries for simplicity
            raise ValueError("Compressed query names not supported")
        idx += 1
        label = data[idx : idx + length].decode('utf-8', errors='ignore')
        labels.append(label)
        idx += length
        
    domain = ".".join(labels)
    return transaction_id, domain

def build_dns_response(transaction_id: int, query_data: bytes, response_txt: str) -> bytes:
    """Builds a raw DNS response UDP packet containing a TXT record answer."""
    header = bytearray()
    header.extend(transaction_id.to_bytes(2, byteorder='big'))  # Transaction ID
    header.extend((0x8180).to_bytes(2, byteorder='big'))        # Flags: Standard Response, No Error
    header.extend((1).to_bytes(2, byteorder='big'))             # Questions count
    header.extend((1).to_bytes(2, byteorder='big'))             # Answer count
    header.extend((0).to_bytes(2, byteorder='big'))             # Authority RRs
    header.extend((0).to_bytes(2, byteorder='big'))             # Additional RRs

    # Extract Question section from query to echo back
    # It starts at byte 12 and ends after the QTYPE and QCLASS (which is domain length + 1 (null) + 4 (qtype/qclass) bytes)
    idx = 12
    while idx < len(query_data):
        length = query_data[idx]
        if length == 0:
            idx += 5  # Include the null byte and 4 bytes for QTYPE/QCLASS
            break
        idx += length + 1
        
    question_sec = query_data[12:idx]
    
    # Answer Section
    answer = bytearray()
    answer.extend((0xc00c).to_bytes(2, byteorder='big'))  # Pointer to domain name (offset 12 in header)
    answer.extend((16).to_bytes(2, byteorder='big'))      # TYPE: TXT (16)
    answer.extend((1).to_bytes(2, byteorder='big'))       # CLASS: IN (1)
    answer.extend((0).to_bytes(4, byteorder='big'))       # TTL: 0 seconds
    
    # TXT data: length-prefixed string
    txt_bytes = response_txt.encode('utf-8')
    # Max length of a single TXT label is 255
    if len(txt_bytes) > 255:
        txt_bytes = txt_bytes[:255]
    
    answer.extend((len(txt_bytes) + 1).to_bytes(2, byteorder='big')) # RDATA Length
    answer.append(len(txt_bytes))
    answer.extend(txt_bytes)
    
    return bytes(header + question_sec + answer)

def parse_dns_response(data: bytes) -> str:
    """Parses a DNS response UDP packet and extracts the text from the TXT answer."""
    if len(data) < 12:
        raise ValueError("Packet too short")
    # Skip Header (12 bytes) and Question Section
    idx = 12
    while idx < len(data):
        length = data[idx]
        if length == 0:
            idx += 5  # Skip null byte and QTYPE/QCLASS
            break
        idx += length + 1
        
    # Now at Answer Section
    if idx + 10 >= len(data):
         raise ValueError("Invalid answer section structure")
         
    # Skip Name pointer (2), Type (2), Class (2), TTL (4)
    idx += 10
    rdlength = int.from_bytes(data[idx:idx+2], byteorder='big')
    idx += 2
    
    txt_len = data[idx]
    txt_content = data[idx+1 : idx+1+txt_len].decode('utf-8', errors='ignore')
    return txt_content

# --- Tunnel Logic ---

class TunnelServer:
    def __init__(self, ip: str, port: int, tunnel_domain: str):
        self.ip = ip
        self.port = port
        self.tunnel_domain = tunnel_domain.lower().strip('.')
        self.buffers: Dict[str, Dict[int, str]] = {}  # session_id -> {chunk_idx: b32_data}

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.ip, self.port))
            log_success(f"DNS Tunnel Server listening on {self.ip}:{self.port} for domain '{self.tunnel_domain}'")
        except Exception as e:
            log_error(f"Failed to bind socket: {e}")
            sys.exit(1)

        while True:
            try:
                data, addr = sock.recvfrom(2048)
                tx_id, domain = parse_dns_query(data)
                domain = domain.lower()
                
                log_info(f"Received query from {addr[0]}:{addr[1]} for: {domain}")
                
                # Check if query is for our tunnel domain
                if domain.endswith(self.tunnel_domain):
                    subdomain = domain[:-len(self.tunnel_domain)].strip('.')
                    parts = subdomain.split('.')
                    
                    # Expect structure: <b32_data>.<chunk_idx>.<total_chunks>.<session_id>
                    if len(parts) >= 4:
                        b32_data = parts[0]
                        try:
                            chunk_idx = int(parts[1])
                            total_chunks = int(parts[2])
                            session_id = parts[3]
                        except ValueError:
                            # Not matching layout, send default mock response
                            resp = build_dns_response(tx_id, data, "ERR-BAD-FORMAT")
                            sock.sendto(resp, addr)
                            continue
                            
                        if session_id not in self.buffers:
                            self.buffers[session_id] = {}
                            
                        self.buffers[session_id][chunk_idx] = b32_data
                        
                        log_success(f"Session {session_id}: Received chunk {chunk_idx + 1}/{total_chunks}")
                        
                        # Check if all chunks received
                        if len(self.buffers[session_id]) == total_chunks:
                            log_info(f"Session {session_id}: All chunks received. Reconstructing payload...")
                            # Reassemble
                            ordered_chunks = [self.buffers[session_id][i] for i in range(total_chunks)]
                            full_b32 = "".join(ordered_chunks)
                            
                            # Base32 requires padding "=" characters
                            missing_padding = len(full_b32) % 8
                            if missing_padding:
                                full_b32 += "=" * (8 - missing_padding)
                                
                            try:
                                payload = base64.b32decode(full_b32.upper().encode('utf-8'))
                                try:
                                    text_payload = payload.decode('utf-8')
                                    print(color_text("\n--- TUNNELED PAYLOAD ---", COLOR_BOLD))
                                    print(text_payload)
                                    print(color_text("------------------------\n", COLOR_BOLD))
                                except UnicodeDecodeError:
                                    # Binary payload (e.g. file)
                                    filename = f"received_file_{session_id}.bin"
                                    with open(filename, 'wb') as f:
                                        f.write(payload)
                                    log_success(f"Saved binary payload to: {filename}")
                            except Exception as decode_err:
                                log_error(f"Failed to decode base32 payload: {decode_err}")
                                
                            # Clear buffer
                            del self.buffers[session_id]
                            
                        resp = build_dns_response(tx_id, data, "ACK")
                        sock.sendto(resp, addr)
                    else:
                        resp = build_dns_response(tx_id, data, "MOCK-OK")
                        sock.sendto(resp, addr)
                else:
                    # Forward/Resolve or just return mock response for standard DNS
                    resp = build_dns_response(tx_id, data, "FORWARD-DISABLED")
                    sock.sendto(resp, addr)
            except KeyboardInterrupt:
                log_info("Stopping server...")
                break
            except Exception as e:
                log_warning(f"Error handling request: {e}")

class TunnelClient:
    def __init__(self, server_ip: str, server_port: int, tunnel_domain: str):
        self.server_ip = server_ip
        self.server_port = server_port
        self.tunnel_domain = tunnel_domain.strip('.')

    def send_payload(self, payload_bytes: bytes, session_id: str = "12345"):
        # Encode to base32 (safely matching DNS domain name characters a-z, 2-7)
        b32_str = base64.b32encode(payload_bytes).decode('utf-8').replace('=', '').lower()
        
        # Max label length in DNS is 63. Let's use 50 to be safe and leave room.
        chunk_size = 50
        chunks = [b32_str[i:i+chunk_size] for i in range(0, len(b32_str), chunk_size)]
        total_chunks = len(chunks)
        
        log_info(f"Splitting payload into {total_chunks} queries...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        
        for idx, chunk in enumerate(chunks):
            # Domain structure: <chunk>.<idx>.<total>.<session_id>.<tunnel_domain>
            query_domain = f"{chunk}.{idx}.{total_chunks}.{session_id}.{self.tunnel_domain}"
            
            # Send up to 3 retries
            retry = 0
            success = False
            while retry < 3 and not success:
                try:
                    tx_id = 1000 + idx + retry
                    query_packet = build_dns_query(query_domain, transaction_id=tx_id)
                    
                    log_info(f"Sending chunk {idx + 1}/{total_chunks} (Attempt {retry+1})...")
                    sock.sendto(query_packet, (self.server_ip, self.server_port))
                    
                    resp_data, _ = sock.recvfrom(2048)
                    resp_txt = parse_dns_response(resp_data)
                    
                    if resp_txt == "ACK":
                        log_success(f"Chunk {idx+1} acknowledged by server.")
                        success = True
                    else:
                        log_warning(f"Unexpected response from server: {resp_txt}")
                        retry += 1
                except socket.timeout:
                    log_warning(f"Timeout waiting for chunk {idx+1} response.")
                    retry += 1
                except Exception as err:
                    log_error(f"Error querying: {err}")
                    retry += 1
                    
            if not success:
                log_error("Failed to transmit chunk after retries. Aborting.")
                sock.close()
                return False
                
        log_success("Transmission completed successfully!")
        sock.close()
        return True

def main():
    parser = argparse.ArgumentParser(
        description="DNS Tunneling Client and Server Daemon Simulator"
    )
    parser.add_argument("mode", choices=["server", "client"], help="Run in server or client mode")
    parser.add_argument("-d", "--domain", default="tunnel.example.com", help="Designated tunnel root domain")
    parser.add_argument("-s", "--server", default="127.0.0.1", help="Server IP address to bind (server) or query (client)")
    parser.add_argument("-p", "--port", type=int, default=8053, help="UDP Port to use (defaults to 8053, standard is 53)")
    
    # Client specifics
    parser.add_argument("-m", "--message", type=str, help="Text message payload to send (client mode)")
    parser.add_argument("-f", "--file", type=str, help="File payload to send (client mode)")
    parser.add_argument("-i", "--session", default="9999", help="Unique session ID for query synchronization")
    
    args = parser.parse_args()
    
    if args.mode == "server":
        server = TunnelServer(args.server, args.port, args.domain)
        server.start()
    elif args.mode == "client":
        payload_bytes = None
        if args.message:
            payload_bytes = args.message.encode('utf-8')
        elif args.file:
            if not os.path.exists(args.file):
                log_error(f"File not found: {args.file}")
                sys.exit(1)
            with open(args.file, 'rb') as f:
                payload_bytes = f.read()
        else:
            log_error("Client mode requires either --message or --file")
            sys.exit(1)
            
        client = TunnelClient(args.server, args.port, args.domain)
        client.send_payload(payload_bytes, session_id=args.session)

if __name__ == "__main__":
    main()
