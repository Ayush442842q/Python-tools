#!/usr/bin/env python3
"""
JSON-RPC Server Mock & Envelope Validator
Author: Antigravity

A standalone utility to spin up a mock JSON-RPC 1.0/2.0 HTTP server, and
a CLI client to send requests/batches and validate conformance of request
and response envelopes to the JSON-RPC specification.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, Tuple, Union

# Standard JSON-RPC 2.0 error codes
ERROR_CODES = {
    -32700: "Parse error (Invalid JSON)",
    -32600: "Invalid Request (Not a valid JSON-RPC object)",
    -32601: "Method not found",
    -32602: "Invalid params",
    -32603: "Internal error",
}

def make_jsonrpc_error(code: int, id_val: Any = None, data: Any = None) -> Dict[str, Any]:
    """Generates standard JSON-RPC error response payload."""
    message = ERROR_CODES.get(code, "Server error")
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {
        "jsonrpc": "2.0",
        "error": err,
        "id": id_val
    }

def make_jsonrpc_success(result: Any, id_val: Any) -> Dict[str, Any]:
    """Generates standard JSON-RPC success response payload."""
    return {
        "jsonrpc": "2.0",
        "result": result,
        "id": id_val
    }

class JSONRPCMockHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler supporting JSON-RPC mocks."""
    
    # Mock database/registered methods
    methods = {
        "ping": lambda params: "pong",
        "echo": lambda params: params,
        "math.add": lambda params: sum(params) if isinstance(params, list) else 0,
        "math.multiply": lambda params: params[0] * params[1] if isinstance(params, list) and len(params) >= 2 else 0,
        "system.listMethods": lambda params: ["ping", "echo", "math.add", "math.multiply", "system.listMethods"]
    }

    def log_message(self, format, *args):
        # Override to log clean custom messages
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format%args))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')

        # 1. Parse JSON
        try:
            request_payload = json.loads(post_data)
        except json.JSONDecodeError:
            response = make_jsonrpc_error(-32700)
            self.send_json_response(response, 500)
            return

        # 2. Process batch vs single request
        if isinstance(request_payload, list):
            # Batch request
            if len(request_payload) == 0:
                response = make_jsonrpc_error(-32600, data="Empty batch array")
                self.send_json_response(response, 400)
                return
                
            responses = []
            for single_req in request_payload:
                res = self.process_single_request(single_req)
                # Notifications (id omitted) should not return a response
                if res is not None:
                    responses.append(res)
                    
            if responses:
                self.send_json_response(responses)
            else:
                # All were notifications, respond with HTTP 204 No Content
                self.send_response(204)
                self.end_headers()
        else:
            # Single request
            res = self.process_single_request(request_payload)
            if res is not None:
                self.send_json_response(res)
            else:
                # Notification
                self.send_response(204)
                self.end_headers()

    def process_single_request(self, req: Any) -> Optional[Dict[str, Any]]:
        """Validates and runs a single JSON-RPC request."""
        if not isinstance(req, dict):
            return make_jsonrpc_error(-32600)

        # Validate version envelope
        version = req.get("jsonrpc")
        if version != "2.0":
            # JSON-RPC 1.0 does not specify version. We default to support 2.0.
            # If they pass a version other than 2.0, we flag it.
            if version is not None:
                return make_jsonrpc_error(-32600, data="Unsupported jsonrpc version. Must be '2.0'.")

        method = req.get("method")
        params = req.get("params")
        id_val = req.get("id")

        if not isinstance(method, str):
            return make_jsonrpc_error(-32600, id_val, data="Missing or invalid method name.")

        # Check if method exists
        if method not in self.methods:
            return make_jsonrpc_error(-32601, id_val, data=f"Method '{method}' not found.")

        # Execute method
        try:
            result = self.methods[method](params)
            # If ID is missing, it's a notification, no response should be sent
            if "id" not in req:
                return None
            return make_jsonrpc_success(result, id_val)
        except Exception as e:
            return make_jsonrpc_error(-32603, id_val, data=str(e))

    def send_json_response(self, data: Any, status: int = 200):
        """Helper to send JSON response."""
        response_body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json-rpc')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

