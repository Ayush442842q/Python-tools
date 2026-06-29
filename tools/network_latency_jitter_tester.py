#!/usr/bin/env python3
"""
Network Latency & Jitter Tester
Measures network round-trip time (RTT), latency jitter (standard variation between
consecutive packets), and packet loss. Supports TCP handshakes or ICMP pings,
and displays a statistical summary with an ASCII latency distribution histogram.
"""

import argparse
import math
import os
import socket
import subprocess
import sys
import time
from typing import List, Tuple, Optional

# Constants for default values
DEFAULT_COUNT = 20
DEFAULT_PORT = 443
DEFAULT_TIMEOUT = 2.0  # seconds

def ping_icmp(target: str, timeout_sec: float) -> Optional[float]:
    """Sends a single ICMP ping using the system's ping command and returns RTT in ms."""
    is_win = sys.platform == "win32"
    
    # Configure ping arguments depending on OS
    if is_win:
        # Windows: -n 1 (count), -w timeout_ms
        timeout_ms = int(timeout_sec * 1000)
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), target]
    else:
        # Unix/macOS: -c 1 (count), -W timeout_sec
        cmd = ["ping", "-c", "1", "-W", str(timeout_sec), target]
        
    try:
        start = time.perf_counter()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_sec + 1.0)
        end = time.perf_counter()
        
        if res.returncode == 0:
            # Successfully got response. Let's parse RTT or calculate wall-clock diff
            # Parsing output is language-dependent, so wall-clock time is a robust fallback,
            # but parsing gives the true network interface RTT. Let's try parsing first.
            output = res.stdout.lower()
            if is_win:
                # Look for "time=Xms" or "time<1ms"
                if "time=" in output:
                    part = output.split("time=")[1].split("ms")[0].strip()
                    return float(part)
                elif "time<1ms" in output:
                    return 0.5
            else:
                # Look for "time=X.YY ms"
                if "time=" in output:
                    part = output.split("time=")[1].split(" ")[0].strip()
                    return float(part)
            
            # Fallback to wall-clock if parsing failed but ping command succeeded
            return (end - start) * 1000.0
        return None
    except Exception:
        return None

