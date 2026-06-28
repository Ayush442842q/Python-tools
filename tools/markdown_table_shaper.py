#!/usr/bin/env python3
"""
Markdown Table Shaper
A command-line utility to parse, filter, sort, select columns, transpose, and re-format Markdown tables.
Reads from files or standard input, performs transformations, and outputs a beautifully aligned Markdown table.
"""

import argparse
import re
import sys

def parse_markdown_table(lines):
    """
    Parses a markdown table from a list of lines.
    Returns: (headers, rows, alignments)
    """
    headers = []
    rows = []
    alignments = []  # 'left', 'center', 'right'
    
    table_started = False
    header_line = None
    separator_line = None
    
    for line in lines:
        cleaned = line.strip()
        if not cleaned.startswith('|'):
            if table_started:
                break  # Table ended
            continue
            
        # Parse table row
        cells = [c.strip() for c in cleaned.split('|')[1:-1]]
        
        # Check if this is the separator line
        # e.g., |:---|:---:|---:| or |---|---|
        is_separator = all(re.match(r'^:?-+:?$', cell) for cell in cells) and len(cells) > 0
        
        if is_separator:
            separator_line = cells
            table_started = True
            # Determine alignments
            for cell in separator_line:
                left = cell.startswith(':')
                right = cell.endswith(':')
                if left and right:
                    alignments.append('center')
                elif right:
                    alignments.append('right')
                else:
                    alignments.append('left')
            continue
            
        if not table_started:
            # We assume the line before separator is the header
            header_line = cells
        else:
            rows.append(cells)
            
    if header_line and separator_line:
        headers = header_line
    else:
        # Fallback if no header/separator found but standard pipe structure exists
        # e.g., first row as headers
        all_pipe_lines = [l.strip() for l in lines if l.strip().startswith('|')]
        if len(all_pipe_lines) >= 1:
            headers = [c.strip() for c in all_pipe_lines[0].split('|')[1:-1]]
            rows = [[c.strip() for c in l.split('|')[1:-1]] for l in all_pipe_lines[1:]]
            alignments = ['left'] * len(headers)
            
    return headers, rows, alignments

def format_markdown_table(headers, rows, alignments=None):
    """Formats headers and rows into a clean, aligned Markdown table."""
    if not headers:
        return ""
        
    num_cols = len(headers)
    if alignments is None or len(alignments) != num_cols:
        alignments = ['left'] * num_cols
        
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for idx in range(min(num_cols, len(row))):
            widths[idx] = max(widths[idx], len(row[idx]))
            
    # Format header
    header_str = "| " + " | ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers)) + " |"
    
    # Format separator
    sep_cells = []
    for idx, align in enumerate(alignments):
        w = widths[idx]
        if align == 'center':
            sep_cells.append(":" + "-" * (w - 2) + ":")
        elif align == 'right':
            sep_cells.append("-" * (w - 1) + ":")
        else:
            sep_cells.append("-" * w)
    separator_str = "| " + " | ".join(sep_cells) + " |"
    
    # Format rows
    row_strs = []
    for row in rows:
        formatted_cells = []
        for idx in range(num_cols):
            val = row[idx] if idx < len(row) else ""
            w = widths[idx]
            align = alignments[idx]
            
            if align == 'center':
                formatted_cells.append(val.center(w))
            elif align == 'right':
                formatted_cells.append(val.rjust(w))
            else:
                formatted_cells.append(val.ljust(w))
        row_strs.append("| " + " | ".join(formatted_cells) + " |")
        
    return "\n".join([header_str, separator_str] + row_strs)

