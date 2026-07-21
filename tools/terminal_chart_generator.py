#!/usr/bin/env python3
"""
Terminal Chart Generator - Render data charts (bar, line, horizontal) directly in the console.

This tool reads data from command-line arguments, CSVs, or stdin and generates
visually appealing charts using Unicode block characters and ANSI colors.
"""

import sys
import os
import argparse
import csv
import math

# ANSI Colors
COLORS = {
    'red': '\033[31m',
    'green': '\033[32m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'cyan': '\033[36m',
    'white': '\033[37m',
    'reset': '\033[0m',
    'bold': '\033[1m',
}

# Block characters for drawing
BLOCK_FULL = '█'
BLOCK_HALF = '▄'
BLOCK_LIGHT = '░'
LINE_CHAR = '●'
VERTICAL_AXIS = '│'
HORIZONTAL_AXIS = '─'
CORNER = '└'

def get_colored_string(text, color):
    """Wrap text in ANSI color escape codes if terminal supports it"""
    if color and color.lower() in COLORS:
        return f"{COLORS[color.lower()]}{text}{COLORS['reset']}"
    return text

def parse_data_string(data_str):
    """Parse comma-separated data, e.g., '10,20,30' or 'Apples:10,Oranges:25'"""
    pairs = [item.strip() for item in data_str.split(',') if item.strip()]
    labels = []
    values = []
    
    for i, pair in enumerate(pairs):
        if ':' in pair:
            lbl, val = pair.split(':', 1)
            labels.append(lbl.strip())
            try:
                values.append(float(val.strip()))
            except ValueError:
                print(f"Warning: Invalid number '{val}' in pair '{pair}'. Using 0.", file=sys.stderr)
                values.append(0.0)
        else:
            labels.append(f"Item {i+1}")
            try:
                values.append(float(pair))
            except ValueError:
                print(f"Warning: Invalid number '{pair}'. Using 0.", file=sys.stderr)
                values.append(0.0)
                
    return labels, values

def read_from_file(filepath):
    """Read labels and values from a CSV or text file"""
    labels = []
    values = []
    try:
        with open(filepath, mode='r', newline='', encoding='utf-8') as f:
            # Check if it has a header or looks like CSV
            sample = f.read(1024)
            f.seek(0)
            
            has_header = False
            try:
                has_header = csv.sniffer().has_header(sample)
            except Exception:
                pass
                
            reader = csv.reader(f)
            if has_header:
                next(reader) # skip header
                
            for i, row in enumerate(reader):
                if not row:
                    continue
                if len(row) >= 2:
                    labels.append(row[0].strip())
                    try:
                        values.append(float(row[1].strip()))
                    except ValueError:
                        values.append(0.0)
                elif len(row) == 1:
                    labels.append(f"Item {i+1}")
                    try:
                        values.append(float(row[0].strip()))
                    except ValueError:
                        values.append(0.0)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
        
    return labels, values

def draw_horizontal_bar(labels, values, max_width, color):
    """Draw a horizontal bar chart"""
    if not values:
        return
        
    max_val = max(values) if max(values) != 0 else 1.0
    min_val = min(values)
    # Adjust for negative values if any
    base_val = 0.0 if min_val >= 0 else min_val
    range_val = max_val - base_val
    
    # Calculate label column width
    lbl_width = max(len(str(lbl)) for lbl in labels)
    lbl_width = min(lbl_width, 25) # cap label width
    
    chart_width = max_width - lbl_width - 15 # reserve room for values/borders
    chart_width = max(10, chart_width)
    
    print("\n" + COLORS['bold'] + "Horizontal Bar Chart" + COLORS['reset'])
    print("─" * max_width)
    
    for lbl, val in zip(labels, values):
        # Format label to fixed width
        truncated_lbl = lbl[:lbl_width].ljust(lbl_width)
        
        # Calculate bar length
        percentage = (val - base_val) / range_val if range_val > 0 else 0
        bar_len = int(percentage * chart_width)
        bar_len = max(0, min(bar_len, chart_width))
        
        # Build bar using blocks
        bar = BLOCK_FULL * bar_len
        # Add a partial block for finer resolution
        remainder = (percentage * chart_width) - bar_len
        if remainder >= 0.5 and bar_len < chart_width:
            bar += BLOCK_HALF
            
        colored_bar = get_colored_string(bar, color)
        
        # Render row
        print(f"{truncated_lbl} {VERTICAL_AXIS} {colored_bar} ({val:g})")
    
    print("─" * max_width)

def draw_vertical_bar(labels, values, height, max_width, color):
    """Draw a vertical bar chart"""
    if not values:
        return
        
    num_items = len(values)
    max_val = max(values) if max(values) != 0 else 1.0
    
    # Scale height
    scaled_heights = []
    for val in values:
        h = int((val / max_val) * height)
        scaled_heights.append(max(0, min(h, height)))
        
    # Calculate spacing between bars
    # Fit bars into max_width
    col_width = max(3, (max_width - 5) // num_items)
    
    print("\n" + COLORS['bold'] + "Vertical Bar Chart" + COLORS['reset'])
    print("─" * max_width)
    
    # Print the bars row by row (top to bottom)
    for r in range(height, 0, -1):
        row_str = f"{r * (max_val / height):6.1f} {VERTICAL_AXIS}"
        for h_val in scaled_heights:
            if h_val >= r:
                bar_part = (BLOCK_FULL * (col_width - 1)).center(col_width)
                row_str += get_colored_string(bar_part, color)
            elif h_val == r - 1 and r > 1:
                # Add light shading to top edge of bar if it falls in-between
                bar_part = (BLOCK_LIGHT * (col_width - 1)).center(col_width)
                row_str += get_colored_string(bar_part, color)
            else:
                row_str += " " * col_width
        print(row_str)
        
    # Print X-axis
    print(" " * 6 + CORNER + HORIZONTAL_AXIS * (num_items * col_width))
    
    # Print labels (first 3 chars or index numbers)
    labels_row = " " * 8
    for i, lbl in enumerate(labels):
        lbl_str = str(lbl)[:col_width-1].center(col_width)
        labels_row += lbl_str
    print(labels_row)
    print("─" * max_width)

def draw_line_chart(labels, values, height, max_width, color):
    """Draw a line chart in the terminal"""
    if not values:
        return
        
    num_items = len(values)
    max_val = max(values) if max(values) != 0 else 1.0
    min_val = min(values)
    range_val = max_val - min_val if max_val != min_val else 1.0
    
    # Scale height
    scaled_heights = []
    for val in values:
        h = int(((val - min_val) / range_val) * (height - 1))
        scaled_heights.append(max(0, min(h, height - 1)))
        
    col_width = max(3, (max_width - 8) // num_items)
    
    print("\n" + COLORS['bold'] + "Line Chart" + COLORS['reset'])
    print("─" * max_width)
    
    # Print lines
    for r in range(height - 1, -1, -1):
        # Y-axis labels
        curr_val = min_val + (r / (height - 1)) * range_val
        row_str = f"{curr_val:6.1f} {VERTICAL_AXIS}"
        
        for i, h_val in enumerate(scaled_heights):
            if h_val == r:
                node = get_colored_string(LINE_CHAR, color)
                # Padding around node
                left_pad = (col_width - 1) // 2
                right_pad = col_width - 1 - left_pad
                row_str += " " * left_pad + node + " " * right_pad
            else:
                row_str += " " * col_width
        print(row_str)
        
    # Print X-axis
    print(" " * 6 + CORNER + HORIZONTAL_AXIS * (num_items * col_width))
    
    # Print labels
    labels_row = " " * 8
    for lbl in labels:
        lbl_str = str(lbl)[:col_width-1].center(col_width)
        labels_row += lbl_str
    print(labels_row)
    print("─" * max_width)

def main():
    parser = argparse.ArgumentParser(
        description="Terminal Chart Generator - Generate visual charts in the terminal."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-d', '--data',
        help="Comma-separated data (e.g., '10,20,30' or 'A:10,B:20,C:30')"
    )
    group.add_argument(
        '-i', '--input',
        help="Path to a text/CSV file containing data"
    )
    group.add_argument(
        '--stdin',
        action='store_true',
        help="Read data from standard input (one value per line or label:value)"
    )
    
    parser.add_argument(
        '-t', '--type',
        choices=['horizontal', 'vertical', 'line'],
        default='horizontal',
        help="Chart type (default: horizontal)"
    )
    parser.add_argument(
        '-w', '--width',
        type=int,
        default=60,
        help="Max width of chart in characters (default: 60)"
    )
    parser.add_argument(
        '-g', '--height',
        type=int,
        default=12,
        help="Chart height for vertical/line charts (default: 12)"
    )
    parser.add_argument(
        '-c', '--color',
        choices=list(COLORS.keys())[:-2], # exclude reset and bold
        default='cyan',
        help="ANSI color theme (default: cyan)"
    )
    
    args = parser.parse_args()
    
    labels, values = [], []
    
    if args.data:
        labels, values = parse_data_string(args.data)
    elif args.input:
        labels, values = read_from_file(args.input)
    elif args.stdin:
        if sys.stdin.isatty():
            print("Enter data (Ctrl+D / Ctrl+Z to finish):")
        stdin_data = sys.stdin.read().strip()
        # Treat lines as items
        lines = [line.strip() for line in stdin_data.split('\n') if line.strip()]
        # Join with comma to reuse parser
        labels, values = parse_data_string(','.join(lines))
        
    if not values:
        print("Error: No valid data points found.", file=sys.stderr)
        sys.exit(1)
        
    # Enable terminal VT processing on Windows
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
    if args.type == 'horizontal':
        draw_horizontal_bar(labels, values, args.width, args.color)
    elif args.type == 'vertical':
        draw_vertical_bar(labels, values, args.height, args.width, args.color)
    elif args.type == 'line':
        draw_line_chart(labels, values, args.height, args.width, args.color)

if __name__ == '__main__':
    main()
