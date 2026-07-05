#!/usr/bin/env python3
"""CSV Correlation Matrix Calculator

Computes Pearson, Spearman, or Kendall rank correlation matrices between
numerical columns in CSV files, and displays ASCII heatmaps or formatted tables.
"""

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


def rank_data(vector: List[float]) -> List[float]:
    """Assign ranks to a list of numbers (handling ties by average rank)."""
    sorted_indices = sorted(range(len(vector)), key=lambda i: vector[i])
    ranks = [0.0] * len(vector)

    i = 0
    while i < len(vector):
        j = i
        while j < len(vector) and vector[sorted_indices[j]] == vector[sorted_indices[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[sorted_indices[k]] = avg_rank
        i = j
    return ranks


def pearson_correlation(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((y[i] - mean_y) ** 2 for i in range(n))

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0
    return cov / denom


def spearman_correlation(x: List[float], y: List[float]) -> float:
    rank_x = rank_data(x)
    rank_y = rank_data(y)
    return pearson_correlation(rank_x, rank_y)


def colorize_val(val: float) -> str:
    """Format correlation value with ANSI color based on strength."""
    val_str = f"{val:+.2f}"
    if val >= 0.7:
        return f"\033[32m{val_str}\033[0m"  # Strong positive green
    elif val >= 0.3:
        return f"\033[36m{val_str}\033[0m"  # Moderate cyan
    elif val <= -0.7:
        return f"\033[31m{val_str}\033[0m"  # Strong negative red
    elif val <= -0.3:
        return f"\033[33m{val_str}\033[0m"  # Moderate yellow
    else:
        return f"\033[90m{val_str}\033[0m"  # Neutral grey


def main():
    parser = argparse.ArgumentParser(
        description="Compute pairwise correlation matrices for numerical columns in a CSV file."
    )
    parser.add_argument("csv_file", help="Path to the input CSV file")
    parser.add_argument(
        "--method",
        choices=["pearson", "spearman"],
        default="pearson",
        help="Correlation method (default: pearson)",
    )
    parser.add_argument("--delimiter", default=",", help="CSV field delimiter (default: comma)")
    parser.add_argument("--format", choices=["table", "matrix", "markdown", "csv"], default="table", help="Output format")

    args = parser.parse_args()
    csv_path = Path(args.csv_file).resolve()

    if not csv_path.exists() or not csv_path.is_file():
        print(f"{COLOR_RED}Error: File '{csv_path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    headers: List[str] = []
    columns_data: Dict[str, List[float]] = {}

    with open(csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=args.delimiter)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            print(f"{COLOR_RED}Error: CSV file is empty.{COLOR_RESET}")
            sys.exit(1)

        raw_columns: Dict[str, List[str]] = {h: [] for h in headers}
        for row in reader:
            if not row:
                continue
            for i, val in enumerate(row):
                if i < len(headers):
                    raw_columns[headers[i]].append(val.strip())

    # Detect numerical columns
    for h, vals in raw_columns.items():
        parsed_vals = []
        is_num = True
        for v in vals:
            if not v:
                continue
            try:
                parsed_vals.append(float(v))
            except ValueError:
                is_num = False
                break
        if is_num and len(parsed_vals) > 1:
            columns_data[h] = parsed_vals

    num_headers = list(columns_data.keys())
    if len(num_headers) < 2:
        print(f"{COLOR_YELLOW}Warning: Fewer than 2 numerical columns detected in '{csv_path.name}'.{COLOR_RESET}")
        sys.exit(0)

    print(f"{COLOR_BOLD}{COLOR_CYAN}CSV Correlation Matrix ({args.method.capitalize()}){COLOR_RESET}")
    print(f"File: {COLOR_BOLD}{csv_path.name}{COLOR_RESET} | Columns: {len(num_headers)}\n")

    # Compute correlation matrix
    matrix: Dict[Tuple[str, str], float] = {}
    cor_func = pearson_correlation if args.method == "pearson" else spearman_correlation

    for h1 in num_headers:
        for h2 in num_headers:
            if h1 == h2:
                matrix[(h1, h2)] = 1.0
            else:
                v1, v2 = columns_data[h1], columns_data[h2]
                min_len = min(len(v1), len(v2))
                matrix[(h1, h2)] = cor_func(v1[:min_len], v2[:min_len])

    col_w = max(len(h[:12]) for h in num_headers) + 2

    if args.format in ("table", "matrix"):
        # Header row
        header_str = " " * col_w + "".join(f"{h[:10]:^{col_w}}" for h in num_headers)
        print(f"{COLOR_BOLD}{header_str}{COLOR_RESET}")
        print("-" * len(header_str))

        for h1 in num_headers:
            row_str = f"{COLOR_BOLD}{h1[:col_w-1]:<{col_w}}{COLOR_RESET}"
            for h2 in num_headers:
                val = matrix[(h1, h2)]
                val_formatted = colorize_val(val)
                row_str += f"{val_formatted:^{col_w + 9}}"
            print(row_str)

    elif args.format == "markdown":
        headers_row = "| Variable | " + " | ".join(num_headers) + " |"
        sep_row = "|---|" + "|---" * len(num_headers) + "|"
        print(headers_row)
        print(sep_row)
        for h1 in num_headers:
            row_vals = [f"{matrix[(h1, h2)]:+.3f}" for h2 in num_headers]
            print(f"| **{h1}** | " + " | ".join(row_vals) + " |")

    elif args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["Variable"] + num_headers)
        for h1 in num_headers:
            writer.writerow([h1] + [f"{matrix[(h1, h2)]:.4f}" for h2 in num_headers])


if __name__ == "__main__":
    main()
