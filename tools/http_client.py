#!/usr/bin/env python3
"""
HTTP Client CLI

A lightweight CLI tool to send HTTP requests, view status codes, inspect headers,
measure request latencies, and pretty-print JSON response bodies. Uses only standard 
library `urllib`.

Usage:
    python tools/http_client.py https://api.github.com/users/octocat
    python tools/http_client.py https://httpbin.org/post -X POST -j '{"name": "test"}'
    python tools/http_client.py https://example.com -H "Accept: text/html" -v
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

# ANSI Color Codes for terminal formatting
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    """Wraps text in ANSI color codes if colors are supported."""
    if supports_color():
        return f"{color_code}{text}{COLOR_RESET}"
    return text

def parse_headers(header_strings: Optional[List[str]]) -> Dict[str, str]:
    """Parses a list of header strings in format 'Key: Value' into a dictionary."""
    headers = {}
    if not header_strings:
        return headers
        
    for h in header_strings:
        if ':' not in h:
            print(f"Warning: Ignoring malformed header '{h}' (missing ':')", file=sys.stderr)
            continue
        key, value = h.split(':', 1)
        headers[key.strip()] = value.strip()
    return headers

def pretty_print_response(
    status_code: int,
    status_msg: str,
    headers: List[tuple],
    body: bytes,
    duration: float,
    verbose: bool,
    output_file: Optional[str]
) -> None:
    """Prints the response code, headers, and formatted body."""
    # Print status line and request time
    status_str = f"HTTP Status: {status_code} {status_msg}"
    if status_code >= 400:
        status_colored = color_text(status_str, COLOR_RED)
    elif status_code >= 300:
        status_colored = color_text(status_str, COLOR_YELLOW)
    else:
        status_colored = color_text(status_str, COLOR_GREEN)
        
    print(f"{color_text('=== Status ===', COLOR_BOLD)}")
    print(f"{status_colored}")
    print(f"Time Elapsed: {duration:.3f}s\n")
    
    # Print response headers if verbose
    if verbose:
        print(f"{color_text('=== Response Headers ===', COLOR_BOLD)}")
        for key, val in headers:
            print(f"{color_text(key, COLOR_CYAN)}: {val}")
        print()
        
    # Process body
    content_type = ""
    for key, val in headers:
        if key.lower() == 'content-type':
            content_type = val.lower()
            break
            
    decoded_body = ""
    is_binary = False
    try:
        decoded_body = body.decode('utf-8')
    except UnicodeDecodeError:
        is_binary = True
        
    if output_file:
        try:
            with open(output_file, 'wb') as f:
                f.write(body)
            print(f"Saved response body to: {output_file}")
        except IOError as e:
            print(f"Error saving to file: {e}", file=sys.stderr)
    else:
        print(f"{color_text('=== Response Body ===', COLOR_BOLD)}")
        if is_binary:
            print(f"[Binary Data: {len(body)} bytes]")
        elif 'application/json' in content_type:
            try:
                parsed_json = json.loads(decoded_body)
                pretty_json = json.dumps(parsed_json, indent=2)
                # Simple color highlighting for JSON keys
                if supports_color():
                    highlighted = ""
                    for line in pretty_json.splitlines():
                        if '"' in line and ':' in line:
                            parts = line.split(':', 1)
                            highlighted += f"{color_text(parts[0], COLOR_CYAN)}:{parts[1]}\n"
                        else:
                            highlighted += f"{line}\n"
                    print(highlighted.rstrip())
                else:
                    print(pretty_json)
            except json.JSONDecodeError:
                print(decoded_body)
        else:
            # Print text content (limit to first 2000 chars to avoid flooding if large HTML)
            if len(decoded_body) > 4000:
                print(decoded_body[:4000])
                print(color_text(f"\n... (truncated {len(decoded_body) - 4000} bytes)", COLOR_YELLOW))
            else:
                print(decoded_body)

def main() -> int:
    parser = argparse.ArgumentParser(description="HTTP Client CLI")
    parser.add_argument('url', help="Target URL (e.g. https://httpbin.org/get)")
    parser.add_argument('-X', '--method', default='GET', help="HTTP Method (GET, POST, PUT, DELETE, PATCH, etc.)")
    parser.add_argument('-H', '--header', action='append', help="Custom headers in 'Key: Value' format")
    parser.add_argument('-d', '--data', help="Raw request body data")
    parser.add_argument('-j', '--json', dest='json_data', help="JSON request body data (sets Content-Type: application/json)")
    parser.add_argument('-v', '--verbose', action='store_true', help="Print request details and response headers")
    parser.add_argument('-o', '--output', help="Save response body to a file")
    parser.add_argument('--timeout', type=float, default=10.0, help="Request timeout in seconds (default: 10.0)")
    parser.add_argument('--insecure', action='store_true', help="Skip SSL/TLS certificate verification")
    
    args = parser.parse_args()
    
    # Ensure scheme is present
    url = args.url
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
        
    headers = parse_headers(args.header)
    
    # Process request data
    data_bytes = None
    if args.json_data:
        try:
            # Validate JSON
            json.loads(args.json_data)
            data_bytes = args.json_data.encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON provided: {e}", file=sys.stderr)
            return 1
    elif args.data:
        data_bytes = args.data.encode('utf-8')
        
    # Configure SSL context
    ctx = None
    if args.insecure:
        ctx = ssl._create_unverified_context()
        
    # Print request log
    if args.verbose:
        print(f"Request: {args.method} {url}")
        for k, v in headers.items():
            print(f"  > {k}: {v}")
        print()
        
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=args.method)
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=args.timeout, context=ctx) as response:
            duration = time.time() - start_time
            body = response.read()
            pretty_print_response(
                response.status,
                response.reason,
                response.getheaders(),
                body,
                duration,
                args.verbose,
                args.output
            )
    except urllib.error.HTTPError as e:
        duration = time.time() - start_time
        body = e.read()
        pretty_print_response(
            e.code,
            e.reason,
            e.headers.items(),
            body,
            duration,
            args.verbose,
            args.output
        )
    except urllib.error.URLError as e:
        print(color_text(f"Error connecting to server: {e.reason}", COLOR_RED), file=sys.stderr)
        return 1
    except TimeoutError:
        print(color_text(f"Error: Connection timed out after {args.timeout} seconds", COLOR_RED), file=sys.stderr)
        return 1
    except Exception as e:
        print(color_text(f"Error: {e}", COLOR_RED), file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
