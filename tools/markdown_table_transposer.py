#!/usr/bin/env python3
"""
Markdown Table Transposer
-------------------------
A CLI utility to parse Markdown tables, transpose rows and columns, align column widths,
and handle alignment specifiers (:---, :---:, ---:).

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import argparse
from typing import List, Tuple, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_markdown_table(table_str: str) -> Tuple[List[str], List[List[str]], List[str]]:
    """
    Parses a markdown table string into headers, data rows, and alignment specifiers.
    """
    lines = [line.strip() for line in table_str.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Invalid Markdown table: must have at least header and separator lines.")

    def split_row(row_line: str) -> List[str]:
        if row_line.startswith("|"):
            row_line = row_line[1:]
        if row_line.endswith("|"):
            row_line = row_line[:-1]
        return [cell.strip() for cell in row_line.split("|")]

    headers = split_row(lines[0])
    sep_cells = split_row(lines[1])

    # Check separator syntax
    alignments = []
    for cell in sep_cells:
        cell_clean = cell.replace(" ", "")
        if cell_clean.startswith(":") and cell_clean.endswith(":"):
            alignments.append("center")
        elif cell_clean.endswith(":"):
            alignments.append("right")
        else:
            alignments.append("left")

    rows = []
    for line in lines[2:]:
        if "|" in line:
            row = split_row(line)
            # Pad or trim row to match header length
            if len(row) < len(headers):
                row.extend([""] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            rows.append(row)

    return headers, rows, alignments


def transpose_table(headers: List[str], rows: List[List[str]], alignments: List[str],
                    row_header_prefix: str = "Attribute") -> Tuple[List[str], List[List[str]], List[str]]:
    """
    Transposes table rows and columns.
    Original headers become the first column of the new table.
    """
    # Create new matrix: row 0 is header + rows data
    matrix = [headers] + rows

    num_rows = len(matrix)
    num_cols = len(matrix[0]) if num_rows > 0 else 0

    transposed_matrix = []
    for c in range(num_cols):
        new_row = [matrix[r][c] for r in range(num_rows)]
        transposed_matrix.append(new_row)

    # New headers: [row_header_prefix, "Row 1", "Row 2", ...]
    new_headers = [row_header_prefix] + [f"Record {i+1}" for i in range(len(rows))]
    new_rows = transposed_matrix
    new_alignments = ["left"] + ["left"] * len(rows)

    return new_headers, new_rows, new_alignments


def format_markdown_table(headers: List[str], rows: List[List[str]], alignments: List[str]) -> str:
    """
    Formats headers, rows, and alignments into a beautifully padded Markdown table.
    """
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
            else:
                col_widths.append(len(cell))

    # Minimum width of 3 for markdown separators
    col_widths = [max(w, 3) for w in col_widths]

    def build_row(cells: List[str]) -> str:
        formatted = []
        for i, cell in enumerate(cells):
            width = col_widths[i]
            align = alignments[i] if i < len(alignments) else "left"
            if align == "right":
                formatted.append(cell.rjust(width))
            elif align == "center":
                formatted.append(cell.center(width))
            else:
                formatted.append(cell.ljust(width))
        return "| " + " | ".join(formatted) + " |"

    def build_sep() -> str:
        seps = []
        for i, width in enumerate(col_widths):
            align = alignments[i] if i < len(alignments) else "left"
            if align == "center":
                seps.append(":" + "-" * (width - 2) + ":")
            elif align == "right":
                seps.append("-" * (width - 1) + ":")
            else:
                seps.append("-" * width)
        return "| " + " | ".join(seps) + " |"

    output_lines = [build_row(headers), build_sep()]
    for row in rows:
        output_lines.append(build_row(row))

    return "\n".join(output_lines)


def process_content(content: str, prefix: str) -> str:
    """
    Finds Markdown tables in text content and transposes them.
    """
    table_block_pattern = re.compile(
        r'((?:(?:\|[^\n]+\|\n?)|(?:[^\n]+\|[^\n]+\n?))+)', re.MULTILINE
    )

    blocks = table_block_pattern.findall(content)
    result = content

    for block in blocks:
        lines = [l for l in block.strip().splitlines() if "|" in l]
        if len(lines) >= 2 and "---" in lines[1]:
            try:
                headers, rows, alignments = parse_markdown_table("\n".join(lines))
                new_h, new_r, new_a = transpose_table(headers, rows, alignments, row_header_prefix=prefix)
                transposed_md = format_markdown_table(new_h, new_r, new_a)
                result = result.replace("\n".join(lines), transposed_md)
            except Exception as e:
                pass  # Skip non-table matching blocks

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Transpose rows and columns in Markdown tables."
    )
    parser.add_argument("file", nargs="?", help="Markdown file to process (reads stdin if omitted)")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify file in place")
    parser.add_argument("-p", "--prefix", default="Attribute", help="Label for transposed first column header (default: Attribute)")
    parser.add_argument("-o", "--output", help="Output file path")

    args = parser.parse_args()

    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        # Demo mode if no input provided
        print(f"{BLUE}{BOLD}Markdown Table Transposer - Demo Mode{RESET}\n")
        demo_table = (
            "| Name | Age | Role | Location |\n"
            "| :--- | :---: | ---: | :--- |\n"
            "| Alice | 28 | Engineer | New York |\n"
            "| Bob | 34 | Designer | London |\n"
            "| Charlie | 22 | Intern | Tokyo |"
        )
        print(f"{BOLD}Original Table:{RESET}\n{demo_table}\n")
        headers, rows, alignments = parse_markdown_table(demo_table)
        new_h, new_r, new_a = transpose_table(headers, rows, alignments, row_header_prefix=args.prefix)
        output_table = format_markdown_table(new_h, new_r, new_a)
        print(f"{GREEN}{BOLD}Transposed Table:{RESET}\n{output_table}")
        return

    result = process_content(content, args.prefix)

    if args.in_place and args.file:
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"{GREEN}Successfully transposed table(s) in {args.file}{RESET}")
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"{GREEN}Output saved to {args.output}{RESET}")
    else:
        print(result)


if __name__ == "__main__":
    main()
