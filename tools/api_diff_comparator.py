#!/usr/bin/env python3
"""
API Response Schema & Diff Comparator - Compare HTTP response payloads or local JSON
files recursively to highlight schema changes, type mismatches, and value differences.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import argparse
from collections import OrderedDict

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def fetch_payload(target, method="GET", headers=None, data=None):
    """Fetch JSON from a URL or load from a local file path."""
    if headers is None:
        headers = {}
    
    # Check if target is a local file
    if os.path.exists(target) and os.path.isfile(target):
        with open(target, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    # Treat as URL
    req_data = None
    if data:
        if isinstance(data, str):
            req_data = data.encode('utf-8')
        else:
            req_data = json.dumps(data).encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(target, data=req_data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_bytes = response.read()
            resp_str = resp_bytes.decode('utf-8')
            return json.loads(resp_str)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e else ""
        raise Exception(f"HTTP Error {e.code}: {e.reason}\nResponse Body: {body}")
    except Exception as e:
        raise Exception(f"Failed to fetch from '{target}': {e}")

class JsonDiffEngine:
    def __init__(self, ignore_values=False):
        self.ignore_values = ignore_values
        self.diffs = []

    def diff(self, obj1, obj2, path="root"):
        """Recursively calculate differences between two JSON structures."""
        type1 = type(obj1)
        type2 = type(obj2)

        # 1. Type Mismatch
        if type1 != type2:
            self.diffs.append({
                'path': path,
                'type': 'Type Mismatch',
                'description': f"Type is '{type1.__name__}' in Target A, but '{type2.__name__}' in Target B",
                'val1': obj1,
                'val2': obj2
            })
            return

        # 2. Dictionary / Object Comparison
        if isinstance(obj1, dict):
            keys1 = set(obj1.keys())
            keys2 = set(obj2.keys())

            # Missing keys in Target B
            missing_in_b = keys1 - keys2
            for key in missing_in_b:
                self.diffs.append({
                    'path': f"{path}.{key}",
                    'type': 'Missing Key in B',
                    'description': f"Key '{key}' is present in Target A, but missing in Target B",
                    'val1': obj1[key],
                    'val2': None
                })

            # Added keys in Target B
            added_in_b = keys2 - keys1
            for key in added_in_b:
                self.diffs.append({
                    'path': f"{path}.{key}",
                    'type': 'Added Key in B',
                    'description': f"Key '{key}' is missing in Target A, but added in Target B",
                    'val1': None,
                    'val2': obj2[key]
                })

            # Recurse common keys
            common_keys = keys1 & keys2
            for key in sorted(common_keys):
                self.diff(obj1[key], obj2[key], path=f"{path}.{key}")

        # 3. List / Array Comparison
        elif isinstance(obj1, list):
            len1 = len(obj1)
            len2 = len(obj2)

            if len1 != len2:
                self.diffs.append({
                    'path': path,
                    'type': 'Array Length Mismatch',
                    'description': f"Array length is {len1} in Target A, but {len2} in Target B",
                    'val1': len1,
                    'val2': len2
                })

            # Compare elements up to minimum length
            for idx in range(min(len1, len2)):
                self.diff(obj1[idx], obj2[idx], path=f"{path}[{idx}]")

        # 4. Primitive Values Comparison
        else:
            if not self.ignore_values and obj1 != obj2:
                self.diffs.append({
                    'path': path,
                    'type': 'Value Mismatch',
                    'description': f"Value is '{obj1}' in Target A, but '{obj2}' in Target B",
                    'val1': obj1,
                    'val2': obj2
                })

def format_value(val):
    """Format JSON values cleanly for display."""
    if val is None:
        return "null"
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)

def main():
    parser = argparse.ArgumentParser(description="API Response Schema & Diff Comparator")
    parser.add_argument("target_a", help="URL or local JSON file path for Target A (Base)")
    parser.add_argument("target_b", help="URL or local JSON file path for Target B (Comparison)")
    parser.add_argument("-X", "--method", default="GET", help="HTTP Request Method (GET, POST, PUT, DELETE) - default GET")
    parser.add_argument("-H", "--header", action="append", help="HTTP Request Header in 'Key: Value' format")
    parser.add_argument("-d", "--data", help="Request HTTP payload data/body string (for POST/PUT)")
    parser.add_argument("--ignore-values", action="store_true", help="Only check schema and type differences, ignore value diffs")
    args = parser.parse_args()

    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_cyan = get_color('cyan')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    # Parse headers
    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()

    print(f"{c_bold}{c_cyan}======================================================================{c_reset}")
    print(f"{c_bold}{c_green}                    API Response Diff Comparator                      {c_reset}")
    print(f"{c_bold}{c_cyan}======================================================================{c_reset}")

    # Fetch Target A
    print(f"Fetching Target A: {args.target_a}")
    try:
        payload_a = fetch_payload(args.target_a, args.method, headers, args.data)
        print(f"{c_green}✓ Target A loaded successfully.{c_reset}")
    except Exception as e:
        print(f"{c_red}Error fetching Target A: {e}{c_reset}")
        sys.exit(1)

    # Fetch Target B
    print(f"Fetching Target B: {args.target_b}")
    try:
        payload_b = fetch_payload(args.target_b, args.method, headers, args.data)
        print(f"{c_green}✓ Target B loaded successfully.{c_reset}")
    except Exception as e:
        print(f"{c_red}Error fetching Target B: {e}{c_reset}")
        sys.exit(1)

    print("-" * 70)

    # Compare
    engine = JsonDiffEngine(ignore_values=args.ignore_values)
    engine.diff(payload_a, payload_b)

    if not engine.diffs:
        print(f"\n{c_green}✓ PERFECT MATCH: No differences found between Target A and Target B!{c_reset}")
        print(f"{c_bold}{c_cyan}======================================================================{c_reset}")
        sys.exit(0)

    # Print differences
    print(f"\n{c_yellow}Detected {len(engine.diffs)} differences:{c_reset}\n")
    
    # Header row
    print(f"{c_bold}{'JSON Path':<25} {'Diff Type':<20} {'Details'}{c_reset}")
    print("-" * 80)
    
    for diff in engine.diffs:
        # Style type
        if diff['type'] == 'Type Mismatch':
            diff_type_str = f"{c_red}{diff['type']:<20}{c_reset}"
        elif 'Missing' in diff['type']:
            diff_type_str = f"{c_yellow}{diff['type']:<20}{c_reset}"
        else:
            diff_type_str = f"{c_cyan}{diff['type']:<20}{c_reset}"

        print(f"{diff['path']:<25} {diff_type_str} {diff['description']}")
        if diff['val1'] is not None or diff['val2'] is not None:
            print(f"   Value A: {c_green}{format_value(diff['val1'])}{c_reset}")
            print(f"   Value B: {c_red}{format_value(diff['val2'])}{c_reset}")
            print()

    print(f"{c_bold}{c_cyan}======================================================================{c_reset}")
    print(f"{c_yellow}STATUS: DIFFERENCES DETECTED ({len(engine.diffs)} issues){c_reset}")
    sys.exit(1)

if __name__ == "__main__":
    main()
