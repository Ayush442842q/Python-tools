#!/usr/bin/env python3
"""
JSON Flattener - Flatten nested JSON objects or unflatten them back.

This tool transforms deeply nested JSON structures into flat key-value pairs
using dotted-key paths (e.g. 'user.profile.name') and can reconstruct the
original nested structure from a flattened file.
"""

import os
import sys
import json
import argparse


def flatten_json(data, separator=".", preserve_lists=False):
    """Flatten a nested dictionary/list structure into dotted keys."""
    flat = {}

    def _flatten(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                new_path = f"{path}{k}{separator}" if path else f"{k}{separator}"
                _flatten(v, new_path)
        elif isinstance(node, list) and not preserve_lists:
            for idx, item in enumerate(node):
                new_path = f"{path}{idx}{separator}" if path else f"{idx}{separator}"
                _flatten(item, new_path)
        else:
            # Leaf node
            if path:
                flat[path[:-len(separator)]] = node
            else:
                flat[""] = node

    _flatten(data)
    return flat


def unflatten_json(flat_dict, separator="."):
    """Reconstruct a nested dictionary/list structure from flat dotted keys."""
    if not flat_dict:
        return {}

    # Check if the root container should be a list or a dict
    is_root_list = True
    for key in flat_dict.keys():
        first_part = key.split(separator)[0]
        if not first_part.isdigit():
            is_root_list = False
            break

    result = [] if is_root_list else {}

    for key, value in flat_dict.items():
        parts = key.split(separator)
        
        # Traverse intermediate containers
        current = result
        for i, part in enumerate(parts[:-1]):
            next_part = parts[i + 1]
            is_next_list = next_part.isdigit()

            if isinstance(current, list):
                idx = int(part)
                # Expand list if index exceeds length
                while len(current) <= idx:
                    current.append(None)
                if current[idx] is None:
                    current[idx] = [] if is_next_list else {}
                current = current[idx]
            else:
                # current is a dict
                if part not in current or current[part] is None:
                    current[part] = [] if is_next_list else {}
                current = current[part]

        # Place final value
        last_part = parts[-1]
        if isinstance(current, list):
            idx = int(last_part)
            while len(current) <= idx:
                current.append(None)
            current[idx] = value
        else:
            current[last_part] = value

    return result


def main():
    parser = argparse.ArgumentParser(
        description="JSON Flattener - Flatten nested JSON objects or unflatten them back."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="JSON file to process (if omitted, reads from standard input)"
    )
    parser.add_argument(
        "-u", "--unflatten",
        action="store_true",
        help="Perform unflattening instead of flattening"
    )
    parser.add_argument(
        "-s", "--separator",
        default=".",
        help="Separator string for flattened keys (default: '.')"
    )
    parser.add_argument(
        "-p", "--preserve-lists",
        action="store_true",
        help="Do not flatten list/array elements (only applicable when flattening)"
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=4,
        help="Indentation size for formatted JSON output (default: 4)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: prints to stdout)"
    )

    args = parser.parse_args()

    # Read input
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                raw_input = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            print("Enter/Paste JSON content (Press Ctrl+D/Ctrl+Z to end):")
        raw_input = sys.stdin.read()

    if not raw_input.strip():
        print("Error: Empty JSON input.", file=sys.stderr)
        sys.exit(1)

    # Load JSON
    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Process
    if args.unflatten:
        if not isinstance(data, dict):
            print("Error: Input for unflattening must be a flat dictionary object.", file=sys.stderr)
            sys.exit(1)
        processed = unflatten_json(data, separator=args.separator)
    else:
        processed = flatten_json(
            data, 
            separator=args.separator, 
            preserve_lists=args.preserve_lists
        )

    # Output JSON representation
    output_content = json.dumps(processed, indent=args.indent)

    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_content + "\n")
            print(f"Success: Output written to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_content)


if __name__ == "__main__":
    main()
