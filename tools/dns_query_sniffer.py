#!/usr/bin/env python3
"""
DNS Query Sniffer & Diagnostic Logger
Binds to a UDP port (e.g. 53, 1053, or 5353) and sniffs incoming DNS packets,
decoding the DNS header and question sections natively to log queries in real-time.
"""

import sys
import socket
import struct
import argparse

# Map of common DNS Query Types
DNS_TYPES = {
    1: "A",
    2: "NS",
    5: "CNAME",
    6: "SOA",
    12: "PTR",
    15: "MX",
    16: "TXT",
    28: "AAAA",
    33: "SRV",
    257: "CAA",
    255: "ANY"
}

# Map of common DNS Classes
DNS_CLASSES = {
    1: "IN",
    3: "CH",
    4: "HS",
    255: "ANY"
}

def decode_dns_name(data, offset):
    """Decode a DNS label-sequence name from binary data starting at offset."""
    labels = []
    original_offset = offset
    jumped = False
    jump_offset = 0
    bytes_read = 0

    while True:
        if offset >= len(data):
            break
        
        length = data[offset]
        
        # Check if it is a compression pointer (starts with 11 bits)
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(data):
                break
            # Obtain pointer location (lower 14 bits)
            pointer = struct.unpack("!H", data[offset:offset+2])[0] & 0x3FFF
            if not jumped:
                jump_offset = offset + 2
                jumped = True
            offset = pointer
            continue
            
        offset += 1
        if not jumped:
            bytes_read += 1
            
        if length == 0:
            break
            
        label = data[offset:offset+length].decode('utf-8', errors='ignore')
        labels.append(label)
        offset += length
        
        if not jumped:
            bytes_read += length

    actual_bytes_read = jump_offset - original_offset if jumped else bytes_read + 1
    return ".".join(labels), actual_bytes_read

def parse_dns_query(data, addr):
    """Parse raw UDP binary payload as a DNS query packet."""
    if len(data) < 12:
        return None # Too short to be a DNS packet
        
    # Header format: ID (2B), Flags (2B), QDCOUNT (2B), ANCOUNT (2B), NSCOUNT (2B), ARCOUNT (2B)
    header = struct.unpack("!HHHHHH", data[:12])
    tx_id = header[0]
    flags = header[1]
    qdcount = header[2] # Question count
    
    # Check flags: QR (bit 15) must be 0 for a query
    is_response = bool(flags & 0x8000)
    if is_response:
        return None # Skip responses, we only want to sniff queries
        
    opcode = (flags >> 11) & 0x0F
    rd = bool(flags & 0x0100) # Recursion Desired
    
    offset = 12
    queries = []
    
    # Parse questions
    for _ in range(qdcount):
        if offset >= len(data):
            break
        name, bytes_read = decode_dns_name(data, offset)
        offset += bytes_read
        
        if offset + 4 > len(data):
            break
            
        qtype, qclass = struct.unpack("!HH", data[offset:offset+4])
        offset += 4
        
        type_str = DNS_TYPES.get(qtype, f"TYPE-{qtype}")
        class_str = DNS_CLASSES.get(qclass, f"CLASS-{qclass}")
        queries.append((name, type_str, class_str))
        
    return {
        "tx_id": tx_id,
        "opcode": opcode,
        "rd": rd,
        "queries": queries,
        "client": f"{addr[0]}:{addr[1]}"
    }

def main():
    parser = argparse.ArgumentParser(description="DNS Query Sniffer & Diagnostic Logger")
    parser.add_argument("-p", "--port", type=int, default=53, help="Port to bind (default: 53. If permission denied, use e.g. 1053 or 5353)")
    parser.add_argument("-i", "--interface", default="0.0.0.0", help="Network interface to bind (default: 0.0.0.0 for all)")
    
    args = parser.parse_args()
    
    # Create UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        sock.bind((args.interface, args.port))
    except PermissionError:
        print(f"Permission Denied: Bidding to port {args.port} requires root/administrator privileges.")
        # Attempt fallback to user-friendly port 5353
        fallback_port = 5353 if args.port == 53 else args.port + 1000
        print(f"Attempting fallback to bind port {fallback_port}...")
        try:
            sock.bind((args.interface, fallback_port))
            args.port = fallback_port
        except Exception as e:
            print(f"Error binding fallback socket: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"Error binding socket: {e}")
        sys.exit(1)

    print(f"DNS Query Sniffer successfully active.")
    print(f"Listening on UDP: {args.interface}:{args.port}")
    print("Press Ctrl+C to terminate.")
    print("=" * 75)
    print(f"{'Client Address':<22} | {'TX-ID':<6} | {'Type':<6} | {'Class':<5} | Query Domain")
    print("-" * 75)

    try:
        while True:
            data, addr = sock.recvfrom(2048)
            try:
                query_info = parse_dns_query(data, addr)
                if query_info and query_info["queries"]:
                    client = query_info["client"]
                    tx_id = f"0x{query_info['tx_id']:04x}"
                    for name, qtype, qclass in query_info["queries"]:
                        print(f"{client:<22} | {tx_id:<6} | {qtype:<6} | {qclass:<5} | {name}")
                        sys.stdout.flush()
            except Exception as e:
                # Silently catch parsing issues for invalid packet formats
                pass
    except KeyboardInterrupt:
        print("\nTerminating DNS query sniffer.")
        sock.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
