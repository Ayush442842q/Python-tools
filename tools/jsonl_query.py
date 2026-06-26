#!/usr/bin/env python3
"""
JSON Lines (JSONL) Query & Processing Tool - Query, filter, and format JSONL datasets

A fast stream-based CLI utility to filter, query, slice, and reformat JSON Lines
(.jsonl or .ndjson) files. It can read from files or stdin, making it perfect
for shell pipelines.

Usage:
    python tools/jsonl_query.py data.jsonl --filter "status == 500" --select timestamp,message
    cat data.jsonl | python tools/jsonl_query.py --filter "level == 'ERROR'" --format csv
    python tools/jsonl_query.py data.jsonl --schema
"""

import argparse
import csv
import json
import sys
from typing import Any, Dict, Generator, List, Optional, Set, Tuple


def read_jsonl(file_obj) -> Generator[Tuple[int, Dict[str, Any], str], None, None]:
    """Yields (line_number, parsed_dict, original_line) from a JSONL file object."""
    for idx, line in enumerate(file_obj, 1):
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue
        try:
            yield idx, json.loads(line_str), line_str
        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error on line {idx}: {e}", file=sys.stderr)
            continue


def safe_eval(expr: str, row: Dict[str, Any]) -> bool:
    """Safely evaluates a Python filter expression against the row dict."""
    allowed_globals = {"__builtins__": None}
    
    # Context dictionary containing 'row', 'r', and direct keys if they are valid identifiers
    context = {"row": row, "r": row}
    for k, v in row.items():
        if k.isidentifier():
            context[k] = v
            
    try:
        return bool(eval(expr, allowed_globals, context))
    except Exception:
        # Ignore errors like NameError (missing key) or TypeError to allow sparse fields
        return False


