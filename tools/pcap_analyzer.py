#!/usr/bin/env python3
"""
PCAP Packet Analyzer - A pure-Python packet capture analyzer.
Parses standard PCAP files, dissects Ethernet, IPv4, TCP, UDP, ICMP, and DNS,
and outputs detailed traffic statistics, top talkers, protocol breakdowns,
and visual terminal charts.
"""

import os
import sys
import struct
import socket
import argparse
from collections import Counter, defaultdict

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def parse_mac(mac_bytes):
    """Format bytes as colon-separated MAC address."""
    return ':'.join(f'{b:02x}' for b in mac_bytes)

def parse_ip(ip_bytes):
    """Format bytes as dot-decimal IP address."""
    return socket.inet_ntoa(ip_bytes)

def parse_dns_name(payload, offset):
    """Parse a DNS label-sequence name from payload at offset."""
    labels = []
    i = offset
    try:
        while i < len(payload):
            length = payload[i]
            if length == 0:
                i += 1
                break
            # Check for compression pointer (not fully handled to keep simple, but standard query name doesn't use it)
            if (length & 0xC0) == 0xC0:
                # Compression pointer - 2 bytes
                i += 2
                labels.append("[compressed]")
                break
            i += 1
            if i + length > len(payload):
                break
            label = payload[i:i+length].decode('ascii', errors='ignore')
            labels.append(label)
            i += length
        return '.'.join(labels), i
    except Exception:
        return "[invalid name]", offset

