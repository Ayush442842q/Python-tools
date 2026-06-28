#!/usr/bin/env python3
"""
HTTP Traffic Recorder & Replayer
Intercepts and logs HTTP traffic as a Forward or Reverse Proxy.
Saves recorded request-response pairs to a JSON file, which can then be replayed offline.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, urlunparse

# ANSI Colors for terminal output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_banner():
    banner = f"""{COLOR_HEADER}{COLOR_BOLD}
  _    _ _______ _______ _____   _______▒▒▒▒  
 | |  | |__   __|__   __|  __ \ |__   __|    
 | |__| |  | |     | |  | |__) |   | |       
 |  __  |  | |     | |  |  ___/    | |       
 | |  | |  | |     | |  | |        | |       
 |_|  |_|  |_|     |_|  |_|        |_|       
                                             
{COLOR_END}{COLOR_BLUE}        HTTP Traffic Recorder & Replay Proxy (Mock Server Engine){COLOR_END}
"""
    print(banner, file=sys.stderr)


# Global state
mode = "record"  # "record" or "replay"
recorded_interactions = []
record_file_path = "traffic_session.json"
target_url = None  # For reverse proxy mode
proxy_mode = "reverse"  # "reverse" or "forward"


def load_recorded_sessions():
    global recorded_interactions
    if os.path.exists(record_file_path):
        try:
            with open(record_file_path, "r", encoding="utf-8") as f:
                recorded_interactions = json.load(f)
            print(f"{COLOR_GREEN}Loaded {len(recorded_interactions)} recorded interaction(s) from {record_file_path}{COLOR_END}", file=sys.stderr)
        except Exception as e:
            print(f"{COLOR_FAIL}Error loading session file: {e}{COLOR_END}", file=sys.stderr)
            sys.exit(1)
    elif mode == "replay":
        print(f"{COLOR_FAIL}Session file '{record_file_path}' not found. Cannot run in replay mode.{COLOR_END}", file=sys.stderr)
        sys.exit(1)


def save_recorded_sessions():
    try:
        with open(record_file_path, "w", encoding="utf-8") as f:
            json.dump(recorded_interactions, f, indent=2)
    except Exception as e:
        print(f"{COLOR_FAIL}Error saving session file: {e}{COLOR_END}", file=sys.stderr)


class ProxyRequestHandler(BaseHTTPRequestHandler):
    
    # Disable automatic console logging by http.server to avoid double logging
    def log_message(self, format, *args):
        pass

    def handle_request(self):
        global recorded_interactions
        
        req_method = self.command
        req_headers = {k: v for k, v in self.headers.items()}
        
        # Read request body
        content_length = int(req_headers.get("Content-Length", 0))
        req_body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        
        # Try to decode request body as string
        req_body_str = None
        is_req_body_base64 = False
        if req_body_bytes:
            try:
                req_body_str = req_body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                req_body_str = base64.b64encode(req_body_bytes).decode("utf-8")
                is_req_body_base64 = True

        # Determine target URL
        if proxy_mode == "forward":
            # Forward proxy: path contains full URL
            req_url = self.path
        else:
            # Reverse proxy: path is relative, combine with target_url
            parsed_target = urlparse(target_url)
            parsed_path = urlparse(self.path)
            # Reconstruct destination URL
            req_url = urlunparse((
                parsed_target.scheme,
                parsed_target.netloc,
                parsed_path.path,
                parsed_path.params,
                parsed_path.query,
                parsed_path.fragment
            ))

        print(f"{COLOR_BOLD}{req_method}{COLOR_END} {req_url}", end=" ", flush=True)

        if mode == "replay":
            self.replay_response(req_method, req_url, req_headers, req_body_bytes)
        else:
            self.record_and_forward(req_method, req_url, req_headers, req_body_bytes, req_body_str, is_req_body_base64)

    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def do_DELETE(self): self.handle_request()
    def do_PATCH(self): self.handle_request()
    def do_OPTIONS(self): self.handle_request()
    def do_HEAD(self): self.handle_request()

    def record_and_forward(self, method, url, headers, body_bytes, body_str, is_body_base64):
        # Prepare headers for forwarding (filter out hop-by-hop headers)
        forward_headers = {}
        hop_by_hop = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", 
                      "te", "trailers", "transfer-encoding", "upgrade", "host"}
        for k, v in headers.items():
            if k.lower() not in hop_by_hop:
                forward_headers[k] = v
                
        # Set Host header based on target URL
        parsed_url = urlparse(url)
        forward_headers["Host"] = parsed_url.netloc

        # Send outgoing request
        req = urllib.request.Request(
            url,
            data=body_bytes if method in ["POST", "PUT", "PATCH", "DELETE"] else None,
            headers=forward_headers,
            method=method
        )
        
        resp_status = 500
        resp_headers = {}
        resp_body_bytes = b""
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                resp_status = response.status
                resp_headers = {k: v for k, v in response.headers.items()}
                resp_body_bytes = response.read()
        except urllib.error.HTTPError as e:
            resp_status = e.code
            resp_headers = {k: v for k, v in e.headers.items()}
            resp_body_bytes = e.read()
        except Exception as e:
            print(f"-> {COLOR_FAIL}Failed to forward request: {e}{COLOR_END}")
            self.send_error(502, f"Bad Gateway: {e}")
            return

        print(f"-> {COLOR_GREEN if resp_status < 400 else COLOR_WARNING}{resp_status}{COLOR_END}")

        # Send response back to original client
        self.send_response(resp_status)
        for k, v in resp_headers.items():
            if k.lower() not in ["transfer-encoding", "content-encoding"]:  # Avoid transfer mismatches
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp_body_bytes)

        # Decode response body for JSON storage
        resp_body_str = None
        is_resp_body_base64 = False
        if resp_body_bytes:
            try:
                resp_body_str = resp_body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                resp_body_str = base64.b64encode(resp_body_bytes).decode("utf-8")
                is_resp_body_base64 = True

        # Store interaction
        interaction = {
            "request": {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body_str,
                "is_base64": is_body_base64
            },
            "response": {
                "status": resp_status,
                "headers": resp_headers,
                "body": resp_body_str,
                "is_base64": is_resp_body_base64
            }
        }
        recorded_interactions.append(interaction)
        save_recorded_sessions()

    def replay_response(self, method, url, headers, body_bytes):
        # Look for a matching recorded interaction
        match = None
        
        # Parse incoming request components to do normalized matching
        parsed_incoming = urlparse(url)
        incoming_path = parsed_incoming.path
        incoming_query = parsed_incoming.query

        for inter in recorded_interactions:
            req = inter["request"]
            if req["method"] != method:
                continue
                
            parsed_rec = urlparse(req["url"])
            if parsed_rec.path != incoming_path or parsed_rec.query != incoming_query:
                continue
                
            # If path and query matches, select this
            match = inter
            break

        if match:
            resp = match["response"]
            status = resp["status"]
            print(f"-> {COLOR_GREEN}[REPLAY {status}]{COLOR_END}")
            
            self.send_response(status)
            for k, v in resp["headers"].items():
                if k.lower() not in ["transfer-encoding", "content-encoding"]:
                    self.send_header(k, v)
            self.end_headers()
            
            # Send body
            if resp["body"]:
                if resp.get("is_base64", False):
                    body_data = base64.b64decode(resp["body"])
                else:
                    body_data = resp["body"].encode("utf-8")
                self.wfile.write(body_data)
        else:
            print(f"-> {COLOR_FAIL}[NOT FOUND IN SESSION]{COLOR_END}")
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Mock Server: No matching recorded interaction found.")


def main():
    global mode, record_file_path, target_url, proxy_mode
    
    parser = argparse.ArgumentParser(
        description="Record HTTP traffic to a file or replay traffic as a mock server."
    )
    parser.add_argument(
        "mode",
        choices=["record", "replay"],
        help="Run mode. 'record' captures outgoing requests; 'replay' serves mocks from file."
    )
    parser.add_argument(
        "-t", "--target",
        help="The target base URL for reverse proxy mode (e.g. https://api.github.com)."
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Port to run the local proxy server on (default: 8080)."
    )
    parser.add_argument(
        "-f", "--file",
        default="traffic_session.json",
        help="Path to save or read the traffic session file (default: traffic_session.json)."
    )
    parser.add_argument(
        "--forward",
        action="store_true",
        help="Run in Forward Proxy mode instead of Reverse Proxy mode. Useful for intercepting global HTTP requests."
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the CLI graphical banner."
    )

    args = parser.parse_args()
    
    if not args.no_banner:
        print_banner()

    mode = args.mode
    record_file_path = args.file
    proxy_mode = "forward" if args.forward else "reverse"
    target_url = args.target

    if proxy_mode == "reverse" and mode == "record" and not target_url:
        parser.error("Reverse proxy recording mode requires a --target URL (e.g., -t https://api.github.com)")

    if mode == "replay":
        load_recorded_sessions()

    # Log initial configuration info
    print(f"{COLOR_BOLD}Configuration:{COLOR_END}")
    print(f"  Mode:          {mode.upper()}")
    print(f"  Proxy Mode:    {proxy_mode.upper()}")
    if proxy_mode == "reverse" and target_url:
        print(f"  Target URL:    {target_url}")
    print(f"  Session File:  {record_file_path}")
    print(f"  Local Port:    {args.port}")
    print(f"\n{COLOR_GREEN}Server running. Press Ctrl+C to stop.{COLOR_END}\n")

    server_address = ("", args.port)
    try:
        httpd = HTTPServer(server_address, ProxyRequestHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{COLOR_WARNING}Shutting down server...{COLOR_END}", file=sys.stderr)
        if mode == "record":
            print(f"Saved {len(recorded_interactions)} interaction(s) to '{record_file_path}'", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