def run_server(host: str, port: int):
    """Starts the mock JSON-RPC server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, JSONRPCMockHandler)
    print(f"\033[92mMock JSON-RPC 2.0 Server running on http://{host}:{port}\033[0m")
    print("Pre-registered Mock Methods:")
    for method in JSONRPCMockHandler.methods.keys():
        print(f"  - {method}")
    print("\nPress Ctrl+C to terminate server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock server.")
        httpd.server_close()
        sys.exit(0)

def validate_jsonrpc_envelope(payload: Dict[str, Any], is_request: bool) -> List[str]:
    """Validates compliance of JSON-RPC request/response structure."""
    issues = []
    
    # Check JSON structure
    if not isinstance(payload, dict):
        return ["Payload is not a valid JSON object."]

    # 1. Version Check
    version = payload.get("jsonrpc")
    if version != "2.0":
        issues.append(f"jsonrpc property must be exactly '2.0' (found: {repr(version)})")

    # 2. ID Check
    if "id" not in payload:
        if is_request:
            # Notifications do not require ID
            pass
        else:
            issues.append("Response envelope is missing the required 'id' parameter.")
    else:
        id_val = payload["id"]
        if id_val is not None and not isinstance(id_val, (str, int, float)):
            issues.append(f"id should be a string, integer, or null (found: {type(id_val).__name__})")

    # 3. Payload Specifics
    if is_request:
        if "method" not in payload:
            issues.append("Request envelope is missing required 'method' property.")
        elif not isinstance(payload["method"], str):
            issues.append("method property must be a string.")
            
        if "params" in payload:
            params = payload["params"]
            if not isinstance(params, (list, dict)):
                issues.append("params must be a structured value (Array or Object).")
    else:
        # Response checks
        has_result = "result" in payload
        has_error = "error" in payload
        
        if has_result and has_error:
            issues.append("Response must NOT contain both 'result' and 'error' properties.")
        elif not has_result and not has_error:
            issues.append("Response must contain either 'result' or 'error' property.")
            
        if has_error:
            err = payload["error"]
            if not isinstance(err, dict):
                issues.append("error property must be a JSON object.")
            else:
                if "code" not in err or not isinstance(err["code"], int):
                    issues.append("error.code must be an integer.")
                if "message" not in err or not isinstance(err["message"], str):
                    issues.append("error.message must be a string.")

    return issues

def send_client_request(url: str, request_data: Any):
    """Sends JSON-RPC client request and validates request/response envelopes."""
    req_body = json.dumps(request_data)
    
    print("\n" + "=" * 80)
    print(" SENDING JSON-RPC REQUEST ".center(80, "="))
    print("=" * 80)
    print(json.dumps(request_data, indent=2))

    # Validate request envelope
    req_issues = []
    if isinstance(request_data, list):
        for idx, sub_req in enumerate(request_data):
            issues = validate_jsonrpc_envelope(sub_req, is_request=True)
            if issues:
                req_issues.extend([f"Batch item [{idx}]: {i}" for i in issues])
    else:
        req_issues = validate_jsonrpc_envelope(request_data, is_request=True)

    if req_issues:
        print("\n\033[93mRequest Compliance Issues Found:\033[0m")
        for issue in req_issues:
            print(f"  [WARN] {issue}")
    else:
        print("\n\033[92mRequest structure is fully compliant with JSON-RPC 2.0!\033[0m")

    # Send Request
    req = urllib.request.Request(
        url,
        data=req_body.encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            status_code = response.status
    except urllib.error.HTTPError as e:
        res_body = e.read().decode('utf-8')
        status_code = e.code
    except Exception as e:
        print(f"\nConnection Error: {e}", file=sys.stderr)
        return

    print("\n" + "=" * 80)
    print(f" RECEIVED JSON-RPC RESPONSE (HTTP {status_code}) ".center(80, "="))
    print("=" * 80)
    
    if not res_body.strip():
        print("Empty response body (e.g. notification submission success).")
        return

    try:
        response_data = json.loads(res_body)
        print(json.dumps(response_data, indent=2))
    except json.JSONDecodeError:
        print(f"\033[91mError: Server response was not valid JSON: {res_body}\033[0m")
        return

    # Validate response envelope
    res_issues = []
    if isinstance(response_data, list):
        for idx, sub_res in enumerate(response_data):
            issues = validate_jsonrpc_envelope(sub_res, is_request=False)
            if issues:
                res_issues.extend([f"Batch item [{idx}]: {i}" for i in issues])
    else:
        res_issues = validate_jsonrpc_envelope(response_data, is_request=False)

    if res_issues:
        print("\n\033[91mResponse Compliance Issues Found:\033[0m")
        for issue in res_issues:
            print(f"  [ERROR] {issue}")
    else:
        print("\n\033[92mResponse structure is fully compliant with JSON-RPC 2.0!\033[0m")

def main():
    parser = argparse.ArgumentParser(
        description="JSON-RPC Server Mock & Envelope Validator - Test JSON-RPC protocol compliance."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Execution mode: server or client")

    # Server mode arguments
    server_parser = subparsers.add_parser("server", help="Start mock JSON-RPC HTTP server")
    server_parser.add_argument("--host", default="localhost", help="Host binding address")
    server_parser.add_argument("--port", type=int, default=8080, help="Port to bind server to")

    # Client mode arguments
    client_parser = subparsers.add_parser("client", help="Send and validate JSON-RPC request envelopes")
    client_parser.add_argument("--url", default="http://localhost:8080", help="URL of JSON-RPC server endpoint")
    client_parser.add_argument("--method", required=True, help="JSON-RPC method name to invoke")
    client_parser.add_argument("--params", help="JSON structured parameters (e.g., '[1, 2]' or '{\"a\": 1}')")
    client_parser.add_argument("--id", type=int, default=1, help="Request id (omit parameter --notification to send notification)")
    client_parser.add_argument("--notification", action="store_true", help="Send request as notification (without id)")
    client_parser.add_argument("--batch", help="Path to a JSON file containing a batch request list")

    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.host, args.port)
    elif args.mode == "client":
        if args.batch:
            try:
                with open(args.batch, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                print(f"Error loading batch file: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Construct request envelope
            payload = {
                "jsonrpc": "2.0",
                "method": args.method
            }
            if args.params:
                try:
                    payload["params"] = json.loads(args.params)
                except json.JSONDecodeError:
                    # Parse parameters as string if not valid JSON structures
                    payload["params"] = args.params
            if not args.notification:
                payload["id"] = args.id

        send_client_request(args.url, payload)

if __name__ == "__main__":
    main()
