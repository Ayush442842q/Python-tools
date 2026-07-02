#!/usr/bin/env python3
"""
JSON Malformed Repairer

Scan, repair, and format malformed JSON files. It resolves common JSON errors:
- Single quotes instead of double quotes
- Unquoted keys (e.g., {name: "value"})
- Trailing commas in objects or lists (e.g., [1, 2, 3,])
- Javascript comments (// inline or /* block */)
- Missing commas between elements

Usage:
    python tools/json_malformed_repairer.py malformed.json -o repaired.json

Requirements:
    - Python 3.6+
"""

import os
import sys
import re
import json
import argparse

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    if enabled:
        print(f"{color}{text}{RESET}", file=sys.stderr)
    else:
        print(text, file=sys.stderr)

def strip_comments(text):
    """Strip JavaScript-style comments (// and /* */) without affecting strings."""
    result = []
    i = 0
    n = len(text)
    in_string = False
    string_char = None
    escaped = False

    while i < n:
        char = text[i]

        # Handle string escape
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == string_char:
                in_string = False
            result.append(char)
            i += 1
            continue

        # Detect string start
        if char in ('"', "'"):
            in_string = True
            string_char = char
            result.append(char)
            i += 1
            continue

        # Detect inline comment
        if i + 1 < n and char == '/' and text[i + 1] == '/':
            # Skip until newline
            i += 2
            while i < n and text[i] != '\n':
                i += 1
            continue

        # Detect block comment
        if i + 1 < n and char == '/' and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2 # Skip the closing */
            continue

        result.append(char)
        i += 1

    return "".join(result)

def repair_json_syntax(text):
    """Repair quotes, unquoted keys, and trailing commas using a tokenizer/replacer approach."""
    # Strip comments first
    text = strip_comments(text)
    
    # 1. Clean trailing commas in objects and arrays: e.g. ,} -> } and ,] -> ]
    # We do a simple regex cleanup, but need to make sure we don't hit strings.
    # To do this safely, we can replace trailing commas inside brackets.
    text = re.sub(r',\s*\}', '}', text)
    text = re.sub(r',\s*\]', ']', text)

    # 2. Repair single quotes to double quotes, and handle unquoted keys.
    # Let's walk the string with a state machine to safely identify keys and string bounds.
    repaired = []
    i = 0
    n = len(text)
    in_single_str = False
    in_double_str = False
    escaped = False

    while i < n:
        char = text[i]

        if in_single_str:
            if escaped:
                escaped = False
                repaired.append(char)
            elif char == '\\':
                escaped = True
                repaired.append(char)
            elif char == "'":
                in_single_str = False
                repaired.append('"') # Swap single quote closure to double quote
            else:
                # Escape internal unescaped double quotes inside this string
                if char == '"':
                    repaired.append('\\"')
                elif char == '\n':
                    repaired.append('\\n') # JSON strings cannot have raw newlines
                elif char == '\t':
                    repaired.append('\\t')
                else:
                    repaired.append(char)
            i += 1
            continue

        if in_double_str:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_double_str = False
            repaired.append(char)
            i += 1
            continue

        # Outside of strings
        if char == "'":
            in_single_str = True
            repaired.append('"') # Start string with double quote
            i += 1
            continue
        elif char == '"':
            in_double_str = True
            repaired.append('"')
            i += 1
            continue

        # Look for unquoted keys: e.g., { name: "val" } or { foo_bar : 12 }
        # Match alphanumeric word followed by optional space and colon
        # But only if it seems to be in a key position (following { or ,)
        # We can run a look-ahead or regex match
        remaining = text[i:]
        # Match word characters starting with letter/underscore, followed by colon
        key_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:", remaining)
        if key_match:
            key_name = key_match.group(1)
            repaired.append(f'"{key_name}":')
            i += len(key_match.group(0))
            continue

        repaired.append(char)
        i += 1

    repaired_str = "".join(repaired)
    
    # 3. Handle missing commas between list items or object pairs (e.g. "a": 1 "b": 2)
    # This is a bit trickier, but we can do a regex check for:
    # double quote / number / boolean followed by white space and then key/value start
    repaired_str = re.sub(r'("|\d+|true|false|null)\s*\n\s*("|[a-zA-Z_\[\{])', r'\1,\n\2', repaired_str)
    
    # Run a final sweep for trailing commas that might have been introduced
    repaired_str = re.sub(r',\s*\}', '}', repaired_str)
    repaired_str = re.sub(r',\s*\]', ']', repaired_str)
    
    return repaired_str

def main():
    parser = argparse.ArgumentParser(
        description="Repair common syntax issues in malformed JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to malformed JSON file")
    parser.add_argument("-o", "--output", help="Path to output repaired JSON file. If omitted, prints to stdout")
    parser.add_argument("-i", "--indent", type=int, default=4, help="JSON formatting indent spaces (default: 4, use 0 for minified)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the original file with repaired JSON")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    if not os.path.exists(args.file):
        print_colored(f"Error: File not found: {args.file}", RED, use_color)
        return 1

    try:
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print_colored(f"Error reading file: {e}", RED, use_color)
        return 1

    # Check if already valid
    already_valid = False
    try:
        json.loads(content)
        already_valid = True
    except Exception:
        pass

    if already_valid:
        print_colored("File is already valid JSON. No repairs needed.", GREEN, use_color)
        if args.overwrite or args.output:
            # Format anyway
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=args.indent if args.indent > 0 else None)
            target = args.file if args.overwrite else args.output
            with open(target, "w", encoding="utf-8") as f:
                f.write(formatted + "\n")
            print_colored(f"Formatted and saved to {target}.", BLUE, use_color)
        else:
            print(content)
        return 0

    # Attempt repairs
    repaired_str = repair_json_syntax(content)
    
    try:
        # Validate repaired JSON
        repaired_json = json.loads(repaired_str)
        success = True
    except json.JSONDecodeError as jde:
        success = False
        print_colored("Failed to repair automatically. JSON is still malformed.", RED, use_color)
        print_colored(f"Parser error details: {jde}", RED, use_color)
        # Print a snippet of where the error occurred
        lines = repaired_str.splitlines()
        err_line = jde.lineno
        err_col = jde.colno
        print_colored("\nRepaired output snippet around error:", YELLOW, use_color)
        for idx in range(max(0, err_line - 3), min(len(lines), err_line + 2)):
            prefix = "--> " if idx == err_line - 1 else "    "
            print(f"{prefix}{idx+1}: {lines[idx]}")
            if idx == err_line - 1:
                print(" " * (len(prefix) + len(str(idx+1)) + 2 + err_col) + "^")
        return 1

    # If successfully repaired
    print_colored("JSON successfully repaired!", GREEN, use_color)
    
    indent = args.indent if args.indent > 0 else None
    formatted_output = json.dumps(repaired_json, indent=indent) + "\n"

    if args.overwrite:
        target = args.file
    elif args.output:
        target = args.output
    else:
        target = None

    if target:
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(formatted_output)
            print_colored(f"Saved repaired JSON to '{target}'.", GREEN, use_color)
        except Exception as e:
            print_colored(f"Error saving to file: {e}", RED, use_color)
            return 1
    else:
        print(formatted_output)

    return 0

if __name__ == "__main__":
    sys.exit(main())
