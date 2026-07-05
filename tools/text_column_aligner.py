#!/usr/bin/env python3
"""
Text Column Aligner
-------------------
Aligns tabular text, space-separated or delimiter-separated data into neat, padded columns.
Supports left, right, and center column alignments, custom border/header styles, and max width limits.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import argparse
from typing import List, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def split_line_into_columns(line: str, delimiter: Optional[str] = None) -> List[str]:
    """Splits a text line into columns based on delimiter or whitespace runs."""
    if delimiter:
        return [col.strip() for col in line.split(delimiter)]
    else:
        # Split on whitespace sequences, but ignore empty leading/trailing
        return [col.strip() for col in re.split(r'\s{2,}|\t', line.strip()) if col.strip()]


def align_columns(
    lines: List[str],
    delimiter: Optional[str] = None,
    separator: str = " | ",
    alignment: str = "left",
    has_header: bool = True,
    max_col_width: Optional[int] = None,
) -> str:
    """
    Parses lines of text and aligns them into tabular formatted output.
    """
    if not lines:
        return ""

    table_data = [split_line_into_columns(line, delimiter) for line in lines if line.strip()]
    if not table_data:
        return ""

    num_cols = max(len(row) for row in table_data)

    # Normalize row lengths
    for row in table_data:
        while len(row) < num_cols:
            row.append("")

    # Calculate column width requirements
    col_widths = [0] * num_cols
    for row in table_data:
        for c_idx, val in enumerate(row):
            w = len(val)
            if max_col_width and w > max_col_width:
                w = max_col_width
            col_widths[c_idx] = max(col_widths[c_idx], w)

    formatted_lines = []

    def format_cell(text: str, width: int, align_mode: str) -> str:
        if max_col_width and len(text) > max_col_width:
            text = text[: max_col_width - 3] + "..."
        if align_mode == "center":
            return text.center(width)
        elif align_mode == "right":
            return text.rjust(width)
        else:
            return text.ljust(width)

    for r_idx, row in enumerate(table_data):
        formatted_cells = []
        for c_idx, val in enumerate(row):
            cell_str = format_cell(val, col_widths[c_idx], alignment)
            formatted_cells.append(cell_str)

        row_str = separator.join(formatted_cells)
        formatted_lines.append(row_str)

        # Insert header separator line after first row if header is enabled
        if r_idx == 0 and has_header:
            sep_cells = ["-" * col_widths[c_idx] for c_idx in range(num_cols)]
            header_border = separator.join(sep_cells)
            formatted_lines.append(header_border)

    return "\n".join(formatted_lines)


def run_demo():
    """Run interactive demonstration."""
    sample_text = """Service Status Port Uptime Memory
api-gateway RUNNING 8080 14d12h 128MB
auth-service RUNNING 8081 14d12h 64MB
database-cluster HEALTHY 5432 45d06h 4096MB
redis-cache WARNING 6379 2d01h 1024MB
monitoring-agent OFF 9090 0s 0MB"""

    print(f"{BOLD}{CYAN}=== Text Column Aligner Demo ==={RESET}\n")
    print(f"{BOLD}Unformatted Input Text:{RESET}\n")
    print(sample_text)

    lines = sample_text.splitlines()

    print(f"\n{BOLD}{YELLOW}--- Left-Aligned with Pipe Separator ---{RESET}")
    print(align_columns(lines, alignment="left", separator=" | ", has_header=True))

    print(f"\n{BOLD}{YELLOW}--- Center-Aligned with Box Border ---{RESET}")
    print(align_columns(lines, alignment="center", separator=" │ ", has_header=True))


def main():
    parser = argparse.ArgumentParser(
        description="Align misaligned text data into neat, padded columns."
    )
    parser.add_argument("input_file", nargs="?", help="Input text file path (reads stdin if omitted)")
    parser.add_argument("-d", "--delimiter", help="Input column delimiter (splits by spaces if omitted)")
    parser.add_argument("-s", "--separator", default=" | ", help="Output column separator (default: ' | ')")
    parser.add_argument(
        "-a",
        "--alignment",
        choices=["left", "center", "right"],
        default="left",
        help="Column text alignment (default: left)",
    )
    parser.add_argument(
        "--no-header", action="store_true", help="Do not treat the first row as a header line"
    )
    parser.add_argument("-w", "--max-width", type=int, help="Maximum width for any column (truncates long cells)")
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    args = parser.parse_args()

    if args.demo or (not args.input_file and sys.stdin.isatty()):
        run_demo()
        return

    if args.input_file:
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading file '{args.input_file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        lines = sys.stdin.readlines()

    output = align_columns(
        lines,
        delimiter=args.delimiter,
        separator=args.separator,
        alignment=args.alignment,
        has_header=not args.no_header,
        max_col_width=args.max_width,
    )
    print(output)


if __name__ == "__main__":
    main()
