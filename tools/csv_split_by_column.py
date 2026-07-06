#!/usr/bin/env python3
"""
CSV Split by Column Value Utility

Splits a CSV file into multiple separate CSV files based on unique values in a target column.

Features:
- Split by any column (by name or 0-indexed position)
- Custom delimiters (comma, tab, semicolon, etc.) and encoding support
- Sanitizes file names for safe disk writing
- Optional filter to only split specified values
- Optional automatic packaging into a ZIP archive
- Summary report of generated files and row counts

Usage:
    python csv_split_by_column.py input.csv --column "Region" --out-dir ./split_output
    python csv_split_by_column.py data.csv --column 2 --zip output.zip
"""

import os
import sys
import csv
import re
import argparse
import zipfile
from collections import defaultdict
from typing import List, Dict, Any, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"


def sanitize_filename(name: str) -> str:
    """Sanitizes string for safe filesystem usage."""
    if not name or name.strip() == "":
        return "empty_value"
    # Replace invalid filename characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", str(name).strip())
    # Replace whitespace sequences with single underscore
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized[:100]  # Limit length for filesystem safety


def parse_column_specifier(specifier: str, header: List[str]) -> int:
    """Resolves column index from name or 0-indexed numeric string."""
    if specifier.isdigit():
        idx = int(specifier)
        if 0 <= idx < len(header):
            return idx
        raise ValueError(f"Column index {idx} out of range (0-{len(header)-1})")
    
    # Match by header name case-insensitively
    spec_lower = specifier.lower().strip()
    for idx, col in enumerate(header):
        if col.lower().strip() == spec_lower:
            return idx
            
    raise ValueError(f"Column '{specifier}' not found in CSV headers: {header}")


def split_csv(
    input_file: str,
    column_spec: str,
    out_dir: str,
    delimiter: str = ",",
    encoding: str = "utf-8",
    filter_values: Optional[List[str]] = None,
    zip_output: Optional[str] = None
) -> Dict[str, Any]:
    """Splits input CSV into multiple files grouped by column values."""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    os.makedirs(out_dir, exist_ok=True)

    filter_set = {v.lower().strip() for v in filter_values} if filter_values else None

    groups = defaultdict(list)
    header = []

    with open(input_file, mode="r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty")

        col_idx = parse_column_specifier(column_spec, header)
        col_name = header[col_idx]

        total_rows = 0
        for row in reader:
            if not row:
                continue
            total_rows += 1
            val = row[col_idx] if col_idx < len(row) else ""
            val_clean = val.strip()

            if filter_set and val_clean.lower() not in filter_set:
                continue

            groups[val_clean].append(row)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    written_files = []

    for val, rows in groups.items():
        safe_val = sanitize_filename(val)
        out_filename = f"{base_name}_{sanitize_filename(col_name)}_{safe_val}.csv"
        out_path = os.path.join(out_dir, out_filename)

        with open(out_path, mode="w", encoding=encoding, newline="") as f_out:
            writer = csv.writer(f_out, delimiter=delimiter)
            writer.writerow(header)
            writer.writerows(rows)

        written_files.append((out_path, len(rows)))

    # Package into zip if requested
    zip_path_result = None
    if zip_output:
        zip_path_result = zip_output if zip_output.endswith(".zip") else f"{zip_output}.zip"
        with zipfile.ZipFile(zip_path_result, "w", zipfile.ZIP_DEFLATED) as zipf:
            for filepath, _ in written_files:
                arcname = os.path.basename(filepath)
                zipf.write(filepath, arcname=arcname)

    return {
        "column_name": col_name,
        "total_rows": total_rows,
        "unique_groups": len(groups),
        "files": written_files,
        "zip_file": zip_path_result
    }


def main():
    parser = argparse.ArgumentParser(
        description="Split a CSV file into separate CSV files based on unique column values."
    )
    parser.add_argument("input_file", help="Path to input CSV file")
    parser.add_argument(
        "--column", "-c", required=True,
        help="Column name or 0-based column index to split by"
    )
    parser.add_argument(
        "--out-dir", "-o", default="split_output",
        help="Directory to save output CSV files (default: ./split_output)"
    )
    parser.add_argument(
        "--delimiter", "-d", default=",",
        help="CSV delimiter character (default: ',')"
    )
    parser.add_argument(
        "--encoding", default="utf-8",
        help="File encoding (default: utf-8)"
    )
    parser.add_argument(
        "--filter", nargs="+",
        help="Limit splitting to specific column values"
    )
    parser.add_argument(
        "--zip", help="Optionally compress output CSV files into a ZIP archive"
    )

    args = parser.parse_args()

    # Handle tab delimiter escape string '\\t'
    delimiter = "\t" if args.delimiter == "\\t" else args.delimiter

    try:
        print(f"\n{BOLD}{CYAN}=== CSV Split by Column Value ==={RESET}")
        print(f"Input file : {args.input_file}")
        print(f"Split column: {args.column}")
        print(f"Output dir  : {args.out_dir}\n")

        res = split_csv(
            input_file=args.input_file,
            column_spec=args.column,
            out_dir=args.out_dir,
            delimiter=delimiter,
            encoding=args.encoding,
            filter_values=args.filter,
            zip_output=args.zip
        )

        print(f"{GREEN}Split operation completed successfully!{RESET}")
        print(f"Target Column   : {res['column_name']}")
        print(f"Total Rows      : {res['total_rows']}")
        print(f"Unique Groups   : {res['unique_groups']}")
        print(f"Files Generated : {len(res['files'])}\n")

        print(f"{BOLD}Generated Files:{RESET}")
        for filepath, count in res["files"]:
            fname = os.path.basename(filepath)
            print(f" - {CYAN}{fname}{RESET} ({count} rows)")

        if res["zip_file"]:
            print(f"\n{GREEN}Packaged into ZIP archive: {res['zip_file']}{RESET}")

    except Exception as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
