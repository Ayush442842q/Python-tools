#!/usr/bin/env python3
"""
Markdown Table Parser
Parses Markdown tables from files or standard input and converts them into CSV, JSON, or TSV formats.
"""

import argparse
import json
import sys
import os
import re

def parse_markdown_table(text):
    """
    Parses a markdown table string into header list and row list.
    Handles escaped pipe characters `\\|`.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None, []

    # Find the table boundaries/rows
    table_lines = []
    in_table = False
    
    for line in lines:
        # Check if the line is part of a markdown table (starts/ends with | or contains |)
        if '|' in line:
            # We don't want to include horizontal lines that are not part of the table,
            # but usually a markdown table row has pipe characters.
            table_lines.append(line)
        elif table_lines:
            # If we had table lines and now we hit a non-table line, we stop
            break

    if not table_lines:
        return None, []

    parsed_rows = []
    for line in table_lines:
        # Strip outer pipes if present
        row_str = line
        if row_str.startswith('|'):
            row_str = row_str[1:]
        if row_str.endswith('|'):
            row_str = row_str[:-1]

        # Split by pipes, taking care of escaped pipes \|
        # A simple split('|') would break on \|. We use regex or a state machine split.
        parts = re.split(r'(?<!\\)\|', row_str)
        # Clean up parts (remove outer whitespace, unescape pipes)
        cells = [p.strip().replace(r'\|', '|') for p in parts]
        parsed_rows.append(cells)

    if len(parsed_rows) < 1:
        return None, []

    # Separate header, separator, and data rows
    header = parsed_rows[0]
    data_start = 1

    # Check if second row is the alignment row (e.g., |---|:---|---:|)
    if len(parsed_rows) > 1:
        second_row = parsed_rows[1]
        is_separator = True
        for cell in second_row:
            # Separator cells should consist of only -, :, or whitespace
            cleaned_cell = cell.replace('-', '').replace(':', '').strip()
            if cleaned_cell != '' and len(cell) > 0:
                is_separator = False
                break
        if is_separator:
            data_start = 2

    data_rows = parsed_rows[data_start:]
    
    # Normalize rows to have the same number of columns as the header
    num_cols = len(header)
    normalized_data_rows = []
    for row in data_rows:
        if len(row) < num_cols:
            row.extend([''] * (num_cols - len(row)))
        elif len(row) > num_cols:
            row = row[:num_cols]
        normalized_data_rows.append(row)

    return header, normalized_data_rows

def to_csv(header, rows, delimiter=','):
    """Formats the table data as CSV/TSV."""
    output = []
    def escape_csv_cell(cell):
        if delimiter in cell or '"' in cell or '\n' in cell or '\r' in cell:
            return '"' + cell.replace('"', '""') + '"'
        return cell

    if header:
        output.append(delimiter.join(escape_csv_cell(c) for c in header))
    for row in rows:
        output.append(delimiter.join(escape_csv_cell(c) for c in row))
    return '\n'.join(output)

def to_json(header, rows, as_objects=True):
    """Formats the table data as JSON."""
    if as_objects and header:
        json_data = []
        for row in rows:
            obj = {}
            for col_idx, col_name in enumerate(header):
                obj[col_name] = row[col_idx]
            json_data.append(obj)
        return json.dumps(json_data, indent=2)
    else:
        return json.dumps({
            "headers": header,
            "rows": rows
        }, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Parse Markdown tables from file or stdin and convert them to CSV, TSV, or JSON."
    )
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r', encoding='utf-8'), default=sys.stdin,
                        help='Input markdown file (default: stdin)')
    parser.add_argument('-f', '--format', choices=['csv', 'tsv', 'json', 'json-raw'], default='csv',
                        help='Output format (default: csv)')
    parser.add_argument('-o', '--output', help='Output file path (default: stdout)')

    args = parser.parse_args()

    try:
        content = args.infile.read()
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return 1

    header, data_rows = parse_markdown_table(content)

    if not header:
        print("Error: No markdown table structure found in input.", file=sys.stderr)
        return 1

    if args.format == 'csv':
        out_content = to_csv(header, data_rows, delimiter=',')
    elif args.format == 'tsv':
        out_content = to_csv(header, data_rows, delimiter='\t')
    elif args.format == 'json':
        out_content = to_json(header, data_rows, as_objects=True)
    elif args.format == 'json-raw':
        out_content = to_json(header, data_rows, as_objects=False)
    else:
        out_content = ""

    if args.output:
        try:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(out_content + '\n')
            print(f"Successfully converted and saved to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(out_content)

    return 0

if __name__ == '__main__':
    sys.exit(main())
