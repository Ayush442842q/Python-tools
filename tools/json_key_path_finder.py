#!/usr/bin/env python3
"""
JSON Key Path Finder

A command-line tool that scans a nested JSON file and returns the exact paths
(e.g., `root.store.book[0].author`) where a specific key or value (or pattern) is found.

Usage:
    python tools/json_key_path_finder.py path/to/file.json --key search_key
    python tools/json_key_path_finder.py path/to/file.json --value search_val --case-insensitive
"""

import argparse
import sys
import os
import json
import re

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def format_path(path_steps):
    """Formats list of path steps into a readable string (e.g., store.book[0].author)"""
    res = "root"
    for step in path_steps:
        if isinstance(step, int):
            res += f"[{step}]"
        else:
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', step):
                res += f".{step}"
            else:
                res += f"['{step}']"
    return res

def search_json(data, path_steps, key_query, val_query, key_re, val_re, case_insensitive):
    matches = []
    
    # Check dictionary keys
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = path_steps + [k]
            
            # Match Key
            if key_query or key_re:
                matched = False
                if key_re:
                    flags = re.IGNORECASE if case_insensitive else 0
                    if re.search(key_re, k, flags):
                        matched = True
                elif key_query:
                    k_str = k.lower() if case_insensitive else k
                    q_str = key_query.lower() if case_insensitive else key_query
                    if q_str in k_str:
                        matched = True
                
                if matched:
                    # Truncate value representation if dictionary/list
                    v_repr = str(v)
                    if isinstance(v, (dict, list)):
                        v_repr = f"<{type(v).__name__} (len={len(v)})>"
                    matches.append((current_path, "key", k, v_repr))
            
            # Recurse
            matches.extend(search_json(v, current_path, key_query, val_query, key_re, val_re, case_insensitive))
            
    # Check array/list items
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            current_path = path_steps + [idx]
            matches.extend(search_json(item, current_path, key_query, val_query, key_re, val_re, case_insensitive))
            
    # Check leaves (scalar values)
    else:
        if val_query or val_re:
            matched = False
            data_str = str(data)
            if val_re:
                flags = re.IGNORECASE if case_insensitive else 0
                if re.search(val_re, data_str, flags):
                    matched = True
            elif val_query:
                d_str = data_str.lower() if case_insensitive else data_str
                q_str = val_query.lower() if case_insensitive else val_query
                if q_str in d_str:
                    matched = True
            
            if matched:
                # Get the key or index that directly holds this value
                last_step = path_steps[-1] if path_steps else ""
                matches.append((path_steps, "value", last_step, data_str))
                
    return matches

def main():
    parser = argparse.ArgumentParser(description="Find matching key or value paths within a JSON file.")
    parser.add_argument("json_file", help="Path to the JSON file to scan")
    parser.add_argument("-k", "--key", help="Search key names for this substring")
    parser.add_argument("-v", "--value", help="Search string representation of values for this substring")
    parser.add_argument("--key-regex", help="Search key names using this regular expression pattern")
    parser.add_argument("--value-regex", help="Search values using this regular expression pattern")
    parser.add_argument("-i", "--case-insensitive", action="store_true", help="Perform case-insensitive search for substring queries")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console output")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    if not (args.key or args.value or args.key_regex or args.value_regex):
        print(f"{COLORS['red']}Error: Must provide at least one search query: --key, --value, --key-regex, or --value-regex{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(args.json_file):
        print(f"{COLORS['red']}Error: File '{args.json_file}' not found.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as jde:
        print(f"{COLORS['red']}JSON Decode Error: {jde}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{COLORS['red']}Error reading file: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    # Run the search
    matches = search_json(
        data,
        path_steps=[],
        key_query=args.key,
        val_query=args.value,
        key_re=args.key_regex,
        val_re=args.value_regex,
        case_insensitive=args.case_insensitive
    )
    
    if not matches:
        print(f"{COLORS['yellow']}No matching keys or values found.{COLORS['reset']}")
        sys.exit(0)
        
    print(f"{COLORS['bold']}Found {len(matches)} matches in '{args.json_file}':{COLORS['reset']}\n")
    
    # Format matches
    for path, match_type, matched_token, value_repr in matches:
        path_str = format_path(path)
        if match_type == "key":
            print(f"Path:  {COLORS['cyan']}{path_str}{COLORS['reset']}")
            print(f"Type:  {COLORS['yellow']}Matched Key Name{COLORS['reset']} -> '{COLORS['bold']}{matched_token}{COLORS['reset']}'")
            print(f"Value: {value_repr}")
        else:
            print(f"Path:  {COLORS['cyan']}{path_str}{COLORS['reset']}")
            print(f"Type:  {COLORS['magenta']}Matched Value{COLORS['reset']}")
            print(f"Value: {COLORS['green']}{value_repr}{COLORS['reset']}")
        print("-" * 60)

if __name__ == "__main__":
    main()
