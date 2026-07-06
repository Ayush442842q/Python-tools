#!/usr/bin/env python3
"""
Markdown Table Column Statistics & Aggregator
---------------------------------------------
Parses GFM Markdown tables from files or standard input, auto-detects column data types
(numeric, text, date), and calculates comprehensive descriptive statistics (count, sum,
min, max, mean, median, std dev, distinct count, null count, top values).
Outputs formatted summary reports in Markdown, JSON, or CSV.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import math
import argparse
from typing import List, Dict, Any, Tuple, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_markdown_tables(text: str) -> List[Dict[str, Any]]:
    """Extract all Markdown GFM tables from text."""
    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Check if line looks like a table row
        if line.startswith("|") and line.endswith("|"):
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            
            # Need at least header, separator, and 1 data row
            if len(table_lines) >= 3:
                header_raw = table_lines[0]
                sep_raw = table_lines[1]
                
                # Verify separator line (e.g., |---|---|)
                if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", sep_raw):
                    headers = [c.strip() for c in header_raw.strip("|").split("|")]
                    data_rows = []
                    for row_line in table_lines[2:]:
                        cells = [c.strip() for c in row_line.strip("|").split("|")]
                        # Align length if mismatched
                        if len(cells) < len(headers):
                            cells.extend([""] * (len(headers) - len(cells)))
                        data_rows.append(cells[:len(headers)])
                    
                    tables.append({
                        "headers": headers,
                        "rows": data_rows,
                        "line_start": i - len(table_lines) + 1
                    })
        else:
            i += 1
    return tables


def clean_number(val_str: str) -> Optional[float]:
    """Clean formatted numbers (e.g. '$1,234.50', '85%', '-42.0') into float."""
    clean = val_str.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("%", "").strip()
    # Remove HTML tags or Markdown formatting
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = re.sub(r"[*_`]", "", clean)
    if not clean:
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def analyze_column(name: str, values: List[str]) -> Dict[str, Any]:
    """Compute statistics for a single table column."""
    total_count = len(values)
    non_empty = [v for v in values if v.strip() != "" and v.strip() != "-"]
    null_count = total_count - len(non_empty)
    
    # Try parsing numeric values
    num_values = []
    for v in non_empty:
        parsed = clean_number(v)
        if parsed is not None:
            num_values.append(parsed)
            
    is_numeric = len(num_values) > 0 and len(num_values) >= len(non_empty) * 0.7
    
    stats: Dict[str, Any] = {
        "column_name": name,
        "total_rows": total_count,
        "valid_count": len(non_empty),
        "null_count": null_count,
        "is_numeric": is_numeric
    }
    
    if is_numeric and num_values:
        num_values.sort()
        n = len(num_values)
        val_sum = sum(num_values)
        val_mean = val_sum / n
        
        # Median
        if n % 2 == 1:
            val_median = num_values[n // 2]
        else:
            val_median = (num_values[n // 2 - 1] + num_values[n // 2]) / 2.0
            
        # Standard deviation
        variance = sum((x - val_mean) ** 2 for x in num_values) / n if n > 1 else 0.0
        val_std = math.sqrt(variance)
        
        stats.update({
            "type": "numeric",
            "min": min(num_values),
            "max": max(num_values),
            "sum": val_sum,
            "mean": val_mean,
            "median": val_median,
            "std_dev": val_std,
            "distinct_count": len(set(num_values))
        })
    else:
        # Categorical statistics
        freq: Dict[str, int] = {}
        for v in non_empty:
            clean_v = re.sub(r"[*_`]", "", v).strip()
            freq[clean_v] = freq.get(clean_v, 0) + 1
            
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top_3 = sorted_freq[:3]
        
        stats.update({
            "type": "categorical",
            "distinct_count": len(freq),
            "top_values": [{"value": k, "count": c, "pct": round(c / len(non_empty) * 100, 1) if non_empty else 0} for k, c in top_3]
        })
        
    return stats


def format_markdown_report(table_idx: int, col_stats: List[Dict[str, Any]]) -> str:
    """Generate Markdown report of table statistics."""
    out = [f"### Table #{table_idx} Column Statistics\n"]
    
    # Numeric Summary Table
    num_cols = [s for s in col_stats if s.get("type") == "numeric"]
    if num_cols:
        out.append("#### Numeric Columns Summary\n")
        out.append("| Column | Valid | Min | Max | Sum | Mean | Median | Std Dev |")
        out.append("|---|---|---|---|---|---|---|---|")
        for c in num_cols:
            out.append(f"| **{c['column_name']}** | {c['valid_count']} | {c['min']:.2f} | {c['max']:.2f} | {c['sum']:.2f} | {c['mean']:.2f} | {c['median']:.2f} | {c['std_dev']:.2f} |")
        out.append("")
        
    # Categorical Summary Table
    cat_cols = [s for s in col_stats if s.get("type") == "categorical"]
    if cat_cols:
        out.append("#### Categorical Columns Summary\n")
        out.append("| Column | Valid | Nulls | Distinct | Top Value (Freq) |")
        out.append("|---|---|---|---|---|")
        for c in cat_cols:
            top_str = "N/A"
            if c["top_values"]:
                top = c["top_values"][0]
                top_str = f"`{top['value']}` ({top['count']} - {top['pct']}%)"
            out.append(f"| **{c['column_name']}** | {c['valid_count']} | {c['null_count']} | {c['distinct_count']} | {top_str} |")
        out.append("")
        
    return "\n".join(out)


DEMO_MARKDOWN = """
# Quarterly Performance Report

