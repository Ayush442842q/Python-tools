#!/usr/bin/env python3
"""
DNS AXFR Zone Transfer Security Tester
A zero-dependency security diagnostic tool to test DNS nameservers for AXFR zone transfer
vulnerabilities (RFC 5936). Queries servers directly using TCP/UDP sockets.
"""

import argparse
import os
import socket
import struct
import sys
from typing import Dict, List, Optional, Tuple


# DNS Types Mapping
DNS_TYPES = {
    1: "A",
    2: "NS",
    5: "CNAME",
    6: "SOA",
    12: "PTR",
    15: "MX",
    16: "TXT",
    28: "AAAA",
    252: "AXFR",
}


def build_dns_query(domain: str, qtype: int) -> bytes:
    """Builds a raw DNS query packet."""
    tx_id = os.urandom(2)
    # Standard query, recursion desired (RD = 1) for resolving NS records,
    # or no recursion (RD = 0) for AXFR.
    flags = b"\x01\x00" if qtype != 252 else b"\x00\x00"
    qd_count = b"\x00\x01"
    an_count = b"\x00\x00"
    ns_count = b"\x00\x00"
    ar_count = b"\x00\x00"
    
    # Format domain labels: e.g., google.com -> \x06google\x03com\x00
    encoded_domain = b""
    for part in domain.split("."):
        if part:
            encoded_domain += bytes([len(part)]) + part.encode("utf-8")
    encoded_domain += b"\x00"
    
    qtype_bytes = struct.pack(">H", qtype)
    qclass_bytes = b"\x00\x01"  # IN class
    
    return tx_id + flags + qd_count + an_count + ns_count + ar_count + encoded_domain + qtype_bytes + qclass_bytes


def parse_name(data: bytes, offset: int) -> Tuple[str, int]:
    """Parses a DNS name field from raw packet bytes, supporting label compression."""
    labels = []
    initial_offset = offset
    jumped = False
    
    while True:
        if offset >= len(data):
            break
        b = data[offset]
        if b == 0:
            if not jumped:
                offset += 1
            break
        elif (b & 0xC0) == 0xC0:  # Decompression pointer
            pointer = struct.unpack(">H", data[offset:offset+2])[0] & 0x3FFF
            if not jumped:
                initial_offset = offset + 2
            jumped = True
            offset = pointer
        else:
            offset += 1
            labels.append(data[offset:offset+b].decode("utf-8", errors="ignore"))
            offset += b
            
    return ".".join(labels), (offset if not jumped else initial_offset)


def parse_dns_record(data: bytes, offset: int) -> Tuple[dict, int]:
    """Parses a single DNS resource record (RR) and extracts type, TTL, and values."""
    name, offset = parse_name(data, offset)
    
    rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[offset:offset+10])
    offset += 10
    
    rdata = data[offset:offset+rdlen]
    rdata_str = ""
    
    # Parse specific record types for visualization
    if rtype == 1:  # A record (IPv4 address)
        rdata_str = socket.inet_ntop(socket.AF_INET, rdata)
    elif rtype == 28:  # AAAA record (IPv6 address)
        rdata_str = socket.inet_ntop(socket.AF_INET6, rdata)
    elif rtype in (2, 5, 6):  # NS, CNAME, or SOA name pointers
        rdata_str, _ = parse_name(data, offset)
    elif rtype == 15:  # MX record
        pref = struct.unpack(">H", rdata[0:2])[0]
        exchange, _ = parse_name(data, offset + 2)
        rdata_str = f"{pref} {exchange}"
    elif rtype == 16:  # TXT record
        # Text records are stored as length-prefixed strings
        txt_parts = []
        txt_offset = 0
        while txt_offset < rdlen:
            txt_len = rdata[txt_offset]
            txt_parts.append(rdata[txt_offset + 1:txt_offset + 1 + txt_len].decode("utf-8", errors="ignore"))
            txt_offset += 1 + txt_len
        rdata_str = " ".join(txt_parts)
    else:
        # Fallback raw hex for unhandled record types
        rdata_str = rdata.hex()
        
    offset += rdlen
    
    return {
        "name": name,
        "type": DNS_TYPES.get(rtype, f"TYPE_{rtype}"),
        "ttl": ttl,
        "data": rdata_str,
    }, offset


def query_ns_servers(domain: str, dns_resolver: str = "8.8.8.8") -> List[str]:
    """Queries public DNS resolver over UDP to discover NS records for a domain."""
    query = build_dns_query(domain, 2)  # NS query
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    
    ns_servers = []
    try:
        sock.sendto(query, (dns_resolver, 53))
        response, _ = sock.recvfrom(4096)
        
        # Parse DNS response header
        # Transaction ID (2 bytes), Flags (2 bytes), Questions count (2), Answers count (2)...
        an_count = struct.unpack(">H", response[6:8])[0]
        
        # Skip question section: domain name ends with \x00, then 4 bytes of class/type
        offset = 12
        while response[offset] != 0:
            offset += response[offset] + 1
        offset += 5  # Skip \x00, type, class
        
        # Parse answers
        for _ in range(an_count):
            record, offset = parse_dns_record(response, offset)
            if record["type"] == "NS":
                ns_servers.append(record["data"])
                
    except Exception as e:
        print(f"[-] Failed to fetch NS servers from resolver {dns_resolver}: {e}", file=sys.stderr)
        
    finally:
        sock.close()
        
    return ns_servers


