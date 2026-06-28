#!/usr/bin/env python3
"""
HTTP Request Repeater & Latency Analyzer

A command-line tool that executes an HTTP/HTTPS request repeatedly to analyze
performance consistency, latency distribution, and response status codes.
Includes statistics computation and a terminal ASCII histogram.

Usage:
    python tools/http_request_repeater.py http://example.com/api --count 20 --delay 0.1
"""

import argparse
import sys
import time
import urllib.request
import urllib.error
import math

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "magenta": "\033[95m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def calculate_stats(latencies):
    """Calculates min, max, avg, median, and stddev of latencies."""
    if not latencies:
        return 0, 0, 0, 0, 0
    
    n = len(latencies)
    min_val = min(latencies)
    max_val = max(latencies)
    avg_val = sum(latencies) / n
    
    # Median
    sorted_lats = sorted(latencies)
    if n % 2 == 1:
        median_val = sorted_lats[n // 2]
    else:
        median_val = (sorted_lats[(n // 2) - 1] + sorted_lats[n // 2]) / 2.0
        
    # Standard deviation
    variance = sum((x - avg_val) ** 2 for x in latencies) / max(1, n - 1)
    stddev_val = math.sqrt(variance)
    
    return min_val, max_val, avg_val, median_val, stddev_val

def draw_histogram(latencies, bins_count=8):
    """Draws a vertical-aligned horizontal ASCII histogram of latencies."""
    if not latencies:
        return
        
    min_val = min(latencies)
    max_val = max(latencies)
    
    # If all latencies are identical, just show one bin
    if min_val == max_val:
        print(f"  {min_val * 1000:.1f} ms: [████████████████████] {len(latencies)}")
        return
        
    bin_width = (max_val - min_val) / bins_count
    bins = [0] * bins_count
    
    for lat in latencies:
        # Place in bin
        bin_idx = int((lat - min_val) / bin_width)
        if bin_idx >= bins_count:
            bin_idx = bins_count - 1
        bins[bin_idx] += 1
        
    max_bin_count = max(bins)
    max_bar_width = 40
    
    print(f"\n{COLORS['bold']}Latency Distribution Histogram:{COLORS['reset']}")
    
    for i in range(bins_count):
        bin_min = min_val + (i * bin_width)
        bin_max = bin_min + bin_width
        count = bins[i]
        
        # Calculate bar length
        bar_len = int((count / max_bin_count) * max_bar_width) if max_bin_count > 0 else 0
        bar = "█" * bar_len
        
        # Format labels
        label = f"  {bin_min*1000:6.1f} - {bin_max*1000:6.1f} ms"
        print(f"{label}: {COLORS['cyan']}{bar:<40}{COLORS['reset']} {count}")

def main():
    parser = argparse.ArgumentParser(description="Repeat HTTP requests and analyze latency distribution.")
    parser.add_argument("url", help="Target URL (e.g. http://example.com/)")
    parser.add_argument("-c", "--count", type=int, default=10, help="Number of requests to make (default: 10)")
    parser.add_argument("-d", "--delay", type=float, default=0.1, help="Delay in seconds between requests (default: 0.1)")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST", "HEAD", "PUT", "DELETE"], help="HTTP Method")
    parser.add_argument("-p", "--payload", help="Request string payload (for POST/PUT requests)")
    parser.add_argument("-H", "--header", nargs="+", default=[], help="Custom headers in Key:Value format")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console output")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    print(f"Repeating {COLORS['bold']}{args.method}{COLORS['reset']} request to {COLORS['cyan']}{args.url}{COLORS['reset']}")
    print(f"Total count: {args.count}, Delay between runs: {args.delay}s\n")
    
    headers = {}
    for h in args.header:
        if ':' in h:
            k, v = h.split(':', 1)
            headers[k.strip()] = v.strip()
            
    data_bytes = None
    if args.payload:
        data_bytes = args.payload.encode('utf-8')
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
    latencies = []
    status_codes = {}
    failures = 0
    
    for i in range(1, args.count + 1):
        req = urllib.request.Request(args.url, data=data_bytes, headers=headers, method=args.method)
        
        start_time = time.perf_counter()
        code = 0
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                code = response.status
        except urllib.error.HTTPError as he:
            code = he.code
        except Exception as e:
            code = "NetworkError"
            failures += 1
            
        elapsed = time.perf_counter() - start_time
        
        if code != "NetworkError":
            latencies.append(elapsed)
            
        status_codes[code] = status_codes.get(code, 0) + 1
        
        # Log individual run
        color = COLORS["green"] if isinstance(code, int) and 200 <= code < 400 else COLORS["red"]
        elapsed_ms = elapsed * 1000
        print(f"  Request #{i:<3} -> Status: {color}{code:<12}{COLORS['reset']} Latency: {elapsed_ms:8.2f} ms")
        
        if i < args.count and args.delay > 0:
            time.sleep(args.delay)
            
    # Calculate stats
    min_lat, max_lat, avg_lat, med_lat, std_lat = calculate_stats(latencies)
    
    print("\n" + "=" * 50)
    print(f"{COLORS['bold']}Latency & Response Summary:{COLORS['reset']}")
    print(f"  Total Requests:   {args.count}")
    print(f"  Successful Runs:  {len(latencies)}")
    print(f"  Network Failures: {failures}")
    print("")
    
    print(f"{COLORS['bold']}Status Code Frequencies:{COLORS['reset']}")
    for code, freq in status_codes.items():
        percentage = (freq / args.count) * 100
        color = COLORS["green"] if isinstance(code, int) and 200 <= code < 400 else COLORS["red"]
        print(f"  - Status {color}{code}{COLORS['reset']}: {freq} ({percentage:.1f}%)")
    print("")
    
    if latencies:
        print(f"{COLORS['bold']}Latency Statistics:{COLORS['reset']}")
        print(f"  Minimum: {COLORS['green']}{min_lat*1000:8.2f} ms{COLORS['reset']}")
        print(f"  Maximum: {COLORS['red']}{max_lat*1000:8.2f} ms{COLORS['reset']}")
        print(f"  Average: {COLORS['yellow']}{avg_lat*1000:8.2f} ms{COLORS['reset']}")
        print(f"  Median:  {med_lat*1000:8.2f} ms")
        print(f"  StdDev:  {std_lat*1000:8.2f} ms")
        
        draw_histogram(latencies)

if __name__ == "__main__":
    main()
