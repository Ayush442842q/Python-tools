#!/usr/bin/env python3
"""
Markdown Table Math Evaluator
Parses Markdown tables, evaluates embedded math formulas (e.g. =SUM(B1:B3), =AVG(C:C), =B1*C1),
updates cell values and summary footer rows, and formats the table with clean alignment.
"""

import re
import sys
import os
import argparse
from typing import List, Dict, Any, Tuple, Optional

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def col_name_to_index(col_name: str) -> int:
    """Converts column letter like 'A', 'B' to 0-based index."""
    res = 0
    for char in col_name.upper():
        res = res * 26 + (ord(char) - ord('A') + 1)
    return res - 1


def parse_cell_ref(cell_ref: str) -> Tuple[int, int]:
    """Parses cell reference like 'B2' into (row_1based, col_0based)."""
    match = re.match(r'^([A-Z]+)(\d+)$', cell_ref.upper())
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    col_str, row_str = match.groups()
    return int(row_str), col_name_to_index(col_str)


def parse_md_table(lines: List[str]) -> Tuple[List[str], List[List[str]], List[str]]:
    """Extracts table header, rows grid, and separator alignment lines."""
    headers: List[str] = []
    separators: List[str] = []
    rows: List[List[str]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not headers:
            headers = cells
        elif not separators and all(re.match(r'^:?-+:?$', c) for c in cells):
            separators = cells
        else:
            rows.append(cells)

    return headers, rows, separators


def evaluate_table(
    headers: List[str],
    rows: List[List[str]],
    precision: int = 2
) -> List[List[str]]:
    """Evaluates formulas in table grid and returns updated rows."""
    grid: Dict[Tuple[int, int], str] = {}
    num_rows = len(rows)

    # Populate cell grid: row 1..N = data rows
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            grid[(r_idx, c_idx)] = val

    def get_number(val_str: str) -> Optional[float]:
        clean = re.sub(r'[\$,]', '', val_str).strip()
        try:
            return float(clean)
        except ValueError:
            return None

    def eval_expression(expr: str, current_r: int, current_c: int) -> str:
        expr = expr.strip()
        if not expr.startswith("="):
            return expr

        formula = expr[1:].strip()

        # Handle range functions: =SUM(B1:B3), =AVG(B1:B3), =MIN(B1:B3), =MAX(B1:B3), =COUNT(B1:B3)
        func_match = re.match(r'^(SUM|AVG|MIN|MAX|COUNT)\(([A-Z]+\d+):([A-Z]+\d+)\)$', formula, re.IGNORECASE)
        if func_match:
            fn, start_ref, end_ref = func_match.groups()
            fn = fn.upper()
            r1, c1 = parse_cell_ref(start_ref)
            r2, c2 = parse_cell_ref(end_ref)

            values: List[float] = []
            for r in range(min(r1, r2), max(r1, r2) + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    if r == current_r and c == current_c:
                        continue
                    raw_val = grid.get((r, c), "")
                    num = get_number(raw_val)
                    if num is not None:
                        values.append(num)

            if not values:
                return "0"

            if fn == "SUM": res = sum(values)
            elif fn == "AVG": res = sum(values) / len(values)
            elif fn == "MIN": res = min(values)
            elif fn == "MAX": res = max(values)
            elif fn == "COUNT": res = float(len(values))

            return f"{res:.{precision}f}" if precision > 0 else f"{int(round(res))}"

        # Handle column full range functions: =SUM(B:B), =AVG(C:C)
        col_func_match = re.match(r'^(SUM|AVG|MIN|MAX|COUNT)\(([A-Z]+):([A-Z]+)\)$', formula, re.IGNORECASE)
        if col_func_match:
            fn, col_start, col_end = col_func_match.groups()
            fn = fn.upper()
            c1 = col_name_to_index(col_start)
            c2 = col_name_to_index(col_end)

            values: List[float] = []
            for r in range(1, num_rows + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    if r == current_r and c == current_c:
                        continue
                    raw_val = grid.get((r, c), "")
                    if raw_val.startswith("="):
                        continue
                    num = get_number(raw_val)
                    if num is not None:
                        values.append(num)

            if not values:
                return "0"

            if fn == "SUM": res = sum(values)
            elif fn == "AVG": res = sum(values) / len(values)
            elif fn == "MIN": res = min(values)
            elif fn == "MAX": res = max(values)
            elif fn == "COUNT": res = float(len(values))

            return f"{res:.{precision}f}" if precision > 0 else f"{int(round(res))}"

        # Handle basic cell arithmetic: =B1*C1, =B2+C2
        arith_match = re.match(r'^([A-Z]+\d+)\s*([\+\-\*/])\s*([A-Z]+\d+)$', formula, re.IGNORECASE)
        if arith_match:
            ref1, op, ref2 = arith_match.groups()
            r1, c1 = parse_cell_ref(ref1)
            r2, c2 = parse_cell_ref(ref2)
            n1 = get_number(grid.get((r1, c1), "0")) or 0.0
            n2 = get_number(grid.get((r2, c2), "0")) or 0.0

            if op == "+": res = n1 + n2
            elif op == "-": res = n1 - n2
            elif op == "*": res = n1 * n2
            elif op == "/": res = n1 / n2 if n2 != 0 else 0.0

            return f"{res:.{precision}f}" if precision > 0 else f"{int(round(res))}"

        return expr

    # First pass: evaluate arithmetic across individual rows
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, cell in enumerate(row):
            if cell.startswith("=") and not any(f in cell.upper() for f in ["SUM", "AVG", "MIN", "MAX", "COUNT"]):
                eval_val = eval_expression(cell, r_idx, c_idx)
                grid[(r_idx, c_idx)] = eval_val

    # Second pass: evaluate aggregate range functions (e.g. totals)
    updated_rows: List[List[str]] = []
    for r_idx, row in enumerate(rows, start=1):
        new_row = []
        for c_idx, cell in enumerate(row):
            if cell.startswith("="):
                eval_val = eval_expression(cell, r_idx, c_idx)
                grid[(r_idx, c_idx)] = eval_val
                new_row.append(eval_val)
            else:
                new_row.append(cell)
        updated_rows.append(new_row)

    return updated_rows


def render_md_table(headers: List[str], rows: List[List[str]]) -> str:
    """Renders table into a formatted Markdown string."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(cell))
            else:
                col_widths.append(len(cell))

    header_line = "| " + " | ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers))) + " |"
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    row_lines = [
        "| " + " | ".join(f"{(row[i] if i < len(row) else ''):<{col_widths[i]}}" for i in range(len(headers))) + " |"
        for row in rows
    ]

    return "\n".join([header_line, sep_line] + row_lines)


def run_demo() -> None:
    """Runs demonstration mode with a sample sales invoice markdown table."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== Markdown Table Math Evaluator Demo ==={COLOR_RESET}\n")

    sample_table = """| Item | Quantity | Unit Price | Total |
| --- | --- | --- | --- |
| Widget A | 10 | 15.50 | =B1*C1 |
| Widget B | 5 | 42.00 | =B2*C2 |
| Service Fee | 1 | 100.00 | =B3*C3 |
| **Total** | =SUM(B1:B3) | | =SUM(D1:D3) |"""

    print(f"{COLOR_BOLD}Input Markdown Table (With Formulas):{COLOR_RESET}")
    print(sample_table)
    print()

    lines = sample_table.strip().splitlines()
    headers, rows, _ = parse_md_table(lines)
    evaluated_rows = evaluate_table(headers, rows, precision=2)
    rendered = render_md_table(headers, evaluated_rows)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Evaluated Markdown Table Result:{COLOR_RESET}")
    print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluates inline standard math formulas (=SUM, =AVG, =A1*B1) inside Markdown tables."
    )
    parser.add_argument("file", nargs="?", help="Markdown file containing tables")
    parser.add_argument("-p", "--precision", type=int, default=2, help="Decimal precision for evaluated numbers")
    parser.add_argument("-i", "--in-place", action="store_true", help="Update input file in place")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demonstration mode")

    args = parser.parse_args()

    if args.demo or not args.file:
        if not args.demo:
            print(f"{COLOR_YELLOW}No Markdown file provided. Running demo mode...{COLOR_RESET}\n")
        run_demo()
        return

    if not os.path.exists(args.file):
        print(f"{COLOR_RED}Error: File '{args.file}' not found.{COLOR_RESET}")
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    headers, rows, _ = parse_md_table(lines)

    if not headers or not rows:
        print(f"{COLOR_RED}Error: No valid Markdown table found in file.{COLOR_RESET}")
        sys.exit(1)

    evaluated_rows = evaluate_table(headers, rows, precision=args.precision)
    rendered = render_md_table(headers, evaluated_rows)

    if args.in_place:
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(rendered + "\n")
        print(f"{COLOR_GREEN}Successfully updated '{args.file}' in place.{COLOR_RESET}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
