#!/usr/bin/env python3
"""
CLI Network Packet Builder & HEX Simulator

An educational tool to construct custom network packets (Ethernet, IPv4, TCP,
UDP, ICMP) step-by-step. Computes internet checksums and renders the resulting
packet as a formatted Hex Dump and structural byte layout in the terminal.
"""

import sys
import struct
import socket
import argparse
from typing import Tuple, List

# ANSI Color Escape Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def colored(text: str, color_code: str) -> str:
    if sys.platform == "win32":
        import os
        os.system("")
    return f"{color_code}{text}{RESET}"

def compute_checksum(data: bytes) -> int:
    """Calculate the standard 16-bit Internet Checksum (RFC 1071)."""
    if len(data) % 2 == 1:
        data += b'\x00'
        
    s = sum(struct.unpack(f">{len(data)//2}H", data))
    
    # Fold 32-bit sum to 16 bits
    while s >> 16:
        s = (s & 0xffff) + (s >> 16)
        
    # One's complement
    return (~s) & 0xffff

def parse_mac(mac_str: str) -> bytes:
    """Convert a colon-separated MAC address to 6 bytes."""
    mac_str = mac_str.replace("-", ":").replace(".", "")
    parts = mac_str.split(":")
    if len(parts) != 6:
        raise ValueError("MAC address must be 6 colon-separated hex bytes (e.g., 00:11:22:33:44:55).")
    try:
        return bytes(int(p, 16) for p in parts)
    except ValueError:
        raise ValueError("Invalid hex characters in MAC address.")

