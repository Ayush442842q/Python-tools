#!/usr/bin/env python3
"""
JSON Formatter and Validator
Formats JSON data and validates its syntax.
"""
import argparse
import json
import sys

def format_json(json_str, indent=2, sort_keys=False):
    """Format JSON string with specified indentation and sorting."""
    try:
        data = json.loads(json_str)
        formatted = json.dumps(data, indent=indent, sort_keys=sort_keys)
        return formatted
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON - {e}"

def main():
    parser = argparse.ArgumentParser(description='Format and validate JSON data.')
    parser.add_argument('input', nargs='?', help='Input JSON string or file path (if omitted, reads from stdin)')
    parser.add_argument('-i', '--indent', type=int, default=2, help='Indentation level (default: 2)')
    parser.add_argument('-s', '--sort', action='store_true', help='Sort keys in output')
    parser.add_argument('-f', '--file', action='store_true', help='Treat input as a file path')
    
    args = parser.parse_args()
    
    # Read input
    if args.input is None:
        json_str = sys.stdin.read()
    elif args.file:
        try:
            with open(args.input, 'r') as f:
                json_str = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.input}' not found.", file=sys.stderr)
            sys.exit(1)
    else:
        json_str = args.input
    
    # Format JSON
    result = format_json(json_str, indent=args.indent, sort_keys=args.sort)
    
    if result.startswith("Error:"):
        print(result, file=sys.stderr)
        sys.exit(1)
    else:
        print(result)

if __name__ == '__main__':
    main()
