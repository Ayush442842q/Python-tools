#!/usr/bin/env python3
"""
CSV Pivot Table Generator - Generate pivot summaries and tables from CSV data.

This tool parses a CSV file and creates a pivot table by grouping by specified
row and column fields, aggregating numerical values using common aggregation
functions (sum, count, avg, min, max). It runs using only standard libraries.
"""

import sys
import os
import csv
import argparse
from collections import defaultdict

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'red': '\033[31m',
    'reset': '\033[0m'
}

def colorize(text, color):
    """Wrap text in ANSI color escape codes if output is a terminal"""
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def parse_float(val):
    """Try to parse a value to float. Return None if it fails."""
    if val is None:
        return None
    val_str = str(val).strip().replace(',', '')
    try:
        return float(val_str)
    except ValueError:
        return None

def calculate_aggregate(values, agg_func):
    """Perform aggregation on a list of numerical values."""
    if not values:
        return 0.0 if agg_func != 'count' else 0

    numeric_vals = [v for v in (parse_float(x) for x in values) if v is not None]
    
    if agg_func == 'count':
        return len(values)
        
    if not numeric_vals:
        return 0.0

    if agg_func == 'sum':
        return sum(numeric_vals)
    elif agg_func == 'avg' or agg_func == 'average':
        return sum(numeric_vals) / len(numeric_vals)
    elif agg_func == 'min':
        return min(numeric_vals)
    elif agg_func == 'max':
        return max(numeric_vals)
    return 0.0

def generate_pivot(csv_path, row_field, col_field, val_field, agg_func='sum', delimiter=','):
    """Read CSV, process groupings, and generate a pivot table structure."""
    if not os.path.exists(csv_path):
        print(colorize(f"Error: CSV file '{csv_path}' does not exist.", 'red'), file=sys.stderr)
        return None

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            # Detect dialect or fallback to default
            try:
                sample = f.read(2048)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample)
                reader = csv.DictReader(f, dialect=dialect)
            except Exception:
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delimiter)

            headers = reader.fieldnames
            if not headers:
                print(colorize("Error: Empty or invalid CSV headers.", 'red'), file=sys.stderr)
                return None

            # Verify fields exist
            for field, name in [(row_field, 'Row'), (col_field, 'Column'), (val_field, 'Value')]:
                if field and field not in headers:
                    print(colorize(f"Error: {name} field '{field}' not found in CSV. Available headers: {', '.join(headers)}", 'red'), file=sys.stderr)
                    return None

            # Pivot map: data[row_val][col_val] = list of raw values to aggregate
            # If col_field is None, we just group by row_field (1D aggregation)
            data = defaultdict(lambda: defaultdict(list))
            all_cols = set()
            all_rows = set()

            for row_idx, row in enumerate(reader):
                r_val = row.get(row_field)
                if r_val is None:
                    r_val = "(empty)"
                else:
                    r_val = r_val.strip()
                
                all_rows.add(r_val)

                c_val = row.get(col_field) if col_field else "Total"
                if c_val is None:
                    c_val = "(empty)"
                else:
                    c_val = c_val.strip()
                
                if col_field:
                    all_cols.add(c_val)

                v_val = row.get(val_field)
                data[r_val][c_val].append(v_val)

            # Sort headers/indexes
            sorted_rows = sorted(list(all_rows))
            sorted_cols = sorted(list(all_cols)) if col_field else ["Total"]

            # Compute aggregated cells
            pivot_table = {}
            row_totals = defaultdict(list)
            col_totals = defaultdict(list)
            grand_total_vals = []

            for r in sorted_rows:
                pivot_table[r] = {}
                for c in sorted_cols:
                    vals = data[r][c]
                    agg_val = calculate_aggregate(vals, agg_func)
                    pivot_table[r][c] = agg_val
                    
                    row_totals[r].extend(vals)
                    col_totals[c].extend(vals)
                    grand_total_vals.extend(vals)

            # Add totals calculations
            row_totals_agg = {r: calculate_aggregate(row_totals[r], agg_func) for r in sorted_rows}
            col_totals_agg = {c: calculate_aggregate(col_totals[c], agg_func) for c in sorted_cols}
            grand_total = calculate_aggregate(grand_total_vals, agg_func)

            return {
                'row_field': row_field,
                'col_field': col_field or '',
                'val_field': val_field,
                'agg_func': agg_func,
                'rows': sorted_rows,
                'cols': sorted_cols,
                'table': pivot_table,
                'row_totals': row_totals_agg,
                'col_totals': col_totals_agg,
                'grand_total': grand_total
            }

    except Exception as e:
        print(colorize(f"Error processing CSV file: {e}", 'red'), file=sys.stderr)
        return None

