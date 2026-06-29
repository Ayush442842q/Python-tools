#!/usr/bin/env python3
"""
CSV Transpose Utility

Rotates rows to columns and columns to rows in a delimited text file (CSV, TSV)
or markdown table. Supports customizing headers, padding, and output formats.

Usage:
    python tools/csv_transpose_utility.py input.csv [options]
"""

import argparse
import csv
import io
import sys

def parse_markdown_table(file_content):
    """Parse Markdown table format into list of lists."""
    rows = []
    lines = file_content.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line.startswith('|') or not line.endswith('|'):
            continue
        # Split by | and strip whitespace
        parts = [p.strip() for p in line.split('|')[1:-1]]
        # Ignore divider line (e.g., |---|---|)
        if all(all(c in '-:| ' for c in part) for part in parts) and len(parts) > 0:
            continue
        rows.append(parts)
    return rows

def format_markdown_table(matrix):
    """Format a matrix of strings into a Markdown table."""
    if not matrix:
        return ""
    
    # Calculate column widths
    col_widths = [0] * len(matrix[0])
    for row in matrix:
        for col_idx, cell in enumerate(row):
            col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))
            
    output = io.StringIO()
    # Write headers
    headers = [str(cell).ljust(col_widths[i]) for i, cell in enumerate(matrix[0])]
    output.write("| " + " | ".join(headers) + " |\n")
    
    # Write divider
    dividers = ["-" * col_widths[i] for i in range(len(col_widths))]
    output.write("| " + " | ".join(dividers) + " |\n")
    
    # Write data rows
    for row in matrix[1:]:
        cells = [str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)]
        output.write("| " + " | ".join(cells) + " |\n")
        
    return output.getvalue()

def transpose_matrix(matrix, fill_value=""):
    """Transpose a 2D grid/list of lists, padding rows of unequal length."""
    if not matrix:
        return []
        
    max_cols = max(len(row) for row in matrix)
    transposed = []
    
    for col_idx in range(max_cols):
        new_row = []
        for row in matrix:
            if col_idx < len(row):
                new_row.append(row[col_idx])
            else:
                new_row.append(fill_value)
        transposed.append(new_row)
        
    return transposed

def main():
    parser = argparse.ArgumentParser(
        description="Transpose utility for CSV, TSV, and Markdown tables."
    )
    parser.add_argument("input", nargs="?", default="-", 
                        help="Path to the input file (default: stdin)")
    parser.add_argument("-d", "--delimiter", default=None,
                        help="CSV delimiter character (default: autodetect or comma)")
    parser.add_argument("-f", "--format", choices=["csv", "tsv", "markdown", "json"], default="csv",
                        help="Output format (default: csv)")
    parser.add_argument("-p", "--pad", default="",
                        help="Value to pad shorter rows with (default: empty string)")
    parser.add_argument("-m", "--markdown", action="store_true",
                        help="Treat input file as a Markdown table")
    parser.add_argument("-o", "--output", help="Path to save output file (default: stdout)")

    args = parser.parse_args()

    # Read input content
    try:
        if args.input == "-":
            content = sys.stdin.read()
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                content = f.read()
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return 1

    if not content.strip():
        print("Error: Input is empty.", file=sys.stderr)
        return 1

    # Parse input matrix
    matrix = []
    if args.markdown or (args.input != "-" and args.input.endswith(".md")) or content.strip().startswith("|"):
        matrix = parse_markdown_table(content)
    else:
        # Delimiter detection
        delim = args.delimiter
        if delim is None:
            # Simple autodetect heuristic
            first_line = content.splitlines()[0] if content else ""
            if "\t" in first_line:
                delim = "\t"
            elif ";" in first_line:
                delim = ";"
            else:
                delim = ","
                
        reader = csv.reader(io.StringIO(content), delimiter=delim)
        try:
            matrix = list(reader)
        except Exception as e:
            print(f"Error parsing CSV: {e}", file=sys.stderr)
            return 1

    if not matrix:
        print("Error: No tabular data parsed.", file=sys.stderr)
        return 1

    # Perform transpose
    transposed = transpose_matrix(matrix, fill_value=args.pad)

    # Format output
    out_content = ""
    if args.format == "csv":
        out_io = io.StringIO()
        writer = csv.writer(out_io, delimiter=",")
        writer.writerows(transposed)
        out_content = out_io.getvalue()
    elif args.format == "tsv":
        out_io = io.StringIO()
        writer = csv.writer(out_io, delimiter="\t")
        writer.writerows(transposed)
        out_content = out_io.getvalue()
    elif args.format == "markdown":
        out_content = format_markdown_table(transposed)
    elif args.format == "json":
        import json
        # Output as lists of objects if first col was header, or list of lists
        out_content = json.dumps(transposed, indent=2)

    # Write output
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_content)
        else:
            sys.stdout.write(out_content)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
