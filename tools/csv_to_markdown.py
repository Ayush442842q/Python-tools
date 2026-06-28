#!/usr/bin/env python3
"""
CSV to Markdown Table Converter - Convert CSV/TSV to Markdown tables and vice-versa.

Usage:
    python tools/csv_to_markdown.py input.csv -o output.md
    python tools/csv_to_markdown.py input.md --reverse -o output.csv
"""

import sys
import os
import csv
import re
import argparse

def is_numeric(val):
    """Check if a string value is numeric (integer, float, or currency formatted)"""
    val = val.strip()
    if not val:
        return False
    # Strip currency symbols and commas
    cleaned = re.sub(r'^[$\u20ac\u00a3\u00a5]|\s|,', '', val)
    try:
        float(cleaned)
        return True
    except ValueError:
        return False

def csv_to_markdown(csv_content, delimiter=None, no_headers=False, custom_alignments=None):
    """Convert CSV text to Markdown table"""
    if not csv_content.strip():
        return ""
    
    # Auto-detect delimiter if not specified
    if not delimiter:
        try:
            sniffer = csv.Sniffer()
            # Sniff first 1024 bytes
            sample = csv_content[:1024]
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
        except Exception:
            # Fallback to comma, check if tab is present
            if '\t' in csv_content.split('\n')[0]:
                delimiter = '\t'
            elif ';' in csv_content.split('\n')[0]:
                delimiter = ';'
            else:
                delimiter = ','

    # Parse CSV lines
    reader = csv.reader(csv_content.strip().splitlines(), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return ""

    if no_headers:
        # Generate dummy headers
        headers = [f"Column {i+1}" for i in range(len(rows[0]))]
        data_rows = rows
    else:
        headers = rows[0]
        data_rows = rows[1:]

    num_cols = len(headers)
    
    # Pad shorter rows to match header column count
    for r in data_rows:
        while len(r) < num_cols:
            r.append("")
        # If row is longer, truncate it or adjust
        if len(r) > num_cols:
            r[:] = r[:num_cols]

    # Detect alignments
    alignments = []
    for col_idx in range(num_cols):
        if custom_alignments and col_idx < len(custom_alignments):
            alignments.append(custom_alignments[col_idx].upper())
        else:
            # Look at data rows to detect numeric columns
            numeric_count = 0
            empty_count = 0
            for r in data_rows:
                val = r[col_idx]
                if not val.strip():
                    empty_count += 1
                elif is_numeric(val):
                    numeric_count += 1
            
            valid_rows = len(data_rows) - empty_count
            if valid_rows > 0 and numeric_count / valid_rows >= 0.7:
                alignments.append('R') # Right align numeric columns
            else:
                alignments.append('L') # Left align others

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for r in data_rows:
        for col_idx in range(num_cols):
            col_widths[col_idx] = max(col_widths[col_idx], len(r[col_idx]))

    # Construct markdown table
    md_lines = []
    
    # 1. Header line
    header_cols = [headers[i].ljust(col_widths[i]) for i in range(num_cols)]
    md_lines.append("| " + " | ".join(header_cols) + " |")

    # 2. Separator line
    sep_cols = []
    for i in range(num_cols):
        align = alignments[i]
        width = col_widths[i]
        if align == 'R':
            sep_cols.append("-" * (width + 1) + ":")
        elif align == 'C':
            sep_cols.append(":" + "-" * width + ":")
        else: # 'L'
            sep_cols.append(":" + "-" * (width + 1))
    md_lines.append("| " + " | ".join(sep_cols) + " |")

    # 3. Data lines
    for r in data_rows:
        data_cols = []
        for i in range(num_cols):
            val = r[i]
            align = alignments[i]
            width = col_widths[i]
            if align == 'R':
                data_cols.append(val.rjust(width))
            elif align == 'C':
                data_cols.append(val.center(width))
            else: # 'L'
                data_cols.append(val.ljust(width))
        md_lines.append("| " + " | ".join(data_cols) + " |")

    return "\n".join(md_lines)

def markdown_to_csv(md_content, delimiter=','):
    """Convert Markdown table back to CSV format"""
    lines = md_content.strip().splitlines()
    csv_rows = []
    
    for line in lines:
        line = line.strip()
        # Check if line matches a table row structure
        if not line.startswith('|') or not line.endswith('|'):
            continue
        
        # Parse the cells
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        
        # Skip separator line (e.g. |---|---| or |:---|---:|)
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
            
        csv_rows.append(cells)

    if not csv_rows:
        return ""

    import io
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator='\n')
    writer.writerows(csv_rows)
    return output.getvalue()

def main():
    parser = argparse.ArgumentParser(
        description="CSV to Markdown Table Converter - Bidirectional converter for tabular data."
    )
    parser.add_argument("input", nargs="?", help="Input file path (reads from standard input if omitted).")
    parser.add_argument("-o", "--output", help="Output file path (writes to standard output if omitted).")
    parser.add_argument("-d", "--delimiter", help="Delimiter used in CSV/TSV (e.g. ',' or ';' or '\\t').")
    parser.add_argument("-r", "--reverse", action="store_true", help="Convert Markdown table back to CSV.")
    parser.add_argument("-a", "--align", help="Force column alignment. Comma-separated characters (L, C, R). Example: 'L,C,R,R'")
    parser.add_argument("--no-headers", action="store_true", help="CSV has no header row (generates dummy headers).")
    
    args = parser.parse_args()

    # Read input content
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: File '{args.input}' not found.", file=sys.stderr)
            return 1
        with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    else:
        # Check if stdin is empty (interactive check)
        if sys.stdin.isatty():
            parser.print_help()
            return 0
        content = sys.stdin.read()

    # Process alignments if provided
    custom_alignments = None
    if args.align:
        custom_alignments = [x.strip().upper() for x in args.align.split(',')]

    # Normalize escape sequences in delimiter
    delim = args.delimiter
    if delim == '\\t':
        delim = '\t'

    # Perform conversion
    try:
        if args.reverse:
            # Default separator back to comma
            output_delim = delim or ','
            result = markdown_to_csv(content, delimiter=output_delim)
        else:
            result = csv_to_markdown(
                content, 
                delimiter=delim, 
                no_headers=args.no_headers, 
                custom_alignments=custom_alignments
            )
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        return 1

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Conversion successful! Written to '{args.output}'")
    else:
        print(result)

    return 0

if __name__ == "__main__":
    sys.exit(main())
