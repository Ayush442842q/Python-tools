#!/usr/bin/env python3
"""
CSV Merge by Column
Merges two CSV files based on a common key column, supporting
Inner, Left, Right, and Outer joins.
"""

import csv
import sys
import argparse
from typing import List, Dict, Set, Tuple, Any

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def read_csv(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read a CSV file and return the header and rows as dictionaries."""
    try:
        with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
            # utf-8-sig automatically strips BOM if present
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV file has no headers or is empty.")
            return list(reader.fieldnames), list(reader)
    except Exception as e:
        print(f"{RED}Error reading CSV file '{file_path}': {e}{RESET}", file=sys.stderr)
        sys.exit(1)

def resolve_headers(
    header1: List[str],
    header2: List[str],
    key1: str,
    key2: str,
    prefix1: str,
    prefix2: str
) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    """
    Resolve column collisions between two CSVs by applying prefixes.
    Returns:
        Tuple of (merged_headers, mapping1, mapping2)
    """
    merged_headers = [key1]
    mapping1 = {}
    mapping2 = {}

    # Map header1 columns
    for col in header1:
        if col == key1:
            mapping1[col] = key1
            continue
        new_name = col
        if col in header2 and col != key2:
            new_name = f"{prefix1}{col}" if prefix1 else col
        mapping1[col] = new_name
        merged_headers.append(new_name)

    # Map header2 columns
    for col in header2:
        if col == key2:
            mapping2[col] = key1 # Map both to key1 (primary key in output)
            continue
        new_name = col
        if col in header1 and col != key1:
            new_name = f"{prefix2}{col}" if prefix2 else col
        mapping2[col] = new_name
        if new_name not in merged_headers:
            merged_headers.append(new_name)

    return merged_headers, mapping1, mapping2

def merge_rows(
    rows1: List[Dict[str, str]],
    rows2: List[Dict[str, str]],
    key1: str,
    key2: str,
    join_type: str,
    null_value: str
) -> Tuple[Set[str], Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """Index rows by key for joining."""
    indexed1 = {}
    indexed2 = {}
    all_keys = set()

    for row in rows1:
        k = row.get(key1, "").strip()
        if k:
            indexed1[k] = row
            all_keys.add(k)

    for row in rows2:
        k = row.get(key2, "").strip()
        if k:
            indexed2[k] = row
            all_keys.add(k)

    return all_keys, indexed1, indexed2

def main():
    parser = argparse.ArgumentParser(
        description="Merge two CSV files based on a shared key column.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Join Types:
  inner  -> Keep only rows with keys matching in BOTH CSVs.
  left   -> Keep all rows from CSV1. Fill missing columns of CSV2 with null value.
  right  -> Keep all rows from CSV2. Fill missing columns of CSV1 with null value.
  outer  -> Keep all rows from BOTH CSVs, filling missing values on either side.

Examples:
  python csv_merge_by_column.py users.csv orders.csv -k id -j left -o merged.csv
  python csv_merge_by_column.py f1.csv f2.csv -k1 email -k2 user_email -j outer --p1 csv1_ --p2 csv2_
        """
    )
    parser.add_argument("csv1", help="Path to the first CSV file (Left)")
    parser.add_argument("csv2", help="Path to the second CSV file (Right)")
    parser.add_argument("-k", "--key", help="Key column name if shared by both CSV files")
    parser.add_argument("-k1", "--key1", help="Key column name in the first CSV (if different)")
    parser.add_argument("-k2", "--key2", help="Key column name in the second CSV (if different)")
    parser.add_argument(
        "-j", "--join",
        choices=["inner", "left", "right", "outer"],
        default="inner",
        help="Join type (default: inner)"
    )
    parser.add_argument(
        "-o", "--output",
        default="-",
        help="Output merged CSV file (defaults to '-' for STDOUT)"
    )
    parser.add_argument(
        "--p1", "--prefix1",
        default="csv1_",
        help="Prefix for colliding headers from first CSV (default: csv1_)"
    )
    parser.add_argument(
        "--p2", "--prefix2",
        default="csv2_",
        help="Prefix for colliding headers from second CSV (default: csv2_)"
    )
    parser.add_argument(
        "--null",
        default="",
        help="Replacement value for missing columns (default: empty string)"
    )

    args = parser.parse_args()

    # Determine key columns
    key1 = args.key1 or args.key
    key2 = args.key2 or args.key

    if not key1 or not key2:
        print(f"{RED}Error: You must specify a join key using -k, or both -k1 and -k2.{RESET}", file=sys.stderr)
        sys.exit(1)

    # Read CSVs
    h1, r1 = read_csv(args.csv1)
    h2, r2 = read_csv(args.csv2)

    # Check key existence
    if key1 not in h1:
        print(f"{RED}Error: Key '{key1}' not found in '{args.csv1}'. Available fields: {', '.join(h1)}{RESET}", file=sys.stderr)
        sys.exit(1)
    if key2 not in h2:
        print(f"{RED}Error: Key '{key2}' not found in '{args.csv2}'. Available fields: {', '.join(h2)}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Resolve header collisions
    merged_headers, map1, map2 = resolve_headers(h1, h2, key1, key2, args.p1, args.p2)

    # Index rows by key
    all_keys, indexed1, indexed2 = merge_rows(r1, r2, key1, key2, args.join, args.null)

    # Filter keys based on join type
    target_keys = []
    if args.join == "inner":
        target_keys = sorted([k for k in all_keys if k in indexed1 and k in indexed2])
    elif args.join == "left":
        target_keys = sorted([k for k in all_keys if k in indexed1])
    elif args.join == "right":
        target_keys = sorted([k for k in all_keys if k in indexed2])
    elif args.join == "outer":
        target_keys = sorted(list(all_keys))

    # Compile merged rows
    merged_rows = []
    for k in target_keys:
        row1 = indexed1.get(k, {})
        row2 = indexed2.get(k, {})

        merged_row = {col: args.null for col in merged_headers}
        merged_row[key1] = k

        # Populate values from first CSV
        for col, val in row1.items():
            if col != key1:
                mapped_col = map1[col]
                merged_row[mapped_col] = val

        # Populate values from second CSV
        for col, val in row2.items():
            if col != key2:
                mapped_col = map2[col]
                merged_row[mapped_col] = val

        merged_rows.append(merged_row)

    # Write output CSV
    try:
        if args.output == "-":
            out_file = sys.stdout
        else:
            out_file = open(args.output, 'w', newline='', encoding='utf-8')
            
        try:
            writer = csv.DictWriter(out_file, fieldnames=merged_headers)
            writer.writeheader()
            writer.writerows(merged_rows)
        finally:
            if args.output != "-":
                out_file.close()
    except Exception as e:
        print(f"{RED}Error writing output: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Print summary status to stderr so it doesn't mess with stdout redirect
    print(
        f"{BOLD}{GREEN}Successfully merged CSVs using '{args.join}' join.{RESET}\n"
        f"  CSV 1: {len(r1)} rows\n"
        f"  CSV 2: {len(r2)} rows\n"
        f"  Merged Output: {len(merged_rows)} rows",
        file=sys.stderr
    )

if __name__ == "__main__":
    main()