class PcapAnalyzer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.total_packets = 0
        self.total_bytes = 0
        self.protocols = Counter()
        self.src_ips = Counter()
        self.dst_ips = Counter()
        self.ip_pairs = Counter()
        self.ports = Counter()
        self.dns_queries = Counter()
        self.icmp_types = Counter()
        self.conversations_bytes = defaultdict(int)
        self.packet_sizes = []
        self.link_type = 1 # Default Ethernet
        self.endian = '='  # native
        
    def analyze(self, max_packets=None, filter_ip=None, filter_port=None, verbose=False):
        c_red = get_color('red')
        c_yellow = get_color('yellow')
        c_green = get_color('green')
        c_cyan = get_color('cyan')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        if not os.path.exists(self.filepath):
            print(f"{c_red}Error: File not found '{self.filepath}'{c_reset}")
            return False

        with open(self.filepath, 'rb') as f:
            # Read Global Header (24 bytes)
            global_header = f.read(24)
            if len(global_header) < 24:
                print(f"{c_red}Error: Invalid PCAP global header (too short).{c_reset}")
                return False

            # Determine endianness from magic number
            magic = struct.unpack('I', global_header[:4])[0]
            if magic == 0xa1b2c3d4:
                self.endian = '<'  # Little endian
            elif magic == 0xd4c3b2a1:
                self.endian = '>'  # Big endian
            elif magic in (0x0a0d0d0a, 0x1a2b3c4d):
                # PCAPNG magic numbers
                print(f"{c_yellow}Warning: Detected PCAPNG file format. This tool optimized for legacy PCAP.{c_reset}")
                print("Trying to parse it or run converters first. If parsing fails, convert to PCAP format.")
                # We can do a rudimentary PCAPNG parse if we just check blocks, but let's advise user.
                return self.parse_pcapng(f, max_packets, filter_ip, filter_port, verbose)
            else:
                print(f"{c_red}Error: Unknown PCAP magic number {hex(magic)}.{c_reset}")
                return False

            # Unpack global header parameters
            _, _, _, _, _, _, network = struct.unpack(self.endian + 'IHHIIII', global_header)
            self.link_type = network
            if self.link_type != 1:
                print(f"{c_yellow}Warning: Link type is {self.link_type} (Not Ethernet). Some dissecting may be limited.{c_reset}")

            if verbose:
                print(f"{c_bold}Parsing PCAP file: {self.filepath}{c_reset}")
                print(f"Link Layer Type: {self.link_type} (Ethernet=1)")
                print(f"Endianness: {'Little-Endian' if self.endian == '<' else 'Big-Endian'}")
                print("-" * 80)

            # Read Packets
            while True:
                if max_packets and self.total_packets >= max_packets:
                    break

                header_bytes = f.read(16)
                if len(header_bytes) < 16:
                    break  # End of file

                ts_sec, ts_usec, incl_len, orig_len = struct.unpack(self.endian + 'IIII', header_bytes)
                packet_data = f.read(incl_len)
                if len(packet_data) < incl_len:
                    print(f"{c_red}Warning: Truncated packet at index {self.total_packets}{c_reset}")
                    break

                self.total_packets += 1
                self.total_bytes += orig_len
                self.packet_sizes.append(orig_len)

                # Process Link Layer
                self.dissect_packet(packet_data, ts_sec, ts_usec, filter_ip, filter_port, verbose)

        return True

    def parse_pcapng(self, f, max_packets, filter_ip, filter_port, verbose):
        """Very basic parser for PCAPNG format (Section Header, Interface, Enhanced Packet blocks)."""
        f.seek(0)
        c_red = get_color('red')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        self.endian = '<' # Default
        
        while True:
            if max_packets and self.total_packets >= max_packets:
                break

            block_header = f.read(8)
            if len(block_header) < 8:
                break

            block_type, block_total_length = struct.unpack(self.endian + 'II', block_header)
            # Re-read if endianness check is needed (SHB type is 0x0A0D0D0A)
            if block_type == 0x0A0D0D0A:
                # Read next 4 bytes (Byte-Order Magic)
                bom_bytes = f.read(4)
                if len(bom_bytes) == 4:
                    bom = struct.unpack('>I', bom_bytes)[0]
                    if bom == 0x1A2B3C4D:
                        self.endian = '>'
                    else:
                        self.endian = '<'
                # Seek back to correct offset in SHB
                f.seek(-4, 1)

            block_data_len = block_total_length - 12  # Subtract type (4), length (4), length-repeat (4)
            if block_data_len < 0:
                break

            block_data = f.read(block_data_len)
            f.read(4) # read ending block length repeat

            # Enhanced Packet Block is 0x00000006
            if block_type == 0x00000006:
                if len(block_data) < 20:
                    continue
                interface_id, ts_high, ts_low, captured_len, original_len = struct.unpack(self.endian + 'IIIII', block_data[:20])
                packet_data = block_data[20:20+captured_len]

                self.total_packets += 1
                self.total_bytes += original_len
                self.packet_sizes.append(original_len)

                # Time calculation (rough approximation assuming 1 microsecond clock resolution)
                ts_sec = (ts_high << 32 | ts_low) // 1000000
                ts_usec = (ts_high << 32 | ts_low) % 1000000

                self.dissect_packet(packet_data, ts_sec, ts_usec, filter_ip, filter_port, verbose)
            
            # Simple Packet Block is 0x00000003
            elif block_type == 0x00000003:
                if len(block_data) < 4:
                    continue
                original_len = struct.unpack(self.endian + 'I', block_data[:4])[0]
                packet_data = block_data[4:]
                self.total_packets += 1
                self.total_bytes += original_len
                self.packet_sizes.append(original_len)
                self.dissect_packet(packet_data, 0, 0, filter_ip, filter_port, verbose)

        return True

    def dissect_packet(self, data, ts_sec, ts_usec, filter_ip=None, filter_port=None, verbose=False):
        # Ethernet Header
        if len(data) < 14:
            self.protocols["Other"] += 1
            return

        dst_mac = parse_mac(data[0:6])
        src_mac = parse_mac(data[6:12])
        ether_type = struct.unpack('>H', data[12:14])[0]

        # Check for VLAN tagging (0x8100)
        offset = 14
        if ether_type == 0x8100:
            if len(data) < 18:
                return
            ether_type = struct.unpack('>H', data[16:18])[0]
            offset = 18

        # IPv4 Dissector
        if ether_type == 0x0800:
            self.protocols["IPv4"] += 1
            if len(data) < offset + 20:
                return

            ip_header = data[offset:offset+20]
            version_ihl = ip_header[0]
            ihl = (version_ihl & 0x0F) * 4
            if len(data) < offset + ihl:
                return

            proto = ip_header[9]
            src_ip = parse_ip(ip_header[12:16])
            dst_ip = parse_ip(ip_header[16:20])

            # Apply IP filter
            if filter_ip and (filter_ip != src_ip and filter_ip != dst_ip):
                return

            self.src_ips[src_ip] += 1
            self.dst_ips[dst_ip] += 1
            self.ip_pairs[(src_ip, dst_ip)] += 1

            ip_payload = data[offset+ihl:]

            # UDP Protocol
            if proto == 17:
                self.protocols["UDP"] += 1
                if len(ip_payload) < 8:
                    return
                src_port, dst_port, udp_len = struct.unpack('>HHH', ip_payload[:6])
                
                # Apply Port filter
                if filter_port and (filter_port != src_port and filter_port != dst_port):
                    return

                self.ports[src_port] += 1
                self.ports[dst_port] += 1
                self.conversations_bytes[(src_ip, src_port, dst_ip, dst_port)] += len(ip_payload)

                udp_payload = ip_payload[8:]

                # DNS Dissector (Port 53)
                if src_port == 53 or dst_port == 53:
                    self.protocols["DNS"] += 1
                    if len(udp_payload) >= 12:
                        # Parse DNS header questions count
                        qd_count = struct.unpack('>H', udp_payload[4:6])[0]
                        if qd_count > 0:
                            dns_name, _ = parse_dns_name(udp_payload, 12)
                            if dns_name:
                                self.dns_queries[dns_name] += 1

                if verbose:
                    print(f"[{ts_sec}.{ts_usec:06d}] UDP  {src_ip}:{src_port} -> {dst_ip}:{dst_port} | Len: {len(data)}")

            # TCP Protocol
            elif proto == 6:
                self.protocols["TCP"] += 1
                if len(ip_payload) < 20:
                    return
                src_port, dst_port = struct.unpack('>HH', ip_payload[:4])
                
                # Apply Port filter
                if filter_port and (filter_port != src_port and filter_port != dst_port):
                    return

                self.ports[src_port] += 1
                self.ports[dst_port] += 1
                self.conversations_bytes[(src_ip, src_port, dst_ip, dst_port)] += len(ip_payload)

                if verbose:
                    # Parse TCP Flags
                    flags = ip_payload[13]
                    flag_list = []
                    if flags & 0x01: flag_list.append("FIN")
                    if flags & 0x02: flag_list.append("SYN")
                    if flags & 0x04: flag_list.append("RST")
                    if flags & 0x08: flag_list.append("PSH")
                    if flags & 0x10: flag_list.append("ACK")
                    if flags & 0x20: flag_list.append("URG")
                    flag_str = "|".join(flag_list) if flag_list else "NONE"
                    print(f"[{ts_sec}.{ts_usec:06d}] TCP  {src_ip}:{src_port} -> {dst_ip}:{dst_port} [{flag_str}] | Len: {len(data)}")

            # ICMP Protocol
            elif proto == 1:
                self.protocols["ICMP"] += 1
                if len(ip_payload) >= 2:
                    icmp_type, icmp_code = struct.unpack('BB', ip_payload[:2])
                    self.icmp_types[(icmp_type, icmp_code)] += 1
                if verbose:
                    print(f"[{ts_sec}.{ts_usec:06d}] ICMP {src_ip} -> {dst_ip} | Len: {len(data)}")

            else:
                self.protocols[f"IP Proto {proto}"] += 1
                if verbose:
                    print(f"[{ts_sec}.{ts_usec:06d}] IP-Proto-{proto} {src_ip} -> {dst_ip} | Len: {len(data)}")

        # IPv6 Dissector
        elif ether_type == 0x86dd:
            self.protocols["IPv6"] += 1
            if len(data) < offset + 40:
                return
            # Minimal parsing of IPv6 to get IPs
            # IPv6 source starts at offset + 8, destination at offset + 24
            src_ip6 = socket.inet_ntop(socket.AF_INET6, data[offset+8:offset+24])
            dst_ip6 = socket.inet_ntop(socket.AF_INET6, data[offset+24:offset+40])

            if filter_ip and (filter_ip != src_ip6 and filter_ip != dst_ip6):
                return

            self.src_ips[src_ip6] += 1
            self.dst_ips[dst_ip6] += 1
            self.ip_pairs[(src_ip6, dst_ip6)] += 1

            next_hdr = data[offset+6]
            if next_hdr == 58:
                self.protocols["ICMPv6"] += 1
            elif next_hdr == 6:
                self.protocols["TCP"] += 1
            elif next_hdr == 17:
                self.protocols["UDP"] += 1

            if verbose:
                print(f"[{ts_sec}.{ts_usec:06d}] IPv6 {src_ip6} -> {dst_ip6} | NextHdr: {next_hdr} | Len: {len(data)}")

        # ARP Protocol
        elif ether_type == 0x0806:
            self.protocols["ARP"] += 1
            if verbose:
                print(f"[{ts_sec}.{ts_usec:06d}] ARP  {src_mac} -> {dst_mac} | Len: {len(data)}")
        else:
            self.protocols[f"EtherType {hex(ether_type)}"] += 1

    def print_summary(self):
        c_red = get_color('red')
        c_yellow = get_color('yellow')
        c_green = get_color('green')
        c_blue = get_color('blue')
        c_cyan = get_color('cyan')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        print(f"\n{c_bold}{c_cyan}======================================================================{c_reset}")
        print(f"{c_bold}{c_green}                     PCAP Packet Analysis Report                      {c_reset}")
        print(f"{c_bold}{c_cyan}======================================================================{c_reset}")
        print(f"File:               {self.filepath}")
        print(f"Total Packets:      {self.total_packets:,}")
        print(f"Total Volume:       {self.total_bytes / 1024 / 1024:.2f} MB ({self.total_bytes:,} bytes)")
        if self.total_packets > 0:
            print(f"Average Pkt Size:   {self.total_bytes / self.total_packets:.1f} bytes")
            print(f"Min / Max Pkt Size: {min(self.packet_sizes)} / {max(self.packet_sizes)} bytes")
        print("-" * 70)

        # Protocol Distribution
        print(f"\n{c_bold}{c_blue}Protocol Distribution:{c_reset}")
        print(f"{'Protocol':<25} {'Packet Count':<15} {'Percentage':<10}")
        print("-" * 55)
        for proto, count in self.protocols.most_common():
            pct = (count / self.total_packets * 100) if self.total_packets > 0 else 0
            # Simple bar chart
            bar_len = int(pct / 5)
            bar = "█" * bar_len
            print(f"{proto:<25} {count:<15,} {pct:>6.1f}%  {bar}")

        # Top Source IPs
        print(f"\n{c_bold}{c_blue}Top Talkers (Source IPs):{c_reset}")
        print(f"{'Source IP':<40} {'Packet Count':<15} {'Percentage':<10}")
        print("-" * 70)
        for ip, count in self.src_ips.most_common(5):
            pct = (count / self.total_packets * 100) if self.total_packets > 0 else 0
            print(f"{ip:<40} {count:<15,} {pct:>6.1f}%")

        # Top Destination IPs
        print(f"\n{c_bold}{c_blue}Top Talkers (Destination IPs):{c_reset}")
        print(f"{'Destination IP':<40} {'Packet Count':<15} {'Percentage':<10}")
        print("-" * 70)
        for ip, count in self.dst_ips.most_common(5):
            pct = (count / self.total_packets * 100) if self.total_packets > 0 else 0
            print(f"{ip:<40} {count:<15,} {pct:>6.1f}%")

        # Top Active Conversations (IP Pairs)
        print(f"\n{c_bold}{c_blue}Top Conversations (IP Pairs):{c_reset}")
        print(f"{'Source IP':<32} {'--->':<6} {'Destination IP':<32} {'Packets':<10}")
        print("-" * 83)
        for (src, dst), count in self.ip_pairs.most_common(5):
            print(f"{src:<32} {'--->':<6} {dst:<32} {count:<10,}")

        # Top Port Activity
        if self.ports:
            print(f"\n{c_bold}{c_blue}Top Ports (TCP/UDP Activity):{c_reset}")
            print(f"{'Port':<15} {'Service Name':<20} {'Occurrence':<15}")
            print("-" * 53)
            for port, count in self.ports.most_common(8):
                try:
                    srv = socket.getservbyport(port)
                except Exception:
                    srv = "unknown"
                print(f"{port:<15} {srv:<20} {count:<15,}")

        # DNS Queries
        if self.dns_queries:
            print(f"\n{c_bold}{c_blue}Top DNS Queries (Port 53):{c_reset}")
            print(f"{'Domain Name':<50} {'Query Count':<15}")
            print("-" * 68)
            for domain, count in self.dns_queries.most_common(10):
                print(f"{domain:<50} {count:<15,}")

        print(f"\n{c_bold}{c_cyan}======================================================================{c_reset}\n")


def main():
    parser = argparse.ArgumentParser(description="PCAP Analyzer - Pure-Python packet capture analyzer")
    parser.add_argument("file", help="Path to the PCAP file to analyze")
    parser.add_argument("-n", "--count", type=int, default=None, help="Maximum number of packets to parse")
    parser.add_argument("--ip", help="Filter packets matching this Source or Destination IP")
    parser.add_argument("--port", type=int, help="Filter packets matching this TCP/UDP Port")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details for each packet in real-time")
    args = parser.parse_args()

    analyzer = PcapAnalyzer(args.file)
    success = analyzer.analyze(
        max_packets=args.count,
        filter_ip=args.ip,
        filter_port=args.port,
        verbose=args.verbose
    )

    if success:
        analyzer.print_summary()
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