| Employee | Department | Target Sales ($) | Actual Sales ($) | Completion Rate (%) | Region |
|---|---|---|---|---|---|
| Alice Smith | Sales | 50,000 | 58,500.50 | 117.0% | North |
| Bob Jones | Sales | 45,000 | 41,200.00 | 91.5% | South |
| Charlie Brown | Engineering | 60,000 | 62,000.00 | 103.3% | North |
| Diana Prince | Sales | 55,000 | 67,800.00 | 123.2% | East |
| Evan Wright | Support | 30,000 | 29,500.00 | 98.3% | West |
| Fiona Gallagher | Sales | 50,000 | 52,100.00 | 104.2% | North |
"""


def main():
    parser = argparse.ArgumentParser(description="Markdown Table Column Statistics & Aggregator")
    parser.add_argument("file", nargs="?", help="Markdown file to analyze (or omit for stdin)")
    parser.add_argument("--table-index", type=int, help="Select specific 1-based table index")
    parser.add_argument("--column", help="Filter statistics for specific column name")
    parser.add_argument("--format", choices=["markdown", "json", "csv"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Save output report to specified file")
    parser.add_argument("--demo", action="store_true", help="Run built-in demo with sample tables")
    
    args = parser.parse_args()
    
    if args.demo:
        print(f"{BOLD}{CYAN}=== Running Markdown Table Column Stats Demo ==={RESET}\n")
        content = DEMO_MARKDOWN
    elif args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' not found.{RESET}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(0)
            
    tables = parse_markdown_tables(content)
    if not tables:
        print(f"{YELLOW}No valid GFM Markdown tables found.{RESET}")
        sys.exit(0)
        
    results = []
    for idx, table in enumerate(tables, 1):
        if args.table_index and idx != args.table_index:
            continue
            
        headers = table["headers"]
        rows = table["rows"]
        
        table_stats = []
        for col_idx, header in enumerate(headers):
            if args.column and args.column.lower() not in header.lower():
                continue
            col_values = [r[col_idx] for r in rows if col_idx < len(r)]
            stats = analyze_column(header, col_values)
            table_stats.append(stats)
            
        results.append({
            "table_index": idx,
            "row_count": len(rows),
            "col_count": len(headers),
            "column_stats": table_stats
        })
        
    if args.format == "json":
        output_str = json.dumps(results, indent=2)
    elif args.format == "csv":
        csv_lines = ["table_index,column,type,valid_count,null_count,min,max,mean,median,std_dev,distinct_count"]
        for res in results:
            t_idx = res["table_index"]
            for c in res["column_stats"]:
                if c["type"] == "numeric":
                    csv_lines.append(f"{t_idx},\"{c['column_name']}\",numeric,{c['valid_count']},{c['null_count']},{c['min']},{c['max']},{c['mean']},{c['median']},{c['std_dev']},{c['distinct_count']}")
                else:
                    csv_lines.append(f"{t_idx},\"{c['column_name']}\",categorical,{c['valid_count']},{c['null_count']},,,,,,{c['distinct_count']}")
        output_str = "\n".join(csv_lines)
    else:
        md_reports = [format_markdown_report(r["table_index"], r["column_stats"]) for r in results]
        output_str = "\n\n".join(md_reports)
        
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"{GREEN}Report successfully saved to {args.output}{RESET}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
