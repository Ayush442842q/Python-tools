#!/usr/bin/env python3
"""
CSV Diff & Reconciliation Tool
Compares two CSV files row-by-row based on a primary key column or index.
Identifies added rows, deleted rows, and modified values/columns.
"""

import sys
import os
import csv
import argparse

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

def supports_color():
    """Returns True if the terminal supports colored output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_CYAN = ""

def load_csv(filepath, delimiter, key_column):
    """
    Loads CSV file into a dictionary keyed by the key_column value.
    Returns: (headers, data_dict, list_of_keys)
    """
    data = {}
    keys = []
    
    with open(filepath, mode="r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file '{filepath}' is empty.")
            
        # Clean headers (strip whitespace)
        headers = [h.strip() for h in headers]
        
        # Determine key column index
        key_idx = -1
        if key_column is not None:
            if key_column.isdigit():
                idx = int(key_column)
                if 0 <= idx < len(headers):
                    key_idx = idx
            else:
                try:
                    key_idx = headers.index(key_column)
                except ValueError:
                    pass
                    
        # Fallback: if key_column not found, use first column (index 0)
        if key_idx == -1:
            if key_column is not None:
                print(f"{COLOR_YELLOW}Warning: Key column '{key_column}' not found. Defaulting to first column '{headers[0]}'.{COLOR_RESET}")
            key_idx = 0
            
        for line_no, row in enumerate(reader, start=2):
            if not row:
                continue
            # Pad row if columns are missing
            if len(row) < len(headers):
                row.extend([""] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
                
            key = row[key_idx].strip()
            
            # Warn about duplicates
            if key in data:
                print(f"{COLOR_YELLOW}Warning: Duplicate key '{key}' found at line {line_no} in '{filepath}'. Overwriting previous entry.{COLOR_RESET}")
                
            data[key] = row
            keys.append(key)
            
    return headers, data, keys, headers[key_idx]

def print_row_diff(key, headers, row1, row2):
    """Prints a detailed field-by-field diff of a modified row."""
    print(f"\n{COLOR_YELLOW}{COLOR_BOLD}Modified Row Key: {key}{COLOR_RESET}")
    print("-" * 50)
    for h, val1, val2 in zip(headers, row1, row2):
        val1_clean = val1.strip()
        val2_clean = val2.strip()
        if val1_clean != val2_clean:
            print(f"  Column {COLOR_CYAN}{h}{COLOR_RESET}:")
            print(f"    {COLOR_RED}- Old:{COLOR_RESET} {val1}")
            print(f"    {COLOR_GREEN}+ New:{COLOR_RESET} {val2}")

def main():
    parser = argparse.ArgumentParser(
        description="CSV Diff & Reconciliation Tool - Compare two CSV files side-by-side highlighting additions, deletions, and changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file_old", help="The reference/original CSV file")
    parser.add_argument("file_new", help="The modified/new CSV file")
    parser.add_argument("--key", "-k", help="The primary key column name or index (default: first column)")
    parser.add_argument("--delimiter", "-d", default=",", help="CSV delimiter character (default: ',')")
    parser.add_argument("--summary-only", "-s", action="store_true", help="Print only summary stats without detailed row-by-row changes")
    
    args = parser.parse_args()
    
    # Validation
    for f in [args.file_old, args.file_new]:
        if not os.path.exists(f):
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} File '{f}' does not exist.", file=sys.stderr)
            return 1
        if os.path.isdir(f):
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} '{f}' is a directory.", file=sys.stderr)
            return 1

    try:
        headers_old, data_old, keys_old, actual_key_col = load_csv(args.file_old, args.delimiter, args.key)
        headers_new, data_new, keys_new, _ = load_csv(args.file_new, args.delimiter, args.key)
    except Exception as e:
        print(f"{COLOR_RED}{COLOR_BOLD}Error loading CSV:{COLOR_RESET} {e}", file=sys.stderr)
        return 1

    # Check header mismatch
    headers_match = headers_old == headers_new
    if not headers_match:
        print(f"{COLOR_YELLOW}{COLOR_BOLD}Warning: Header mismatch between CSV files!{COLOR_RESET}")
        print(f"  Old Headers: {headers_old}")
        print(f"  New Headers: {headers_new}")
        
        # We will align by intersection of headers if mismatch, or use indices
        common_headers = [h for h in headers_old if h in headers_new]
        if not common_headers:
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} No overlapping column headers found between files. Cannot compare.", file=sys.stderr)
            return 1
        print(f"  Aligning comparison on overlapping columns: {common_headers}\n")
    else:
        common_headers = headers_old

    # Sets for diff
    set_old = set(data_old.keys())
    set_new = set(data_new.keys())
    
    deleted_keys = sorted(list(set_old - set_new))
    added_keys = sorted(list(set_new - set_old))
    common_keys = set_old & set_new

    modified_keys = []
    unchanged_count = 0

    # Align indexes
    indices_old = [headers_old.index(h) for h in common_headers]
    indices_new = [headers_new.index(h) for h in common_headers]

    for key in common_keys:
        row_old = data_old[key]
        row_new = data_new[key]
        
        # Extract common fields
        fields_old = [row_old[i] for i in indices_old]
        fields_new = [row_new[i] for i in indices_new]
        
        if fields_old != fields_new:
            modified_keys.append((key, fields_old, fields_new))
        else:
            unchanged_count += 1

    # Print Report
    print(f"=== {COLOR_BOLD}CSV Diff Report{COLOR_RESET} ===")
    print(f"File (Old): {COLOR_BLUE}{args.file_old}{COLOR_RESET}")
    print(f"File (New): {COLOR_BLUE}{args.file_new}{COLOR_RESET}")
    print(f"Reconciliation Key Column: {COLOR_BOLD}{actual_key_col}{COLOR_RESET}")
    print("=" * 50)
    
    print(f"\n{COLOR_BOLD}Reconciliation Summary:{COLOR_RESET}")
    print(f"  {COLOR_GREEN}+ Added Rows:{COLOR_RESET}     {len(added_keys)}")
    print(f"  {COLOR_RED}- Deleted Rows:{COLOR_RESET}   {len(deleted_keys)}")
    print(f"  {COLOR_YELLOW}~ Modified Rows:{COLOR_RESET}  {len(modified_keys)}")
    print(f"  = Unchanged Rows: {unchanged_count}")
    print(f"  Total Rows (Old): {len(data_old)}")
    print(f"  Total Rows (New): {len(data_new)}\n")
    
    if args.summary_only:
        return 0
        
    # Detail Additions
    if added_keys:
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}+++ Added Rows ({len(added_keys)}) +++{COLOR_RESET}")
        for k in added_keys:
            # Print headers/row values aligned
            row = data_new[k]
            formatted_fields = ", ".join(f"{h}={v}" for h, v in zip(headers_new, row))
            print(f"  [{k}]: {formatted_fields}")
            
    # Detail Deletions
    if deleted_keys:
        print(f"\n{COLOR_RED}{COLOR_BOLD}--- Deleted Rows ({len(deleted_keys)}) ---{COLOR_RESET}")
        for k in deleted_keys:
            row = data_old[k]
            formatted_fields = ", ".join(f"{h}={v}" for h, v in zip(headers_old, row))
            print(f"  [{k}]: {formatted_fields}")

    # Detail Modifications
    if modified_keys:
        print(f"\n{COLOR_YELLOW}{COLOR_BOLD}~~~ Modified Rows ({len(modified_keys)}) ~~~{COLOR_RESET}")
        for k, old_f, new_f in modified_keys:
            print_row_diff(k, common_headers, old_f, new_f)

    print("\nComparison finished.")
    
    if added_keys or deleted_keys or modified_keys:
        return 2 # return changes detected status
    return 0

if __name__ == "__main__":
    sys.exit(main())
