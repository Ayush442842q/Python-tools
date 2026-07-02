#!/usr/bin/env python3
"""
Markdown Table to SVG Chart Compiler
Scans Markdown files for numerical data tables, extracts the data,
and compiles beautiful, responsive SVG charts (bar, line, or pie) with styling.

Features:
1. Automatically parses Markdown tables, detecting headers and row values.
2. Infers data types, pairing categorical columns (X-axis) with numerical columns (Y-axis).
3. Synthesizes beautiful SVG structures:
   - Vertical and Horizontal Bar charts (grouped or single)
   - Line charts with grid lines, axis labels, and circle markers
   - Pie charts with sector slice angles, labels, and legends
4. Embeds modern dark/light CSS themes and hover animations into the output SVG.
5. Saves SVG charts directly to files or outputs them to stdout.
"""

import argparse
import math
import os
import re
import sys
from typing import Dict, List, Tuple, Union

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

# Default Color Palette for chart series
PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f43f5e"]


def parse_markdown_tables(content: str) -> List[Tuple[List[str], List[List[str]]]]:
    """
    Parses Markdown content and returns a list of tables.
    Each table is represented as a tuple: (headers, rows).
    """
    tables = []
    lines = content.splitlines()
    
    current_table_rows = []
    in_table = False
    
    for line in lines:
        line = line.strip()
        # Markdown table lines must contain '|'
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            
            # Skip separator line, e.g., |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                in_table = True
                continue
                
            current_table_rows.append(cells)
        else:
            if in_table and len(current_table_rows) >= 2:
                # We have headers and at least one row
                headers = current_table_rows[0]
                rows = current_table_rows[1:]
                tables.append((headers, rows))
            current_table_rows = []
            in_table = False
            
    # Capture table if file ends with it
    if in_table and len(current_table_rows) >= 2:
        headers = current_table_rows[0]
        rows = current_table_rows[1:]
        tables.append((headers, rows))
        
    return tables


def extract_numeric_data(headers: List[str], rows: List[List[str]]) -> Tuple[List[str], List[str], List[List[float]]]:
    """
    Identifies categorical and numeric columns.
    Returns (labels, value_headers, series_values).
    """
    num_cols = len(headers)
    col_types = []  # List of 'num' or 'str'
    
    parsed_columns = [[] for _ in range(num_cols)]
    
    for row in rows:
        # Pad row if short
        row_cells = row + [""] * (num_cols - len(row))
        for col_idx, cell in enumerate(row_cells):
            parsed_columns[col_idx].append(cell)
            
    # Check type of each column
    numeric_col_indices = []
    label_col_idx = 0
    
    for col_idx in range(num_cols):
        values = parsed_columns[col_idx]
        is_numeric = True
        converted_values = []
        
        for val in values:
            clean_val = re.sub(r"[^\d\.-]", "", val)
            try:
                converted_values.append(float(clean_val))
            except ValueError:
                is_numeric = False
                break
                
        if is_numeric and len(converted_values) > 0:
            numeric_col_indices.append((col_idx, converted_values))
        else:
            # First text column will be used for labels
            if label_col_idx == 0:
                label_col_idx = col_idx

    # Build labels
    labels = parsed_columns[label_col_idx]
    
    # Build values and series names
    value_headers = []
    series_values = []
    
    for col_idx, converted in numeric_col_indices:
        if col_idx == label_col_idx:
            continue
        value_headers.append(headers[col_idx])
        series_values.append(converted)
        
    return labels, value_headers, series_values


