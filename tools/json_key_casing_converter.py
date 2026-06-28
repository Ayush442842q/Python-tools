#!/usr/bin/env python3
"""
JSON Key Casing Converter
Recursively converts all keys in a JSON file to a specified casing style
(camelCase, snake_case, pascalCase, kebab-case, UPPERCASE).
"""

import re
import sys
import json
import argparse
from typing import Any, Dict, List, Union

def to_snake_case(s: str) -> str:
    """Convert any string to snake_case."""
    # Handle camelCase/PascalCase boundaries
    s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    s = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s)
    # Replace spaces, hyphens, and periods with underscores
    s = re.sub(r'[-\s\.]+', '_', s)
    # Remove any duplicate underscores or leading/trailing underscores
    s = re.sub(r'_+', '_', s)
    return s.lower().strip('_')

def convert_string(s: str, target: str) -> str:
    """Convert a string to the target casing format."""
    if not s or s.isspace():
        return s
        
    snake = to_snake_case(s)
    parts = snake.split('_')
    
    if target == 'snake_case':
        return snake
    elif target == 'camelCase':
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])
    elif target == 'pascalCase':
        return ''.join(p.capitalize() for p in parts)
    elif target == 'kebab-case':
        return '-'.join(parts)
    elif target == 'UPPERCASE':
        return snake.upper()
    elif target == 'lowercase':
        return ''.join(parts).lower()
    else:
        raise ValueError(f"Unknown target casing: {target}")

def convert_json_keys(data: Any, target: str) -> Any:
    """Recursively convert all keys in a JSON structure."""
    if isinstance(data, dict):
        new_dict = {}
        for key, val in data.items():
            new_key = convert_string(str(key), target) if isinstance(key, str) else key
            new_dict[new_key] = convert_json_keys(val, target)
        return new_dict
    elif isinstance(data, list):
        return [convert_json_keys(item, target) for item in data]
    else:
        return data

def main():
    parser = argparse.ArgumentParser(
        description="Recursively convert all keys in a JSON structure to a specified casing style.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Casing formats:
  camelCase    ->  userFirstName
  snake_case   ->  user_first_name
  pascalCase   ->  UserFirstName
  kebab-case   ->  user-first-name
  UPPERCASE    ->  USER_FIRST_NAME
  lowercase    ->  userfirstname

Examples:
  python json_key_casing_converter.py input.json -c camelCase -o output.json
  cat input.json | python json_key_casing_converter.py -c snake_case
        """
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Input JSON file (defaults to STDIN)"
    )
    parser.add_argument(
        "-c", "--casing",
        required=True,
        choices=['camelCase', 'snake_case', 'pascalCase', 'kebab-case', 'UPPERCASE', 'lowercase'],
        help="Target casing format for keys"
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Output JSON file (defaults to STDOUT)"
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2, use 0 for minified)"
    )

    args = parser.parse_args()

    try:
        raw_content = args.input.read()
        if not raw_content.strip():
            print("Error: Input is empty.", file=sys.stderr)
            sys.exit(1)
            
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    converted_data = convert_json_keys(data, args.casing)

    indent = args.indent if args.indent > 0 else None
    separators = (',', ':') if args.indent == 0 else None

    try:
        json.dump(converted_data, args.output, indent=indent, separators=separators, ensure_ascii=False)
        # Add newline at end of output file/stream
        args.output.write('\n')
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
