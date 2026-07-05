#!/usr/bin/env python3
"""
ENV File Sorter & Formatter

Sorts, reorganizes, and formats .env files by variable name, key prefixes
(e.g., APP_, DB_, AWS_), or custom priority. Features automatic prefix
grouping, key deduplication, value alignment, and comment preservation.
"""

import os
import sys
import re
import argparse
from collections import OrderedDict

# Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_env_content(content):
    """
    Parses .env file content into structured records including comments,
    empty lines, and key-value pairs.
    """
    lines = content.splitlines()
    records = []
    current_comments = []
    
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            if current_comments:
                records.append({'type': 'comment_block', 'lines': current_comments})
                current_comments = []
            records.append({'type': 'blank', 'line': ''})
            continue
            
        if stripped.startswith('#'):
            current_comments.append(line)
            continue
            
        if '=' in line:
            # Parse Key-Value pair
            parts = line.split('=', 1)
            key = parts[0].strip()
            value = parts[1]
            
            # Extract inline comment if present (assuming space before # or quoted value)
            inline_comment = ""
            # Simple heuristic for inline comments outside quotes
            if '#' in value:
                in_quote = False
                quote_char = None
                comment_idx = -1
                for i, char in enumerate(value):
                    if char in ('"', "'"):
                        if not in_quote:
                            in_quote = True
                            quote_char = char
                        elif char == quote_char:
                            in_quote = False
                    elif char == '#' and not in_quote:
                        comment_idx = i
                        break
                if comment_idx != -1:
                    inline_comment = value[comment_idx:]
                    value = value[:comment_idx]

            records.append({
                'type': 'kv',
                'key': key,
                'value': value,
                'comments': current_comments,
                'inline_comment': inline_comment,
                'raw': line,
                'line_num': line_num
            })
            current_comments = []
        else:
            # Standalone unrecognized line
            records.append({
                'type': 'raw',
                'line': line,
                'comments': current_comments,
                'line_num': line_num
            })
            current_comments = []

    if current_comments:
        records.append({'type': 'comment_block', 'lines': current_comments})

    return records


def get_key_prefix(key):
    """Extract prefix group for key (e.g. DB_HOST -> DB, AWS_SECRET -> AWS)."""
    if '_' in key:
        return key.split('_')[0].upper()
    return "GENERAL"


def sort_and_format_env(records, sort_mode='prefix', dedup_strategy='keep-last', align_equal=False, group_headers=True):
    """
    Sorts and formats parsed .env records according to rules.
    """
    # 1. Collect and deduplicate key-value pairs
    kv_items = []
    seen_keys = {}
    duplicates_found = []

    for item in records:
        if item['type'] == 'kv':
            k = item['key']
            if k in seen_keys:
                duplicates_found.append(k)
                if dedup_strategy == 'keep-last':
                    kv_items[seen_keys[k]] = item
                elif dedup_strategy == 'fail':
                    raise ValueError(f"Duplicate key '{k}' found on line {item['line_num']}")
                # if keep-first, ignore current item
            else:
                seen_keys[k] = len(kv_items)
                kv_items.append(item)

    # 2. Sort key-value pairs
    if sort_mode == 'alphabetical':
        kv_items.sort(key=lambda x: x['key'].lower())
    elif sort_mode == 'length':
        kv_items.sort(key=lambda x: len(x['key']))
    elif sort_mode == 'prefix':
        kv_items.sort(key=lambda x: (get_key_prefix(x['key']), x['key'].lower()))

    # Calculate padding for equal alignment if enabled
    max_key_len = max([len(x['key']) for x in kv_items], default=0) if align_equal else 0

    # 3. Reconstruct output
    output_lines = []
    current_group = None

    for item in kv_items:
        key = item['key']
        value = item['value']
        comments = item['comments']
        inline_comment = item['inline_comment']
        prefix = get_key_prefix(key)

        # Insert Section Headers when grouping by prefix
        if sort_mode == 'prefix' and group_headers:
            if prefix != current_group:
                if current_group is not None:
                    output_lines.append("")
                current_group = prefix
                output_lines.append(f"# ==========================================")
                output_lines.append(f"# {prefix} CONFIGURATION")
                output_lines.append(f"# ==========================================")

        # Print attached leading comments
        for c in comments:
            output_lines.append(c)

        # Print key-value pair
        padded_key = key.ljust(max_key_len) if align_equal else key
        line = f"{padded_key}={value}"
        if inline_comment:
            line = f"{line} {inline_comment}".rstrip()
        output_lines.append(line)

    return "\n".join(output_lines) + "\n", duplicates_found


def main():
    parser = argparse.ArgumentParser(
        description="ENV File Sorter & Formatter - Organize and standardize .env configuration files."
    )
    parser.add_argument("env_file", help="Path to the .env file to process")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout or overwrite if --in-place)")
    parser.add_argument("-i", "--in-place", action="store_true", help="Overwrite input file directly")
    parser.add_argument(
        "-s", "--sort",
        choices=['prefix', 'alphabetical', 'length'],
        default='prefix',
        help="Sorting strategy (default: prefix)"
    )
    parser.add_argument(
        "-d", "--dedup",
        choices=['keep-last', 'keep-first', 'fail'],
        default='keep-last',
        help="Duplicate key handling strategy (default: keep-last)"
    )
    parser.add_argument("--align-equal", action="store_true", help="Align '=' signs across all keys")
    parser.add_argument("--no-headers", action="store_true", help="Disable section header comments in prefix mode")
    parser.add_argument("--dry-run", action="store_true", help="Display results without saving to disk")

    args = parser.parse_args()

    if not os.path.exists(args.env_file):
        print(f"{RED}[ERROR]{RESET} File '{args.env_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.env_file, 'r', encoding='utf-8') as f:
            content = f.read()

        records = parse_env_content(content)
        formatted_content, duplicates = sort_and_format_env(
            records,
            sort_mode=args.sort,
            dedup_strategy=args.dedup,
            align_equal=args.align_equal,
            group_headers=not args.no_headers
        )

        if duplicates:
            print(f"{YELLOW}[WARNING]{RESET} Deduplicated keys: {', '.join(set(duplicates))}", file=sys.stderr)

        if args.dry_run:
            print(f"{CYAN}--- DRY RUN OUTPUT ({args.env_file}) ---{RESET}")
            print(formatted_content)
        elif args.in_place:
            with open(args.env_file, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            print(f"{GREEN}[SUCCESS]{RESET} Successfully updated '{args.env_file}' in-place.")
        elif args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            print(f"{GREEN}[SUCCESS]{RESET} Written formatted output to '{args.output}'.")
        else:
            sys.stdout.write(formatted_content)

    except Exception as e:
        print(f"{RED}[ERROR]{RESET} Failed to process env file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
