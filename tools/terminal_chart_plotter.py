#!/usr/bin/env python3
"""
Terminal Chart Plotter

A command-line tool to plot horizontal bar charts and statistics directly in the
terminal using Unicode block characters. Supports input from CSV, JSON, or stdin.

Usage:
    python tools/terminal_chart_plotter.py dataset.csv --x-col Category --y-col Value
    cat data.json | python tools/terminal_chart_plotter.py --json --x-col label --y-col count
"""

import argparse
import sys
import json
import csv
import shutil

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "reset": "\033[0m"
}

def print(*args, **kwargs):
    import builtins
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                cleaned = arg.replace('█', '#').replace('│', '|').replace('═', '=').replace('─', '-')
                new_args.append(cleaned.encode('ascii', errors='replace').decode('ascii'))
            else:
                new_args.append(arg)
        builtins.print(*new_args, **kwargs)

def get_terminal_width():
    """Returns the width of the terminal, defaulting to 80 if not detectable."""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def read_csv_data(filepath, x_col, y_col):
    """Reads data from a CSV file or stdin."""
    data = []
    f = open(filepath, 'r', newline='', encoding='utf-8') if filepath else sys.stdin
    try:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("Error: Empty CSV or invalid format.", file=sys.stderr)
            return None
        
        # If columns aren't specified, guess them (first column X, second column Y)
        col_x = x_col if x_col else reader.fieldnames[0]
        col_y = y_col if y_col else (reader.fieldnames[1] if len(reader.fieldnames) > 1 else None)
        
        if not col_y:
            print("Error: Could not determine Y column for numeric values.", file=sys.stderr)
            return None

        for row in reader:
            val_str = row.get(col_y, "0").strip()
            try:
                val = float(val_str) if '.' in val_str else int(val_str)
            except ValueError:
                val = 0.0
            data.append((row.get(col_x, "Unknown").strip(), val))
    finally:
        if filepath:
            f.close()
    return data

def read_json_data(filepath, x_col, y_col):
    """Reads data from a JSON file or stdin."""
    f = open(filepath, 'r', encoding='utf-8') if filepath else sys.stdin
    try:
        raw_data = json.load(f)
    except Exception as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return None
    finally:
        if filepath:
            f.close()

    # Normalize JSON list of objects or key-value dictionary
    data = []
    if isinstance(raw_data, list):
        if not raw_data:
            return []
        first = raw_data[0]
        col_x = x_col if x_col else (first.keys() if isinstance(first, dict) else [0])
        # Convert list of keys to list
        col_x = list(col_x)[0] if isinstance(col_x, (list, dict, keys := type({}.keys()))) else col_x
        col_y = y_col if y_col else (list(first.keys())[1] if isinstance(first, dict) and len(first) > 1 else None)
        
        for item in raw_data:
            if isinstance(item, dict):
                val_str = item.get(col_y, 0)
                try:
                    val = float(val_str)
                except ValueError:
                    val = 0.0
                data.append((str(item.get(col_x, "Unknown")), val))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    val = float(item[1])
                except ValueError:
                    val = 0.0
                data.append((str(item[0]), val))
    elif isinstance(raw_data, dict):
        for k, v in raw_data.items():
            try:
                val = float(v)
            except (ValueError, TypeError):
                val = 0.0
            data.append((str(k), val))
    return data

def plot_chart(data, title, color_name="cyan", max_width=None):
    """Plots a horizontal bar chart of the data."""
    if not data:
        print("No data to plot.")
        return

    # Find longest label for alignment
    max_label_len = max(len(label) for label, _ in data)
    max_label_len = min(max_label_len, 30)  # Cap label width

    # Find max value for scaling
    max_val = max(val for _, val in data)
    min_val = min(val for _, val in data)
    
    # Avoid division by zero
    if max_val == min_val == 0:
        scale_max = 1.0
    else:
        scale_max = max(abs(max_val), abs(min_val))

    # Calculate width of chart area
    term_width = get_terminal_width()
    if not max_width:
        # 30 chars for labels, value labels, borders, and margins
        max_chart_width = max(term_width - max_label_len - 15, 20)
    else:
        max_chart_width = max_width

    color = COLORS.get(color_name.lower(), COLORS["cyan"])
    reset = COLORS["reset"]

    print("\n" + "=" * term_width)
    print(f" {title.upper()} ".center(term_width, "═"))
    print("=" * term_width + "\n")

    for label, val in data:
        # Truncate label if too long
        disp_label = label[:max_label_len].ljust(max_label_len)
        
        # Calculate bars
        if scale_max > 0:
            bar_len = int((abs(val) / scale_max) * max_chart_width)
        else:
            bar_len = 0
            
        bar = "█" * bar_len
        
        # Format output based on positive or negative value
        if val >= 0:
            print(f" {disp_label} │ {color}{bar}{reset} {val}")
        else:
            # For negative values, prefix with a minus indicator
            print(f" {disp_label} │ {COLORS['red']}{bar}{reset} ({val})")
            
    print("\n" + "─" * term_width)
    print(f" Total Items: {len(data)} | Max Value: {max_val} | Min Value: {min_val}")
    print("─" * term_width + "\n")

def main():
    parser = argparse.ArgumentParser(description="Plot text/Unicode bar charts in the terminal.")
    parser.add_argument("file", nargs="?", help="CSV or JSON file to parse (reads from stdin if omitted)")
    parser.add_argument("--json", action="store_true", help="Parse input as JSON (default is CSV)")
    parser.add_argument("--x-col", help="Column name/key for X-axis labels")
    parser.add_argument("--y-col", help="Column name/key for Y-axis values (numbers)")
    parser.add_argument("--title", default="Terminal Bar Chart", help="Title of the chart")
    parser.add_argument("--color", default="cyan", choices=list(COLORS.keys())[:-1], help="Bar color")
    parser.add_argument("--width", type=int, help="Override default chart width")
    
    args = parser.parse_args()

    # Read the data
    if args.json:
        data = read_json_data(args.file, args.x_col, args.y_col)
    else:
        # Try to auto-detect json from extension if not specified
        if args.file and args.file.endswith('.json'):
            data = read_json_data(args.file, args.x_col, args.y_col)
        else:
            data = read_csv_data(args.file, args.x_col, args.y_col)

    if data is None:
        return 1

    plot_chart(data, args.title, args.color, args.width)
    return 0

if __name__ == "__main__":
    sys.exit(main())
