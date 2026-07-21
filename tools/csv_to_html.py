#!/usr/bin/env python3
"""
CSV to HTML Converter

Converts a CSV file into a clean, modern, responsive HTML table.

Usage:
    python tools/csv_to_html.py input.csv [-o output.html] [--title "My Table"]
"""

import argparse
import csv
import html
import os
import sys

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 2rem;
            background-color: #f8f9fa;
            color: #212529;
        }}
        h1 {{
            color: #343a40;
            margin-bottom: 1.5rem;
        }}
        .table-container {{
            overflow-x: auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            padding: 1rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th, td {{
            padding: 12px 15px;
            border-bottom: 1px solid #dee2e6;
        }}
        th {{
            background-color: #f1f3f5;
            color: #495057;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .footer {{
            margin-top: 1.5rem;
            font-size: 0.85rem;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="table-container">
        <table>
            <thead>
                {thead}
            </thead>
            <tbody>
                {tbody}
            </tbody>
        </table>
    </div>
    <div class="footer">
        Generated with CSV to HTML Converter. Total rows: {total_rows}
    </div>
</body>
</html>
"""

def csv_to_html(csv_path, title):
    thead_rows = []
    tbody_rows = []
    row_count = 0

    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Read header
            try:
                headers = next(reader)
                thead_rows.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>")
            except StopIteration:
                return "<p>Empty CSV file.</p>", 0

            # Read rows
            for row in reader:
                row_count += 1
                tbody_rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>")
                
    except Exception as e:
        print(f"Error processing CSV: {e}")
        sys.exit(1)

    thead = "\n                ".join(thead_rows)
    tbody = "\n                ".join(tbody_rows)

    return HTML_TEMPLATE.format(
        title=html.escape(title),
        thead=thead,
        tbody=tbody,
        total_rows=row_count
    ), row_count

def main():
    parser = argparse.ArgumentParser(description="CSV to HTML Converter - Convert CSV data into styled HTML tables")
    parser.add_argument('input', help='Path to the input CSV file')
    parser.add_argument('-o', '--output', help='Path to output HTML file (default: prints to stdout)')
    parser.add_argument('-t', '--title', default="CSV Data Export", help='Title of the HTML document')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: CSV file '{args.input}' not found.")
        return 1

    html_content, rows = csv_to_html(args.input, args.title)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"Successfully converted '{args.input}' to HTML. Saved to '{args.output}' (Rows: {rows})")
        except Exception as e:
            print(f"Error writing to output file: {e}")
            return 1
    else:
        print(html_content)

    return 0

if __name__ == "__main__":
    sys.exit(main())
