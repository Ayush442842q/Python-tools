#!/usr/bin/env python3
"""
Local Port Finder & Inspector
Checks if local TCP/UDP ports are in use and finds available free ports.
"""

import argparse
import socket
import sys

def is_port_in_use(port, host='127.0.0.1', protocol='tcp'):
    """Check if a port is currently in use on the local system."""
    if protocol.lower() == 'tcp':
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.bind((host, port))
                return False  # Binding succeeded, so port is NOT in use
            except socket.error:
                return True   # Binding failed, port IS in use
    else:  # UDP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.bind((host, port))
                return False
            except socket.error:
                return True

def find_free_ports(start_port=8000, end_port=9000, count=1, host='127.0.0.1'):
    """Find available free ports in a specified range."""
    free_ports = []
    for port in range(start_port, end_port + 1):
        if len(free_ports) >= count:
            break
        if not is_port_in_use(port, host, 'tcp'):
            free_ports.append(port)
            
    return free_ports

def get_port_banner(port, host='127.0.0.1'):
    """Attempt to grab a service banner if the port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.connect((host, port))
            # Send an empty line or HTTP request to prompt a response
            s.sendall(b"\r\n")
            banner = s.recv(1024).decode('utf-8', errors='ignore').strip()
            return banner if banner else "Connected (No banner returned)"
        except Exception:
            return "Connection refused/closed"

def main():
    parser = argparse.ArgumentParser(description='Find free local ports and inspect active ports.')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--find', action='store_true',
                        help='Find one or more free TCP ports')
    group.add_argument('-c', '--check', type=str,
                        help='Check status of specific ports (comma-separated list, e.g., 80,443,8080)')
    
    parser.add_argument('-r', '--range', type=str, default='8000-9000',
                        help='Port range to scan for finding free ports (default: 8000-9000)')
    parser.add_argument('-n', '--count', type=int, default=1,
                        help='Number of free ports to find (default: 1)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='Target host for scanning (default: 127.0.0.1)')
    parser.add_argument('-u', '--udp', action='store_true',
                        help='Check UDP ports instead of TCP (applies only to --check)')
    parser.add_argument('-b', '--banner', action='store_true',
                        help='Try to grab service banner for active ports')

    args = parser.parse_args()

    # Handle finding free ports
    if args.find:
        try:
            start, end = map(int, args.range.split('-'))
        except ValueError:
            print("Error: Invalid range format. Use START-END (e.g., 8000-9000).", file=sys.stderr)
            sys.exit(1)
            
        if start > end:
            start, end = end, start
            
        print(f"Searching for {args.count} free TCP port(s) in range {start}-{end} on {args.host}...")
        free_ports = find_free_ports(start, end, args.count, args.host)
        
        if free_ports:
            print("\nAvailable free ports:")
            for p in free_ports:
                print(f"  - {p}")
            if len(free_ports) < args.count:
                print(f"\nWarning: Only found {len(free_ports)} free ports in range.")
        else:
            print(f"\nNo free ports found in range {start}-{end}.", file=sys.stderr)
            sys.exit(1)

    # Handle checking specific ports
    elif args.check:
        ports_to_check = []
        for part in args.check.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    s, e = map(int, part.split('-'))
                    ports_to_check.extend(range(s, e + 1))
                except ValueError:
                    print(f"Error: Invalid sub-range '{part}' in port list.", file=sys.stderr)
                    sys.exit(1)
            else:
                try:
                    ports_to_check.append(int(part))
                except ValueError:
                    print(f"Error: Invalid port number '{part}'.", file=sys.stderr)
                    sys.exit(1)
                    
        proto = 'udp' if args.udp else 'tcp'
        print(f"Checking {len(ports_to_check)} {proto.upper()} port(s) on {args.host}...")
        print(f"{'PORT':<8} {'STATUS':<12} {'INFO/BANNER' if args.banner and proto == 'tcp' else ''}")
        print("-" * 50)
        
        for p in ports_to_check:
            in_use = is_port_in_use(p, args.host, proto)
            status = "IN USE" if in_use else "FREE"
            
            info = ""
            if in_use and args.banner and proto == 'tcp':
                info = get_port_banner(p, args.host)
                
            print(f"{p:<8} {status:<12} {info}")

if __name__ == '__main__':
    main()
