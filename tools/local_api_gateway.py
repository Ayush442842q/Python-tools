#!/usr/bin/env python3
"""
Local HTTP API Gateway & Reverse Proxy - Route requests to multiple local/remote backend services.

This tool runs a lightweight HTTP reverse proxy gateway. It matches incoming URL path 
prefixes to configure target backends, forwards request methods, headers, and bodies,
and returns the backend responses. It also includes rate limiting (per client IP)
and real-time colorized console metrics (status codes, latencies, and routing logs).

Usage:
    python tools/local_api_gateway.py --route /api=http://localhost:8000 --route /static=http://localhost:5000 --port 9000

Example:
    python tools/local_api_gateway.py -r /api=http://localhost:8000 -r /=http://localhost:3000 -p 9000 --rate-limit 10
"""

import argparse
import sys
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Tuple
from collections import defaultdict

# Simple rate limiter using token bucket algorithm
class TokenBucket:
    def __init__(self, capacity: float, fill_rate: float):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_update = time.time()

    def consume(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class GatewayRequestHandler(BaseHTTPRequestHandler):
    routes: List[Tuple[str, str]] = []  # List of (path_prefix, target_base_url)
    rate_limit: float = 0.0             # 0 means disabled, otherwise max requests per second
    ip_buckets: Dict[str, TokenBucket] = {}
    
    # ANSI color codes for logs
    COLOR_GREEN = "\033[92m"
    COLOR_YELLOW = "\033[93m"
    COLOR_RED = "\033[91m"
    COLOR_BLUE = "\033[94m"
    COLOR_RESET = "\033[0m"

    def log_message(self, format: str, *args: Any) -> None:
        # Override to suppress default logs, as we print custom structured logs
        pass

    def check_rate_limit(self) -> bool:
        """Evaluate rate limiting for client IP."""
        if self.rate_limit <= 0:
            return True
        
        client_ip = self.client_address[0]
        if client_ip not in self.ip_buckets:
            # Capacity equal to rate_limit, fill rate equal to rate_limit per second
            self.ip_buckets[client_ip] = TokenBucket(self.rate_limit, self.rate_limit)
        
        return self.ip_buckets[client_ip].consume()

    def get_target_url(self) -> Tuple[str, str, str]:
        """Find the matching backend for the current request path."""
        # Sort routes by path length descending to match the most specific route first
        sorted_routes = sorted(self.routes, key=lambda x: len(x[0]), reverse=True)
        
        for prefix, target in sorted_routes:
            if self.path.startswith(prefix):
                # Calculate sub-path, e.g., if prefix is /api and path is /api/users, sub-path is /users
                sub_path = self.path[len(prefix):]
                # Ensure correct joining slash
                if not sub_path.startswith('/') and sub_path:
                    sub_path = '/' + sub_path
                
                # Clean target URL (remove trailing slash)
                clean_target = target.rstrip('/')
                target_url = clean_target + sub_path
                return prefix, clean_target, target_url
                
        return "", "", ""

    def handle_proxy(self):
        start_time = time.time()
        client_ip = self.client_address[0]

        # 1. Rate Limiting Check
        if not self.check_rate_limit():
            latency = (time.time() - start_time) * 1000
            self.send_error_response(429, "Too Many Requests - Rate limit exceeded")
            self.print_log(client_ip, self.command, self.path, "RATE_LIMIT", 429, latency)
            return

        # 2. Path Routing Check
        prefix, clean_target, target_url = self.get_target_url()
        if not target_url:
            latency = (time.time() - start_time) * 1000
            self.send_error_response(502, "Bad Gateway - No route matched for this path")
            self.print_log(client_ip, self.command, self.path, "NO_ROUTE", 502, latency)
            return

        # 3. Read request body if present
        content_length = int(self.headers.get('Content-Length', 0))
        req_body = self.rfile.read(content_length) if content_length > 0 else None

        # 4. Prepare request headers to forward
        headers = {}
        for key, val in self.headers.items():
            # Skip Hop-by-Hop headers that shouldn't be forwarded by a proxy
            if key.lower() in ('connection', 'keep-alive', 'proxy-authenticate', 
                               'proxy-authorization', 'te', 'trailers', 
                               'transfer-encoding', 'upgrade', 'host'):
                continue
            headers[key] = val

        # Add proxy tracking headers
        headers['X-Forwarded-For'] = client_ip
        headers['X-Forwarded-Host'] = self.headers.get('Host', '')
        headers['X-Forwarded-Proto'] = 'http'

        # 5. Execute proxy request
        req = urllib.request.Request(
            url=target_url,
            data=req_body,
            headers=headers,
            method=self.command
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                # Read response headers and body
                resp_body = response.read()
                resp_headers = response.info()
                
                # Send response status
                self.send_response(response.status)
                
                # Forward response headers
                for key, val in resp_headers.items():
                    if key.lower() in ('transfer-encoding', 'connection'):
                        continue
                    self.send_header(key, val)
                self.end_headers()
                
                # Write body
                self.wfile.write(resp_body)
                
                latency = (time.time() - start_time) * 1000
                self.print_log(client_ip, self.command, self.path, clean_target, response.status, latency)

        except urllib.error.HTTPError as e:
            # Target backend returned HTTP error (3xx, 4xx, 5xx)
            try:
                resp_body = e.read()
                self.send_response(e.code)
                for key, val in e.headers.items():
                    if key.lower() in ('transfer-encoding', 'connection'):
                        continue
                    self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp_body)
            except Exception:
                self.send_error_response(e.code, str(e))
                
            latency = (time.time() - start_time) * 1000
            self.print_log(client_ip, self.command, self.path, clean_target, e.code, latency)

        except urllib.error.URLError as e:
            # Failed to reach backend (connection refused, timeout, dns, etc.)
            latency = (time.time() - start_time) * 1000
            self.send_error_response(504, f"Gateway Timeout - Failed to connect to backend: {e.reason}")
            self.print_log(client_ip, self.command, self.path, f"ERR: {clean_target}", 504, latency)

        except Exception as e:
            # Internal server error
            latency = (time.time() - start_time) * 1000
            self.send_error_response(500, f"Internal Gateway Error: {str(e)}")
            self.print_log(client_ip, self.command, self.path, "GATEWAY_ERROR", 500, latency)

    def do_GET(self):
        self.handle_proxy()

    def do_POST(self):
        self.handle_proxy()

    def do_PUT(self):
        self.handle_proxy()

    def do_DELETE(self):
        self.handle_proxy()

    def do_PATCH(self):
        self.handle_proxy()

    def send_error_response(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        err_json = f'{{"status": "error", "code": {code}, "message": "{message}"}}'
        self.wfile.write(err_json.encode('utf-8'))

    def print_log(self, ip: str, method: str, path: str, target: str, status: int, latency_ms: float):
        """Print a color-coded log line to stdout."""
        # Status code color selection
        if status < 300:
            color = self.COLOR_GREEN
        elif status < 400:
            color = self.COLOR_BLUE
        elif status < 500:
            color = self.COLOR_YELLOW
        else:
            color = self.COLOR_RED

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = (
            f"[{timestamp}] {self.COLOR_BLUE}{ip}{self.COLOR_RESET} "
            f"| {method} {path} "
            f"-> {self.COLOR_BLUE}{target}{self.COLOR_RESET} "
            f"| {color}{status}{self.COLOR_RESET} "
            f"| {latency_ms:.1f}ms\n"
        )
        sys.stdout.write(log_line)
        sys.stdout.flush()


def parse_route(route_str: str) -> Tuple[str, str]:
    """Parse key=value route definitions."""
    if '=' not in route_str:
        raise argparse.ArgumentTypeError(f"Route must be in format 'prefix=url', got '{route_str}'")
    prefix, url = route_str.split('=', 1)
    if not prefix.startswith('/'):
        prefix = '/' + prefix
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    return prefix, url


def main():
    parser = argparse.ArgumentParser(description="Start a local HTTP API Gateway & Reverse Proxy.")
    parser.add_argument(
        "-r", "--route", 
        action="append", 
        type=parse_route,
        required=True,
        help="Routing rule in format: /path=http://backend_url (e.g. /api=http://localhost:8080)"
    )
    parser.add_argument("-p", "--port", type=int, default=9000, help="Port to run gateway on (default: 9000)")
    parser.add_argument("--host", default="0.0.0.0", help="Binding address (default: 0.0.0.0)")
    parser.add_argument("--rate-limit", type=float, default=0.0, help="Max requests per second per IP (default: 0 = disabled)")
    
    args = parser.parse_args()

    GatewayRequestHandler.routes = args.route
    GatewayRequestHandler.rate_limit = args.rate_limit

    server = HTTPServer((args.host, args.port), GatewayRequestHandler)
    
    print("=" * 60)
    print("           LOCAL HTTP API GATEWAY & REVERSE PROXY")
    print("=" * 60)
    print(f"Gateway Server listening on http://{'localhost' if args.host == '0.0.0.0' else args.host}:{args.port}")
    print("Routing configuration:")
    for prefix, target in args.route:
        print(f"  {prefix}  ===>  {target}")
    if args.rate_limit > 0:
        print(f"Rate limiting active: max {args.rate_limit} req/sec per client IP")
    else:
        print("Rate limiting: Disabled")
    print("-" * 60)
    print("Logs format: [Time] Client_IP | Method Path -> Routed_Target | Status | Latency")
    print("-" * 60)
    print("Press Ctrl+C to terminate.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down gateway...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