def ping_tcp(target: str, port: int, timeout_sec: float) -> Optional[float]:
    """Measures TCP connection handshake time to target:port and returns RTT in ms."""
    try:
        # Resolve target IP
        addr_info = socket.getaddrinfo(target, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return None
        
        family, socktype, proto, canonname, sockaddr = addr_info[0]
        s = socket.socket(family, socktype, proto)
        s.settimeout(timeout_sec)
        
        start = time.perf_counter()
        s.connect(sockaddr)
        end = time.perf_counter()
        
        s.close()
        return (end - start) * 1000.0
    except (socket.timeout, socket.error):
        return None

def calculate_jitter(rtts: List[float]) -> float:
    """Calculates latency jitter as the average of absolute differences between consecutive samples."""
    if len(rtts) < 2:
        return 0.0
    diffs = [abs(rtts[i+1] - rtts[i]) for i in range(len(rtts) - 1)]
    return sum(diffs) / len(diffs)

def calculate_stats(rtts: List[float]) -> Tuple[float, float, float, float, float]:
    """Returns (min, max, avg, std_dev, p95) of RTTs."""
    if not rtts:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    
    rtts_sorted = sorted(rtts)
    min_r = rtts_sorted[0]
    max_r = rtts_sorted[-1]
    avg_r = sum(rtts) / len(rtts)
    
    # Standard deviation
    variance = sum((x - avg_r) ** 2 for x in rtts) / len(rtts)
    std_dev = math.sqrt(variance)
    
    # 95th percentile
    p95_idx = int(len(rtts_sorted) * 0.95)
    p95 = rtts_sorted[min(p95_idx, len(rtts_sorted) - 1)]
    
    return min_r, max_r, avg_r, std_dev, p95

def draw_ascii_histogram(rtts: List[float], num_buckets: int = 10, max_width: int = 50):
    """Draws a vertical/horizontal ASCII histogram showing latency distribution."""
    if not rtts:
        return
        
    min_r, max_r = min(rtts), max(rtts)
    span = max_r - min_r
    
    # If all RTTs are identical, create a single bucket
    if span == 0:
        print(f"\n[*] Latency Distribution Histogram (All RTTs = {min_r:.2f} ms):")
        print(f"  {min_r:6.1f} ms | {'#' * len(rtts)}")
        return
        
    buckets = [0] * num_buckets
    bucket_size = span / num_buckets
    
    for r in rtts:
        # Calculate bucket index
        idx = int((r - min_r) / bucket_size)
        if idx >= num_buckets:
            idx = num_buckets - 1
        buckets[idx] += 1
        
    max_count = max(buckets)
    if max_count == 0:
        max_count = 1
        
    print("\n[*] Latency Distribution Histogram:")
    for i in range(num_buckets):
        b_min = min_r + i * bucket_size
        b_max = b_min + bucket_size
        count = buckets[i]
        
        # Calculate bar length
        bar_len = int((count / max_count) * max_width)
        bar = "#" * bar_len
        if count > 0 and bar_len == 0:
            bar = "."
            
        print(f"  {b_min:6.1f} - {b_max:6.1f} ms | {count:3} | {bar}")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Network Latency & Jitter Benchmarking tool. Monitors stability and packet loss."
    )
    parser.add_argument("target", help="Target hostname or IP address (e.g. google.com, 1.1.1.1)")
    parser.add_argument("-c", "--count", type=int, default=DEFAULT_COUNT, help=f"Number of test cycles (default: {DEFAULT_COUNT})")
    parser.add_argument("-t", "--tcp", action="store_true", help="Use TCP port handshakes instead of ICMP pings")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"TCP port to test connection (default: {DEFAULT_PORT})")
    parser.add_argument("-w", "--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Connection timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("-i", "--interval", type=float, default=0.2, help="Interval sleep time between test cycles in seconds (default: 0.2)")
    args = parser.parse_args()

    target = args.target
    count = args.count
    use_tcp = args.tcp
    port = args.port
    timeout = args.timeout
    interval = args.interval

    # Validate target resolution
    try:
        ip = socket.gethostbyname(target)
        resolved_info = f"({ip})"
    except socket.gaierror:
        print(f"[-] Error: Could not resolve hostname '{target}'")
        sys.exit(1)

    print("=" * 65)
    mode_str = f"TCP Handshake (port {port})" if use_tcp else "ICMP Ping"
    print(f" Network Latency & Jitter Tester: {target} {resolved_info}")
    print(f" Mode: {mode_str} | Cycles: {count} | Timeout: {timeout}s")
    print("=" * 65)
    
    rtts = []
    lost_packets = 0
    
    try:
        for i in range(1, count + 1):
            if use_tcp:
                rtt = ping_tcp(target, port, timeout)
            else:
                rtt = ping_icmp(target, timeout)
                
            if rtt is not None:
                rtts.append(rtt)
                status_str = f"RTT={rtt:.2f} ms"
            else:
                lost_packets += 1
                status_str = "REQUEST TIMEOUT / LOST"
                
            print(f" Cycle {i:<3}: {status_str}")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[-] Test interrupted by user.")
        
    # Analyze and output results
    print("\n" + "=" * 65)
    print(" TEST STATISTICAL REPORT")
    print("=" * 65)
    
    total_packets = len(rtts) + lost_packets
    if total_packets == 0:
        print("[-] No test data collected.")
        sys.exit(1)
        
    loss_pct = (lost_packets / total_packets) * 100.0
    print(f" Packets: Sent = {total_packets}, Received = {len(rtts)}, Lost = {lost_packets} ({loss_pct:.1f}% loss)")
    
    if rtts:
        min_r, max_r, avg_r, std_dev, p95 = calculate_stats(rtts)
        jitter = calculate_jitter(rtts)
        
        print(f" Latency (RTT) : Min = {min_r:.2f} ms | Max = {max_r:.2f} ms | Avg = {avg_r:.2f} ms")
        print(f" Percentiles   : p95 = {p95:.2f} ms | StdDev = {std_dev:.2f} ms")
        print(f" Jitter        : {jitter:.2f} ms (avg consecutive variation)")
        
        # Stability rating
        stability_desc = "EXCELLENT"
        if loss_pct > 5.0 or jitter > 30.0:
            stability_desc = "POOR"
        elif loss_pct > 1.0 or jitter > 10.0:
            stability_desc = "FAIR"
        elif jitter > 3.0:
            stability_desc = "GOOD"
            
        print(f" Connection Stability Rating: {stability_desc}")
        
        # Draw distribution histogram
        draw_ascii_histogram(rtts)
    else:
        print("[-] All test packets were lost. Check network connection or target host access.")

if __name__ == "__main__":
    main()
