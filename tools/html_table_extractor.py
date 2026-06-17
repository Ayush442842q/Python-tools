#!/usr/bin/env python3
"""
HTML Table Extractor
Extracts tables from HTML files, raw HTML string, or URLs and outputs them in CSV, JSON, or Markdown table formats.

Usage:
    python tools/html_table_extractor.py <source> [options]

Arguments:
    source                 Path to HTML file, URL, or "-" for stdin

Options:
    -f, --format FORMAT    Output format: csv, json, markdown (default: markdown)
    -i, --index INDEX      Zero-based index of the table to extract (default: 0, extracts first table. Use -1 to extract all)
    -o, --output FILE      Output file path (default: stdout)
    -h, --help             Show this help message and exit

Example:
    python tools/html_table_extractor.py sample.html -f markdown
    python tools/html_table_extractor.py https://example.com/page.html -i 1 -f csv
"""

import argparse
import json
import sys
import os
import urllib.request
from html.parser import HTMLParser


class TableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_tr = False
        self.in_cell = False
        self.is_header = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_tr = True
            self.current_row = []
        elif tag in ('th', 'td') and self.in_tr:
            self.in_cell = True
            self.is_header = (tag == 'th')
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_table:
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)
        elif tag == 'tr' and self.in_tr:
            self.in_tr = False
            self.current_table.append(self.current_row)
        elif tag in ('th', 'td') and self.in_cell:
            self.in_cell = False
            cell_text = "".join(self.current_cell).strip()
            self.current_row.append({
                'text': cell_text,
                'is_header': self.is_header
            })

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


def format_table(table, fmt):
    """Format a single table parsed into the specified format."""
    if not table:
        return ""

    # Prepare standard rows of strings
    rows = []
    for r in table:
        row_data = [cell['text'] for cell in r]
        rows.append(row_data)

    if fmt == 'json':
        # Check if first row consists of headers
        headers = []
        has_headers = len(table[0]) > 0 and any(cell['is_header'] for cell in table[0])
        if has_headers:
            headers = [cell['text'] for cell in table[0]]
            data_rows = rows[1:]
        else:
            headers = [f"Column_{i+1}" for i in range(len(rows[0]))]
            data_rows = rows

        json_data = []
        for row in data_rows:
            # Pad or truncate row to match header length
            row_dict = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else ""
                row_dict[h] = val
            json_data.append(row_dict)
        return json.dumps(json_data, indent=2)

    elif fmt == 'csv':
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    elif fmt == 'markdown':
        if not rows:
            return ""
        # Find column widths
        num_cols = max(len(row) for row in rows)
        col_widths = [0] * num_cols
        for row in rows:
            for i, cell in enumerate(row):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell))
        
        # Check if first row is header
        has_headers = len(table[0]) > 0 and any(cell['is_header'] for cell in table[0])
        
        lines = []
        
        # Header Row
        header_row = rows[0] if has_headers else [f"Column {i+1}" for i in range(num_cols)]
        # Pad row to match num_cols
        header_row += [""] * (num_cols - len(header_row))
        
        header_line = "| " + " | ".join(val.ljust(col_widths[i]) for i, val in enumerate(header_row)) + " |"
        lines.append(header_line)
        
        # Separator Row
        separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(num_cols)) + " |"
        lines.append(separator_line)
        
        # Data Rows
        start_idx = 1 if has_headers else 0
        for r_idx in range(start_idx, len(rows)):
            row = rows[r_idx]
            row += [""] * (num_cols - len(row))
            data_line = "| " + " | ".join(val.ljust(col_widths[i]) for i, val in enumerate(row)) + " |"
            lines.append(data_line)
            
        return "\n".join(lines)

    return ""


def main():
    parser = argparse.ArgumentParser(description="Extract tables from HTML files, raw HTML, or URLs.")
    parser.add_argument('source', help='HTML file path, URL, or "-" for stdin')
    parser.add_argument('-f', '--format', choices=['csv', 'json', 'markdown'], default='markdown',
                        help='Output format (default: markdown)')
    parser.add_argument('-i', '--index', type=int, default=0,
                        help='Zero-based index of the table to extract (default: 0, -1 for all)')
    parser.add_argument('-o', '--output', help='Output file path (default: stdout)')
    
    args = parser.parse_args()

    # Read HTML content
    html_content = ""
    try:
        if args.source == '-':
            html_content = sys.stdin.read()
        elif args.source.startswith('http://') or args.source.startswith('https://'):
            req = urllib.request.Request(
                args.source, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
        else:
            if not os.path.exists(args.source):
                print(f"Error: Source file '{args.source}' does not exist.", file=sys.stderr)
                return 1
            with open(args.source, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
    except Exception as e:
        print(f"Error reading source: {e}", file=sys.stderr)
        return 1

    # Parse HTML
    parser_obj = TableHTMLParser()
    parser_obj.feed(html_content)

    if not parser_obj.tables:
        print("No tables found in HTML source.", file=sys.stderr)
        return 1

    output_content = ""
    if args.index == -1:
        # Export all tables
        formatted_tables = []
        for idx, table in enumerate(parser_obj.tables):
            table_str = format_table(table, args.format)
            if args.format == 'markdown':
                formatted_tables.append(f"### Table {idx + 1}\n\n{table_str}")
            elif args.format == 'json':
                # Parse back to object to make one nested JSON
                formatted_tables.append(json.loads(table_str))
            else:
                formatted_tables.append(f"# Table {idx + 1}\n{table_str}")
        
        if args.format == 'json':
            output_content = json.dumps(formatted_tables, indent=2)
        elif args.format == 'csv':
            output_content = "\n\n".join(formatted_tables)
        else:
            output_content = "\n\n".join(formatted_tables)
    else:
        if args.index < 0 or args.index >= len(parser_obj.tables):
            print(f"Error: Table index {args.index} out of range (found {len(parser_obj.tables)} tables).", file=sys.stderr)
            return 1
        output_content = format_table(parser_obj.tables[args.index], args.format)

    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_content)
                f.write('\n')
            print(f"Successfully wrote table data to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_content)

    return 0


if __name__ == '__main__':
    sys.exit(main())
