#!/usr/bin/env python3
"""
Dotenv Diff

A command-line tool to compare two environment (.env) files, identifying missing
variables in either file and highlighting differences in their values.

Usage:
    python tools/dotenv_diff.py path/to/first.env path/to/second.env [options]
"""

import argparse
import sys
import os
import re

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def parse_env_file(file_path):
    """
    Parses a .env file and returns a dictionary of key-value pairs.
    Handles comments, empty lines, and basic quoted values.
    """
    env_dict = {}
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Match KEY=VALUE (taking care of optional export prefix)
            match = re.match(r'^(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*(.*)$', line)
            if match:
                key, val = match.groups()
                # Strip wrapping quotes if any
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env_dict[key] = val
    return env_dict

def main():
    parser = argparse.ArgumentParser(description="Compare two .env files for key and value discrepancies.")
    parser.add_argument("file_a", help="Path to the first .env file (e.g., .env.example)")
    parser.add_argument("file_b", help="Path to the second .env file (e.g., .env)")
    parser.add_argument("--ignore-values", action="store_true", help="Only check for key existence, ignore value differences")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console output")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    try:
        dict_a = parse_env_file(args.file_a)
        dict_b = parse_env_file(args.file_b)
    except Exception as e:
        print(f"{COLORS['red']}Error: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    keys_a = set(dict_a.keys())
    keys_b = set(dict_b.keys())
    
    only_a = keys_a - keys_b
    only_b = keys_b - keys_a
    common = keys_a & keys_b
    
    diff_values = {}
    if not args.ignore_values:
        for key in common:
            if dict_a[key] != dict_b[key]:
                diff_values[key] = (dict_a[key], dict_b[key])
                
    # Output results
    has_differences = False
    
    print(f"{COLORS['bold']}Dotenv Comparison Results:{COLORS['reset']}")
    print(f"File A (Reference): {COLORS['cyan']}{args.file_a}{COLORS['reset']} ({len(keys_a)} keys)")
    print(f"File B (Target):    {COLORS['cyan']}{args.file_b}{COLORS['reset']} ({len(keys_b)} keys)\n")
    
    if only_a:
        has_differences = True
        print(f"{COLORS['yellow']}Keys present only in File A ({args.file_a}):{COLORS['reset']}")
        for key in sorted(only_a):
            print(f"  - {COLORS['red']}{key}{COLORS['reset']}")
        print()
        
    if only_b:
        has_differences = True
        print(f"{COLORS['yellow']}Keys present only in File B ({args.file_b}):{COLORS['reset']}")
        for key in sorted(only_b):
            print(f"  - {COLORS['green']}{key}{COLORS['reset']}")
        print()
        
    if diff_values:
        has_differences = True
        print(f"{COLORS['yellow']}Value discrepancies (Common keys with different values):{COLORS['reset']}")
        # Find maximum key length for formatting
        max_key_len = max(len(k) for k in diff_values.keys())
        for key in sorted(diff_values.keys()):
            val_a, val_b = diff_values[key]
            # Redact/truncate long values for readability
            val_a_disp = val_a if len(val_a) < 40 else val_a[:37] + "..."
            val_b_disp = val_b if len(val_b) < 40 else val_b[:37] + "..."
            print(f"  {COLORS['bold']}{key:<{max_key_len}}{COLORS['reset']}:")
            print(f"    File A: {COLORS['red']}{val_a_disp}{COLORS['reset']}")
            print(f"    File B: {COLORS['green']}{val_b_disp}{COLORS['reset']}")
        print()
        
    if not has_differences:
        print(f"{COLORS['green']}Success: Both files have matching keys and values!{COLORS['reset']}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