def generate_bar_chart(labels: List[str], series_names: List[str], series_data: List[List[float]], title: str) -> str:
    # Dimensions
    width, height = 800, 500
    padding_top, padding_bottom, padding_left, padding_right = 60, 60, 80, 150
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    
    # Find max value
    max_val = 0.1
    for s in series_data:
        max_val = max(max_val, max(s) if s else 0.1)
        
    # Y-axis scaling
    y_max = math.ceil(max_val * 1.1)
    
    svg = [
        f'<svg width="100%" height="100%" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background:#1e1e2e; font-family:system-ui, sans-serif;">',
        '  <style>',
        '    .bar { transition: transform 0.2s, opacity 0.2s; cursor: pointer; }',
        '    .bar:hover { filter: brightness(1.2); }',
        '    .grid-line { stroke: #313244; stroke-width: 1; }',
        '    .axis { stroke: #45475a; stroke-width: 2; }',
        '    .text { fill: #cdd6f4; font-size: 12px; }',
        '    .title { fill: #f5c2e7; font-size: 18px; font-weight: bold; }',
        '    .legend-text { fill: #a6adc8; font-size: 12px; }',
        '  </style>',
        f'  <text x="{width/2}" y="35" text-anchor="middle" class="text title">{title}</text>'
    ]
    
    # Grid lines & Y Axis Labels
    grid_count = 5
    for i in range(grid_count + 1):
        y_val = y_max * (i / grid_count)
        y_pos = padding_top + chart_height - (y_val / y_max) * chart_height
        svg.append(f'  <line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + chart_width}" y2="{y_pos}" class="grid-line" />')
        svg.append(f'  <text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" class="text">{y_val:.1f}</text>')

    # Draw bars & X Axis Labels
    num_groups = len(labels)
    num_series = len(series_data)
    group_width = chart_width / max(1, num_groups)
    bar_width = (group_width * 0.7) / max(1, num_series)
    
    for group_idx, label in enumerate(labels):
        group_x = padding_left + group_idx * group_width
        
        # X-axis label
        label_x = group_x + group_width / 2
        svg.append(f'  <text x="{label_x}" y="{padding_top + chart_height + 20}" text-anchor="middle" class="text">{label}</text>')
        
        # Bars for each series
        for series_idx, series in enumerate(series_data):
            val = series[group_idx]
            bar_h = (val / y_max) * chart_height
            bar_x = group_x + (group_width * 0.15) + series_idx * bar_width
            bar_y = padding_top + chart_height - bar_h
            color = PALETTE[series_idx % len(PALETTE)]
            
            svg.append(f'  <rect x="{bar_x}" y="{bar_y}" width="{max(1, bar_width - 2)}" height="{max(1, bar_h)}" fill="{color}" class="bar" rx="3">')
            svg.append(f'    <title>{series_names[series_idx]} ({label}): {val}</title>')
            svg.append(f'  </rect>')

    # Axis lines
    svg.append(f'  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" class="axis" />')
    svg.append(f'  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" class="axis" />')

    # Legend
    legend_x = width - padding_right + 20
    for series_idx, name in enumerate(series_names):
        legend_y = padding_top + series_idx * 25
        color = PALETTE[series_idx % len(PALETTE)]
        svg.append(f'  <rect x="{legend_x}" y="{legend_y}" width="15" height="15" fill="{color}" rx="2" />')
        svg.append(f'  <text x="{legend_x + 25}" y="{legend_y + 12}" class="legend-text">{name}</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def generate_line_chart(labels: List[str], series_names: List[str], series_data: List[List[float]], title: str) -> str:
    # Dimensions
    width, height = 800, 500
    padding_top, padding_bottom, padding_left, padding_right = 60, 60, 80, 150
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    
    # Find max value
    max_val = 0.1
    for s in series_data:
        max_val = max(max_val, max(s) if s else 0.1)
    y_max = math.ceil(max_val * 1.1)
    
    svg = [
        f'<svg width="100%" height="100%" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background:#1e1e2e; font-family:system-ui, sans-serif;">',
        '  <style>',
        '    .line { fill: none; stroke-width: 3; stroke-linecap: round; }',
        '    .dot { transition: r 0.2s, fill 0.2s; cursor: pointer; }',
        '    .dot:hover { r: 7; fill: #ffffff; }',
        '    .grid-line { stroke: #313244; stroke-width: 1; }',
        '    .axis { stroke: #45475a; stroke-width: 2; }',
        '    .text { fill: #cdd6f4; font-size: 12px; }',
        '    .title { fill: #f5c2e7; font-size: 18px; font-weight: bold; }',
        '    .legend-text { fill: #a6adc8; font-size: 12px; }',
        '  </style>',
        f'  <text x="{width/2}" y="35" text-anchor="middle" class="text title">{title}</text>'
    ]
    
    # Grid lines & Y Axis Labels
    grid_count = 5
    for i in range(grid_count + 1):
        y_val = y_max * (i / grid_count)
        y_pos = padding_top + chart_height - (y_val / y_max) * chart_height
        svg.append(f'  <line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + chart_width}" y2="{y_pos}" class="grid-line" />')
        svg.append(f'  <text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" class="text">{y_val:.1f}</text>')

    num_points = len(labels)
    x_step = chart_width / max(1, num_points - 1)
    
    # Draw Lines & Points
    for series_idx, series in enumerate(series_data):
        color = PALETTE[series_idx % len(PALETTE)]
        points = []
        
        for pt_idx, val in enumerate(series):
            pt_x = padding_left + pt_idx * x_step
            pt_y = padding_top + chart_height - (val / y_max) * chart_height
            points.append(f"{pt_x},{pt_y}")
            
        path_data = "M " + " L ".join(points)
        svg.append(f'  <path d="{path_data}" class="line" stroke="{color}" />')
        
        # Draw dots
        for pt_idx, val in enumerate(series):
            pt_x = padding_left + pt_idx * x_step
            pt_y = padding_top + chart_height - (val / y_max) * chart_height
            svg.append(f'  <circle cx="{pt_x}" cy="{pt_y}" r="4" fill="{color}" stroke="#1e1e2e" stroke-width="2" class="dot">')
            svg.append(f'    <title>{series_names[series_idx]} ({labels[pt_idx]}): {val}</title>')
            svg.append(f'  </circle>')

    # Draw X axis labels
    for pt_idx, label in enumerate(labels):
        pt_x = padding_left + pt_idx * x_step
        svg.append(f'  <text x="{pt_x}" y="{padding_top + chart_height + 20}" text-anchor="middle" class="text">{label}</text>')

    # Axis lines
    svg.append(f'  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" class="axis" />')
    svg.append(f'  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" class="axis" />')

    # Legend
    legend_x = width - padding_right + 20
    for series_idx, name in enumerate(series_names):
        legend_y = padding_top + series_idx * 25
        color = PALETTE[series_idx % len(PALETTE)]
        svg.append(f'  <rect x="{legend_x}" y="{legend_y}" width="15" height="15" fill="{color}" rx="2" />')
        svg.append(f'  <text x="{legend_x + 25}" y="{legend_y + 12}" class="legend-text">{name}</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def generate_pie_chart(labels: List[str], series_name: str, values: List[float], title: str) -> str:
    # Dimensions
    width, height = 700, 500
    cx, cy, radius = 250, 250, 160
    total = sum(values)
    
    svg = [
        f'<svg width="100%" height="100%" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background:#1e1e2e; font-family:system-ui, sans-serif;">',
        '  <style>',
        '    .slice { transition: transform 0.2s, filter 0.2s; cursor: pointer; transform-origin: 250px 250px; }',
        '    .slice:hover { transform: scale(1.05); filter: brightness(1.2); }',
        '    .text { fill: #cdd6f4; font-size: 12px; }',
        '    .title { fill: #f5c2e7; font-size: 18px; font-weight: bold; }',
        '    .legend-text { fill: #a6adc8; font-size: 12px; }',
        '  </style>',
        f'  <text x="{width/2}" y="35" text-anchor="middle" class="text title">{title} ({series_name})</text>'
    ]
    
    current_angle = 0.0
    
    for idx, val in enumerate(values):
        percentage = val / total if total > 0 else 0
        angle = percentage * 360
        
        # Calculate arc coordinates
        x1 = cx + radius * math.cos(math.radians(current_angle - 90))
        y1 = cy + radius * math.sin(math.radians(current_angle - 90))
        
        x2 = cx + radius * math.cos(math.radians(current_angle + angle - 90))
        y2 = cy + radius * math.sin(math.radians(current_angle + angle - 90))
        
        large_arc = 1 if angle > 180 else 0
        
        color = PALETTE[idx % len(PALETTE)]
        
        # Draw path slice
        if angle >= 360:
            svg.append(f'  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="{color}" class="slice">')
            svg.append(f'    <title>{labels[idx]}: {val} ({percentage*100:.1f}%)</title>')
            svg.append(f'  </circle>')
        else:
            path_data = f"M {cx} {cy} L {x1} {y1} A {radius} {radius} 0 {large_arc} 1 {x2} {y2} Z"
            svg.append(f'  <path d="{path_data}" fill="{color}" class="slice">')
            svg.append(f'    <title>{labels[idx]}: {val} ({percentage*100:.1f}%)</title>')
            svg.append(f'  </path>')
            
        current_angle += angle

    # Draw Legend
    legend_x = 480
    for idx, label in enumerate(labels):
        legend_y = 100 + idx * 25
        color = PALETTE[idx % len(PALETTE)]
        val = values[idx]
        pct = (val / total * 100) if total > 0 else 0
        svg.append(f'  <rect x="{legend_x}" y="{legend_y}" width="15" height="15" fill="{color}" rx="2" />')
        svg.append(f'  <text x="{legend_x + 25}" y="{legend_y + 12}" class="legend-text">{label}: {val} ({pct:.1f}%)</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def main():
    parser = argparse.ArgumentParser(
        description="Scans markdown files for tables and compiles beautiful visual SVG charts from them.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the markdown file to parse")
    parser.add_argument("--type", choices=["bar", "line", "pie"], default="bar", help="Chart type (default: bar)")
    parser.add_argument("--title", help="Optional custom chart title", default="")
    parser.add_argument("--output", help="Optional output path for the SVG chart. Defaults to standard output.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"{COLOR_RED}Error: File '{args.file}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()
        
    tables = parse_markdown_tables(content)
    if not tables:
        print(f"{COLOR_YELLOW}No markdown tables found in '{args.file}'.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    # Process the first table found
    headers, rows = tables[0]
    labels, value_headers, series_values = extract_numeric_data(headers, rows)
    
    if not series_values:
        print(f"{COLOR_RED}Error: Table contains no numerical columns for chart series.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    title = args.title or f"Chart compiled from {os.path.basename(args.file)}"
    chart_svg = ""
    
    if args.type == "bar":
        chart_svg = generate_bar_chart(labels, value_headers, series_values, title)
    elif args.type == "line":
        chart_svg = generate_line_chart(labels, value_headers, series_values, title)
    elif args.type == "pie":
        # Pie chart takes one numerical series. Use the first one.
        chart_svg = generate_pie_chart(labels, value_headers[0], series_values[0], title)
        
    if args.output:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write(chart_svg)
        print(f"{COLOR_GREEN}Successfully compiled SVG chart to '{args.output}'.{COLOR_RESET}")
    else:
        print(chart_svg)


if __name__ == "__main__":
    main()