def get_field_by_path(data: Dict[str, Any], path: str) -> Any:
    """Extracts a nested field using dot-notation, e.g., 'user.profile.name'."""
    parts = path.split('.')
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Formats list of rows into an ASCII table."""
    if not headers and not rows:
        return ""
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < len(widths):
                widths[idx] = max(widths[idx], len(str(cell)))
            else:
                widths.append(len(str(cell)))

    # Build separator line
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    
    # Build header line
    hdr_line = "|" + "|".join(f" {headers[i].ljust(widths[i])} " for i in range(len(headers))) + "|"
    
    lines = [sep, hdr_line, sep.replace("-", "=")]
    for row in rows:
        # Pad row to match widths length
        row_cells = list(row) + [""] * (len(widths) - len(row))
        line = "|" + "|".join(f" {str(row_cells[i]).ljust(widths[i])} " for i in range(len(widths))) + "|"
        lines.append(line)
    lines.append(sep)
    
    return "\n".join(lines)


def analyze_schema(file_obj, sample_limit: int = 1000) -> None:
    """Analyzes schema structure and type counts in the JSONL file."""
    keys_info: Dict[str, Dict[str, int]] = {}
    total_records = 0

    def record_type(prefix: str, value: Any):
        t_name = type(value).__name__
        if isinstance(value, dict):
            for k, v in value.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                record_type(new_prefix, v)
        elif isinstance(value, list):
            # Record list type representation
            list_types = {type(item).__name__ for item in value}
            t_name = f"list[{','.join(sorted(list_types))}]" if list_types else "list[empty]"
            keys_info.setdefault(prefix, {}).setdefault(t_name, 0)
            keys_info[prefix][t_name] += 1
        else:
            keys_info.setdefault(prefix, {}).setdefault(t_name, 0)
            keys_info[prefix][t_name] += 1

    for _, row, _ in read_jsonl(file_obj):
        total_records += 1
        record_type("", row)
        if sample_limit and total_records >= sample_limit:
            break

    if total_records == 0:
        print("No valid JSON records found to analyze.")
        return

    print("=" * 60)
    print(f"JSONL Schema Analysis (Sampled {total_records} records)")
    print("=" * 60)
    print(f"{'Field Path':<35} | {'Type (Frequency)':<22}")
    print("-" * 60)

    for field, types in sorted(keys_info.items()):
        type_strs = []
        for t, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_records) * 100
            type_strs.append(f"{t} ({pct:.0f}%)")
        print(f"{field:<35} | {', '.join(type_strs):<22}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast stream-based CLI tool to filter, query, slice, and reformat JSON Lines files."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="JSONL file to read (reads from stdin if omitted or '-')"
    )
    parser.add_argument(
        "-f", "--filter",
        help="Python expression to filter rows (e.g. \"status == 200 and 'err' in message\")"
    )
    parser.add_argument(
        "-p", "--select",
        help="Comma-separated keys or dot-notation paths to project/keep (e.g. \"timestamp,user.id,message\")"
    )
    parser.add_argument(
        "-s", "--slice",
        help="Slice output index using Python slice format (e.g., '10:20', ':100', '-5:')"
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        help="Limit number of output rows"
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "json", "csv", "table"],
        default="jsonl",
        help="Output format (default: jsonl)"
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Analyze and print schema of the dataset instead of matching rows"
    )

    args = parser.parse_args()

    # Determine input stream
    if not args.file or args.file == '-':
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(0)
        input_stream = sys.stdin
    else:
        try:
            input_stream = open(args.file, 'r', encoding='utf-8')
        except IOError as e:
            print(f"Error opening file: {e}", file=sys.stderr)
            sys.exit(1)

    # 1. Schema Mode
    if args.schema:
        try:
            analyze_schema(input_stream)
        finally:
            if input_stream is not sys.stdin:
                input_stream.close()
        return

    # Parse slice if provided
    slice_obj = None
    if args.slice:
        try:
            parts = args.slice.split(':')
            start = int(parts[0]) if parts[0] else None
            end = int(parts[1]) if len(parts) > 1 and parts[1] else None
            step = int(parts[2]) if len(parts) > 2 and parts[2] else None
            slice_obj = slice(start, end, step)
        except ValueError:
            parser.error("Invalid slice format. Use 'start:stop:step'")

    # Extract select fields
    select_fields = [f.strip() for f in args.select.split(',')] if args.select else None

    # Stream & Filter
    results: List[Dict[str, Any]] = []
    match_count = 0
    
    try:
        for idx, row, original_line in read_jsonl(input_stream):
            # Apply filter
            if args.filter:
                if not safe_eval(args.filter, row):
                    continue

            match_count += 1
            
            # Apply selection/projection
            if select_fields:
                projected = {}
                for field in select_fields:
                    val = get_field_by_path(row, field)
                    if val is not None:
                        projected[field] = val
                results.append(projected)
            else:
                results.append(row)
                
            # If we aren't slicing, and we've reached a limit count, we can stop early
            if not slice_obj and args.count and len(results) >= args.count:
                break
    finally:
        if input_stream is not sys.stdin:
            input_stream.close()

    # Apply slicing
    if slice_obj:
        results = results[slice_obj]

    # Apply count limit if sliced
    if slice_obj and args.count:
        results = results[:args.count]

    # Format Output
    if not results:
        return

    if args.format == 'jsonl':
        for row in results:
            print(json.dumps(row))
            
    elif args.format == 'json':
        print(json.dumps(results, indent=2))
        
    elif args.format == 'csv':
        # Gather all unique keys present in the selected results
        headers = select_fields if select_fields else sorted(list({k for r in results for k in r.keys()}))
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        for row in results:
            # Handle missing keys gracefully
            writer.writerow({k: row.get(k, '') for k in headers})
            
    elif args.format == 'table':
        headers = select_fields if select_fields else sorted(list({k for r in results for k in r.keys()}))
        rows_str: List[List[str]] = []
        for row in results:
            rows_str.append([str(row.get(h, '')) for h in headers])
        print(format_table(headers, rows_str))


if __name__ == '__main__':
    main()
