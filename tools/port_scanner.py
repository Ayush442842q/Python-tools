"""
Port Scanner Tool
A simple, multithreaded TCP port scanner to scan a range of ports on a target host.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import sys

def parse_ports(port_arg):
    ports = []
    # If commas are present, split by comma
    parts = port_arg.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start > end or start < 1 or end > 65535:
                    raise ValueError
                ports.extend(range(start, end + 1))
            except ValueError:
                print(f"[ERROR] Invalid port range: {part}")
                sys.exit(1)
        else:
            try:
                p = int(part)
                if p < 1 or p > 65535:
                    raise ValueError
                ports.append(p)
            except ValueError:
                print(f"[ERROR] Invalid port number: {part}")
                sys.exit(1)
    # Deduplicate and sort
    return sorted(list(set(ports)))

def scan_port(target, port, timeout):
    try:
        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((target, port))
            if result == 0:
                return port, True
    except Exception:
        pass
    return port, False

def main():
    parser = argparse.ArgumentParser(
        description="A multithreaded TCP port scanner."
    )
    parser.add_argument("target", help="Target hostname or IP address (e.g., 'localhost' or '8.8.8.8').")
    parser.add_argument(
        "-p", "--ports",
        default="1-1024",
        help="Ports to scan. Can be a range (e.g. '1-1024'), comma-separated list ('80,443,8080'), or mixed ('22,80-100'). Default: 1-1024"
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=50,
        help="Number of threads for concurrent scanning (default: 50)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Socket timeout in seconds (default: 1.0)."
    )
    
    args = parser.parse_args()

    # Resolve target IP
    try:
        target_ip = socket.gethostbyname(args.target)
    except socket.gaierror as e:
        print(f"[ERROR] Could not resolve host '{args.target}': {e}")
        sys.exit(1)

    ports_to_scan = parse_ports(args.ports)

    print(f"Scanning target: {args.target} ({target_ip})")
    print(f"Scanning {len(ports_to_scan)} ports with {args.threads} threads...")
    print("-" * 50)

    open_ports = []
    
    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Submit scan tasks
            futures = {executor.submit(scan_port, target_ip, port, args.timeout): port for port in ports_to_scan}
            
            for future in as_completed(futures):
                port, is_open = future.result()
                if is_open:
                    print(f"[OK] Port {port} is OPEN")
                    open_ports.append(port)
    except KeyboardInterrupt:
        print("\n[INFO] Scan cancelled by user.")
        sys.exit(1)

    print("-" * 50)
    open_ports.sort()
    print(f"[PASS] Scan complete. Found {len(open_ports)} open ports.")
    if open_ports:
        print(f"Open ports: {', '.join(map(str, open_ports))}")
        
    sys.exit(0)

if __name__ == "__main__":
    main()
