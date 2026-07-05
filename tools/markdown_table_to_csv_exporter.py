#!/usr/bin/env python3
"""
Markdown Table to CSV Exporter
--------------------------------
Extracts tables from Markdown documents and exports them into CSV, TSV, or JSON formats.
Supports cleaning formatting tags (links, bold, italics, inline code) and handling multiple tables.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import csv
import json
import argparse
from typing import List, Dict, Any, Optional

# Terminal ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def clean_markdown_cell(text: str) -> str:
    """Strip common Markdown syntax from table cell text."""
    # Convert markdown links [text](url) to just text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bold / italic markers
    text = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', text)
    # Remove backtick code formatting
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Convert HTML line breaks to spaces
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Unescape escaped pipe characters
    text = text.replace(r'\|', '|')
    return text.strip()


def parse_markdown_tables(md_content: str, clean_formatting: bool = True) -> List[Dict[str, Any]]:
    """
    Parses all Markdown tables from a string.
    Returns a list of table dicts containing 'headers' and 'rows'.
    """
    tables = []
    lines = md_content.splitlines()
    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i].strip()
        # Look for potential header line containing pipe '|'
        if line.startswith("|") or ("|" in line and not line.startswith("```")):
            # Check if next line is a valid separator line (e.g. |---|---| or :---:)
            if i + 1 < num_lines:
                next_line = lines[i + 1].strip()
                if re.match(r'^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?$', next_line):
                    # Found table header and separator
                    table_lines = [line]
                    i += 2
                    # Gather data rows
                    while i < num_lines:
                        row_line = lines[i].strip()
                        if not row_line or ("|" not in row_line and not row_line.startswith("|")):
                            break
                        table_lines.append(row_line)
                        i += 1

                    # Parse headers and rows
                    headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
                    if clean_formatting:
                        headers = [clean_markdown_cell(h) for h in headers]

                    rows = []
                    for r_line in table_lines[1:]:
                        cells = [c.strip() for c in r_line.strip("|").split("|")]
                        if clean_formatting:
                            cells = [clean_markdown_cell(c) for c in cells]
                        # Pad row to match header count
                        while len(cells) < len(headers):
                            cells.append("")
                        rows.append(cells[:len(headers)])

                    tables.append({"headers": headers, "rows": rows})
                    continue
        i += 1

    return tables


def export_table(table: Dict[str, Any], format_type: str = "csv", delimiter: str = ",") -> str:
    """Exports a parsed table dict to CSV, TSV, or JSON string."""
    headers = table["headers"]
    rows = table["rows"]

    if format_type.lower() == "json":
        json_data = [dict(zip(headers, row)) for row in rows]
        return json.dumps(json_data, indent=2)
    else:
        import io
        output = io.StringIO()
        delim = "\t" if format_type.lower() == "tsv" else delimiter
        writer = csv.writer(output, delimiter=delim)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()


def run_demo():
    """Run interactive demonstration with sample Markdown containing tables."""
    sample_md = """# Sample Project Statistics

Here is the current team performance matrix:

| Employee ID | Name | Role | Tasks Completed | Status |
| :--- | :--- | :--- | :---: | ---: |
| EMP-101 | **Alice Smith** | Lead Engineer | 42 | `Active` |
| EMP-102 | [Bob Jones](mailto:bob@example.com) | Data Analyst | 35 | `Active` |
| EMP-103 | Charlie Brown | UI Designer | 28 | `On Leave` |
| EMP-104 | *Diana Prince* | DevOps Specialist | 50 | `Active` |

## Server Metrics Table

| Hostname | IP Address | Load Avg | Disk Usage |
| --- | --- | --- | --- |
| srv-01 | 192.168.1.10 | 0.45 | 68% |
| srv-02 | 192.168.1.11 | 1.12 | 84% |
"""
    print(f"{BOLD}{CYAN}=== Markdown Table to CSV Exporter Demo ==={RESET}\n")
    print(f"{BOLD}Input Markdown Text:{RESET}\n")
    print(sample_md)

    tables = parse_markdown_tables(sample_md, clean_formatting=True)
    print(f"{GREEN}Successfully parsed {len(tables)} table(s) from Markdown!{RESET}\n")

    for idx, table in enumerate(tables, start=1):
        print(f"{BOLD}{YELLOW}--- Table #{idx} (CSV Format) ---{RESET}")
        csv_out = export_table(table, format_type="csv")
        print(csv_out)

        print(f"{BOLD}{YELLOW}--- Table #{idx} (JSON Format) ---{RESET}")
        json_out = export_table(table, format_type="json")
        print(json_out)


def main():
    parser = argparse.ArgumentParser(
        description="Extract tables from Markdown files and export to CSV, TSV, or JSON."
    )
    parser.add_argument("input_file", nargs="?", help="Path to input Markdown file")
    parser.add_argument("-o", "--output", help="Output file path (prints to stdout if omitted)")
    parser.add_argument(
        "-f", "--format", choices=["csv", "tsv", "json"], default="csv", help="Output format (default: csv)"
    )
    parser.add_argument(
        "-t", "--table-index", type=int, default=0, help="Index of table to export (1-based, 0 exports all)"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Preserve raw Markdown formatting inside cells without cleaning"
    )
    parser.add_argument("--delimiter", default=",", help="Custom delimiter for CSV output (default: comma)")
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    args = parser.parse_args()

    if args.demo or (not args.input_file and sys.stdin.isatty()):
        run_demo()
        return

    if args.input_file:
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file '{args.input_file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content = sys.stdin.read()

    tables = parse_markdown_tables(content, clean_formatting=not args.raw)

    if not tables:
        print("No valid Markdown tables found in the input.", file=sys.stderr)
        sys.exit(1)

    if args.table_index > 0:
        if args.table_index > len(tables):
            print(
                f"Error: Specified table index {args.table_index} exceeds total tables found ({len(tables)}).",
                file=sys.stderr,
            )
            sys.exit(1)
        target_tables = [tables[args.table_index - 1]]
    else:
        target_tables = tables

    output_chunks = []
    for idx, table in enumerate(target_tables, start=1):
        exported = export_table(table, format_type=args.format, delimiter=args.delimiter)
        if len(target_tables) > 1 and args.format in ("csv", "tsv"):
            output_chunks.append(f"# Table {idx}\n" + exported)
        else:
            output_chunks.append(exported)

    final_output = "\n".join(output_chunks)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(final_output)
            print(f"Exported {len(target_tables)} table(s) to '{args.output}'.")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(final_output)


if __name__ == "__main__":
    main()
