#!/usr/bin/env python3
"""
HTTP Traffic Speed Shaper & Rate Limiter Proxy
A lightweight HTTP/HTTPS proxy server designed to simulate network latency,
bandwidth throttling, and HTTP 429 Rate Limiting behavior for API/web testing.
"""

import os
import sys
import time
import argparse
import socket
import select
import threading
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import http.client

class RateLimiterProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        # Clean console log output
        sys.stdout.write(f"[Proxy] {format % args}\n")
        sys.stdout.flush()

    def apply_latency(self):
        """Simulate latency by sleeping before handling the request."""
        if self.server.latency > 0:
            time.sleep(self.server.latency / 1000.0)

    def throttle_connection(self, source_sock, dest_sock):
        """Tunnels data between two sockets, applying bandwidth limits."""
        # Convert KB/s to Bytes/s
        bytes_per_sec = self.server.speed_kbps * 1024 if self.server.speed_kbps > 0 else 0
        chunk_size = 4096
        
        # Calculate time needed for one chunk to maintain speed
        chunk_delay = chunk_size / bytes_per_sec if bytes_per_sec > 0 else 0

        inputs = [source_sock, dest_sock]
        try:
            while self.server.running:
                readable, _, exceptional = select.select(inputs, [], inputs, 1.0)
                if exceptional:
                    break
                
                for sock in readable:
                    data = sock.recv(chunk_size)
                    if not data:
                        return
                    
                    # Determine destination
                    out_sock = dest_sock if sock is source_sock else source_sock
                    out_sock.sendall(data)
                    
                    # Apply speed throttle delay if requested
                    if chunk_delay > 0:
                        time.sleep(chunk_delay)
        except Exception:
            pass

    def check_rate_limit(self, path):
        """Checks if the request path matches rate-limit mock filters."""
        for pattern, status_code in self.server.rate_limit_rules:
            if re.search(pattern, path):
                return status_code
        return None

    def do_CONNECT(self):
        """Handle HTTPS tunneling (CONNECT method)."""
        self.apply_latency()
        
        # Check rate-limit matching before connecting
        # The path for CONNECT is 'host:port'
        limit_code = self.check_rate_limit(self.path)
        if limit_code:
            self.send_error_response(limit_code)
            return

        # Extract destination host and port
        try:
            host, port_str = self.path.split(":")
            port = int(port_str)
        except ValueError:
            self.send_error(400, "Bad Request: Invalid CONNECT path")
            return

        # Establish connection to destination server
        try:
            dest_sock = socket.create_connection((host, port), timeout=10)
        except Exception as e:
            self.send_error(502, f"Bad Gateway: Connection failed ({e})")
            return

        # Reply 200 Connection Established to client
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.wfile.flush()

        # Start tunneling thread
        client_sock = self.connection
        self.throttle_connection(client_sock, dest_sock)
        dest_sock.close()

    def send_error_response(self, status_code):
        """Sends a mock rate-limit error response (e.g. 429 Too Many Requests)."""
        status_messages = {
            429: "Too Many Requests",
            503: "Service Unavailable",
            408: "Request Timeout"
        }
        msg = status_messages.get(status_code, "Rate Limited")
        
        response_body = f"<html><body><h1>{status_code} {msg}</h1><p>Simulated by Rate Limiter Proxy.</p></body></html>"
        encoded_body = response_body.encode('utf-8')

        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded_body)))
        self.send_header('Retry-After', '10')  # Standard rate-limiting headers
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(encoded_body)
        self.wfile.flush()
        print(f"Mocked rate-limit response: HTTP {status_code} for path {self.path}")

    def handle_http_request(self, method):
        """Forwards HTTP requests (GET, POST, etc.) applying speed and latency shaping."""
        self.apply_latency()
        
        limit_code = self.check_rate_limit(self.path)
        if limit_code:
            self.send_error_response(limit_code)
            return

        # Parse request URL
        parsed_url = urlparse(self.path)
        if not parsed_url.netloc:
            # If path doesn't contain netloc, fallback to Host header
            host = self.headers.get('Host')
            path = self.path
        else:
            host = parsed_url.netloc
            path = parsed_url.path
            if parsed_url.query:
                path += f"?{parsed_url.query}"

        # Clean host/port
        if ":" in host:
            hostname, port_str = host.split(":")
            port = int(port_str)
        else:
            hostname = host
            port = 80

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Build clean forwarding headers
        headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ('connection', 'keep-alive', 'proxy-connection'):
                headers[key] = val
        headers['Connection'] = 'close'

        # Send HTTP request to destination server
        conn = None
        try:
            conn = http.client.HTTPConnection(hostname, port, timeout=10)
            conn.request(method, path, body, headers)
            res = conn.getresponse()
            
            # Send response headers back to client
            self.send_response(res.status)
            for header_name, header_val in res.getheaders():
                if header_name.lower() not in ('connection', 'keep-alive', 'transfer-encoding'):
                    self.send_header(header_name, header_val)
            self.send_header('Connection', 'close')
            self.end_headers()

            # Read and write response data, throttling speeds
            bytes_per_sec = self.server.speed_kbps * 1024 if self.server.speed_kbps > 0 else 0
            chunk_size = 4096
            chunk_delay = chunk_size / bytes_per_sec if bytes_per_sec > 0 else 0

            while True:
                chunk = res.read(chunk_size)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                if chunk_delay > 0:
                    time.sleep(chunk_delay)
                    
        except Exception as e:
            self.send_error(502, f"Bad Gateway: Forwarding failed ({e})")
        finally:
            if conn:
                conn.close()

    def do_GET(self):
        self.handle_http_request("GET")

    def do_POST(self):
        self.handle_http_request("POST")

    def do_PUT(self):
        self.handle_http_request("PUT")

    def do_DELETE(self):
        self.handle_http_request("DELETE")

    def do_PATCH(self):
        self.handle_http_request("PATCH")

    def do_OPTIONS(self):
        self.handle_http_request("OPTIONS")

    def do_HEAD(self):
        self.handle_http_request("HEAD")


class ThreadedHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, latency=0, speed_kbps=0, rate_limit_rules=None):
        super().__init__(server_address, RequestHandlerClass)
        self.latency = latency
        self.speed_kbps = speed_kbps
        self.rate_limit_rules = rate_limit_rules or []
        self.running = True

    def process_request(self, request, client_address):
        """Processes request in a separate thread to handle concurrent connection throttling."""
        t = threading.Thread(target=self.process_request_thread, args=(request, client_address), daemon=True)
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            pass
        finally:
            self.shutdown_request(request)


def parse_rate_limits(limits_arg):
    """Parses rate limit rules formatted as 'regex:status_code,regex2:status_code'."""
    rules = []
    if not limits_arg:
        return rules
    for item in limits_arg.split(','):
        if ':' in item:
            try:
                pattern, code = item.rsplit(':', 1)
                rules.append((pattern, int(code)))
            except ValueError:
                print(f"Skipping invalid rate limit rule: {item}")
    return rules

def main():
    parser = argparse.ArgumentParser(description="HTTP Traffic Speed Shaper & Rate Limiter Proxy")
    parser.add_argument('--port', type=int, default=8888, help='Proxy port to listen on (default: 8888)')
    parser.add_argument('--bind', default='127.0.0.1', help='Proxy host to bind to (default: 127.0.0.1)')
    parser.add_argument('--latency', type=int, default=0, help='Add delay to all requests in milliseconds (e.g. 150)')
    parser.add_argument('--speed', type=int, default=0, help='Bandwidth speed limit in KB/s (e.g. 64 for slow mobile connection, 0 for unlimited)')
    parser.add_argument('--rate-limit', help='Comma-separated regex pattern and HTTP status code triggers (e.g. "/api/v2/.*:429,/checkout:503")')

    args = parser.parse_args()

    rate_limit_rules = parse_rate_limits(args.rate_limit)

    print("==================================================")
    print("HTTP Traffic Speed Shaper & Rate Limiter Proxy")
    print(f"Running at http://{args.bind}:{args.port}")
    if args.latency > 0:
        print(f"Simulated Latency: {args.latency} ms")
    if args.speed > 0:
        print(f"Simulated Bandwidth Speed Limit: {args.speed} KB/s")
    if rate_limit_rules:
        print("Rate Limit Rules Active:")
        for pattern, code in rate_limit_rules:
            print(f"  Matches: '{pattern}' -> Return HTTP {code}")
    print("Configure your browser or app proxy to use this server.")
    print("Press Ctrl+C to stop.")
    print("==================================================")

    server = None
    try:
        server = ThreadedHTTPServer((args.bind, args.port), RateLimiterProxyHandler,
                                    latency=args.latency,
                                    speed_kbps=args.speed,
                                    rate_limit_rules=rate_limit_rules)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy server...")
    finally:
        if server:
            server.running = False
            server.server_close()
        print("Proxy stopped.")

if __name__ == '__main__':
    main()
