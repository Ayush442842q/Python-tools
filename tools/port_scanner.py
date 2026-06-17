#!/usr/bin/env python3
"""
TCP Port Scanner & Service Banner Grabber
Scan open ports on a target host concurrently and attempts service banner grabbing.
"""

import sys
import socket
import argparse
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Common ports list to scan by default
COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    115: "SFTP",
    135: "RPC",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    587: "SMTP (Submission)",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    8080: "HTTP-Proxy/Tomcat",
    8443: "HTTPS-Alt"
}

def grab_banner(sock, port):
    """
    Attempt to grab service banner from the socket.
    """
    sock.settimeout(2.0)
    try:
        # For HTTP, HTTPS, send a request to trigger a response banner
        if port in [80, 8080]:
            sock.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
        elif port == 443:
            # Simple HTTPS request won't work easily without SSL wrapper, but we can try
            sock.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
            
        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        # Clean up binary/non-printable chars
        banner = "".join(ch for ch in banner if 32 <= ord(ch) < 127 or ch in "\n\r\t")
        return banner.split('\n')[0][:80] # Return first line up to 80 chars
    except Exception:
        return None

def scan_port(host, port, timeout):
    """
    Scan a single port on a host and return its state.
    """
    result = {
        'port': port,
        'status': 'closed',
        'service': COMMON_PORTS.get(port, 'Unknown'),
        'banner': None
    }
    
    try:
        # Create socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            # Try to connect
            status_code = sock.connect_ex((host, port))
            if status_code == 0:
                result['status'] = 'open'
                # Attempt to grab banner
                banner = grab_banner(sock, port)
                if banner:
                    result['banner'] = banner
    except Exception as e:
        result['status'] = f"error ({str(e)})"
        
    return result

def parse_ports_arg(ports_str):
    """
    Parse the ports argument string (e.g. '80', '1-1024', '22,80,443').
    """
    ports = []
    if not ports_str:
        return sorted(list(COMMON_PORTS.keys()))
        
    for part in ports_str.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if 1 <= start <= end <= 65535:
                    ports.extend(range(start, end + 1))
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid port range: {part}")
        else:
            try:
                p = int(part)
                if 1 <= p <= 65535:
                    ports.append(p)
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid port: {part}")
    return sorted(list(set(ports)))

def main():
    parser = argparse.ArgumentParser(
        description="TCP Port Scanner & Service Banner Grabber",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target", help="Target IP address or hostname to scan")
    parser.add_argument(
        "--ports", "-p", 
        type=parse_ports_arg, 
        help="Ports to scan: common (default), single port (e.g. 80), range (e.g. 1-1024), list (e.g. 22,80,443)"
    )
    parser.add_argument("--threads", "-t", type=int, default=50, help="Number of worker threads (default: 50)")
    parser.add_argument("--timeout", type=float, default=1.5, help="Socket timeout in seconds (default: 1.5)")
    parser.add_argument("--json-out", "-j", help="Output file to save results in JSON format")
    
    args = parser.parse_args()
    
    target_host = args.target
    # Resolve host
    try:
        target_ip = socket.gethostbyname(target_host)
    except socket.gaierror:
        print(f"Error: Could not resolve hostname '{target_host}'", file=sys.stderr)
        return 1
        
    ports_to_scan = args.ports or sorted(list(COMMON_PORTS.keys()))
    
    print(f"Starting Scan for {target_host} ({target_ip})")
    print(f"Scan initiated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scanning {len(ports_to_scan)} ports using {args.threads} threads...")
    print("-" * 65)
    
    open_ports = []
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        # Submit all tasks
        futures = {
            executor.submit(scan_port, target_ip, port, args.timeout): port 
            for port in ports_to_scan
        }
        
        # Display open ports in real-time
        for future in as_completed(futures):
            res = future.result()
            if res['status'] == 'open':
                open_ports.append(res)
                banner_str = f" | Banner: {res['banner']}" if res['banner'] else ""
                print(f"Port {res['port']:<6} [OPEN]   Service: {res['service']:<18}{banner_str}")
                
    print("-" * 65)
    print(f"Scan complete. Found {len(open_ports)} open port(s).")
    
    # Save to file
    if args.json_out:
        output_data = {
            'target_host': target_host,
            'target_ip': target_ip,
            'scan_time': datetime.now().isoformat(),
            'open_ports': open_ports
        }
        try:
            with open(args.json_out, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4)
            print(f"Results saved to '{args.json_out}'")
        except Exception as e:
            print(f"Error saving JSON results: {e}", file=sys.stderr)
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
