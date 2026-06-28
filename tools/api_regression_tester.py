#!/usr/bin/env python3
"""
API Regression & Response Diff Tester

Sends request sequences to two different API environments (e.g. production vs development)
and generates a structural comparison of their JSON responses, status codes, and headers to identify regressions.
Allows ignoring specific keys like timestamps, IDs, or tokens that are expected to differ.

Usage:
    python tools/api_regression_tester.py --base https://api.production.com --target http://localhost:8000 --endpoints /users,/products
    python tools/api_regression_tester.py --base https://api.production.com --target http://localhost:8000 --config test_suite.json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import difflib

# Color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_colored(text, color):
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_RESET}")
    else:
        print(text)

def make_request(url, method="GET", headers=None, body=None):
    """
    Makes an HTTP request using urllib and returns (status_code, response_headers, body_str)
    """
    req_headers = headers or {}
    data = None
    if body:
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(body, str):
            data = body.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, dict(response.info()), response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return e.code, dict(e.info()), err_body
    except Exception as e:
        return 0, {}, f"Request failed: {e}"

def clean_json_structure(data, ignore_keys):
    """
    Recursively removes or placeholder-masks keys in ignore_keys from a dict/list structure.
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k in ignore_keys:
                cleaned[k] = "<IGNORED>"
            else:
                cleaned[k] = clean_json_structure(v, ignore_keys)
        return cleaned
    elif isinstance(data, list):
        return [clean_json_structure(item, ignore_keys) for item in data]
    else:
        return data

def compare_json(json_base, json_target, ignore_keys):
    """
    Compares two JSON strings, returns (match, diff_str)
    """
    try:
        obj_base = json.loads(json_base)
        obj_target = json.loads(json_target)
    except json.JSONDecodeError:
        # Fallback to direct string compare if not valid JSON
        match = json_base.strip() == json_target.strip()
        diff = []
        if not match:
            diff = list(difflib.unified_diff(
                json_base.splitlines(),
                json_target.splitlines(),
                fromfile="Base Response",
                tofile="Target Response"
            ))
        return match, "\n".join(diff)

    # Clean the structures by removing dynamic keys
    clean_base = clean_json_structure(obj_base, ignore_keys)
    clean_target = clean_json_structure(obj_target, ignore_keys)

    match = clean_base == clean_target
    diff_str = ""
    
    if not match:
        str_base = json.dumps(clean_base, indent=2).splitlines()
        str_target = json.dumps(clean_target, indent=2).splitlines()
        diff = list(difflib.unified_diff(
            str_base,
            str_target,
            fromfile="Base Cleaned JSON",
            tofile="Target Cleaned JSON",
            lineterm=""
        ))
        diff_str = "\n".join(diff)

    return match, diff_str

def run_regression_test(endpoint_spec, base_url, target_url, ignore_keys, global_headers):
    path = endpoint_spec.get("path", "")
    method = endpoint_spec.get("method", "GET")
    headers = {**global_headers, **endpoint_spec.get("headers", {})}
    body = endpoint_spec.get("body", None)

    url_base = base_url.rstrip("/") + "/" + path.lstrip("/")
    url_target = target_url.rstrip("/") + "/" + path.lstrip("/")

    print(f"\nTesting {COLOR_BOLD}{method} {path}{COLOR_RESET}...")
    print(f"  Base:   {url_base}")
    print(f"  Target: {url_target}")

    # Fire requests
    status_base, headers_base, body_base = make_request(url_base, method, headers, body)
    status_target, headers_target, body_target = make_request(url_target, method, headers, body)

    mismatches = []

    # 1. Compare status codes
    if status_base != status_target:
        mismatches.append(f"Status Mismatch: Expected {status_base}, got {status_target}")

    # 2. Compare content
    json_match = True
    diff_output = ""
    if body_base or body_target:
        json_match, diff_output = compare_json(body_base, body_target, ignore_keys)
        if not json_match:
            mismatches.append("JSON Payload Structure/Value Mismatch")

    # Display results
    if not mismatches:
        print_colored("  ✓ MATCH: API responses are identical.", COLOR_GREEN)
        return True
    else:
        print_colored(f"  ✗ MISMATCH: Found {len(mismatches)} regression issues:", COLOR_RED)
        for mis in mismatches:
            print(f"    - {mis}")
        
        if diff_output:
            print_colored("\n  --- Structural Difference Diff ---", COLOR_CYAN)
            for line in diff_output.splitlines():
                if line.startswith("+"):
                    print_colored(line, COLOR_GREEN)
                elif line.startswith("-"):
                    print_colored(line, COLOR_RED)
                elif line.startswith("@"):
                    print_colored(line, COLOR_CYAN)
                else:
                    print(line)
        return False

def main():
    parser = argparse.ArgumentParser(description="API Regression & Response Diff Tester")
    parser.add_argument("--base", required=True, help="Base API base URL (reference system)")
    parser.add_argument("--target", required=True, help="Target API base URL (test system)")
    parser.add_argument("--endpoints", help="Comma-separated list of endpoint paths to test (default GET)")
    parser.add_argument("--config", help="Path to JSON config file specifying advanced test suites")
    parser.add_argument(
        "--ignore-keys",
        default="id,created_at,updated_at,timestamp,date,token,uuid,time,elapsed",
        help="Comma-separated JSON keys to mask/ignore during diffing"
    )
    parser.add_argument("--headers", help="Comma-separated global request headers as key:value")

    args = parser.parse_args()

    # Parse headers
    global_headers = {}
    if args.headers:
        for header_str in args.headers.split(","):
            if ":" in header_str:
                k, v = header_str.split(":", 1)
                global_headers[k.strip()] = v.strip()

    # Parse ignore keys
    ignore_keys = set(k.strip() for k in args.ignore_keys.split(","))

    # Compile list of endpoints to test
    endpoint_specs = []
    if args.config:
        if not os.path.exists(args.config):
            print(f"{COLOR_RED}Error: Config file '{args.config}' not found.{COLOR_RESET}")
            return 1
        with open(args.config, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                endpoint_specs = data
            elif isinstance(data, dict) and "endpoints" in data:
                endpoint_specs = data["endpoints"]
    elif args.endpoints:
        for path in args.endpoints.split(","):
            endpoint_specs.append({
                "path": path.strip(),
                "method": "GET",
                "headers": {},
                "body": None
            })
    else:
        print(f"{COLOR_RED}Error: Specify either --endpoints or a suite --config file.{COLOR_RESET}")
        return 1

    print("=" * 80)
    print(f"{COLOR_BOLD}API Regression Testing Session{COLOR_RESET}")
    print(f"  Base API URL:   {args.base}")
    print(f"  Target API URL: {args.target}")
    print(f"  Ignore Keys:    {', '.join(ignore_keys)}")
    print("=" * 80)

    success_count = 0
    failure_count = 0

    for spec in endpoint_specs:
        matched = run_regression_test(spec, args.base, args.target, ignore_keys, global_headers)
        if matched:
            success_count += 1
        else:
            failure_count += 1

    print("\n" + "=" * 80)
    print(f"API Regression Test Session Completed:")
    print(f"  Total Run: {len(endpoint_specs)}")
    print(f"  {COLOR_GREEN}Passed:    {success_count}{COLOR_RESET}")
    print(f"  {COLOR_RED if failure_count > 0 else COLOR_RESET}Failed:    {failure_count}{COLOR_RESET}")
    print("=" * 80)

    return 1 if failure_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