def attempt_axfr(domain: str, ns_ip: str) -> Tuple[bool, List[dict], str]:
    """
    Attempts to perform a TCP AXFR zone transfer for the domain on the target IP.
    Returns (is_vulnerable, parsed_records, status_message).
    """
    query = build_dns_query(domain, 252)  # AXFR query
    # TCP queries are prefixed by a 2-byte length header
    tcp_query = struct.pack(">H", len(query)) + query
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    
    records = []
    try:
        sock.connect((ns_ip, 53))
        sock.sendall(tcp_query)
        
        # Read the response. AXFR responses can span multiple TCP segments/packets.
        # We continue reading until we receive the second SOA record indicating transfer completion,
        # or the socket closes, or we find a refusal code in the DNS header.
        
        soa_count = 0
        first_read = True
        
        while True:
            # Read 2-byte length prefix
            len_bytes = sock.recv(2)
            if len(len_bytes) < 2:
                break
                
            packet_len = struct.unpack(">H", len_bytes)[0]
            
            # Read full packet
            packet = b""
            while len(packet) < packet_len:
                chunk = sock.recv(packet_len - len(packet))
                if not chunk:
                    break
                packet += chunk
                
            if len(packet) < packet_len:
                break
                
            # Process DNS flags on first response packet
            if first_read:
                # Flags are bytes 2 and 3 of DNS header
                flags = struct.unpack(">H", packet[2:4])[0]
                rcode = flags & 0x000F
                
                if rcode == 5:
                    return False, [], "Refused (RCODE 5) - AXFR forbidden"
                elif rcode == 1:
                    return False, [], "Format Error (RCODE 1)"
                elif rcode == 4:
                    return False, [], "Not Implemented (RCODE 4)"
                elif rcode != 0:
                    return False, [], f"Query Failed (RCODE {rcode})"
                
                first_read = False
                
            # Parse record counts
            an_count = struct.unpack(">H", packet[6:8])[0]
            
            # Skip question section (only on the first packet usually, but let's check)
            offset = 12
            while packet[offset] != 0:
                offset += packet[offset] + 1
            offset += 5  # Skip \x00, type, class
            
            # Parse answer resource records in the packet
            for _ in range(an_count):
                if offset >= len(packet):
                    break
                record, offset = parse_dns_record(packet, offset)
                records.append(record)
                
                if record["type"] == "SOA":
                    soa_count += 1
                    
            # A full zone transfer starts and ends with an SOA record.
            # If we've seen 2 SOA records, the transfer is complete.
            if soa_count >= 2:
                break
                
        if len(records) > 0:
            return True, records, f"Success - Transferred {len(records)} records"
        return False, [], "Refused - Empty zone returned"
        
    except socket.timeout:
        return False, [], "Timeout - TCP connection timed out"
    except ConnectionRefusedError:
        return False, [], "Connection Refused - Port 53 closed on TCP"
    except Exception as e:
        return False, [], f"Error: {e}"
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="DNS AXFR Zone Transfer Security Auditor. "
                    "Tests nameservers for zone transfer vulnerabilities."
    )
    parser.add_argument("domain", help="The target domain to test (e.g., zonetransfer.me)")
    parser.add_argument("-s", "--server", help="Test a specific name server IP or host directly")
    parser.add_argument("-r", "--resolver", default="8.8.8.8", help="DNS resolver to lookup NS servers (default: 8.8.8.8)")
    
    args = parser.parse_args()
    target_domain = args.domain
    
    ns_targets = []
    
    if args.server:
        # Resolve server argument if it's a hostname
        try:
            ns_ip = socket.gethostbyname(args.server)
            ns_targets.append((args.server, ns_ip))
        except Exception as e:
            print(f"[-] Could not resolve target server {args.server}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[*] Resolving NS servers for {target_domain} using {args.resolver}...")
        ns_hosts = query_ns_servers(target_domain, args.resolver)
        
        if not ns_hosts:
            print("[-] No nameservers found for domain. Try specifying a server directly with -s.", file=sys.stderr)
            sys.exit(1)
            
        print(f"[+] Found {len(ns_hosts)} name servers:")
        for host in ns_hosts:
            try:
                ip = socket.gethostbyname(host)
                ns_targets.append((host, ip))
                print(f"    - {host} ({ip})")
            except Exception:
                print(f"    - {host} (Failed to resolve IP)")

    print("-" * 75)
    print(f"Testing {target_domain} for AXFR vulnerabilities...")
    print("-" * 75)
    
    vulnerable_any = False
    
    for host, ip in ns_targets:
        print(f"[*] Querying nameserver: {host} ({ip})...")
        is_vuln, records, msg = attempt_axfr(target_domain, ip)
        
        if is_vuln:
            vulnerable_any = True
            print(f"[!] VULNERABLE: {msg} on {host}")
            print("-" * 75)
            # Display transfer stats
            type_counts = {}
            for r in records:
                type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
                
            print("Summary of records found:")
            for rtype, count in sorted(type_counts.items()):
                print(f"  {rtype:<8}: {count}")
            print("-" * 75)
            
            # Print first 20 records as sample
            print("Sample Records (first 20):")
            for r in records[:20]:
                print(f"  {r['name']:<25} {r['ttl']:<6} {r['type']:<6} {r['data']}")
            if len(records) > 20:
                print(f"  ... and {len(records) - 20} more records.")
            print("-" * 75)
        else:
            print(f"[+] SECURE: {host} responded: {msg}")
            print("-" * 75)
            
    if vulnerable_any:
        print("[!] Risk Assessment: HIGH. One or more nameservers allow unauthorized zone transfers.")
        sys.exit(1)
    else:
        print("[+] Risk Assessment: LOW. All tested nameservers blocked AXFR zone transfers.")
        sys.exit(0)


if __name__ == "__main__":
    main()
