#!/usr/bin/env python3
"""
HTTP Intercepting & Mocking Proxy Server

A local HTTP proxy server that intercepts outgoing HTTP requests and mocks responses
based on configurable regex patterns (status code, headers, body, delay), while
transparently forwarding non-matching traffic. Supports both Forward Proxy mode
(system proxy) and Reverse Proxy mode (gateway to a specific backend).
"""

import sys
import os
import argparse
import json
import re
import socket
import select
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Global rules list
MOCK_RULES: List[Dict[str, Any]] = []
DEFAULT_TARGET_URL: Optional[str] = None

SAMPLE_RULES = [
    {
        "pattern": r"/api/users/\d+",
        "status": 200,
        "delay": 0.5,
        "headers": {
            "Content-Type": "application/json",
            "X-Mocked-By": "Antigravity-Mock-Proxy"
        },
        "body": {
            "id": 42,
            "name": "John Doe (Mocked)",
            "email": "mock@example.com",
            "role": "Administrator"
        }
    },
    {
        "pattern": r"/api/error-test",
        "status": 500,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {
            "error": "InternalServerError",
            "message": "Simulated proxy error response"
        }
    }
]

def load_rules(rules_path: str) -> None:
    """Loads mocking rules from a JSON file."""
    global MOCK_RULES
    if not os.path.exists(rules_path):
        print(color_text(f"Rules file '{rules_path}' not found. Initializing with sample rules.", COLOR_YELLOW))
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_RULES, f, indent=4)
        MOCK_RULES = SAMPLE_RULES
        return
        
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            MOCK_RULES = json.load(f)
        print(color_text(f"Loaded {len(MOCK_RULES)} mock rule(s) from '{rules_path}'", COLOR_GREEN))
    except Exception as e:
        print(color_text(f"Error loading rules file: {e}", COLOR_RED))
        sys.exit(1)

def find_mock_rule(url_path: str) -> Optional[Dict[str, Any]]:
    """Checks if the request path matches any mock rule."""
    for rule in MOCK_RULES:
        pattern = rule.get("pattern", "")
        if re.search(pattern, url_path):
            return rule
    return None

class InterceptingProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """Custom clean logging."""
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_CONNECT(self) -> None:
        """
        Handles HTTPS CONNECT tunneling.
        Since we cannot inspect HTTPS without local root CA certificates (MITM decryption),
        we act as a transparent tunnel for secure requests.
        """
        address = self.path.split(':')
        host = address[0]
        port = int(address[1]) if len(address) > 1 else 443
        
        try:
            # Connect to destination server
            upstream_sock = socket.create_connection((host, port), timeout=10)
            self.send_response(200, "Connection Established")
            self.end_headers()
            
            # Tunnel data between client and upstream
            self.tunnel_sockets(self.connection, upstream_sock)
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {e}")

    def tunnel_sockets(self, client_sock: socket.socket, server_sock: socket.socket) -> None:
        """Tunnels raw TCP traffic between two sockets."""
        sockets = [client_sock, server_sock]
        keep_running = True
        
        while keep_running:
            readable, _, errored = select.select(sockets, [], sockets, 10)
            if errored:
                break
            for sock in readable:
                other = server_sock if sock is client_sock else client_sock
                try:
                    data = sock.recv(8192)
                    if not data:
                        keep_running = False
                        break
                    other.sendall(data)
                except socket.error:
                    keep_running = False
                    break

    def handle_request(self) -> None:
        """Main dispatcher for GET, POST, PUT, DELETE, etc."""
        url_path = self.path
        
        # In Forward Proxy mode, path is absolute: http://host/path
        # In Reverse Proxy mode, path is relative: /path
        is_relative = url_path.startswith('/')
        
        # Check mock patterns
        matched_rule = find_mock_rule(url_path)
        
        if matched_rule:
            self.serve_mock_response(matched_rule, url_path)
            return

        # Not matched -> Forward request
        if is_relative and not DEFAULT_TARGET_URL:
            # Direct request to proxy root without backend target
            self.send_error(404, "Not Found. No mock matches this path, and no reverse proxy --target specified.")
            return
            
        self.forward_traffic(is_relative)

    def serve_mock_response(self, rule: Dict[str, Any], url_path: str) -> None:
        """Simulates response defined in rules."""
        delay = rule.get("delay", 0.0)
        if delay > 0:
            time.sleep(delay)
            
        status = rule.get("status", 200)
        headers = rule.get("headers", {})
        body_data = rule.get("body", "")
        
        # Convert dictionary body to json string if necessary
        if isinstance(body_data, (dict, list)):
            body_bytes = json.dumps(body_data).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        elif isinstance(body_data, str):
            body_bytes = body_data.encode("utf-8")
        else:
            body_bytes = str(body_data).encode("utf-8")
            
        print(color_text(f"[MOCK INTERCEPT] {self.command} {url_path} => Status {status}", COLOR_BOLD + COLOR_GREEN))
        
        self.send_response(status)
        for h_name, h_val in headers.items():
            self.send_header(h_name, h_val)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def forward_traffic(self, is_relative: bool) -> None:
        """Forwards standard HTTP traffic to destination."""
        if is_relative:
            # Reverse Proxy mode: Combine backend target with relative path
            target_url = DEFAULT_TARGET_URL.rstrip('/') + self.path
        else:
            # Forward Proxy mode: path is the full destination URL
            target_url = self.path
            
        print(color_text(f"[PROXY FORWARD] {self.command} {target_url}", COLOR_CYAN))
        
        # Extract headers from incoming request
        headers = {}
        for h_name in self.headers:
            # Avoid sending Host header that mismatches target in reverse proxy mode
            if is_relative and h_name.lower() == 'host':
                continue
            headers[h_name] = self.headers[h_name]
            
        # Read request body if present
        content_length = int(self.headers.get('Content-Length', 0))
        req_data = self.rfile.read(content_length) if content_length > 0 else None
        
        # Rebuild request
        req = urllib.request.Request(
            target_url,
            data=req_data,
            headers=headers,
            method=self.command
        )
        
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                self.send_response(res.status)
                # Forward response headers
                for res_h_name, res_h_val in res.getheaders():
                    # Avoid duplicate transfer encoding headers
                    if res_h_name.lower() != 'transfer-encoding':
                        self.send_header(res_h_name, res_h_val)
                self.end_headers()
                # Pipe response body
                self.wfile.write(res.read())
        except urllib.error.HTTPError as e:
            # Handle HTTP errors from target server gracefully by passing them back
            self.send_response(e.code)
            for res_h_name, res_h_val in e.headers.items():
                if res_h_name.lower() != 'transfer-encoding':
                    self.send_header(res_h_name, res_h_val)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {e}")

    # Bind handlers for HTTP verbs
    def do_GET(self) -> None: self.handle_request()
    def do_POST(self) -> None: self.handle_request()
    def do_PUT(self) -> None: self.handle_request()
    def do_DELETE(self) -> None: self.handle_request()
    def do_PATCH(self) -> None: self.handle_request()
    def do_OPTIONS(self) -> None: self.handle_request()
    def do_HEAD(self) -> None: self.handle_request()


def main() -> int:
    global DEFAULT_TARGET_URL
    
    parser = argparse.ArgumentParser(
        description="HTTP Intercepting & Mocking Proxy Server",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-p", "--port", type=int, default=8888, help="Port to run proxy server on (default: 8888)")
    parser.add_argument("-c", "--config", default="mock_rules.json", help="Path to JSON configuration rules file (default: mock_rules.json)")
    parser.add_argument("-t", "--target", help="Target URL for Reverse Proxy mode (e.g., http://localhost:3000)")
    
    args = parser.parse_args()
    
    # Configure mode
    if args.target:
        DEFAULT_TARGET_URL = args.target
        if not DEFAULT_TARGET_URL.startswith(('http://', 'https://')):
            DEFAULT_TARGET_URL = 'http://' + DEFAULT_TARGET_URL
        print(color_text(f"Mode: REVERSE PROXY (Gateway to {DEFAULT_TARGET_URL})", COLOR_BOLD + COLOR_CYAN))
    else:
        print(color_text("Mode: FORWARD PROXY (Configure client browser/system to use localhost as proxy)", COLOR_BOLD + COLOR_CYAN))
        
    load_rules(args.config)
    
    # Initialize and start HTTPServer
    server_address = ('', args.port)
    httpd = HTTPServer(server_address, InterceptingProxyHandler)
    
    print(f"Mocking Proxy Server listening on port {color_text(str(args.port), COLOR_BOLD + COLOR_GREEN)}... press Ctrl+C to terminate.")
    print("-" * 80)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mocking Proxy Server...")
    finally:
        httpd.server_close()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
