#!/usr/bin/env python3
"""
Markdown Frontmatter Validator

A tool to validate the YAML frontmatter header of Markdown files recursively
in a directory against user-defined structural rules (required fields, expected data types,
and date formats).

Usage:
    python tools/markdown_frontmatter_validator.py path/to/folder --require title date tags --types date:date tags:list draft:boolean
"""

import argparse
import sys
import os
import re
from datetime import datetime

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

def parse_simple_yaml(yaml_text):
    """
    Helper to parse simple YAML into a Python dictionary.
    Handles standard scalar values, inline lists, and bulleted lists.
    """
    metadata = {}
    lines = yaml_text.strip().split('\n')
    current_key = None
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        if line_stripped.startswith('- ') and current_key is not None:
            val = line_stripped[2:].strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if isinstance(metadata[current_key], list):
                metadata[current_key].append(val)
            else:
                metadata[current_key] = [val]
            continue
            
        match = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_stripped)
        if match:
            key, val = match.groups()
            val = val.strip()
            
            if val.startswith('[') and val.endswith(']'):
                items = [item.strip() for item in val[1:-1].split(',')]
                cleaned_items = []
                for item in items:
                    if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                        item = item[1:-1]
                    cleaned_items.append(item)
                metadata[key] = cleaned_items
                current_key = key
            else:
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                
                # Try conversions
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.isdigit():
                    val = int(val)
                metadata[key] = val
                current_key = key
        else:
            if current_key and line_stripped:
                if isinstance(metadata[current_key], str):
                    metadata[current_key] += " " + line_stripped
    return metadata

def check_frontmatter(file_path):
    """Reads file and returns frontmatter dict, raw match info, or error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, f"Could not read file: {e}"
        
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None, "Missing YAML frontmatter header (must start and end with '---')"
        
    yaml_text = match.group(1)
    try:
        data = parse_simple_yaml(yaml_text)
        return data, None
    except Exception as e:
        return None, f"YAML parsing error: {e}"

def validate_types(key, value, expected_type, date_format):
    """Validates value data type and returns error message or None."""
    if expected_type == "string":
        if not isinstance(value, str):
            return f"'{key}' must be a string (got {type(value).__name__})"
    elif expected_type == "list":
        if not isinstance(value, list):
            return f"'{key}' must be a list (got {type(value).__name__})"
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            return f"'{key}' must be a boolean (got {type(value).__name__})"
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"'{key}' must be a number (got {type(value).__name__})"
    elif expected_type == "date":
        # Convert date to string first to check format
        val_str = str(value)
        try:
            datetime.strptime(val_str, date_format)
        except ValueError:
            return f"'{key}' has invalid date format '{val_str}' (expected '{date_format}')"
    return None

def main():
    parser = argparse.ArgumentParser(description="Validate Markdown frontmatter header metadata.")
    parser.add_argument("directory", help="Directory containing Markdown files to scan")
    parser.add_argument("--require", nargs="+", default=[], help="List of required frontmatter key names")
    parser.add_argument("--types", nargs="+", default=[], help="Specify types for keys as key:type (types: string, list, boolean, number, date)")
    parser.add_argument("--date-format", default="%Y-%m-%d", help="Date format to check date-typed fields (default: %%Y-%%m-%%d)")
    parser.add_argument("--no-color", action="store_true", help="Disable console colors")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    if not os.path.isdir(args.directory):
        print(f"{COLORS['red']}Error: '{args.directory}' is not a valid directory.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    # Parse expected types
    type_rules = {}
    valid_types = {"string", "list", "boolean", "number", "date"}
    for rule in args.types:
        if ':' not in rule:
            print(f"{COLORS['red']}Error: Type rule '{rule}' must be formatted as key:type.{COLORS['reset']}", file=sys.stderr)
            sys.exit(1)
        k, t = rule.split(':', 1)
        t = t.lower()
        if t not in valid_types:
            print(f"{COLORS['red']}Error: Invalid type '{t}'. Allowed: {', '.join(valid_types)}{COLORS['reset']}", file=sys.stderr)
            sys.exit(1)
        type_rules[k] = t
        
    print(f"Scanning directory: {COLORS['cyan']}{args.directory}{COLORS['reset']}")
    print(f"Validation rules: Required={args.require}, Types={type_rules}\n")
    
    failed_files = 0
    total_files = 0
    
    for root, _, files in os.walk(args.directory):
        for file in files:
            if file.endswith('.md'):
                total_files += 1
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, args.directory)
                
                metadata, err = check_frontmatter(full_path)
                file_errors = []
                
                if err:
                    file_errors.append(err)
                else:
                    # 1. Check required keys
                    for req_key in args.require:
                        if req_key not in metadata:
                            file_errors.append(f"Missing required key: '{req_key}'")
                            
                    # 2. Check types
                    for k, v in metadata.items():
                        if k in type_rules:
                            type_err = validate_types(k, v, type_rules[k], args.date_format)
                            if type_err:
                                file_errors.append(type_err)
                                
                if file_errors:
                    failed_files += 1
                    print(f"[{COLORS['red']}FAIL{COLORS['reset']}] {COLORS['bold']}{rel_path}{COLORS['reset']}")
                    for e in file_errors:
                        print(f"  - {COLORS['yellow']}{e}{COLORS['reset']}")
                else:
                    # Verbose pass logging optional, let's print simple success
                    pass
                    
    print("\n" + "=" * 50)
    print(f"Total Markdown Files Scanned: {total_files}")
    if failed_files > 0:
        print(f"Validation Result: {COLORS['red']}{COLORS['bold']}FAILED{COLORS['reset']} ({failed_files} files did not pass validation)")
        sys.exit(1)
    else:
        print(f"Validation Result: {COLORS['green']}{COLORS['bold']}PASSED{COLORS['reset']} (all files conform to rules!)")
        sys.exit(0)

if __name__ == "__main__":
    main()
