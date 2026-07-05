#!/usr/bin/env python3
"""HTTP Response Replay Server

Reads recorded HTTP traffic dumps or HAR files and spins up a local mock web
server replaying matching HTTP responses based on request path, method, and parameters.
"""

import argparse
import json
import re
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


class MockRoute:
    def __init__(self, method: str, path_pattern: str, status: int, headers: Dict[str, str], body: bytes):
        self.method = method.upper()
        self.path_pattern = path_pattern
        self.status = status
        self.headers = headers
        self.body = body

    def matches(self, request_method: str, request_path: str) -> bool:
        if self.method != "*" and self.method != request_method.upper():
            return False
        return bool(re.match(f"^{self.path_pattern}$", request_path))


class TrafficStore:
    def __init__(self):
        self.routes: List[MockRoute] = []

    def load_from_har(self, har_path: Path):
        data = json.loads(har_path.read_text(encoding="utf-8"))
        entries = data.get("log", {}).get("entries", [])
        for entry in entries:
            req = entry.get("request", {})
            resp = entry.get("response", {})
            full_url = req.get("url", "")
            parsed = urlparse(full_url)
            path = parsed.path or "/"

            headers = {h["name"]: h["value"] for h in resp.get("headers", [])}
            body_text = resp.get("content", {}).get("text", "")
            body = body_text.encode("utf-8")

            self.routes.append(
                MockRoute(
                    method=req.get("method", "GET"),
                    path_pattern=re.escape(path),
                    status=resp.get("status", 200),
                    headers=headers,
                    body=body,
                )
            )

    def load_from_json(self, json_path: Path):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        routes_data = data if isinstance(data, list) else data.get("routes", [])
        for r in routes_data:
            method = r.get("method", "*")
            path = r.get("path", ".*")
            status = r.get("status", 200)
            headers = r.get("headers", {"Content-Type": "application/json"})
            body_val = r.get("body", "")
            if isinstance(body_val, (dict, list)):
                body_bytes = json.dumps(body_val).encode("utf-8")
            else:
                body_bytes = str(body_val).encode("utf-8")

            self.routes.append(
                MockRoute(
                    method=method,
                    path_pattern=path,
                    status=status,
                    headers=headers,
                    body=body_bytes,
                )
            )

    def find_match(self, method: str, path: str) -> Optional[MockRoute]:
        for r in self.routes:
            if r.matches(method, path):
                return r
        return None


def create_handler_class(store: TrafficStore):
    class ReplayRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Custom logging with colors
            pass

        def do_request(self):
            parsed = urlparse(self.path)
            req_path = parsed.path
            match = store.find_match(self.command, req_path)

            if match:
                print(f"  {COLOR_GREEN}[REPLAY {match.status}]{COLOR_RESET} {self.command} {self.path}")
                self.send_response(match.status)
                for k, v in match.headers.items():
                    if k.lower() not in ("content-length", "transfer-encoding"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(match.body)))
                self.end_headers()
                self.wfile.write(match.body)
            else:
                print(f"  {COLOR_RED}[NOT FOUND 404]{COLOR_RESET} {self.command} {self.path}")
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                resp_body = json.dumps({"error": "No matching route found", "path": self.path, "method": self.command}).encode("utf-8")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

        do_GET = do_request
        do_POST = do_request
        do_PUT = do_request
        do_DELETE = do_request
        do_PATCH = do_request

    return ReplayRequestHandler


def main():
    parser = argparse.ArgumentParser(
        description="Replay HTTP traffic recordings or HAR files using a local mock HTTP server."
    )
    parser.add_argument("file", help="Path to JSON routes file or HAR recording")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")

    args = parser.parse_args()
    traffic_file = Path(args.file).resolve()

    if not traffic_file.exists():
        print(f"{COLOR_RED}Error: File '{traffic_file}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    store = TrafficStore()
    if traffic_file.suffix.lower() == ".har":
        store.load_from_har(traffic_file)
    else:
        store.load_from_json(traffic_file)

    handler_cls = create_handler_class(store)
    server = HTTPServer((args.host, args.port), handler_cls)

    print(f"{COLOR_BOLD}{COLOR_CYAN}HTTP Response Replay Server{COLOR_RESET}")
    print(f"Loaded routes: {COLOR_YELLOW}{len(store.routes)}{COLOR_RESET}")
    print(f"Listening on: {COLOR_BOLD}http://{args.host}:{args.port}{COLOR_RESET} (Press Ctrl+C to stop)\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}Stopping Replay Server.{COLOR_RESET}")
        server.server_close()


if __name__ == "__main__":
    main()
