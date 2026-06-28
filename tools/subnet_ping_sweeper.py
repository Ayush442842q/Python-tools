#!/usr/bin/env python3
"""
Subnet Ping Sweeper
Fast, multi-threaded IP subnet and IP range scanner that probes hosts using the system's native ping utility
and displays active hosts, response latencies (RTT), and summary stats.
"""

import sys
import os
import re
import argparse
import subprocess
import socket
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def ip_to_int(ip):
    """Convert IPv4 string to 32-bit integer"""
    return struct.unpack("!I", socket.inet_aton(ip))[0]

def int_to_ip(num):
    """Convert 32-bit integer back to IPv4 string"""
    return socket.inet_ntoa(struct.pack("!I", num))

def parse_cidr(cidr_str):
    """Parse CIDR notation (e.g. 192.168.1.0/24) and return list of IPs"""
    try:
        ip_part, mask_part = cidr_str.split('/')
        mask = int(mask_part)
        if mask < 0 or mask > 32:
            raise ValueError("Mask must be between 0 and 32")
        
        ip_num = ip_to_int(ip_part)
        # Calculate network prefix mask
        net_mask = (0xFFFFFFFF << (32 - mask)) & 0xFFFFFFFF
        network_ip = ip_num & net_mask
        
        # Calculate number of hosts
        num_hosts = 2 ** (32 - mask)
        
        # If /32, just return the single IP
        if mask == 32:
            return [int_to_ip(network_ip)]
        
        # For other networks, return all addresses (excluding network and broadcast for /30 or larger)
        if mask <= 30:
            start = network_ip + 1
            end = network_ip + num_hosts - 1
        else:
            start = network_ip
            end = network_ip + num_hosts
            
        return [int_to_ip(i) for i in range(start, end)]
    except Exception as e:
        raise ValueError(f"Invalid CIDR notation: {cidr_str}. Error: {e}")

def parse_ip_range(range_str):
    """Parse IP range (e.g. 192.168.1.1-192.168.1.50 or 192.168.1.1-50) and return list of IPs"""
    range_str = range_str.replace(' ', '')
    try:
        if '-' not in range_str:
            # Single IP
            socket.inet_aton(range_str)
            return [range_str]
            
        start_part, end_part = range_str.split('-')
        
        # Validate start IP
        socket.inet_aton(start_part)
        
        if '.' in end_part:
            # Full IP range (e.g., 192.168.1.1-192.168.1.50)
            socket.inet_aton(end_part)
            start_num = ip_to_int(start_part)
            end_num = ip_to_int(end_part)
        else:
            # Partial IP range (e.g., 192.168.1.1-50)
            start_num = ip_to_int(start_part)
            octets = start_part.split('.')
            octets[-1] = end_part
            end_ip = '.'.join(octets)
            socket.inet_aton(end_ip)
            end_num = ip_to_int(end_ip)
            
        if start_num > end_num:
            start_num, end_num = end_num, start_num
            
        return [int_to_ip(i) for i in range(start_num, end_num + 1)]
    except Exception as e:
        raise ValueError(f"Invalid IP range format: {range_str}. Error: {e}")

def ping_host(ip, timeout_ms=1000):
    """Ping a single host using native OS commands and return RTT or None if offline"""
    is_windows = sys.platform == "win32"
    
    # Configure command and options
    if is_windows:
        # -n 1: 1 packet
        # -w timeout_ms: timeout in ms
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        # -c 1: 1 packet
        # -W timeout_s: timeout in seconds
        timeout_s = str(max(1, timeout_ms // 1000))
        cmd = ["ping", "-c", "1", "-W", timeout_s, ip]
        
    try:
        start_time = time.time()
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=float(timeout_ms) / 1000.0 + 0.5
        )
        elapsed = (time.time() - start_time) * 1000.0
        
        if process.returncode == 0:
            # Extract latency RTT from output if possible
            rtt = elapsed
            output = process.stdout
            
            # Simple RTT regex pattern matching for "time=X ms" or "time=X.Y ms"
            match = re.search(r"time[=<]([0-9\.]+)\s*ms", output, re.IGNORECASE)
            if match:
                rtt = float(match.group(1))
            return ip, True, rtt
        else:
            return ip, False, 0.0
    except Exception:
        return ip, False, 0.0

def main():
    parser = argparse.ArgumentParser(description="Multi-threaded subnet and IP range ping sweeper.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--cidr", help="Subnet in CIDR format (e.g. 192.168.1.0/24)")
    group.add_argument("-r", "--range", help="IP range (e.g. 10.0.0.1-10.0.0.50 or 10.0.0.1-50)")
    
    parser.add_argument("-t", "--threads", type=int, default=50, help="Number of concurrent ping threads (default: 50)")
    parser.add_argument("-w", "--timeout", type=int, default=1000, help="Ping timeout in milliseconds (default: 1000)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print offline hosts as well")
    
    args = parser.parse_args()
    
    try:
        if args.cidr:
            ips = parse_cidr(args.cidr)
            scan_type = f"CIDR subnet '{args.cidr}'"
        else:
            ips = parse_ip_range(args.range)
            scan_type = f"IP range '{args.range}'"
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    total_ips = len(ips)
    print(f"Starting ping sweep on {total_ips} hosts in {scan_type} using {args.threads} threads...")
    print("=" * 60)
    
    active_hosts = []
    start_time = time.time()
    
    # Run the sweep using a thread pool
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(ping_host, ip, args.timeout): ip for ip in ips}
        
        for future in as_completed(futures):
            ip, is_alive, rtt = future.result()
            if is_alive:
                active_hosts.append((ip, rtt))
                print(f"  [+] Host: {ip:<15} is ALIVE (RTT: {rtt:.1f} ms)")
            elif args.verbose:
                print(f"  [-] Host: {ip:<15} is OFFLINE")
                
    duration = time.time() - start_time
    
    # Sort active hosts by IP numerical value
    active_hosts.sort(key=lambda x: ip_to_int(x[0]))
    
    print("=" * 60)
    print("Sweep Summary:")
    print(f"  • Scan Duration:    {duration:.2f} seconds")
    print(f"  • Total IPs Scanned: {total_ips}")
    print(f"  • Active Hosts:      {len(active_hosts)}")
    print(f"  • Inactive Hosts:    {total_ips - len(active_hosts)}")
    print("")
    
    if active_hosts:
        print("Active Hosts List:")
        print(f"  {'IP Address':<18} {'RTT (latency)':<15}")
        print(f"  {'-'*18} {'-'*15}")
        for ip, rtt in active_hosts:
            print(f"  {ip:<18} {rtt:.1f} ms")
    else:
        print("No active hosts found.")
    print("=" * 60)

if __name__ == "__main__":
    main()
