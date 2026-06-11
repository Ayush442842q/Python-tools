#!/usr/bin/env python3
"""
REST API Mock Server

A lightweight, zero-dependency REST API mock server.
It serves custom JSON endpoints based on a configuration file, logs incoming
requests in detail (method, path, headers, query parameters, body), and
supports simulating network latency.

Usage:
    python tools/api_mock_server.py [--port 8080] [--config mock_config.json] [--delay 0.5]
"""

import argparse
import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ANSI escape codes for styling
CLR_HEADER = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

DEFAULT_CONFIG_FILE = "mock_config.json"

DEFAULT_CONFIG_DATA = {
    "endpoints": [
        {
            "path": "/api/health",
            "method": "GET",
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"status": "healthy", "timestamp": "live"}
        },
        {
            "path": "/api/users",
            "method": "GET",
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": [
                {"id": 1, "name": "Alice Smith", "email": "alice@example.com"},
                {"id": 2, "name": "Bob Jones", "email": "bob@example.com"}
            ]
        },
        {
            "path": "/api/users",
            "method": "POST",
            "status": 201,
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "User created successfully", "id": 3}
        },
        {
            "path": "/api/items/1",
            "method": "PUT",
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "Item 1 updated successfully"}
        },
        {
            "path": "/api/items/1",
            "method": "DELETE",
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "Item 1 deleted successfully"}
        }
    ]
}


class MockRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to suppress default HTTP server log to stdout/stderr
        pass

    def _get_method_color(self, method):
        colors = {
            "GET": CLR_GREEN,
            "POST": CLR_BLUE,
            "PUT": CLR_YELLOW,
            "DELETE": CLR_RED,
            "PATCH": CLR_HEADER
        }
        return colors.get(method.upper(), CLR_RESET)

    def _get_status_color(self, status):
        if status < 300:
            return CLR_GREEN
        elif status < 400:
            return CLR_BLUE
        elif status < 500:
            return CLR_YELLOW
        else:
            return CLR_RED

    def handle_request(self):
        method = self.command
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Read body if present
        content_length = int(self.headers.get('Content-Length', 0))
        body = ""
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8')

        # Log request
        method_color = self._get_method_color(method)
        print(f"\n{method_color}{CLR_BOLD}=== INCOMING REQUEST: {method} {path} ==={CLR_RESET}")
        
        if query_params:
            print(f"{CLR_CYAN}Query Params:{CLR_RESET} {json.dumps(query_params)}")
        
        print(f"{CLR_CYAN}Headers:{CLR_RESET}")
        for key, val in self.headers.items():
            print(f"  {key}: {val}")

        if body:
            print(f"{CLR_CYAN}Body:{CLR_RESET}")
            try:
                # Pretty print if JSON
                json_body = json.loads(body)
                print(json.dumps(json_body, indent=2))
            except json.JSONDecodeError:
                print(f"  {body}")

        # Simulate network delay if specified
        if self.server.delay > 0:
            print(f"{CLR_YELLOW}Simulating delay of {self.server.delay}s...{CLR_RESET}")
            time.sleep(self.server.delay)

        # Search config endpoints
        matching_endpoint = None
        for endpoint in self.server.config.get("endpoints", []):
            if endpoint.get("path") == path and endpoint.get("method", "GET").upper() == method.upper():
                matching_endpoint = endpoint
                break

        if matching_endpoint:
            status = matching_endpoint.get("status", 200)
            headers = matching_endpoint.get("headers", {})
            body_data = matching_endpoint.get("body", "")

            # Send response
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            
            # Auto-set Content-Length if body is string or JSON
            response_content = b""
            if body_data is not None:
                if isinstance(body_data, (dict, list)):
                    # Dynamically update health timestamp if needed
                    if path == "/api/health" and isinstance(body_data, dict):
                        body_data = body_data.copy()
                        body_data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    response_content = json.dumps(body_data).encode('utf-8')
                    if "Content-Type" not in headers:
                        self.send_header("Content-Type", "application/json")
                else:
                    response_content = str(body_data).encode('utf-8')

            self.send_header("Content-Length", str(len(response_content)))
            self.end_headers()
            self.wfile.write(response_content)

            status_color = self._get_status_color(status)
            print(f"{CLR_GREEN}Response Sent:{CLR_RESET} Status {status_color}{status}{CLR_RESET}")
        else:
            # Endpoint not found
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            response_content = json.dumps({"error": "Endpoint not mocked", "path": path, "method": method}).encode('utf-8')
            self.send_header("Content-Length", str(len(response_content)))
            self.end_headers()
            self.wfile.write(response_content)
            print(f"{CLR_RED}Response Sent: Status 404 (Not Found){CLR_RESET}")

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PUT(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def do_OPTIONS(self):
        # Support CORS by default
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"{CLR_YELLOW}Config file '{config_path}' not found. Generating default config...{CLR_RESET}")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG_DATA, f, indent=4)
            print(f"{CLR_GREEN}Default config generated successfully.{CLR_RESET}")
        except Exception as e:
            print(f"{CLR_RED}Error writing config file: {e}{CLR_RESET}")
            return DEFAULT_CONFIG_DATA
        return DEFAULT_CONFIG_DATA

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{CLR_RED}Error reading config file: {e}. Using empty configuration.{CLR_RESET}")
        return {"endpoints": []}


def main():
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI color escape sequences on Windows

    parser = argparse.ArgumentParser(
        description="REST API Mock Server - Start a lightweight mock REST server"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Port to run the mock server on (default: 8080)"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to JSON configuration file (default: {DEFAULT_CONFIG_FILE})"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=0.0,
        help="Simulate response delay in seconds (default: 0.0)"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    server_address = ('', args.port)
    httpd = HTTPServer(server_address, MockRequestHandler)
    httpd.config = config
    httpd.delay = args.delay

    print("=" * 60)
    print(f"{CLR_GREEN}{CLR_BOLD}REST API MOCK SERVER RUNNING{CLR_RESET}")
    print("=" * 60)
    print(f"Local URL:  {CLR_BLUE}http://localhost:{args.port}{CLR_RESET}")
    print(f"Config:     {args.config}")
    if args.delay > 0:
        print(f"Delay:      {args.delay} seconds")
    print(f"Endpoints Loaded ({len(config.get('endpoints', []))}):")
    for endpoint in config.get("endpoints", []):
        method = f"[{endpoint.get('method', 'GET')}]"
        print(f"  {CLR_YELLOW}{method:<8}{CLR_RESET} {endpoint.get('path')} -> Status {endpoint.get('status')}")
    print("\nPress Ctrl+C to stop the server.")
    print("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{CLR_YELLOW}Shutting down server...{CLR_RESET}")
        httpd.server_close()
        print(f"{CLR_GREEN}Server stopped.{CLR_RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