def format_hex_dump(data: bytes) -> str:
    """Format bytes as a standard hexadecimal dump (Wireshark-like)."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        
        # Hex values part
        hex_vals = [f"{b:02x}" for b in chunk]
        # Pad if chunk is less than 16 bytes
        hex_str_left = " ".join(hex_vals[:8])
        hex_str_right = " ".join(hex_vals[8:])
        hex_str = f"{hex_str_left:<23}  {hex_str_right:<23}"
        
        # ASCII printable part
        ascii_vals = []
        for b in chunk:
            if 32 <= b <= 126:
                ascii_vals.append(chr(b))
            else:
                ascii_vals.append(".")
        ascii_str = "".join(ascii_vals)
        
        lines.append(f"{i:04x}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)

def build_ethernet_header(dst_mac: str, src_mac: str, eth_type: int) -> bytes:
    dst = parse_mac(dst_mac)
    src = parse_mac(src_mac)
    return struct.pack("!6s6sH", dst, src, eth_type)

def build_ipv4_header(src_ip: str, dst_ip: str, proto: int, payload_len: int, ttl: int = 64) -> bytes:
    version = 4
    ihl = 5 # 20 bytes (no options)
    ver_ihl = (version << 4) + ihl
    tos = 0
    total_len = 20 + payload_len
    packet_id = 54321
    flags_fragment = 0x4000 # Don't Fragment flag set
    src_bytes = socket.inet_aton(src_ip)
    dst_bytes = socket.inet_aton(dst_ip)
    
    # Build header with checksum set to 0 initially
    hdr_without_checksum = struct.pack(
        "!BBHHHBBH4s4s",
        ver_ihl, tos, total_len, packet_id, flags_fragment, ttl, proto, 0, src_bytes, dst_bytes
    )
    
    # Calculate checksum
    chk = compute_checksum(hdr_without_checksum)
    
    # Rebuild header with correct checksum
    return struct.pack(
        "!BBHHHBBH4s4s",
        ver_ihl, tos, total_len, packet_id, flags_fragment, ttl, proto, chk, src_bytes, dst_bytes
    )

def build_udp_header(src_port: int, dst_port: int, payload: bytes, src_ip: str = None, dst_ip: str = None) -> bytes:
    length = 8 + len(payload)
    
    # Build header with checksum set to 0
    udp_hdr = struct.pack("!HHHH", src_port, dst_port, length, 0)
    
    # Compute UDP Checksum if pseudo-header info is available
    if src_ip and dst_ip:
        src_bytes = socket.inet_aton(src_ip)
        dst_bytes = socket.inet_aton(dst_ip)
        # Pseudo header: Src IP, Dst IP, Reserved (1 byte), Proto (17 for UDP), UDP Length (2 bytes)
        pseudo_hdr = struct.pack("!4s4sBBH", src_bytes, dst_bytes, 0, 17, length)
        chk = compute_checksum(pseudo_hdr + udp_hdr + payload)
        # Re-pack with checksum
        udp_hdr = struct.pack("!HHHH", src_port, dst_port, length, chk)
        
    return udp_hdr

def build_tcp_header(src_port: int, dst_port: int, seq: int, ack: int, flags: str, payload: bytes, src_ip: str = None, dst_ip: str = None) -> bytes:
    # Flags mapping
    flag_val = 0
    flag_map = {'FIN': 1, 'SYN': 2, 'RST': 4, 'PSH': 8, 'ACK': 16, 'URG': 32}
    for f in flags.replace(" ", "").split(","):
        if f.upper() in flag_map:
            flag_val += flag_map[f.upper()]
            
    data_offset = 5 # 5 32-bit words = 20 bytes
    offset_res = (data_offset << 4) + 0
    window = 8192
    urg_ptr = 0
    
    # Build header with checksum set to 0
    tcp_hdr = struct.pack(
        "!HHIIBBHHH",
        src_port, dst_port, seq, ack, offset_res, flag_val, window, 0, urg_ptr
    )
    
    # Compute TCP Checksum if pseudo-header info is available
    if src_ip and dst_ip:
        src_bytes = socket.inet_aton(src_ip)
        dst_bytes = socket.inet_aton(dst_ip)
        total_len = 20 + len(payload)
        # Pseudo header: Src IP, Dst IP, Reserved, Proto (6 for TCP), TCP Length
        pseudo_hdr = struct.pack("!4s4sBBH", src_bytes, dst_bytes, 0, 6, total_len)
        chk = compute_checksum(pseudo_hdr + tcp_hdr + payload)
        # Re-pack with checksum
        tcp_hdr = struct.pack(
            "!HHIIBBHHH",
            src_port, dst_port, seq, ack, offset_res, flag_val, window, chk, urg_ptr
        )
        
    return tcp_hdr

def build_icmp_header(icmp_type: int, icmp_code: int, payload: bytes) -> bytes:
    # Initial pack with 0 checksum
    icmp_hdr = struct.pack("!BBHHH", icmp_type, icmp_code, 0, 1234, 1) # ID=1234, Seq=1
    chk = compute_checksum(icmp_hdr + payload)
    return struct.pack("!BBHHH", icmp_type, icmp_code, chk, 1234, 1)

def run_interactive():
    print(colored("=" * 65, BOLD + CYAN))
    print(colored("          CLI NETWORK PACKET BUILDER & SIMULATOR            ", BOLD + CYAN))
    print(colored("=" * 65, BOLD + CYAN))
    print("Welcome! Let's build a custom network packet step-by-step.")
    print("-" * 65)
    
    try:
        # Layer 2: Ethernet
        print(colored("\n[Layer 2] Ethernet Header Setup", BOLD + YELLOW))
        dst_mac = input("  Destination MAC address [00:11:22:33:44:55]: ").strip() or "00:11:22:33:44:55"
        src_mac = input("  Source MAC address      [66:77:88:99:aa:bb]: ").strip() or "66:77:88:99:aa:bb"
        
        # Layer 3: IPv4
        print(colored("\n[Layer 3] IPv4 Header Setup", BOLD + YELLOW))
        src_ip = input("  Source IP address       [192.168.1.50]: ").strip() or "192.168.1.50"
        dst_ip = input("  Destination IP address  [8.8.8.8]: ").strip() or "8.8.8.8"
        ttl = int(input("  Time To Live (TTL)      [64]: ").strip() or "64")
        
        # Protocol choice
        print(colored("\n[Layer 4] Protocol Selection", BOLD + YELLOW))
        print("  1. TCP (Transmission Control Protocol)")
        print("  2. UDP (User Datagram Protocol)")
        print("  3. ICMP (Internet Control Message Protocol)")
        proto_choice = input("  Select protocol (1-3)   [1]: ").strip() or "1"
        
        payload_text = input("\n  Enter payload text (e.g. 'Hello Network'): ").strip() or "Hello Network"
        payload_bytes = payload_text.encode('utf-8')
        
        # Build headers
        l4_bytes = b''
        proto_id = 0
        proto_name = ""
        
        if proto_choice == "1": # TCP
            proto_id = 6
            proto_name = "TCP"
            print(colored("\n[TCP Configuration]", BOLD + MAGENTA))
            src_port = int(input("    Source Port      [12345]: ").strip() or "12345")
            dst_port = int(input("    Destination Port [80]: ").strip() or "80")
            flags = input("    TCP Flags (comma-separated, e.g. SYN,ACK) [SYN]: ").strip() or "SYN"
            l4_bytes = build_tcp_header(src_port, dst_port, 1000, 0, flags, payload_bytes, src_ip, dst_ip)
            
        elif proto_choice == "2": # UDP
            proto_id = 17
            proto_name = "UDP"
            print(colored("\n[UDP Configuration]", BOLD + MAGENTA))
            src_port = int(input("    Source Port      [5353]: ").strip() or "5353")
            dst_port = int(input("    Destination Port [53]: ").strip() or "53")
            l4_bytes = build_udp_header(src_port, dst_port, payload_bytes, src_ip, dst_ip)
            
        else: # ICMP
            proto_id = 1
            proto_name = "ICMP"
            print(colored("\n[ICMP Configuration]", BOLD + MAGENTA))
            print("    1. Echo Request (Ping)")
            print("    2. Echo Reply")
            icmp_type_choice = input("    Select type (1-2) [1]: ").strip() or "1"
            icmp_type = 8 if icmp_type_choice == "1" else 0 # 8=Echo request, 0=Echo reply
            l4_bytes = build_icmp_header(icmp_type, 0, payload_bytes)
            
        # Assemble complete packet
        eth_hdr = build_ethernet_header(dst_mac, src_mac, 0x0800) # 0x0800 = IPv4
        ip_hdr = build_ipv4_header(src_ip, dst_ip, proto_id, len(l4_bytes) + len(payload_bytes), ttl)
        
        complete_packet = eth_hdr + ip_hdr + l4_bytes + payload_bytes
        
        # Display structures
        print(colored("\n" + "=" * 65, BOLD + GREEN))
        print(colored("           CONSTRUCTED PACKET VISUALIZATION                  ", BOLD + GREEN))
        print(colored("=" * 65, BOLD + GREEN))
        
        # Visual breakdown block diagram
        print(colored("\n[Layer Headers Struct Block Diagram]", BOLD + YELLOW))
        print(f"┌─────────────────────────────────────────────────────────────┐")
        print(f"│ {colored('Ethernet Header', BOLD+CYAN):<57} │ (14 Bytes)")
        print(f"│   Dst MAC: {dst_mac:<47} │")
        print(f"│   Src MAC: {src_mac:<47} │")
        print(f"│   Type:    0x0800 (IPv4)                                    │")
        print(f"├─────────────────────────────────────────────────────────────┤")
        print(f"│ {colored('IPv4 Header', BOLD+CYAN):<57} │ (20 Bytes)")
        print(f"│   Src IP: {src_ip:<48} │")
        print(f"│   Dst IP: {dst_ip:<48} │")
        print(f"│   TTL: {ttl:<12} Protocol: {proto_name:<28} │")
        print(f"├─────────────────────────────────────────────────────────────┤")
        print(f"│ {colored(proto_name + ' Header', BOLD+CYAN):<57} │ ({len(l4_bytes)} Bytes)")
        if proto_choice == "1":
            print(f"│   Src Port: {src_port:<12} Dst Port: {dst_port:<28} │")
            print(f"│   Flags: {flags:<50} │")
        elif proto_choice == "2":
            print(f"│   Src Port: {src_port:<12} Dst Port: {dst_port:<28} │")
        else:
            type_str = "Echo Request (Ping)" if icmp_type == 8 else "Echo Reply"
            print(f"│   Type: {icmp_type} ({type_str:<41}) │")
        print(f"├─────────────────────────────────────────────────────────────┤")
        print(f"│ {colored('Payload', BOLD+CYAN):<57} │ ({len(payload_bytes)} Bytes)")
        print(f"│   Text: \"{payload_text:<48}\" │")
        print(f"└─────────────────────────────────────────────────────────────┘")
        
        # Hex Dump Output
        print(colored("\n[Wireshark-like Hex Dump]", BOLD + YELLOW))
        print(format_hex_dump(complete_packet))
        print()
        
    except ValueError as e:
        print(colored(f"\n[!] Input Error: {e}", RED))
    except Exception as e:
        print(colored(f"\n[!] Error building packet: {e}", RED))

def main():
    parser = argparse.ArgumentParser(description="CLI Network Packet Builder & HEX Simulator")
    parser.add_argument("--interactive", action="store_true", default=True, help="Run in interactive mode (default)")
    parser.parse_args()
    
    run_interactive()

if __name__ == "__main__":
    main()
