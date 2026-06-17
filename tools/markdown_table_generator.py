#!/usr/bin/env python3
"""
Markdown Table Generator - Convert CSV, JSON, or delimited text into Markdown tables.
"""

import argparse
import csv
import json
import sys
import os

def parse_csv(content, delimiter=','):
    """Parse CSV content into a list of rows."""
    try:
        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        return [row for row in reader if row]
    except Exception as e:
        print(f"Error parsing CSV: {e}", file=sys.stderr)
        return []

def parse_json(content):
    """Parse JSON content into a list of rows."""
    try:
        data = json.loads(content)
        if isinstance(data, list):
            if all(isinstance(row, list) for row in data):
                return data
            elif all(isinstance(row, dict) for row in data):
                # JSON array of objects
                # Get all unique keys for headers
                headers = []
                for item in data:
                    for key in item.keys():
                        if key not in headers:
                            headers.append(key)
                
                rows = [headers]
                for item in data:
                    rows.append([str(item.get(h, '')) for h in headers])
                return rows
        elif isinstance(data, dict):
            # Key-value dictionary table
            rows = [["Key", "Value"]]
            for k, v in data.items():
                rows.append([str(k), str(v)])
            return rows
        print("Error: JSON must be an array of arrays, array of objects, or a key-value dictionary.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return []

def format_markdown_table(rows, alignments=None, has_header=True):
    """Generate aligned Markdown table from rows."""
    if not rows:
        return ""
    
    # Pad all rows to have the same number of columns
    num_cols = max(len(row) for row in rows)
    padded_rows = []
    for row in rows:
        padded = [str(cell).strip().replace('\n', ' ') for cell in row]
        if len(padded) < num_cols:
            padded += [''] * (num_cols - len(padded))
        padded_rows.append(padded)
    
    # Calculate column widths
    col_widths = [0] * num_cols
    for row in padded_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    
    # Ensure a minimum width for empty columns
    col_widths = [max(w, 3) for w in col_widths]
    
    # Prepare alignments
    align_list = ['left'] * num_cols
    if alignments:
        for i, align in enumerate(alignments[:num_cols]):
            if align.lower() in ('c', 'center'):
                align_list[i] = 'center'
            elif align.lower() in ('r', 'right'):
                align_list[i] = 'right'
    
    output = []
    
    # Header row
    header_row = padded_rows[0] if has_header else [f"Column {i+1}" for i in range(num_cols)]
    header_line = "| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(header_row)) + " |"
    output.append(header_line)
    
    # Separator row
    sep_cells = []
    for i, align in enumerate(align_list):
        width = col_widths[i]
        if align == 'center':
            sep_cells.append(":" + "-" * (width - 2) + ":")
        elif align == 'right':
            sep_cells.append("-" * (width - 1) + ":")
        else:
            sep_cells.append(":" + "-" * (width - 1))
    output.append("| " + " | ".join(sep_cells) + " |")
    
    # Data rows
    start_idx = 1 if has_header else 0
    for row in padded_rows[start_idx:]:
        row_cells = []
        for i, cell in enumerate(row):
            width = col_widths[i]
            align = align_list[i]
            if align == 'center':
                row_cells.append(cell.center(width))
            elif align == 'right':
                row_cells.append(cell.rjust(width))
            else:
                row_cells.append(cell.ljust(width))
        output.append("| " + " | ".join(row_cells) + " |")
        
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Convert CSV, JSON, or Delimited text to Markdown table.")
    parser.add_argument("input_file", nargs="?", help="Input file path (reads from stdin if omitted)")
    parser.add_argument("-o", "--output", help="Output file path (prints to stdout if omitted)")
    parser.add_argument("-t", "--type", choices=['csv', 'json', 'tsv'], help="Force parsing type")
    parser.add_argument("-d", "--delimiter", default=",", help="Delimiter for text/CSV input (default: comma)")
    parser.add_argument("-a", "--align", help="Alignments as comma-separated letters: l (left), c (center), r (right)")
    parser.add_argument("--no-header", action="store_true", help="Input does not have a header row")
    
    args = parser.parse_args()
    
    # Read input
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Guess type if not specified
            file_type = args.type or os.path.splitext(args.input_file)[1].lower().lstrip('.')
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content = sys.stdin.read()
        file_type = args.type or 'csv'
        
    if not content.strip():
        print("Error: Input is empty.", file=sys.stderr)
        sys.exit(1)
        
    # Determine delimiter
    delim = args.delimiter
    if file_type == 'tsv' or args.type == 'tsv':
        delim = '\t'
        
    # Parse rows
    if file_type == 'json' or args.type == 'json':
        rows = parse_json(content)
    else:
        rows = parse_csv(content, delimiter=delim)
        
    if not rows:
        print("Error: Could not extract table rows from input.", file=sys.stderr)
        sys.exit(1)
        
    # Parse alignments
    alignments = []
    if args.align:
        alignments = [x.strip() for x in args.align.split(',')]
        
    # Generate table
    table = format_markdown_table(rows, alignments, has_header=not args.no_header)
    
    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(table + '\n')
            print(f"Successfully generated Markdown table to {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(table)

if __name__ == "__main__":
    main()
