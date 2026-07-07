#!/usr/bin/env python3
"""
HTTP Connection Pool & Keep-Alive Latency Analyzer

Measures and visualizes the performance benefits of HTTP Keep-Alive (connection reuse)
against creating a new TCP/TLS socket connection for every sequential request.

This tool runs two test groups:
1. No Connection Reuse: Closes the connection and creates a new socket/handshake for each request.
2. Connection Reuse: Reuses the same socket/connection channel across all requests (Keep-Alive).

It outputs latency statistics and prints a comparative ASCII bar chart.

Usage:
    python tools/http_connection_pool_analyzer.py https://httpbin.org/status/200 --count 10
"""

import os
import sys
import time
import argparse
import urllib.parse
import http.client
from typing import Dict, List, Tuple, Any

# Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

USE_COLOR = supports_color()

def colorize(text: str, color_code: str) -> str:
    if USE_COLOR:
        return f"{color_code}{text}{COLOR_RESET}"
    return text

def parse_url(url_str: str) -> Tuple[str, str, int, str]:
    """Parses URL into scheme, host, port, and path/query."""
    if not url_str.startswith(('http://', 'https://')):
        url_str = 'http://' + url_str
    
    parsed = urllib.parse.urlparse(url_str)
    scheme = parsed.scheme
    host = parsed.hostname or ''
    port = parsed.port
    
    if not port:
        port = 443 if scheme == 'https' else 80
        
    path = parsed.path
    if not path:
        path = '/'
    if parsed.query:
        path += '?' + parsed.query
        
    return scheme, host, port, path

def run_test_no_reuse(scheme: str, host: str, port: int, path: str, count: int) -> List[float]:
    """Runs sequential requests creating a new connection each time."""
    latencies = []
    
    for i in range(count):
        start = time.perf_counter()
        conn = None
        try:
            if scheme == 'https':
                conn = http.client.HTTPSConnection(host, port, timeout=10)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=10)
                
            conn.request("GET", path, headers={"Connection": "close"})
            resp = conn.getresponse()
            resp.read() # Consume body
            latencies.append((time.perf_counter() - start) * 1000.0)
        except Exception as e:
            print(colorize(f"Request {i+1} failed: {e}", COLOR_RED), file=sys.stderr)
        finally:
            if conn:
                conn.close()
                
    return latencies

def run_test_with_reuse(scheme: str, host: str, port: int, path: str, count: int) -> List[float]:
    """Runs sequential requests reusing the same connection."""
    latencies = []
    conn = None
    
    try:
        if scheme == 'https':
            conn = http.client.HTTPSConnection(host, port, timeout=10)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=10)
            
        for i in range(count):
            start = time.perf_counter()
            # Send Keep-Alive headers
            conn.request("GET", path, headers={"Connection": "keep-alive"})
            resp = conn.getresponse()
            resp.read() # Consume body to make connection reusable
            latencies.append((time.perf_counter() - start) * 1000.0)
    except Exception as e:
        print(colorize(f"Keep-Alive Request failed: {e}", COLOR_RED), file=sys.stderr)
    finally:
        if conn:
            conn.close()
            
    return latencies

def generate_ascii_bar(val: float, max_val: float, width: int = 40) -> str:
    """Generates an ASCII bar matching the ratio of val to max_val."""
    if max_val == 0:
        return ""
    fill_len = int((val / max_val) * width)
    fill_len = max(1, min(fill_len, width))
    return "█" * fill_len + "░" * (width - fill_len)

def print_stats(name: str, latencies: List[float], max_all: float):
    if not latencies:
        print(f"{name}: No successful requests.")
        return
        
    avg = sum(latencies) / len(latencies)
    minimum = min(latencies)
    maximum = max(latencies)
    
    print(colorize(f"--- {name} ---", COLOR_BOLD))
    print(f"  Average Latency : {avg:.2f} ms")
    print(f"  Min/Max Latency : {minimum:.2f} ms / {maximum:.2f} ms")
    
    # Render individual request bars
    print("  Timeline:")
    for idx, l in enumerate(latencies):
        bar = generate_ascii_bar(l, max_all)
        print(f"    Req #{idx+1:<2} ({l:6.1f} ms) | {bar}")

def main():
    parser = argparse.ArgumentParser(description="Analyze performance difference between HTTP connection reuse and recreation.")
    parser.add_argument("url", help="Target HTTP/HTTPS URL to test.")
    parser.add_argument("-c", "--count", type=int, default=5, help="Number of sequential requests to perform.")
    
    args = parser.parse_args()
    
    try:
        scheme, host, port, path = parse_url(args.url)
    except Exception as e:
        print(colorize(f"Failed to parse URL: {e}", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    print(colorize(f"=== HTTP Keep-Alive & Connection Reuse Analyzer ===", COLOR_BOLD + COLOR_BLUE))
    print(f"Target Host : {host}:{port}")
    print(f"Target Path : {path}")
    print(f"Iterations  : {args.count} requests per mode\n")

    # Warm-up request to DNS cache / establish basic routing
    print("Performing warm-up connection...")
    try:
        warmup_conn = http.client.HTTPSConnection(host, port) if scheme == 'https' else http.client.HTTPConnection(host, port)
        warmup_conn.request("GET", path)
        warmup_conn.getresponse().read()
        warmup_conn.close()
    except Exception as e:
        print(colorize(f"Warm-up failed: {e}. Target may be unreachable.", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    print("Running Mode 1: No Connection Reuse (Closing socket after each request)...")
    no_reuse_lats = run_test_no_reuse(scheme, host, port, path, args.count)
    
    print("Running Mode 2: Connection Reuse (Keep-Alive)...")
    reuse_lats = run_test_with_reuse(scheme, host, port, path, args.count)

    print("\n" + "=" * 60)
    print(colorize("RESULTS SUMMARY", COLOR_BOLD + COLOR_CYAN))
    print("=" * 60)

    all_lats = no_reuse_lats + reuse_lats
    max_lat_all = max(all_lats) if all_lats else 1.0

    print_stats("No Connection Reuse (New Socket/Handshake)", no_reuse_lats, max_lat_all)
    print()
    print_stats("Connection Reuse (Keep-Alive Pool)", reuse_lats, max_lat_all)

    # Summary performance metric
    if no_reuse_lats and reuse_lats:
        avg_no_reuse = sum(no_reuse_lats) / len(no_reuse_lats)
        avg_reuse = sum(reuse_lats) / len(reuse_lats)
        
        diff = avg_no_reuse - avg_reuse
        if diff > 0:
            percentage = (diff / avg_no_reuse) * 100
            print("\n" + "=" * 60)
            msg = f"Connection reuse is {percentage:.1f}% faster! (Saved average of {diff:.2f} ms per request)"
            print(colorize(msg, COLOR_GREEN + COLOR_BOLD))
            print("Explanation: Reusing connections avoids repeated TCP 3-way handshakes and TLS negotiations.")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("Both modes performed similarly. This can happen on local networks or with hyper-low latency endpoints.")
            print("=" * 60)

if __name__ == "__main__":
    main()
