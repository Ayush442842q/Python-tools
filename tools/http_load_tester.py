#!/usr/bin/env python3
"""
HTTP Load Tester - A multi-threaded CLI tool to benchmark web servers.

Features:
- Benchmarks HTTP/HTTPS URLs with concurrent requests.
- Calculates detailed metrics (RPS, latency percentiles, error rates).
- Zero external dependencies (uses standard library urllib and threading).
"""

import argparse
import http.client
import json
import ssl
import sys
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
import threading
from queue import Queue

# Terminal coloring helper
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @classmethod
    def disable(cls):
        cls.HEADER = ''
        cls.BLUE = ''
        cls.GREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''

# Global results list
results = []
results_lock = threading.Lock()

def worker(url, method, headers, data, timeout, ssl_context, queue, progress_callback):
    """Worker thread target to send requests."""
    while not queue.empty():
        try:
            queue.get_nowait()
        except Exception:
            break

        start_time = time.perf_counter()
        status = 0
        error = None
        
        try:
            req = urllib.request.Request(url, method=method)
            for k, v in headers.items():
                req.add_header(k, v)
            
            # Send request
            with urllib.request.urlopen(req, data=data, timeout=timeout, context=ssl_context) as response:
                status = response.status
                # Read body to fully complete response download
                response.read()
        except urllib.error.HTTPError as e:
            status = e.code
        except urllib.error.URLError as e:
            error = str(e.reason)
        except Exception as e:
            error = str(e)
        
        end_time = time.perf_counter()
        latency = (end_time - start_time) * 1000 # in milliseconds
        
        with results_lock:
            results.append({
                'latency': latency,
                'status': status,
                'error': error
            })
        
        progress_callback()
        queue.task_done()

def parse_headers(header_strings):
    """Parse custom headers passed as list of 'Key: Value' strings."""
    headers = {}
    if not header_strings:
        return headers
    for h in header_strings:
        if ':' in h:
            k, v = h.split(':', 1)
            headers[k.strip()] = v.strip()
        else:
            print(f"{Colors.WARNING}Warning: Ignoring malformed header '{h}' (format should be 'Key: Value'){Colors.ENDC}")
    return headers

