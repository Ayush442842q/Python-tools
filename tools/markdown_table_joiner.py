#!/usr/bin/env python3
"""
Markdown Table Relational Joiner & Union Utility
Performs SQL-like joins (INNER, LEFT, RIGHT, FULL OUTER) and UNIONs on Markdown tables.
"""

import argparse
import re
import sys
from typing import List, Dict, Tuple, Optional

def parse_markdown_table(content: str) -> Tuple[List[str], List[List[str]]]:
    """
    Parses a Markdown table string into a list of headers and list of rows.
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    # Locate the table boundary
    table_lines = []
    in_table = False
    for line in lines:
        if line.startswith('|') and line.endswith('|'):
            in_table = True
            table_lines.append(line)
        elif in_table:
            # Table ended or broken
            break
            
    if not table_lines:
        # Fallback: try parsing lines that have pipes inside even if they don't start/end with pipes
        for line in lines:
            if '|' in line:
                table_lines.append(line)

    if len(table_lines) < 2:
        raise ValueError("Could not find a valid Markdown table with at least headers and separator row.")

    # Parse rows
    parsed_rows = []
    for line in table_lines:
        # Split by pipe, stripping boundary pipes
        cleaned = line.strip()
        if cleaned.startswith('|'):
            cleaned = cleaned[1:]
        if cleaned.endswith('|'):
            cleaned = cleaned[:-1]
        
        cells = [cell.strip() for cell in cleaned.split('|')]
        parsed_rows.append(cells)

    # Separate headers, alignment row, and data rows
    headers = parsed_rows[0]
    
    # Check if second row is separator/alignment row (e.g., |---|:---|)
    has_separator = False
    data_start_idx = 1
    if len(parsed_rows) > 1:
        second_row = parsed_rows[1]
        if all(re.match(r'^:?-+:?$', cell) for cell in second_row if cell):
            has_separator = True
            data_start_idx = 2

    data_rows = parsed_rows[data_start_idx:]
    return headers, data_rows

def format_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """
    Formats headers and rows into a clean, aligned Markdown table.
    """
    if not headers:
        return ""

    # Compute maximum width for each column to align correctly
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(str(cell)))
            else:
                col_widths.append(len(str(cell)))

    # Format header row
    header_str = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    
    # Format separator row
    separator_str = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    
    # Format data rows
    row_strs = []
    for row in rows:
        row_padded = []
        for i in range(len(headers)):
            cell_val = str(row[i]) if i < len(row) else ""
            row_padded.append(cell_val.ljust(col_widths[i]))
        row_strs.append("| " + " | ".join(row_padded) + " |")

    return "\n".join([header_str, separator_str] + row_strs)

def perform_join(
    headers1: List[str], rows1: List[List[str]],
    headers2: List[str], rows2: List[List[str]],
    key1: str, key2: str, join_type: str
) -> Tuple[List[str], List[List[str]]]:
    # Resolve key indices
    try:
        k1_idx = headers1.index(key1)
    except ValueError:
        # Try as int index
        if key1.isdigit() and int(key1) < len(headers1):
            k1_idx = int(key1)
        else:
            raise ValueError(f"Join key '{key1}' not found in Table 1 headers: {headers1}")

    try:
        k2_idx = headers2.index(key2)
    except ValueError:
        if key2.isdigit() and int(key2) < len(headers2):
            k2_idx = int(key2)
        else:
            raise ValueError(f"Join key '{key2}' not found in Table 2 headers: {headers2}")

    # Build header list for joined table
    # Standard join columns: Table 1 columns + Table 2 columns (excluding Table 2 key column to avoid duplication)
    t2_indices_to_include = [i for i in range(len(headers2)) if i != k2_idx]
    
    # Resolve duplicate column headers
    joined_headers = list(headers1)
    for idx in t2_indices_to_include:
        h_name = headers2[idx]
        if h_name in joined_headers:
            joined_headers.append(f"{h_name}_t2")
        else:
            joined_headers.append(h_name)

    joined_rows = []

    # Map Table 2 rows by join key
    t2_map: Dict[str, List[List[str]]] = {}
    for r2 in rows2:
        val = r2[k2_idx] if k2_idx < len(r2) else ""
        t2_map.setdefault(val, []).append(r2)

    matched_t2_keys = set()

    for r1 in rows1:
        key_val = r1[k1_idx] if k1_idx < len(r1) else ""
        t2_matches = t2_map.get(key_val, [])

        if t2_matches:
            matched_t2_keys.add(key_val)
            for r2 in t2_matches:
                # Combine rows
                combined = list(r1)
                for idx in t2_indices_to_include:
                    combined.append(r2[idx] if idx < len(r2) else "")
                joined_rows.append(combined)
        else:
            # No match
            if join_type in ("left", "outer"):
                combined = list(r1)
                # Pad Table 2 columns with empty values
                combined.extend([""] * len(t2_indices_to_include))
                joined_rows.append(combined)

    if join_type in ("right", "outer"):
        # Add non-matching Table 2 rows
        for key_val, r2_list in t2_map.items():
            if key_val not in matched_t2_keys:
                for r2 in r2_list:
                    # Construct row: Table 1 empty values + Table 2 values
                    combined = [""] * len(headers1)
                    # Set the join key in the column position of Table 1 key
                    combined[k1_idx] = key_val
                    for idx in t2_indices_to_include:
                        combined.append(r2[idx] if idx < len(r2) else "")
                    joined_rows.append(combined)

    return joined_headers, joined_rows

def perform_union(
    headers1: List[str], rows1: List[List[str]],
    headers2: List[str], rows2: List[List[str]]
) -> Tuple[List[str], List[List[str]]]:
    # Combine headers keeping order from table 1 then additions from table 2
    union_headers = list(headers1)
    for h in headers2:
        if h not in union_headers:
            union_headers.append(h)

    union_rows = []

    # Map Table 1 row columns
    for r1 in rows1:
        new_row = []
        for h in union_headers:
            if h in headers1:
                idx = headers1.index(h)
                new_row.append(r1[idx] if idx < len(r1) else "")
            else:
                new_row.append("")
        union_rows.append(new_row)

    # Map Table 2 row columns
    for r2 in rows2:
        new_row = []
        for h in union_headers:
            if h in headers2:
                idx = headers2.index(h)
                new_row.append(r2[idx] if idx < len(r2) else "")
            else:
                new_row.append("")
        union_rows.append(new_row)

    return union_headers, union_rows

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Table Relational Joiner & Union Utility - Performs inner/left/right/outer joins and unions on Markdown tables."
    )
    parser.add_argument("table1", help="Path to Markdown file containing Table 1")
    parser.add_argument("table2", help="Path to Markdown file containing Table 2")
    parser.add_argument("-t", "--type", choices=["inner", "left", "right", "outer", "union"], default="inner",
                        help="Join or union operation type (default: inner)")
    parser.add_argument("-k1", "--key1", help="Join key column name or index for Table 1")
    parser.add_argument("-k2", "--key2", help="Join key column name or index for Table 2 (defaults to key1 value if omitted)")
    parser.add_argument("-o", "--output", help="Write result to file instead of standard output")

    args = parser.parse_args()

    # Read tables
    try:
        with open(args.table1, "r", encoding="utf-8") as f:
            content1 = f.read()
        headers1, rows1 = parse_markdown_table(content1)
    except Exception as e:
        print(f"Error parsing Table 1: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.table2, "r", encoding="utf-8") as f:
            content2 = f.read()
        headers2, rows2 = parse_markdown_table(content2)
    except Exception as e:
        print(f"Error parsing Table 2: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply operation
    try:
        if args.type == "union":
            res_headers, res_rows = perform_union(headers1, rows1, headers2, rows2)
        else:
            k1 = args.key1 or headers1[0]
            k2 = args.key2 or args.key1 or headers2[0]
            res_headers, res_rows = perform_join(headers1, rows1, headers2, rows2, k1, k2, args.type)
        
        result_table = format_markdown_table(res_headers, res_rows)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result_table + "\n")
            print(f"Merged table written successfully to: {args.output}")
        else:
            print(result_table)

    except Exception as e:
        print(f"Operation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
