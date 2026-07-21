#!/usr/bin/env python3
"""
Markdown Table to JSON Converter
Converts Markdown tables in files or stdin into structured JSON data.

Features:
- Parses single or multiple Markdown tables from input text or files.
- Automatically infers data types (integers, floats, booleans, nulls).
- Supports array of objects format (rows as dicts) or column-based format.
- Pretty-prints JSON output to stdout or saves to a file.
"""

import sys
import os
import re
import json
import argparse
from typing import List, Dict, Any, Union

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def parse_value(val_str: str) -> Union[int, float, bool, None, str]:
    """Casts string values to appropriate Python primitive types."""
    val = val_str.strip()
    if not val or val.lower() in ("null", "none", "-", "n/a"):
        return None
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    # Try integer
    try:
        if re.match(r"^-?\d+$", val):
            return int(val)
    except ValueError:
        pass
    # Try float
    try:
        if re.match(r"^-?\d+\.\d+$", val):
            return float(val)
    except ValueError:
        pass
    return val


def parse_markdown_tables(text: str) -> List[List[Dict[str, Any]]]:
    """
    Extracts all Markdown tables from text and parses each into a list of row dictionaries.
    """
    lines = text.splitlines()
    tables: List[List[Dict[str, Any]]] = []
    current_table_lines: List[str] = []

    def process_table_block(block: List[str]) -> List[Dict[str, Any]]:
        if len(block) < 2:
            return []
        
        # Helper to split pipeline-delimited row
        def split_row(row_line: str) -> List[str]:
            row_line = row_line.strip()
            if row_line.startswith("|"):
                row_line = row_line[1:]
            if row_line.endswith("|"):
                row_line = row_line[:-1]
            return [cell.strip() for cell in row_line.split("|")]

        headers = split_row(block[0])
        
        # Check if line 1 is separator line (e.g., |---|---:|)
        sep_line = block[1].strip()
        is_sep = bool(re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$", sep_line))
        
        start_row = 2 if is_sep else 1
        rows: List[Dict[str, Any]] = []

        for line in block[start_row:]:
            if not line.strip() or not "|" in line:
                continue
            cells = split_row(line)
            row_dict: Dict[str, Any] = {}
            for idx, header in enumerate(headers):
                val = cells[idx] if idx < len(cells) else ""
                row_dict[header] = parse_value(val)
            rows.append(row_dict)
            
        return rows

    for line in lines:
        if "|" in line:
            current_table_lines.append(line)
        else:
            if current_table_lines:
                parsed = process_table_block(current_table_lines)
                if parsed:
                    tables.append(parsed)
                current_table_lines = []
    
    if current_table_lines:
        parsed = process_table_block(current_table_lines)
        if parsed:
            tables.append(parsed)

    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Markdown tables to JSON.")
    parser.add_argument("input", nargs="?", type=str, help="Input Markdown file path (reads stdin if omitted).")
    parser.add_argument("-o", "--output", type=str, help="Output JSON file path.")
    parser.add_argument("--first-only", action="store_true", help="Return only the first table instead of list of tables.")
    parser.add_argument("--no-type-cast", action="store_true", help="Keep all table cell values as strings.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level (default: 2).")

    args = parser.parse_args()

    if args.input and os.path.exists(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        content = sys.stdin.read()

    tables = parse_markdown_tables(content)

    if not tables:
        print("No valid Markdown tables found.", file=sys.stderr)
        sys.exit(1)

    result = tables[0] if args.first_only else (tables[0] if len(tables) == 1 else tables)

    json_str = json.dumps(result, indent=args.indent, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")
        print(f"Successfully exported JSON to {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