def print_stats(total_time, total_requests, concurrency):
    """Calculate and print statistics."""
    with results_lock:
        local_results = list(results)
    
    if not local_results:
        print(f"\n{Colors.FAIL}Error: No requests were completed.{Colors.ENDC}")
        return

    success_count = sum(1 for r in local_results if 200 <= r['status'] < 400)
    failed_count = sum(1 for r in local_results if r['status'] >= 400 or r['status'] == 0)
    
    latencies = sorted([r['latency'] for r in local_results])
    avg_latency = sum(latencies) / len(latencies)
    min_latency = latencies[0]
    max_latency = latencies[-1]
    
    # Percentiles
    def get_percentile(sorted_list, pct):
        if not sorted_list:
            return 0
        idx = int(len(sorted_list) * pct)
        idx = min(idx, len(sorted_list) - 1)
        return sorted_list[idx]
    
    p50 = get_percentile(latencies, 0.50)
    p90 = get_percentile(latencies, 0.90)
    p95 = get_percentile(latencies, 0.95)
    p99 = get_percentile(latencies, 0.99)
    
    # Status codes and errors mapping
    status_counts = {}
    errors = {}
    for r in local_results:
        if r['status'] > 0:
            status_counts[r['status']] = status_counts.get(r['status'], 0) + 1
        if r['error']:
            errors[r['error']] = errors.get(r['error'], 0) + 1

    rps = total_requests / total_time
    
    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}{Colors.HEADER}Benchmark Results{Colors.ENDC}")
    print("=" * 50)
    print(f"Total Requests:        {total_requests}")
    print(f"Concurrency level:     {concurrency}")
    print(f"Time Taken for Tests:  {total_time:.3f} seconds")
    print(f"Requests per Second:   {Colors.GREEN if rps > 10 else Colors.BLUE}{rps:.2f} [#/sec]{Colors.ENDC}")
    print(f"Successful Requests:   {Colors.GREEN}{success_count}{Colors.ENDC}")
    print(f"Failed Requests:       {Colors.FAIL if failed_count > 0 else Colors.GREEN}{failed_count}{Colors.ENDC}")
    print("-" * 50)
    print(f"{Colors.BOLD}Latency Profile (ms):{Colors.ENDC}")
    print(f"  Average:             {avg_latency:.2f} ms")
    print(f"  Min:                 {min_latency:.2f} ms")
    print(f"  50% (Median):        {p50:.2f} ms")
    print(f"  90%:                 {p90:.2f} ms")
    print(f"  95%:                 {p95:.2f} ms")
    print(f"  99%:                 {p99:.2f} ms")
    print(f"  Max:                 {max_latency:.2f} ms")
    print("-" * 50)
    print(f"{Colors.BOLD}HTTP Status Codes Distribution:{Colors.ENDC}")
    for code, count in sorted(status_counts.items()):
        status_color = Colors.GREEN if 200 <= code < 400 else Colors.FAIL
        print(f"  Status {status_color}{code}{Colors.ENDC}:            {count} requests")
    
    if errors:
        print("-" * 50)
        print(f"{Colors.BOLD}Errors Detail:{Colors.ENDC}")
        for err_msg, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            print(f"  {Colors.FAIL}{err_msg}{Colors.ENDC}: {count} occurrences")
    print("=" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="HTTP Load Tester - A lightweight, zero-dependency benchmarking tool")
    parser.add_argument("url", help="Target URL to test (e.g. http://example.com/)")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Total number of requests to perform (default: 100)")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Number of concurrent requests to make (default: 10)")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST", "PUT", "DELETE", "HEAD"], help="HTTP Method to use (default: GET)")
    parser.add_argument("-d", "--data", help="Data to send in request body (for POST/PUT)")
    parser.add_argument("-H", "--header", action="append", help="Add custom headers (e.g. -H 'Authorization: Bearer token')")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10)")
    parser.add_argument("-k", "--insecure", action="store_true", help="Allow insecure/unverified SSL connections")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")

    args = parser.parse_args()

    if args.no_color or sys.platform == 'win32':
        # Disable colors on Windows by default unless terminal supports it
        # Try enabling vt100 processing on Windows first
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            if args.no_color or not sys.stdout.isatty():
                Colors.disable()

    # Basic validations
    if args.concurrency > args.requests:
        print(f"{Colors.WARNING}Warning: Concurrency level cannot exceed total requests. Setting concurrency to {args.requests}.{Colors.ENDC}")
        args.concurrency = args.requests

    if args.concurrency <= 0 or args.requests <= 0:
        print(f"{Colors.FAIL}Error: Requests and concurrency must be positive integers.{Colors.ENDC}")
        return 1

    # Validate URL
    parsed_url = urlparse(args.url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print(f"{Colors.FAIL}Error: Invalid URL. URL must contain scheme (http/https) and domain (e.g. http://example.com/){Colors.ENDC}")
        return 1

    # Prepare request payload
    req_data = None
    if args.data:
        req_data = args.data.encode('utf-8')

    # Parse headers
    headers = parse_headers(args.header)
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'HTTP-Load-Tester/1.0'
    if req_data and 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

    # Configure SSL
    ssl_context = None
    if parsed_url.scheme == 'https':
        if args.insecure:
            ssl_context = ssl._create_unverified_context()
        else:
            ssl_context = ssl.create_default_context()

    print(f"Benchmarking {args.url} (concurrency={args.concurrency}, requests={args.requests})...")

    # Queue of requests
    queue = Queue()
    for i in range(args.requests):
        queue.put(i)

    # Progress tracker
    completed = 0
    progress_lock = threading.Lock()
    
    def update_progress():
        nonlocal completed
        with progress_lock:
            completed += 1
            # Draw simple progress bar
            pct = int((completed / args.requests) * 100)
            bar_len = 30
            filled_len = int(bar_len * completed // args.requests)
            bar = '=' * filled_len + '-' * (bar_len - filled_len)
            sys.stdout.write(f"\rProgress: [{bar}] {pct}% ({completed}/{args.requests})")
            sys.stdout.flush()

    # Start threads
    threads = []
    start_time = time.perf_counter()
    
    for _ in range(args.concurrency):
        t = threading.Thread(
            target=worker, 
            args=(args.url, args.method, headers, req_data, args.timeout, ssl_context, queue, update_progress)
        )
        t.daemon = True
        t.start()
        threads.append(t)

    # Wait for completion
    for t in threads:
        t.join()
        
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    print() # Clear line from progress bar
    print_stats(total_time, args.requests, args.concurrency)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Benchmark interrupted by user. Displaying partial results...{Colors.ENDC}")
        print_stats(0.001, len(results), 0)
        sys.exit(1)
