#!/usr/bin/env python3
"""
Mock DNS Server - A lightweight UDP DNS server for local development and testing

This tool runs a local DNS server that resolves hostnames based on a JSON
configuration file. It is useful for testing network configurations, custom
routing, or offline application behavior.

Usage:
    python tools/dns_server_mock.py [options]

Options:
    -c, --config FILE       Path to JSON configuration file (default: dns_config.json)
    -p, --port PORT         Port to listen on (default: 5353 to avoid privilege issues)
    -i, --interface IP      Interface IP to bind to (default: 127.0.0.1)
    -h, --help              Show this help message and exit

Example config (dns_config.json):
{
  "example.com": {
    "A": "127.0.0.1",
    "AAAA": "::1",
    "TXT": "v=spf1 -all",
    "MX": "10 mail.example.com."
  },
  "mail.example.com": {
    "A": "127.0.0.2"
  }
}
"""

import argparse
import json
import os
import socket
import sys
from typing import Dict, Any, Tuple, Optional


def create_dns_response(data: bytes, records: Dict[str, Any]) -> bytes:
    """Parses a DNS request and constructs a valid DNS response."""
    # Transaction ID (first 2 bytes)
    transaction_id = data[:2]
    
    # Flags: Response, Opcode=0, AA=1, TC=0, RD=1, RA=1, Z=0, RCODE=0
    flags = b'\x81\x80'
    
    # Questions count (2 bytes)
    qd_count = data[4:6]
    
    # Extract query domain name
    domain_parts = []
    idx = 12
    while True:
        length = data[idx]
        if length == 0:
            idx += 1
            break
        domain_parts.append(data[idx + 1:idx + 1 + length].decode('utf-8', errors='ignore'))
        idx += 1 + length
        
    domain_name = ".".join(domain_parts)
    
    # Query Type and Query Class
    q_type = data[idx:idx + 2]
    q_class = data[idx + 2:idx + 4]
    
    # Check if domain exists in our mock records
    domain_records = records.get(domain_name, {})
    
    # Determine the response type based on query type
    # A = \x00\x01, AAAA = \x00\x1c, TXT = \x00\x10, MX = \x00\x0f, CNAME = \x00\x05
    type_code = int.from_bytes(q_type, byteorder='big')
    
    answer_bytes = b''
    an_count_val = 0
    
    rdata_str = None
    r_type = None
    
    if type_code == 1:    # A Record
        rdata_str = domain_records.get('A')
        r_type = 1
    elif type_code == 28: # AAAA Record
        rdata_str = domain_records.get('AAAA')
        r_type = 28
    elif type_code == 16: # TXT Record
        rdata_str = domain_records.get('TXT')
        r_type = 16
    elif type_code == 15: # MX Record
        rdata_str = domain_records.get('MX')
        r_type = 15
    elif type_code == 5:  # CNAME Record
        rdata_str = domain_records.get('CNAME')
        r_type = 5
        
    # Check for CNAME fallback if target record type isn't directly configured
    if not rdata_str and 'CNAME' in domain_records and type_code != 5:
        rdata_str = domain_records.get('CNAME')
        r_type = 5  # We return CNAME answer instead
        
    if rdata_str:
        an_count_val = 1
        # Answer Name: pointer to domain name in question (\xc0\x0c)
        answer_bytes += b'\xc0\x0c'
        # Answer Type (2 bytes)
        answer_bytes += r_type.to_bytes(2, byteorder='big')
        # Answer Class: IN (\x00\x01)
        answer_bytes += b'\x00\x01'
        # TTL: 60 seconds (4 bytes)
        answer_bytes += b'\x00\x00\x00\x3c'
        
        # Format RDATA based on record type
        if r_type == 1:  # A
            try:
                ip_bytes = socket.inet_aton(rdata_str)
                answer_bytes += len(ip_bytes).to_bytes(2, byteorder='big')
                answer_bytes += ip_bytes
            except socket.error:
                an_count_val = 0
                answer_bytes = b''
        elif r_type == 28: # AAAA
            try:
                ip_bytes = socket.inet_pton(socket.AF_INET6, rdata_str)
                answer_bytes += len(ip_bytes).to_bytes(2, byteorder='big')
                answer_bytes += ip_bytes
            except socket.error:
                an_count_val = 0
                answer_bytes = b''
        elif r_type == 16: # TXT
            txt_bytes = rdata_str.encode('utf-8')
            # TXT record prefix is 1-byte length of text block
            txt_payload = bytes([len(txt_bytes)]) + txt_bytes
            answer_bytes += len(txt_payload).to_bytes(2, byteorder='big')
            answer_bytes += txt_payload
        elif r_type == 5:  # CNAME
            cname_payload = b''
            for part in rdata_str.strip('.').split('.'):
                cname_payload += bytes([len(part)]) + part.encode('utf-8')
            cname_payload += b'\x00'
            answer_bytes += len(cname_payload).to_bytes(2, byteorder='big')
            answer_bytes += cname_payload
        elif r_type == 15: # MX
            # Format: [preference (2 bytes)] [exchange domain name (dns wire format)]
            parts = rdata_str.split(' ', 1)
            pref = int(parts[0]) if parts[0].isdigit() else 10
            exchange = parts[1] if len(parts) > 1 else parts[0]
            
            mx_payload = pref.to_bytes(2, byteorder='big')
            for part in exchange.strip('.').split('.'):
                mx_payload += bytes([len(part)]) + part.encode('utf-8')
            mx_payload += b'\x00'
            
            answer_bytes += len(mx_payload).to_bytes(2, byteorder='big')
            answer_bytes += mx_payload

    # Set response answer counts
    an_count = an_count_val.to_bytes(2, byteorder='big')
    ns_count = b'\x00\x00'
    ar_count = b'\x00\x00'
    
    header = transaction_id + flags + qd_count + an_count + ns_count + ar_count
    question = data[12:idx + 4]
    
    return header + question + answer_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock DNS Server over UDP.")
    parser.add_argument("-c", "--config", default="dns_config.json", help="Path to config file")
    parser.add_argument("-p", "--port", type=int, default=5353, help="Port to listen on")
    parser.add_argument("-i", "--interface", default="127.0.0.1", help="Interface to bind to")
    
    args = parser.parse_args()
    
    # If config does not exist, write a default template config
    if not os.path.exists(args.config):
        default_config = {
            "example.local": {
                "A": "127.0.0.1",
                "AAAA": "::1",
                "TXT": "v=spf1 a -all",
                "CNAME": "alias.example.local"
            },
            "alias.example.local": {
                "A": "192.168.1.100"
            },
            "mail.example.local": {
                "A": "10.0.0.5",
                "MX": "10 mail.example.local."
            }
        }
        try:
            write_mode = "w"
            with open(args.config, write_mode, encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default configuration file at: {args.config}")
        except Exception as e:
            print(f"Warning: Could not create default configuration file: {e}", file=sys.stderr)
            
    # Load configuration
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        print(f"Error reading configuration file {args.config}: {e}", file=sys.stderr)
        return 1
        
    # Start UDP server
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.bind((args.interface, args.port))
        print(f"Mock DNS Server started on {args.interface}:{args.port}")
        print(f"Loaded {len(records)} host routing tables.")
        print("Press Ctrl+C to terminate.")
    except Exception as e:
        print(f"Failed to bind socket on {args.interface}:{args.port}: {e}", file=sys.stderr)
        if args.port < 1024:
            print("Note: Ports < 1024 require administrative privileges.", file=sys.stderr)
        return 1
        
    try:
        while True:
            data, addr = udp_socket.recvfrom(512)
            try:
                response = create_dns_response(data, records)
                udp_socket.sendto(response, addr)
            except Exception as query_err:
                print(f"Error processing query from {addr}: {query_err}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nShutting down Mock DNS Server...")
    finally:
        udp_socket.close()
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
