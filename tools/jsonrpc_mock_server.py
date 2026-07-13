#!/usr/bin/env python3
"""
jsonrpc_mock_server - Mock server for JSON-RPC 2.0 web services

Spins up a lightweight local HTTP server that validates and handles JSON-RPC 2.0
requests, supporting single requests, batch requests, notifications, and custom
method-response mappings from a configuration file.

Usage:
    python tools/jsonrpc_mock_server.py [options]

Example:
    python tools/jsonrpc_mock_server.py --port 8545 --generate-config
"""

import argparse
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# Standard JSON-RPC 2.0 Error Codes
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL_ERROR = -32603

DEFAULT_CONFIG = {
    "methods": {
        "web3_clientVersion": {
            "result": "AntigravityJSONRPCMock/v1.0.0/python"
        },
        "net_version": {
            "result": "1"
        },
        "eth_blockNumber": {
            "result": "0x11ff22"
        },
        "subtract": {
            "description": "Subtracts the second parameter from the first",
            "result": None,  # Will be dynamically handled or static
            # If dynamic logic is not used, this fallback is returned
            "fallback_result": 19
        }
    }
}


def make_jsonrpc_error(code, message, data=None, req_id=None):
    """Generate a standard JSON-RPC 2.0 error response."""
    response = {
        "jsonrpc": "2.0",
        "error": {
            "code": code,
            "message": message
        },
        "id": req_id
    }
    if data is not None:
        response["error"]["data"] = data
    return response


def make_jsonrpc_success(result, req_id):
    """Generate a standard JSON-RPC 2.0 success response."""
    return {
        "jsonrpc": "2.0",
        "result": result,
        "id": req_id
    }


class JSONRPCHandler(BaseHTTPRequestHandler):
    config = DEFAULT_CONFIG

    def do_POST(self):
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        if not post_data:
            self.send_error_response(ERROR_INVALID_REQUEST, "Empty request body")
            return

        # Parse JSON
        try:
            request_payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            self.send_error_response(ERROR_PARSE, f"Parse error: {str(e)}")
            return

        # Handle batch or single request
        if isinstance(request_payload, list):
            if not request_payload:
                self.send_error_response(ERROR_INVALID_REQUEST, "Empty batch request")
                return
            responses = []
            for req in request_payload:
                res = self.process_request(req)
                if res is not None:  # Notifications don't return responses
                    responses.append(res)
            
            # Send batch response (if there are any non-notification responses)
            if responses:
                self.send_json_response(responses)
            else:
                self.send_empty_response()
        else:
            response = self.process_request(request_payload)
            if response is not None:
                self.send_json_response(response)
            else:
                self.send_empty_response()

    def process_request(self, req):
        """Process a single JSON-RPC request object."""
        # 1. Validate request structure
        if not isinstance(req, dict):
            return make_jsonrpc_error(ERROR_INVALID_REQUEST, "Invalid Request: expected an object")

        req_id = req.get("id")
        
        # Check jsonrpc version
        if req.get("jsonrpc") != "2.0":
            return make_jsonrpc_error(ERROR_INVALID_REQUEST, "Invalid Request: missing or incorrect jsonrpc version", req_id=req_id)

        # Check method
        method = req.get("method")
        if not method or not isinstance(method, str):
            return make_jsonrpc_error(ERROR_INVALID_REQUEST, "Invalid Request: method must be a non-empty string", req_id=req_id)

        params = req.get("params")

        print(f" -> Method: [ {method} ] | Params: {params} | ID: {req_id}")

        # 2. Match method in config
        method_rules = self.config.get("methods", {}).get(method)
        if method_rules is None:
            print(f" <- Error: Method not found: {method}")
            return make_jsonrpc_error(ERROR_METHOD_NOT_FOUND, f"Method not found: '{method}'", req_id=req_id)

        # Check if it's a notification (no ID)
        if req_id is None:
            print(f" <- Notification processed (no response sent)")
            return None

        # Determine result (can check if there is custom logic or fallback)
        result = method_rules.get("result")
        if result is None:
            # Check for fallback or dynamic logic simulations
            result = method_rules.get("fallback_result")
            
            # Perform simple dynamic simulation for mock methods
            if method == "subtract" and isinstance(params, list) and len(params) >= 2:
                try:
                    result = params[0] - params[1]
                except Exception:
                    pass
            elif method == "subtract" and isinstance(params, dict):
                try:
                    subtrahend = params.get("subtrahend", 0)
                    minuend = params.get("minuend", 0)
                    result = minuend - subtrahend
                except Exception:
                    pass

        print(f" <- Success: {result}")
        return make_jsonrpc_success(result, req_id)

    def send_json_response(self, payload):
        """Send a JSON formatted response."""
        response_bytes = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def send_error_response(self, code, message):
        """Send a generic top-level JSON-RPC error."""
        payload = make_jsonrpc_error(code, message)
        self.send_json_response(payload)

    def send_empty_response(self):
        """Send an empty response for notifications."""
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        # Override default server logs to reduce noise
        pass


def run_server(host, port, config_path):
    # Load configuration
    config = DEFAULT_CONFIG
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"Loaded config from: {config_path}")
        except Exception as e:
            print(f"Error loading config {config_path}: {e}. Using default mock config.")
    
    JSONRPCHandler.config = config

    server_address = (host, port)
    httpd = HTTPServer(server_address, JSONRPCHandler)
    print(f"Starting JSON-RPC Mock Server on http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="JSON-RPC 2.0 Mock HTTP Server"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8545,
        help="Port to bind the server to (default: 8545)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to JSON-RPC method configuration file"
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate a default config file 'jsonrpc_mock_config.json' and exit"
    )

    args = parser.parse_args()

    if args.generate_config:
        filename = "jsonrpc_mock_config.json"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            print(f"Successfully generated default configuration in '{filename}'")
            return 0
        except Exception as e:
            print(f"Error generating config file: {e}")
            return 1

    run_server(args.host, args.port, args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
