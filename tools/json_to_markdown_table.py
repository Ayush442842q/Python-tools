#!/usr/bin/env python3
"""
JSON to Markdown Table Converter
Reads a JSON array of objects (from file, URL, or stdin), recursively flattens nested
structures using dot-notation, and outputs a beautifully formatted Markdown table.
Supports custom columns, renaming, alignments, and sorting.
"""

import argparse
import json
import sys
import urllib.request
from typing import Any, Dict, List, Tuple


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Recursively flattens a nested dictionary, creating dot-notation keys."""
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Stringify lists to keep them in a single table cell
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def get_value_by_dot_path(d: Dict[str, Any], path: str) -> Any:
    """Retrieves a nested value from a dictionary using a dot-separated path."""
    parts = path.split(".")
    curr = d
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return ""
    return curr


def parse_columns_arg(columns_arg: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Parses column arguments containing aliases.
    E.g. "id:ID,user.name:Username" -> ['id', 'user.name'], {'id': 'ID', 'user.name': 'Username'}
    """
    keys = []
    aliases = {}
    parts = columns_arg.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            key, alias = part.split(":", 1)
            key = key.strip()
            alias = alias.strip()
            keys.append(key)
            aliases[key] = alias
        else:
            keys.append(part)
            aliases[part] = part
    return keys, aliases


def build_markdown_table(
    data: List[Dict[str, Any]],
    keys: List[str],
    aliases: Dict[str, str],
    alignments: Dict[str, str],
) -> str:
    """Constructs a Markdown table from a list of flattened dictionaries."""
    if not data:
        return "No data to display."

    headers = [aliases.get(k, k) for k in keys]
    
    # Calculate column widths for pretty padding
    col_widths = {k: len(aliases.get(k, k)) for k in keys}
    
    # Prepare rows
    rows_str_values: List[Dict[str, str]] = []
    for item in data:
        row_map = {}
        for k in keys:
            val = item.get(k, "")
            # Sanitize newlines and pipes in Markdown
            val_str = str(val).replace("\n", " ").replace("\r", "").replace("|", "\\|")
            row_map[k] = val_str
            col_widths[k] = max(col_widths[k], len(val_str))
        rows_str_values.append(row_map)

    # 1. Headers Row
    header_parts = []
    for k in keys:
        header_text = aliases.get(k, k)
        header_parts.append(f" {header_text:<{col_widths[k]}} ")
    markdown = "|" + "|".join(header_parts) + "|\n"

    # 2. Separators Row (Alignments)
    sep_parts = []
    for k in keys:
        align = alignments.get(k, "left").lower()
        width = col_widths[k]
        if align == "center":
            sep_parts.append(f":{'-' * width}:")
        elif align == "right":
            sep_parts.append(f"{'-' * (width + 1)}:")
        else:  # left
            sep_parts.append(f":{'-' * (width + 1)}")
    markdown += "|" + "|".join(sep_parts) + "|\n"

    # 3. Data Rows
    for row in rows_str_values:
        row_parts = []
        for k in keys:
            val_str = row[k]
            align = alignments.get(k, "left").lower()
            width = col_widths[k]
            if align == "center":
                row_parts.append(f" {val_str:^{width}} ")
            elif align == "right":
                row_parts.append(f" {val_str:>{width}} ")
            else:  # left
                row_parts.append(f" {val_str:<{width}} ")
        markdown += "|" + "|".join(row_parts) + "|\n"

    return markdown


def main():
    parser = argparse.ArgumentParser(
        description="Convert a JSON file, URL, or stdin into a formatted Markdown table."
    )
    parser.add_argument("source", nargs="?", default="-",
                        help="JSON file path, URL, or '-' for stdin (default: stdin)")
    parser.add_argument("-c", "--columns",
                        help="Comma-separated column paths with optional aliases (e.g. 'id:ID,user.name:Username')")
    parser.add_argument("-s", "--sort",
                        help="Dot-path field to sort the table rows by")
    parser.add_argument("-d", "--descending", action="store_true",
                        help="Sort descending instead of ascending")
    parser.add_argument("-a", "--align",
                        help="Alignments for columns, comma-separated (left, center, right). E.g. 'left,center,right'")

    args = parser.parse_args()

    # 1. Read JSON source
    json_str = ""
    if args.source == "-":
        json_str = sys.stdin.read()
    elif args.source.startswith("http://") or args.source.startswith("https://"):
        try:
            req = urllib.request.Request(args.source, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                json_str = response.read().decode("utf-8")
        except Exception as e:
            print(f"Error fetching URL {args.source}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(args.source, "r", encoding="utf-8") as f:
                json_str = f.read()
        except Exception as e:
            print(f"Error reading file {args.source}: {e}", file=sys.stderr)
            sys.exit(1)

    if not json_str.strip():
        print("Empty input. No JSON data found.", file=sys.stderr)
        sys.exit(1)

    # 2. Parse JSON
    try:
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse input as valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert single dictionary to list containing it
    if isinstance(parsed_json, dict):
        # If it's a simple flat key-value dict, convert to key-value table list
        if not any(isinstance(v, (dict, list)) for v in parsed_json.values()):
            parsed_json = [{"Key": k, "Value": v} for k, v in parsed_json.items()]
        else:
            parsed_json = [parsed_json]
    elif not isinstance(parsed_json, list):
        print("Input must be a JSON array of objects or a single JSON object.", file=sys.stderr)
        sys.exit(1)

    if not parsed_json:
        print("JSON array is empty. Nothing to convert.")
        sys.exit(0)

    # 3. Flatten and process rows
    flat_data = [flatten_dict(item) for item in parsed_json]

    # Collect all unique keys from flattened dicts to build dynamic schema if not specified
    all_keys = []
    for item in flat_data:
        for k in item.keys():
            if k not in all_keys:
                all_keys.append(k)

    # 4. Resolve Columns and Headers
    if args.columns:
        keys, aliases = parse_columns_arg(args.columns)
    else:
        keys = all_keys
        aliases = {k: k for k in keys}

    # 5. Handle Sorting
    if args.sort:
        sort_key = args.sort
        
        # Sort helper to handle missing keys gracefully
        def sort_val(item):
            val = item.get(sort_key, "")
            if val is None:
                return ""
            # If values can be compared numerically, cast them
            if isinstance(val, (int, float)):
                return val
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val).lower()

        flat_data.sort(key=sort_val, reverse=args.descending)

    # 6. Resolve Alignments
    alignments = {}
    if args.align:
        align_list = [a.strip() for a in args.align.split(",")]
        for idx, key in enumerate(keys):
            if idx < len(align_list):
                alignments[key] = align_list[idx]
            else:
                alignments[key] = "left"
    else:
        # Default all to left
        alignments = {k: "left" for k in keys}

    # 7. Generate and output table
    markdown_table = build_markdown_table(flat_data, keys, aliases, alignments)
    print(markdown_table)


if __name__ == "__main__":
    main()
