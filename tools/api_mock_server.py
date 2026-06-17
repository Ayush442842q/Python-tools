#!/usr/bin/env python3
"""
API Mock Server - A lightweight HTTP/REST API mock server

This tool reads a JSON configuration file defining mock routes, HTTP methods,
status codes, response headers, response bodies, and simulated network delays,
and hosts a local mock API server.

Usage:
    python tools/api_mock_server.py [--port PORT] [--config CONFIG_FILE] [--write-sample]

Example:
    python tools/api_mock_server.py --port 8080 --config tools/mock_config.json
"""

import argparse
import json
import os
import sys
import time
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional

DEFAULT_PORT = 8080
DEFAULT_CONFIG = "mock_config.json"

SAMPLE_CONFIG = [
    {
        "path": "/api/users",
        "method": "GET",
        "status": 200,
        "headers": {
            "Content-Type": "application/json",
            "X-Mock-Server": "Python-API-Mock"
        },
        "body": [
            {"id": 1, "name": "Alice Smith", "role": "Developer"},
            {"id": 2, "name": "Bob Jones", "role": "Designer"},
            {"id": 3, "name": "Charlie Brown", "role": "Product Manager"}
        ],
        "delay": 0.2
    },
    {
        "path": "/api/users/1",
        "method": "GET",
        "status": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {"id": 1, "name": "Alice Smith", "role": "Developer"}
    },
    {
        "path": "/api/users",
        "method": "POST",
        "status": 201,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {"status": "success", "message": "User created successfully", "id": 4}
    },
    {
        "path": "/api/status",
        "method": "GET",
        "status": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {"status": "healthy", "uptime": "up"}
    }
]


class MockRequestHandler(BaseHTTPRequestHandler):
    routes: List[Dict[str, Any]] = []

    def log_message(self, format: str, *args: Any) -> None:
        # Custom logging format to include clean timestamps
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def handle_request(self, method: str) -> None:
        # Extract path without query parameters
        parsed_path = self.path.split('?')[0]
        
        # Find matching route configuration
        matched_route = self.find_route(method, parsed_path)
        
        if not matched_route:
            self.send_error_response(404, f"Route not found: {method} {parsed_path}")
            return

        # Simulate network latency/delay if specified
        delay = matched_route.get("delay", 0.0)
        if delay > 0:
            time.sleep(delay)

        # Send status code
        status = matched_route.get("status", 200)
        self.send_response(status)

        # Send headers
        headers = matched_route.get("headers", {})
        has_content_type = False
        for key, value in headers.items():
            self.send_header(key, value)
            if key.lower() == 'content-type':
                has_content_type = True
        
        # Default header if missing
        if not has_content_type:
            self.send_header("Content-Type", "application/json")
        
        self.end_headers()

        # Send body
        body = matched_route.get("body", "")
        if body is not None:
            if isinstance(body, (dict, list)):
                self.wfile.write(json.dumps(body, indent=2).encode('utf-8'))
            else:
                self.wfile.write(str(body).encode('utf-8'))

    def find_route(self, method: str, path: str) -> Optional[Dict[str, Any]]:
        for route in self.routes:
            if route.get("method", "GET").upper() != method.upper():
                continue
            
            route_path = route.get("path", "")
            
            # Direct exact match
            if route_path == path:
                return route
            
            # Simple wildcard/parameter matching (e.g. /api/users/:id)
            pattern = re.sub(r':[a-zA-Z0-9_]+', r'[^/]+', route_path)
            # Support basic '*' wildcard
            pattern = pattern.replace('*', '.*')
            
            if re.match(f"^{pattern}$", path):
                return route
                
        return None

    def send_error_response(self, code: int, message: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": {
                "code": code,
                "message": message
            }
        }, indent=2).encode('utf-8'))

    def do_GET(self) -> None:
        self.handle_request("GET")

    def do_POST(self) -> None:
        self.handle_request("POST")

    def do_PUT(self) -> None:
        self.handle_request("PUT")

    def do_DELETE(self) -> None:
        self.handle_request("DELETE")

    def do_PATCH(self) -> None:
        self.handle_request("PATCH")


def write_sample_config(filepath: str) -> None:
    try:
        with open(filepath, 'w') as f:
            json.dump(SAMPLE_CONFIG, f, indent=4)
        print(f"Created sample configuration file: {filepath}")
    except Exception as e:
        print(f"Error creating sample config: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a mock API server")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Port to run server on (default: {DEFAULT_PORT})')
    parser.add_argument('--config', default=DEFAULT_CONFIG, help=f'Path to JSON config file (default: {DEFAULT_CONFIG})')
    parser.add_argument('--write-sample', action='store_true', help='Write a sample config file and exit')
    
    args = parser.parse_args()

    if args.write_sample:
        write_sample_config(args.config)
        return 0

    # Auto-generate config file if it does not exist
    if not os.path.exists(args.config):
        print(f"Configuration file '{args.config}' not found.")
        write_sample_config(args.config)

    # Load configuration
    try:
        with open(args.config, 'r') as f:
            routes = json.load(f)
            if not isinstance(routes, list):
                print("Error: Config root must be a JSON array of route objects.", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    MockRequestHandler.routes = routes

    server_address = ('', args.port)
    httpd = HTTPServer(server_address, MockRequestHandler)
    
    print("=" * 60)
    print(f"API Mock Server running on port {args.port}...")
    print(f"Configured routes ({len(routes)} total):")
    for r in routes:
        print(f"  {r.get('method', 'GET').upper():<6} {r.get('path', '')} -> Status {r.get('status', 200)}")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API Mock Server...")
    finally:
        httpd.server_close()
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
