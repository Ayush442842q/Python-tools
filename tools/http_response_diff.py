#!/usr/bin/env python3
"""
HTTP Response & API Endpoint Comparator Tool

Compares two HTTP API endpoints or saved HTTP response files (headers, status codes, response time,
and JSON payload structures), rendering side-by-side or unified structural diffs with ANSI highlights.
"""

import os
import sys
import json
import time
import difflib
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional, List

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def fetch_or_load(target: str, timeout: float = 10.0, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, str], str, float]:
    """
    Fetch URL or load file.
    Returns: (status_code, response_headers, body_text, response_time_ms)
    """
    if target.startswith('http://') or target.startswith('https://'):
        req = urllib.request.Request(target, headers=headers or {'User-Agent': 'HTTP-Response-Diff/1.0'})
        start_t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                elapsed = (time.time() - start_t) * 1000.0
                body = response.read().decode('utf-8', errors='replace')
                res_headers = {k.lower(): v for k, v in response.headers.items()}
                return response.status, res_headers, body, elapsed
        except urllib.error.HTTPError as e:
            elapsed = (time.time() - start_t) * 1000.0
            body = e.read().decode('utf-8', errors='replace')
            res_headers = {k.lower(): v for k, v in e.headers.items()}
            return e.code, res_headers, body, elapsed
        except Exception as e:
            raise RuntimeError(f"Failed to fetch '{target}': {e}")
    else:
        if not os.path.exists(target):
            raise FileNotFoundError(f"File '{target}' not found.")
        start_t = time.time()
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        elapsed = (time.time() - start_t) * 1000.0
        return 200, {'content-type': 'text/plain'}, content, elapsed


def diff_headers(h1: Dict[str, str], h2: Dict[str, str], ignore_keys: List[str]) -> List[str]:
    """Diff two header sets ignoring specified volatile header keys."""
    diffs = []
    ignore_set = {k.lower() for k in ignore_keys}

    all_keys = sorted(list(set(h1.keys()) | set(h2.keys())))
    for k in all_keys:
        if k in ignore_set:
            continue
        v1 = h1.get(k)
        v2 = h2.get(k)
        if v1 != v2:
            if v1 is None:
                diffs.append(f"  {GREEN}+ Header '{k}': missing in A -> '{v2}' in B{RESET}")
            elif v2 is None:
                diffs.append(f"  {RED}- Header '{k}': '{v1}' in A -> missing in B{RESET}")
            else:
                diffs.append(f"  {YELLOW}~ Header '{k}': '{v1}' (A) vs '{v2}' (B){RESET}")
    return diffs


def format_json_if_possible(body: str) -> str:
    """Pretty print JSON string if valid, else return as-is."""
    try:
        data = json.loads(body)
        return json.dumps(data, indent=2, sort_keys=True)
    except Exception:
        return body


def compare_responses(target_a: str, target_b: str, ignore_headers: List[str], timeout: float):
    print(f"{BOLD}{CYAN}Fetching & Analyzing Targets...{RESET}")
    print(f"  Target A: {target_a}")
    print(f"  Target B: {target_b}\n")

    code_a, head_a, body_a, time_a = fetch_or_load(target_a, timeout=timeout)
    code_b, head_b, body_b, time_b = fetch_or_load(target_b, timeout=timeout)

    print(f"{BOLD}=== 1. Summary Comparison ==={RESET}")
    status_color_a = GREEN if code_a < 400 else RED
    status_color_b = GREEN if code_b < 400 else RED
    print(f"Status Code  : Target A ({status_color_a}{code_a}{RESET}) | Target B ({status_color_b}{code_b}{RESET})")
    print(f"Latency      : Target A ({time_a:.1f}ms) | Target B ({time_b:.1f}ms)\n")

    print(f"{BOLD}=== 2. Headers Comparison ==={RESET}")
    header_diffs = diff_headers(head_a, head_b, ignore_headers)
    if not header_diffs:
        print(f"  {GREEN}✓ Headers are identical (excluding ignored headers).{RESET}")
    else:
        for line in header_diffs:
            print(line)

    print(f"\n{BOLD}=== 3. Response Body Diff ==={RESET}")
    formatted_a = format_json_if_possible(body_a).splitlines()
    formatted_b = format_json_if_possible(body_b).splitlines()

    diff_lines = list(difflib.unified_diff(
        formatted_a, formatted_b,
        fromfile="Target_A", tofile="Target_B",
        lineterm=""
    ))

    if not diff_lines:
        print(f"  {GREEN}✓ Response bodies are identical.{RESET}")
    else:
        for line in diff_lines[:100]: # Limit diff to first 100 lines
            if line.startswith('+') and not line.startswith('+++'):
                print(f"{GREEN}{line}{RESET}")
            elif line.startswith('-') and not line.startswith('---'):
                print(f"{RED}{line}{RESET}")
            elif line.startswith('@@'):
                print(f"{CYAN}{line}{RESET}")
            else:
                print(line)
        if len(diff_lines) > 100:
            print(f"{YELLOW}... ({len(diff_lines) - 100} more diff lines omitted){RESET}")


def main():
    parser = argparse.ArgumentParser(description="Compare two HTTP API endpoints or saved HTTP response files.")
    parser.add_argument("target_a", help="First URL or local file path")
    parser.add_argument("target_b", help="Second URL or local file path")
    parser.add_argument("-i", "--ignore-header", action="append", default=["date", "x-request-id", "set-cookie", "age", "server"],
                        help="Header names to ignore during comparison")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="HTTP request timeout in seconds")

    args = parser.parse_args()

    try:
        compare_responses(args.target_a, args.target_b, args.ignore_header, args.timeout)
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
