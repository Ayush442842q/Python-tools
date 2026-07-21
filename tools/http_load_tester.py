#!/usr/bin/env python3
"""
HTTP Load Tester - A lightweight utility to benchmark web servers and APIs.
Measures latency, throughput, success rates, and status code distributions under load.
"""

import argparse
import sys
import time
import urllib.request
import urllib.error
from threading import Thread, Lock
from collections import Counter

# Global metrics collector and lock
metrics = {
    'total_requests': 0,
    'success_requests': 0,
    'failed_requests': 0,
    'latencies': [],
    'status_codes': Counter(),
    'errors': Counter()
}
metrics_lock = Lock()

def send_request(url, method, headers, data, timeout):
    """Sends a single HTTP request and records its metrics."""
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start_time = time.perf_counter()
    status_code = None
    error_msg = None
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
    except urllib.error.HTTPError as e:
        status_code = e.code
    except urllib.error.URLError as e:
        error_msg = str(e.reason)
    except Exception as e:
        error_msg = str(e)
        
    duration = time.perf_counter() - start_time
    
    with metrics_lock:
        metrics['total_requests'] += 1
        if status_code:
            metrics['status_codes'][status_code] += 1
            # Classify 2xx as success
            if 200 <= status_code < 300:
                metrics['success_requests'] += 1
                metrics['latencies'].append(duration)
            else:
                metrics['failed_requests'] += 1
        else:
            metrics['failed_requests'] += 1
            metrics['errors'][error_msg or "Unknown network error"] += 1

def worker(url, method, headers, data, timeout, requests_per_thread):
    """Worker thread target to execute a slice of the workload."""
    for _ in range(requests_per_thread):
        send_request(url, method, headers, data, timeout)

def format_bar_chart(counter, width=40):
    """Generates a text-based horizontal bar chart for status codes/errors."""
    if not counter:
        return "  No data available"
    
    max_val = max(counter.values())
    lines = []
    for key, count in sorted(counter.items()):
        bar_len = int((count / max_val) * width) if max_val > 0 else 0
        bar = "#" * bar_len + "-" * (width - bar_len)
        lines.append(f"  {str(key):<15} : {count:<5} [{bar}]")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="HTTP Load Tester: A lightweight, standalone web benchmarking tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/http_load_tester.py http://example.com/
  python tools/http_load_tester.py https://api.github.com/ -n 50 -c 10
  python tools/http_load_tester.py http://httpbin.org/post -m POST -d '{"name":"test"}' -H "Content-Type: application/json"
"""
    )
    
    parser.add_argument("url", help="Target URL to test (e.g. http://example.com)")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Total number of requests to perform (default: 100)")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Number of multiple concurrent requests to make (default: 10)")
    parser.add_argument("-m", "--method", default="GET", help="HTTP Method (GET, POST, PUT, DELETE, etc.)")
    parser.add_argument("-d", "--data", help="Data to send in request body (for POST/PUT requests)")
    parser.add_argument("-H", "--header", action="append", help="Custom headers (e.g. -H 'Content-Type: json' -H 'Auth: secret')")
    parser.add_argument("-t", "--timeout", type=float, default=5.0, help="Timeout in seconds for each request (default: 5.0)")
    
    args = parser.parse_args()
    
    if args.concurrency > args.requests:
        print(f"[*] Adjusting concurrency to total request count ({args.requests})")
        args.concurrency = args.requests

    # Format payload
    payload = args.data.encode('utf-8') if args.data else None
    
    # Parse custom headers
    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()
            else:
                print(f"[!] Warning: Ignoring malformed header '{h}' (format should be 'Name: Value')")

    # Add default User-Agent if not specified
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'HTTP-Load-Tester/1.0'

    print("=" * 60)
    print(f"Benchmarking: {args.url}")
    print(f"Method:       {args.method}")
    print(f"Requests:     {args.requests} (distributed over {args.concurrency} concurrent threads)")
    print(f"Timeout:      {args.timeout}s")
    print("=" * 60)
    print("[*] Load test started...")
    
    start_time = time.perf_counter()
    
    # Spawn threads
    threads = []
    req_per_thread = args.requests // args.concurrency
    remainder = args.requests % args.concurrency
    
    for i in range(args.concurrency):
        # Distribute remaining requests across first few threads
        t_reqs = req_per_thread + (1 if i < remainder else 0)
        t = Thread(target=worker, args=(args.url, args.method, headers, payload, args.timeout, t_reqs))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    total_time = time.perf_counter() - start_time
    
    # Compute stats
    req_per_sec = metrics['total_requests'] / total_time if total_time > 0 else 0
    success_rate = (metrics['success_requests'] / metrics['total_requests']) * 100 if metrics['total_requests'] > 0 else 0
    
    # Sort latencies
    latencies = sorted(metrics['latencies'])
    min_lat = latencies[0] * 1000 if latencies else 0
    max_lat = latencies[-1] * 1000 if latencies else 0
    avg_lat = (sum(latencies) / len(latencies)) * 1000 if latencies else 0
    
    def get_percentile(p):
        if not latencies:
            return 0
        idx = int(len(latencies) * p)
        return latencies[min(idx, len(latencies) - 1)] * 1000

    p50 = get_percentile(0.50)
    p90 = get_percentile(0.90)
    p99 = get_percentile(0.99)
    
    print("[+] Test completed.")
    print("=" * 60)
    print("RESULTS & STATISTICS")
    print("=" * 60)
    print(f"Elapsed Time:         {total_time:.3f} seconds")
    print(f"Total Requests:       {metrics['total_requests']}")
    print(f"Successful Requests:  {metrics['success_requests']}")
    print(f"Failed Requests:      {metrics['failed_requests']}")
    print(f"Success Rate:         {success_rate:.2f}%")
    print(f"Throughput:           {req_per_sec:.2f} req/sec")
    print("-" * 60)
    print("LATENCY STATISTICS (Successful Requests Only)")
    print(f"  Minimum:            {min_lat:.2f} ms")
    print(f"  Average:            {avg_lat:.2f} ms")
    print(f"  Maximum:            {max_lat:.2f} ms")
    print(f"  50th Percentile:    {p50:.2f} ms (median)")
    print(f"  90th Percentile:    {p90:.2f} ms")
    print(f"  99th Percentile:    {p99:.2f} ms")
    print("-" * 60)
    print("STATUS CODE DISTRIBUTION")
    print(format_bar_chart(metrics['status_codes']))
    
    if metrics['errors']:
        print("-" * 60)
        print("CONNECTION/NETWORK ERRORS")
        print(format_bar_chart(metrics['errors']))
    print("=" * 60)

if __name__ == "__main__":
    main()
