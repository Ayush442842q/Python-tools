#!/usr/bin/env python3
"""
API Rate Limit Analyzer

A tool to actively probe an API (safely) and analyze rate-limiting headers 
such as X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, and Retry-After.
Calculates bucket capacity, leak rate, reset window, and simulates request load.

Usage:
    python tools/api_rate_limit_analyzer.py <url> [options]
"""

import sys
import time
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from threading import Thread, Lock

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# Common rate limit headers to check
RATE_LIMIT_HEADERS = [
    # Standard / common headers
    "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset", "ratelimit-remaining",
    "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "x-ratelimit-decay",
    "x-ratelimit-remaining-points", "x-rate-limit-limit", "x-rate-limit-remaining", "x-rate-limit-reset",
    "retry-after", "x-retry-after"
]

class RateLimitInfo:
    def __init__(self):
        self.limit = None
        self.remaining = None
        self.reset_time = None
        self.retry_after = None
        self.custom_headers = {}

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
     ⚙️   API RATE LIMIT PROBER & ANALYZER  ⚙️
========================================================={RESET}
"""
    print(banner)

def parse_headers(headers):
    """Extracts rate-limiting information from HTTP headers."""
    info = RateLimitInfo()
    
    for key, val in headers.items():
        lower_key = key.lower()
        if lower_key in RATE_LIMIT_HEADERS:
            info.custom_headers[key] = val
            
            if "limit" in lower_key:
                try:
                    info.limit = int(val)
                except ValueError:
                    pass
            elif "remaining" in lower_key:
                try:
                    info.remaining = int(val)
                except ValueError:
                    pass
            elif "reset" in lower_key:
                try:
                    # Could be epoch timestamp or seconds remaining
                    info.reset_time = float(val)
                except ValueError:
                    pass
            elif "retry-after" in lower_key:
                try:
                    info.retry_after = int(val)
                except ValueError:
                    pass
                    
    return info

def make_request(url, headers, method="GET", data=None):
    """Sends a single HTTP request and captures headers and status."""
    req = urllib.request.Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
        
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as response:
            latency = time.time() - start_time
            response_headers = dict(response.info())
            return response.status, response_headers, latency, None
    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        response_headers = dict(e.headers)
        return e.code, response_headers, latency, str(e.reason)
    except Exception as e:
        return 0, {}, 0.0, str(e)

def format_reset_time(val):
    """Formats the reset value to human-readable text."""
    if val is None:
        return "Unknown"
    
    # Check if epoch timestamp
    if val > 1700000000:
        remaining = val - time.time()
        time_struct = time.localtime(val)
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time_struct)
        if remaining > 0:
            return f"{time_str} (in {remaining:.1f}s)"
        else:
            return f"{time_str} (Passed/Reset)"
    else:
        return f"{val} seconds"

def main():
    parser = argparse.ArgumentParser(
        description="API Rate Limit Analyzer - Safely probe endpoints to identify rate limit rules.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="Target API URL to analyze")
    parser.add_argument("--method", "-X", default="GET", help="HTTP Method (GET, POST, etc.)")
    parser.add_argument("--header", "-H", action="append", help="HTTP Request Header (e.g. 'Authorization: Bearer token')")
    parser.add_argument("--data", "-d", help="HTTP Request Body Data")
    parser.add_argument("--probe-count", "-p", type=int, default=3, help="Number of probing requests to send sequentially")
    parser.add_argument("--probe-delay", type=float, default=0.5, help="Seconds delay between probes")
    parser.add_argument("--simulate-limit", action="store_true", help="Attempt to hit the rate limit (Warning: May result in temporary IP ban!)")
    
    args = parser.parse_args()
    print_banner()
    
    # Process headers
    req_headers = {"User-Agent": "APIRateLimitAnalyzer/1.0"}
    if args.header:
        for h in args.header:
            if ":" in h:
                k, v = h.split(":", 1)
                req_headers[k.strip()] = v.strip()
                
    post_data = args.data.encode('utf-8') if args.data else None

    print(f"🔗 Target: {BOLD}{args.url}{RESET}")
    print(f"📥 Method: {BOLD}{args.method}{RESET}")
    print(f"🕵️  Probing rate limiting headers...")

    # First sequential probes
    probes = []
    for i in range(args.probe_count):
        if i > 0:
            time.sleep(args.probe_delay)
            
        print(f"   Request {i+1}/{args.probe_count}... ", end="", flush=True)
        status, resp_headers, latency, error = make_request(args.url, req_headers, args.method, post_data)
        
        if status == 0:
            print(f"{RED}Failed: {error}{RESET}")
            continue
            
        rate_info = parse_headers(resp_headers)
        probes.append((status, rate_info, latency))
        
        status_color = GREEN if 200 <= status < 300 else (RED if status == 429 else YELLOW)
        print(f"Status: {status_color}{status}{RESET} | Latency: {latency:.3f}s")

    if not probes:
        print(f"{RED}Error: All probing requests failed.{RESET}")
        return 1

    # Analysis of the last probe
    last_status, last_info, last_latency = probes[-1]
    
    print(f"\n{BOLD}📊 Detected Rate Limiting Headers:{RESET}")
    if not last_info.custom_headers:
        print(f"  {YELLOW}No standard rate limiting headers detected.{RESET}")
        print("  The endpoint might not use rate-limiting headers or uses custom, unmapped headers.")
    else:
        for k, v in last_info.custom_headers.items():
            print(f"  • {BOLD}{k}{RESET}: {v}")

    print(f"\n{BOLD}ℹ️  Rate Limit Summary:{RESET}")
    print(f"  Limit / Capacity  : {GREEN if last_info.limit else YELLOW}{last_info.limit or 'Not Specified'}{RESET}")
    print(f"  Remaining Points  : {GREEN if last_info.remaining else YELLOW}{last_info.remaining or 'Not Specified'}{RESET}")
    print(f"  Reset Info        : {format_reset_time(last_info.reset_time)}")
    if last_info.retry_after is not None:
        print(f"  Retry-After Value : {RED}{last_info.retry_after} seconds{RESET}")

    # Estimate consumption rate
    if len(probes) >= 2 and last_info.remaining is not None:
        first_rem = probes[0][1].remaining
        last_rem = last_info.remaining
        if first_rem is not None and last_rem is not None:
            diff = first_rem - last_rem
            print(f"  Consumed in probe : {diff} points over {len(probes)} requests")

    # Interactive simulation mode (hitting the limit)
    if args.simulate_limit:
        print(f"\n{RED}{BOLD}⚠️ WARNING: Rate limit saturation starting...{RESET}")
        print("This sends rapid requests until a 429 status or depletion is reached.")
        confirm = input("Do you want to proceed? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return 0
            
        print("🛢️ Flooding endpoint to trigger rate limits (max 50 requests)...")
        max_flood = 50
        hit_429 = False
        
        for k in range(max_flood):
            status, resp_headers, latency, error = make_request(args.url, req_headers, args.method, post_data)
            rate_info = parse_headers(resp_headers)
            rem = rate_info.remaining if rate_info.remaining is not None else "N/A"
            
            print(f"   [{k+1}] Status: {status} | Remaining: {rem} | Latency: {latency:.3f}s")
            
            if status == 429:
                hit_429 = True
                print(f"\n{RED}🚨 RATE LIMIT TRIGGERED (HTTP 429)!{RESET}")
                if rate_info.retry_after:
                    print(f"   Server requires waiting: {BOLD}{rate_info.retry_after}s{RESET} before retrying.")
                break
                
            if rate_info.remaining == 0:
                print(f"\n{YELLOW}⚠️  Remaining points reached 0. Expecting rate limiting.{RESET}")
                
            time.sleep(0.05) # fast loop

        if not hit_429:
            print(f"\n{GREEN}Completed flood. Did not hit a 429 error code.{RESET}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