def filter_rows(headers, rows, filter_expr):
    """
    Filters rows based on filter expression.
    Format support:
    - 'ColumnName==Value'
    - 'ColumnName>Value'
    - 'ColumnName<Value'
    - 'SearchText' (checks all columns)
    """
    match = re.match(r'^([^>=<!]+)(==|!=|>|<|>=|<=)(.*)$', filter_expr)
    if not match:
        # Search string check across all cells
        query = filter_expr.lower()
        return [r for r in rows if any(query in cell.lower() for cell in r)]
        
    col_name = match.group(1).strip()
    op = match.group(2)
    val_str = match.group(3).strip()
    
    # Clean quotes from value
    if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
        val_str = val_str[1:-1]
        
    # Find column index (case-insensitive)
    col_idx = -1
    for idx, h in enumerate(headers):
        if h.lower() == col_name.lower():
            col_idx = idx
            break
            
    if col_idx == -1:
        # Fallback to column index number
        try:
            col_idx = int(col_name)
        except ValueError:
            print(f"Warning: Column '{col_name}' not found. Skipping filter.", file=sys.stderr)
            return rows
            
    filtered = []
    for row in rows:
        if col_idx >= len(row):
            continue
        cell_val = row[col_idx]
        
        # Try numeric comparison
        try:
            num_cell = float(cell_val)
            num_val = float(val_str)
            if op == '==': match_ok = num_cell == num_val
            elif op == '!=': match_ok = num_cell != num_val
            elif op == '>': match_ok = num_cell > num_val
            elif op == '<': match_ok = num_cell < num_val
            elif op == '>=': match_ok = num_cell >= num_val
            elif op == '<=': match_ok = num_cell <= num_val
        except ValueError:
            # String comparison
            if op == '==': match_ok = cell_val.lower() == val_str.lower()
            elif op == '!=': match_ok = cell_val.lower() != val_str.lower()
            elif op == '>': match_ok = cell_val.lower() > val_str.lower()
            elif op == '<': match_ok = cell_val.lower() < val_str.lower()
            elif op == '>=': match_ok = cell_val.lower() >= val_str.lower()
            elif op == '<=': match_ok = cell_val.lower() <= val_str.lower()
            else: match_ok = False
            
        if match_ok:
            filtered.append(row)
            
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Markdown Table Shaper - Filter, sort, select, and reshape Markdown tables")
    parser.add_argument("-i", "--input", help="Input Markdown file (default: read from stdin)")
    parser.add_argument("-o", "--output", help="Output file (default: write to stdout)")
    parser.add_argument("-t", "--transpose", action="store_true", help="Transpose rows and columns")
    parser.add_argument("-s", "--sort-by", help="Column name or index to sort by")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting order")
    parser.add_argument("-c", "--columns", help="Comma-separated column names or indices to keep")
    parser.add_argument("-f", "--filter", help="Filter rows (e.g. 'Status==Active', 'Price>50', or generic search string)")
    parser.add_argument("-l", "--limit", type=int, help="Limit number of output data rows")
    
    args = parser.parse_args()
    
    # Read input lines
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print("Note: Waiting for markdown table input from stdin...", file=sys.stderr)
        lines = sys.stdin.readlines()
        
    headers, rows, alignments = parse_markdown_table(lines)
    
    if not headers:
        print("Error: Could not find or parse a valid markdown table from the input.", file=sys.stderr)
        return 1
        
    # 1. Filter rows
    if args.filter:
        rows = filter_rows(headers, rows, args.filter)
        
    # 2. Select columns
    if args.columns:
        col_selectors = [c.strip() for c in args.columns.split(',')]
        new_indices = []
        for sel in col_selectors:
            # Try to match name first
            found = False
            for idx, h in enumerate(headers):
                if h.lower() == sel.lower():
                    new_indices.append(idx)
                    found = True
                    break
            if not found:
                try:
                    idx = int(sel)
                    if 0 <= idx < len(headers):
                        new_indices.append(idx)
                    else:
                        print(f"Warning: Column index {idx} out of range.", file=sys.stderr)
                except ValueError:
                    print(f"Warning: Column '{sel}' not found.", file=sys.stderr)
                    
        if new_indices:
            headers = [headers[i] for i in new_indices]
            alignments = [alignments[i] for i in new_indices]
            new_rows = []
            for row in rows:
                new_rows.append([row[i] if i < len(row) else "" for i in new_indices])
            rows = new_rows
            
    # 3. Sort by column
    if args.sort_by:
        sort_col = args.sort_by
        col_idx = -1
        for idx, h in enumerate(headers):
            if h.lower() == sort_col.lower():
                col_idx = idx
                break
        if col_idx == -1:
            try:
                col_idx = int(sort_col)
            except ValueError:
                pass
                
        if 0 <= col_idx < len(headers):
            def sort_key(row):
                val = row[col_idx] if col_idx < len(row) else ""
                # Try sorting numerically if possible
                try:
                    return (0, float(val))
                except ValueError:
                    return (1, val.lower())
                    
            rows.sort(key=sort_key, reverse=args.reverse)
        else:
            print(f"Warning: Sort column '{sort_col}' not found. Skipping sorting.", file=sys.stderr)
            
    # 4. Transpose (rotate) table
    if args.transpose:
        # Columns become rows
        # Row 1 is: [Header1, Row1Val1, Row2Val1, ...]
        transposed_headers = ["Metric"] + [f"Row {i+1}" for i in range(len(rows))]
        transposed_rows = []
        for col_idx in range(len(headers)):
            col_name = headers[col_idx]
            new_row = [col_name]
            for row in rows:
                new_row.append(row[col_idx] if col_idx < len(row) else "")
            transposed_rows.append(new_row)
            
        headers = transposed_headers
        rows = transposed_rows
        alignments = ['left'] * len(headers)
        
    # 5. Apply Limit
    if args.limit is not None and args.limit >= 0:
        rows = rows[:args.limit]
        
    # Format output
    output_table = format_markdown_table(headers, rows, alignments)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_table + "\n")
            print(f"Transformed table successfully written to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(output_table)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
