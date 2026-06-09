#!/usr/bin/env python3
"""
Markdown Table Generator

Creates formatted Markdown tables from CSV or raw text inputs.
Supports reading from files or standard input, custom delimiters, column alignments, 
and outputting directly to console or a file.

Usage:
    python tools/markdown_table_generator.py -i data.csv
    python tools/markdown_table_generator.py --delimiter ";" --align L C R -i data.txt
    cat data.csv | python tools/markdown_table_generator.py
"""

import argparse
import csv
import io
import os
import sys

def generate_markdown_table(rows, has_header=True, alignments=None):
    """
    Generates a formatted markdown table string from a list of rows (lists of strings).
    """
    if not rows:
        return ""

    # Determine maximum number of columns
    num_cols = max(len(row) for row in rows)

    # Pad rows that have fewer columns
    for row in rows:
        if len(row) < num_cols:
            row.extend([""] * (num_cols - len(row)))

    # Parse alignments
    # Alignments can be L (left), C (center), R (right). Default is Left.
    align_styles = []
    if alignments:
        # Map input characters to their representation
        for i in range(num_cols):
            if i < len(alignments):
                char = alignments[i].upper()
                if char in ('L', 'LEFT'):
                    align_styles.append('L')
                elif char in ('R', 'RIGHT'):
                    align_styles.append('R')
                elif char in ('C', 'CENTER'):
                    align_styles.append('C')
                else:
                    align_styles.append('L')
            else:
                align_styles.append('L')
    else:
        align_styles = ['L'] * num_cols

    # Separate header and data rows
    if has_header:
        headers = [str(cell).strip() for cell in rows[0]]
        data_rows = [[str(cell).strip() for cell in row] for row in rows[1:]]
    else:
        headers = [f"Column {i+1}" for i in range(num_cols)]
        data_rows = [[str(cell).strip() for cell in row] for row in rows]

    # Calculate the maximum width of each column (minimum width of 3 for Markdown formatting)
    col_widths = [3] * num_cols
    for i in range(num_cols):
        col_widths[i] = max(col_widths[i], len(headers[i]))
        for row in data_rows:
            col_widths[i] = max(col_widths[i], len(row[i]))

    # Helper function to pad cell based on alignment
    def format_cell(val, width, alignment):
        if alignment == 'R':
            return val.rjust(width)
        elif alignment == 'C':
            return val.center(width)
        else:
            return val.ljust(width)

    # Build header row
    header_line = "| " + " | ".join(format_cell(headers[i], col_widths[i], align_styles[i]) for i in range(num_cols)) + " |"

    # Build separator row
    separator_parts = []
    for i in range(num_cols):
        width = col_widths[i]
        align = align_styles[i]
        if align == 'R':
            separator_parts.append("-" * (width + 1) + ":")
        elif align == 'C':
            separator_parts.append(":" + "-" * width + ":")
        else:
            separator_parts.append(":" + "-" * (width + 1))
    separator_line = "|" + "|".join(separator_parts) + "|"

    # Build data rows
    markdown_lines = [header_line, separator_line]
    for row in data_rows:
        row_line = "| " + " | ".join(format_cell(row[i], col_widths[i], align_styles[i]) for i in range(num_cols)) + " |"
        markdown_lines.append(row_line)

    return "\n".join(markdown_lines)

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Table Generator - Convert CSV or structured text into formatted Markdown tables."
    )
    parser.add_argument(
        '-i', '--input', 
        help='Path to the input file containing CSV/delimited text. If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-d', '--delimiter', 
        default=',', 
        help='Delimiter character separating fields (default: comma ","). Use "\\t" for tab.'
    )
    parser.add_argument(
        '-a', '--align', 
        nargs='*', 
        help='Alignments for columns: L (left), C (center), R (right). Can specify multiple, e.g. -a L C R.'
    )
    parser.add_argument(
        '--no-header', 
        action='store_true', 
        help='Treat the first line of the input as data instead of headers.'
    )
    parser.add_argument(
        '-o', '--output', 
        help='Path to save the generated Markdown table. If omitted, prints to console.'
    )

    args = parser.parse_args()

    # Determine input source
    if args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', newline='', encoding='utf-8') as f:
                input_data = f.read()
        except Exception as e:
            print(f"[ERROR] Could not read file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        input_data = sys.stdin.read()

    if not input_data.strip():
        print("[ERROR] Input data is empty.", file=sys.stderr)
        return 1

    # Normalize tab delimiter if specified
    delim = args.delimiter
    if delim == '\\t':
        delim = '\t'

    # Parse rows using csv reader
    try:
        reader = csv.reader(io.StringIO(input_data), delimiter=delim)
        rows = list(reader)
    except Exception as e:
        print(f"[ERROR] Failed to parse input text as delimited data: {e}", file=sys.stderr)
        return 1

    if not rows:
        print("[ERROR] No valid rows found in the input data.", file=sys.stderr)
        return 1

    # Flatten alignments argument if provided as a single string/list of chars
    alignments = None
    if args.align:
        # If the user passed something like ["LCR"], split it into ['L', 'C', 'R']
        alignments = []
        for a in args.align:
            alignments.extend(list(a))

    markdown_table = generate_markdown_table(rows, has_header=not args.no_header, alignments=alignments)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_table + "\n")
            print(f"[OK] Markdown table successfully written to '{args.output}'.")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(markdown_table)

    return 0

if __name__ == '__main__':
    sys.exit(main())
