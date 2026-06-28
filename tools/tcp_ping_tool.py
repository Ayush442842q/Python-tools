#!/usr/bin/env python3
"""
TCP Port Ping Utility
A command-line network utility to measure connection latency to a specific host and port
over TCP. Extremely useful when standard ICMP ping is blocked by network firewalls.
"""

import argparse
import socket
import sys
import time
import statistics

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

def print_color(text, color):
    """Print text with ANSI color if supported."""
    print(f"{color}{text}{COLOR_RESET}")

def tcp_ping(host, port, timeout=2.0):
    """Attempt to connect to target host:port over TCP and return connection time (ms) or None."""
    start_time = time.perf_counter()
    try:
        # Create TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        # Connection succeeded
        latency = (time.perf_counter() - start_time) * 1000.0
        sock.close()
        return latency, None
    except socket.timeout:
        return None, "Request timeout"
    except ConnectionRefusedError:
        # Connection refused still confirms the port is reachable/active in some layer
        latency = (time.perf_counter() - start_time) * 1000.0
        return latency, "Connection refused (Port closed but reachable)"
    except socket.gaierror:
        return None, "DNS resolution failed/Unknown host"
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(
        description="TCP Port Ping Utility - Measure connection latency over TCP sockets.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("host", help="Target host address (e.g. google.com, 192.168.1.1)")
    parser.add_argument("port", type=int, help="Target TCP port (e.g. 80, 443, 22)")
    parser.add_argument("-c", "--count", type=int, default=4, help="Number of ping requests to send (default: 4, 0 for infinite)")
    parser.add_argument("-t", "--timeout", type=float, default=2.0, help="Socket connect timeout in seconds (default: 2.0)")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="Interval between pings in seconds (default: 1.0)")
    
    args = parser.parse_args()

    # Resolve target hostname first
    try:
        ip = socket.gethostbyname(args.host)
        print_color(f"[*] TCP PING {args.host} ({ip}) on port {args.port} (timeout={args.timeout}s):", COLOR_BOLD + COLOR_BLUE)
    except socket.gaierror:
        print_color(f"[-] DNS Error: Could not resolve hostname '{args.host}'", COLOR_RED)
        return 1

    latencies = []
    sent = 0
    received = 0
    refused = 0
    lost = 0

    count_limit = args.count if args.count > 0 else float('inf')

    try:
        while sent < count_limit:
            sent += 1
            latency, err = tcp_ping(ip, args.port, args.timeout)
            
            if latency is not None:
                received += 1
                latencies.append(latency)
                status_str = f"Reply from {ip}: port={args.port} time={latency:.2f}ms"
                if err:
                    refused += 1
                    status_str += f" ({err})"
                    print_color(status_str, COLOR_YELLOW)
                else:
                    print_color(status_str, COLOR_GREEN)
            else:
                lost += 1
                print_color(f"Request failed: {err}", COLOR_RED)

            # Wait for interval if not the last ping
            if sent < count_limit:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[-] Ping interrupted by user.")

    # Calculate statistics
    print("\n" + "=" * 50)
    print_color(f"[*] TCP Connection stats for {args.host}:{args.port}:", COLOR_BOLD + COLOR_BLUE)
    loss_pct = (lost / sent) * 100.0 if sent > 0 else 0
    print(f"    Packets: Sent = {sent}, Received = {received}, Lost = {lost} ({loss_pct:.1f}% loss)")
    
    if latencies:
        min_lat = min(latencies)
        max_lat = max(latencies)
        avg_lat = statistics.mean(latencies)
        std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
        print_color(f"    Latency (ms): Min = {min_lat:.2f}ms, Max = {max_lat:.2f}ms, Avg = {avg_lat:.2f}ms, StdDev = {std_dev:.2f}ms", COLOR_CYAN)
        if refused > 0:
            print_color(f"    Note: {refused} connections were refused but latency was measured.", COLOR_YELLOW)

    return 0

if __name__ == "__main__":
    sys.exit(main())