def print_pivot_table(pivot):
    """Print the pivot table in a clean text table format."""
    if not pivot:
        return

    row_field = pivot['row_field']
    col_field = pivot['col_field']
    val_field = pivot['val_field']
    agg_func = pivot['agg_func']
    
    rows = pivot['rows']
    cols = pivot['cols']
    table = pivot['table']
    row_totals = pivot['row_totals']
    col_totals = pivot['col_totals']
    grand_total = pivot['grand_total']

    # Determine title / header info
    print(colorize(f"\n--- Pivot Table Summary ---", 'bold'))
    print(f"Rows:      {colorize(row_field, 'cyan')}")
    if col_field:
        print(f"Columns:   {colorize(col_field, 'cyan')}")
    print(f"Values:    {colorize(val_field, 'cyan')} ({agg_func.upper()})\n")

    # Format values helper
    def fmt(val):
        if isinstance(val, float):
            # If it's a clean int representations
            if val.is_integer():
                return f"{int(val):,}"
            return f"{val:,.2f}"
        return f"{val:,}"

    # Determine column widths
    # Row label column width
    row_label_width = max(len(row_field), max(len(r) for r in rows), 12) + 2
    
    # Other columns width
    col_widths = {}
    for c in cols:
        max_len = len(c)
        for r in rows:
            max_len = max(max_len, len(fmt(table[r][c])))
        max_len = max(max_len, len(fmt(col_totals[c])))
        col_widths[c] = max_len + 2

    # Row total column width (if col_field was provided)
    total_col_width = 0
    if col_field:
        total_col_width = max(8, max(len(fmt(row_totals[r])) for r in rows), len(fmt(grand_total))) + 2

    # Print table header
    header_row = f"{row_field:<{row_label_width}}"
    if col_field:
        header_row += "".join(f"{c:>{col_widths[c]}}" for c in cols)
        header_row += f"{'Total':>{total_col_width}}"
    else:
        header_row += f"{agg_func.upper() + '(' + val_field + ')':>{col_widths['Total']}}"
    
    print(colorize(header_row, 'bold'))
    print("-" * len(header_row))

    # Print data rows
    for r in rows:
        row_str = f"{r:<{row_label_width}}"
        for c in cols:
            row_str += f"{fmt(table[r][c]):>{col_widths[c]}}"
        if col_field:
            row_str += f"{fmt(row_totals[r]):>{total_col_width}}"
        print(row_str)

    # Print totals row
    print("-" * len(header_row))
    totals_row = f"{'Total':<{row_label_width}}"
    for c in cols:
        totals_row += f"{fmt(col_totals[c]):>{col_widths[c]}}"
    if col_field:
        totals_row += f"{fmt(grand_total):>{total_col_width}}"
    print(colorize(totals_row, 'bold'))
    print()

def main():
    parser = argparse.ArgumentParser(
        description="CSV Pivot Table Generator - Summarize CSV records into pivot layouts without external libraries.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("csv_path", help="Path to input CSV file.")
    parser.add_argument("-r", "--rows", required=True, help="Column name to group rows by.")
    parser.add_argument("-c", "--cols", help="Column name to group columns by (optional).")
    parser.add_argument("-v", "--values", required=True, help="Column name containing numerical values to aggregate.")
    parser.add_argument(
        "-a", "--agg", 
        choices=['sum', 'count', 'avg', 'average', 'min', 'max'], 
        default='sum',
        help="Aggregation function to use (default: sum)."
    )
    parser.add_argument(
        "-d", "--delimiter", 
        default=",", 
        help="Delimiter character to use if sniffing fails (default: ',')."
    )

    args = parser.parse_args()
    
    pivot = generate_pivot(
        csv_path=args.csv_path,
        row_field=args.rows,
        col_field=args.cols,
        val_field=args.values,
        agg_func=args.agg,
        delimiter=args.delimiter
    )
    
    if pivot:
        print_pivot_table(pivot)
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
