#!/usr/bin/env python3
"""
JSON Diff Tool
Compares two JSON files and displays the differences recursively, highlighting
additions, deletions, and modifications in a structured format.
"""

import sys
import json
import argparse

# ANSI color codes
COLOR_GREEN = '\033[92m'
COLOR_RED = '\033[91m'
COLOR_YELLOW = '\033[93m'
COLOR_RESET = '\033[0m'

def print_diff(diff_type, path, val1=None, val2=None, use_color=True):
    """Print formatted diff entry."""
    path_str = " -> ".join(str(p) for p in path) if path else "root"
    
    if diff_type == 'added':
        marker = "+"
        color = COLOR_GREEN if use_color else ""
        reset = COLOR_RESET if use_color else ""
        print(f"{color}{marker} [ADDED]   {path_str}: {json.dumps(val2)}{reset}")
    elif diff_type == 'removed':
        marker = "-"
        color = COLOR_RED if use_color else ""
        reset = COLOR_RESET if use_color else ""
        print(f"{color}{marker} [REMOVED] {path_str}: {json.dumps(val1)}{reset}")
    elif diff_type == 'modified':
        marker = "~"
        color = COLOR_YELLOW if use_color else ""
        reset = COLOR_RESET if use_color else ""
        print(f"{color}{marker} [CHANGED] {path_str}: {json.dumps(val1)} => {json.dumps(val2)}{reset}")

def compare_json(obj1, obj2, path, use_color):
    """Recursively compare two JSON objects (dicts, lists, or primitives)."""
    differences = 0
    
    if type(obj1) != type(obj2):
        print_diff('modified', path, obj1, obj2, use_color)
        return 1

    if isinstance(obj1, dict):
        keys1 = set(obj1.keys())
        keys2 = set(obj2.keys())
        
        # Keys removed
        for key in sorted(keys1 - keys2):
            print_diff('removed', path + [key], obj1[key], None, use_color)
            differences += 1
            
        # Keys added
        for key in sorted(keys2 - keys1):
            print_diff('added', path + [key], None, obj2[key], use_color)
            differences += 1
            
        # Common keys
        for key in sorted(keys1 & keys2):
            differences += compare_json(obj1[key], obj2[key], path + [key], use_color)
            
    elif isinstance(obj1, list):
        len1 = len(obj1)
        len2 = len(obj2)
        min_len = min(len1, len2)
        
        for i in range(min_len):
            differences += compare_json(obj1[i], obj2[i], path + [i], use_color)
            
        if len1 > len2:
            for i in range(min_len, len1):
                print_diff('removed', path + [i], obj1[i], None, use_color)
                differences += 1
        elif len2 > len1:
            for i in range(min_len, len2):
                print_diff('added', path + [i], None, obj2[i], use_color)
                differences += 1
                
    else:
        if obj1 != obj2:
            print_diff('modified', path, obj1, obj2, use_color)
            return 1
            
    return differences

def main():
    parser = argparse.ArgumentParser(
        description="JSON Diff Tool - Compare two JSON files recursively",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file1", help="Path to the first JSON file (original)")
    parser.add_argument("file2", help="Path to the second JSON file (modified)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    
    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty()
    
    try:
        with open(args.file1, 'r', encoding='utf-8') as f1:
            json1 = json.load(f1)
    except json.JSONDecodeError as e:
        print(f"Error parsing '{args.file1}': {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading '{args.file1}': {e}", file=sys.stderr)
        return 1

    try:
        with open(args.file2, 'r', encoding='utf-8') as f2:
            json2 = json.load(f2)
    except json.JSONDecodeError as e:
        print(f"Error parsing '{args.file2}': {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading '{args.file2}': {e}", file=sys.stderr)
        return 1

    print(f"Comparing '{args.file1}' and '{args.file2}':")
    print("-" * 60)
    
    diff_count = compare_json(json1, json2, [], use_color)
    
    print("-" * 60)
    if diff_count == 0:
        print("Files are identical.")
    else:
        print(f"Comparison finished. Found {diff_count} difference(s).")
        
    return 0 if diff_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
