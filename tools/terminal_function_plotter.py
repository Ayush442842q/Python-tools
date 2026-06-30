#!/usr/bin/env python3
"""
Terminal Mathematical Function Grapher

Plots mathematical expressions (e.g. sin(x), x**2, cos(x)/2) on a 2D ASCII/Unicode grid
directly in the terminal. Safely parses input expressions using AST validation.

Usage:
    python terminal_function_plotter.py "sin(x)" --range "-6.28,6.28"
"""

import sys
import argparse
import math
import ast

# Whitelist of allowed nodes in the AST to prevent arbitrary code execution
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,  # Python 3.8+
    ast.Name,
    ast.Call,
    ast.Load,
    # Operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub
)

ALLOWED_FUNCTIONS = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sinh': math.sinh,
    'cosh': math.cosh,
    'tanh': math.tanh,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'sqrt': math.sqrt,
    'abs': abs,
    'ceil': math.ceil,
    'floor': math.floor,
}

ALLOWED_CONSTANTS = {
    'pi': math.pi,
    'e': math.e,
}

def validate_expression(expr_str):
    """Parses expression with AST and validates against whitelist to ensure safety."""
    try:
        tree = ast.parse(expr_str, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Syntax error in expression: {e}")
        
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Unauthorized code element detected: '{type(node).__name__}'")
            
        if isinstance(node, ast.Name):
            if node.id not in ('x', 'pi', 'e') and node.id not in ALLOWED_FUNCTIONS:
                raise ValueError(f"Unauthorized variable/constant reference: '{node.id}'")
                
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                func_name = node.func.id if isinstance(node.func, ast.Name) else "complex call"
                raise ValueError(f"Unauthorized function call: '{func_name}'")
                
    return compile(tree, '<string>', 'eval')

def evaluate_formula(compiled_code, x_val):
    """Evaluates the compiled formula with a specific value of x."""
    eval_globals = {"__builtins__": None}
    eval_locals = {
        'x': x_val,
        **ALLOWED_FUNCTIONS,
        **ALLOWED_CONSTANTS
    }
    try:
        return float(eval(compiled_code, eval_globals, eval_locals))
    except (ValueError, ZeroDivisionError, OverflowError):
        # Ignore math domain errors, division by zero, and overflows (returns None)
        return None

def plot_graphs(formulas, x_min, x_max, y_min, y_max, width, height, colors_enabled, use_unicode=True):
    """Generates the 2D grid plot string."""
    # 1. Initialize grid with empty spaces
    # We will use Unicode or ASCII characters for axes
    grid = [[' ' for _ in range(width)] for _ in range(height)]
    
    # 2. Evaluate all formulas across the X range
    # We calculate step size
    x_step = (x_max - x_min) / (width - 1)
    
    # If y_min or y_max are not supplied, auto-scale based on evaluations
    evaluated_series = []  # list of dicts mapping col_idx -> y_val
    all_y_vals = []
    
    for compiled_code in formulas:
        series = {}
        for col in range(width):
            x = x_min + col * x_step
            y = evaluate_formula(compiled_code, x)
            if y is not None and not math.isnan(y) and not math.isinf(y):
                series[col] = y
                all_y_vals.append(y)
        evaluated_series.append(series)
        
    if not all_y_vals:
        print("Error: No plottable values generated. Check your function domain ranges (e.g. log(x) for x <= 0).")
        return ""
        
    if y_min is None:
        y_min = min(all_y_vals)
    if y_max is None:
        y_max = max(all_y_vals)
        
    # Prevent divide by zero if function is constant
    if y_min == y_max:
        y_min -= 1.0
        y_max += 1.0
        
    y_step = (y_max - y_min) / (height - 1)
    
    # 3. Draw axes
    # Draw Y-axis if 0 is in the X-range
    y_axis_col = None
    if x_min <= 0 <= x_max:
        y_axis_col = int((0 - x_min) / x_step)
        if 0 <= y_axis_col < width:
            for row in range(height):
                grid[row][y_axis_col] = '│' if use_unicode else '|'
                
    # Draw X-axis if 0 is in the Y-range
    x_axis_row = None
    if y_min <= 0 <= y_max:
        x_axis_row = height - 1 - int((0 - y_min) / y_step)
        if 0 <= x_axis_row < height:
            for col in range(width):
                if grid[x_axis_row][col] in ('│', '|'):
                    grid[x_axis_row][col] = '┼' if use_unicode else '+'
                else:
                    grid[x_axis_row][col] = '─' if use_unicode else '-'
                    
    # 4. Plot curves
    # Plotting symbols for different functions
    symbols = ['*', 'o', '#', 'x', '+', '@', '%']
    ansi_colors = [
        '\033[94m',  # Blue
        '\033[92m',  # Green
        '\033[91m',  # Red
        '\033[93m',  # Yellow
        '\033[95m',  # Magenta
        '\033[96m',  # Cyan
    ]
    
    for f_idx, series in enumerate(evaluated_series):
        symbol = symbols[f_idx % len(symbols)]
        color = ansi_colors[f_idx % len(ansi_colors)] if colors_enabled else ""
        reset = '\033[0m' if colors_enabled else ""
        
        for col, y in series.items():
            # Find closest row index
            # Row 0 is the top, corresponding to y_max
            # Row height-1 is the bottom, corresponding to y_min
            row = height - 1 - int((y - y_min) / y_step)
            if 0 <= row < height:
                grid[row][col] = f"{color}{symbol}{reset}"
                
    # 5. Render output
    output_lines = []
    # Border top
    output_lines.append(f"{'┌' if use_unicode else '+'}{('─' if use_unicode else '-') * width}{'┐' if use_unicode else '+'}")
    
    # Grid content
    for r_idx, row in enumerate(grid):
        # Attach Y labels for top, middle, and bottom
        y_label = ""
        if r_idx == 0:
            y_label = f" {y_max:8.2f}"
        elif r_idx == height // 2:
            y_label = f" {y_min + (y_max - y_min) / 2:8.2f}"
        elif r_idx == height - 1:
            y_label = f" {y_min:8.2f}"
        else:
            y_label = " " * 9
            
        row_str = "".join(row)
        output_lines.append(f"{'│' if use_unicode else '|'}{row_str}{'│' if use_unicode else '|'}{y_label}")
        
    # Border bottom
    output_lines.append(f"{'└' if use_unicode else '+'}{('─' if use_unicode else '-') * width}{'┘' if use_unicode else '+'}")
    
    # X labels
    x_label_line = f" {x_min:<12.2f}" + " " * (width - 26) + f"{x_max:>12.2f} "
    output_lines.append(x_label_line)
    
    return "\n".join(output_lines)

def main():
    parser = argparse.ArgumentParser(
        description="Plot mathematical functions directly in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "formulas",
        nargs="+",
        help="One or more mathematical formulas to plot (e.g. 'sin(x)', 'x**2 - 2')."
    )
    
    parser.add_argument(
        "-r", "--range",
        default="-10,10",
        help="X range as 'min,max' (default: '-10,10')"
    )
    
    parser.add_argument(
        "-y", "--yrange",
        default=None,
        help="Y range as 'min,max' (default: auto-scale)"
    )
    
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=70,
        help="Plot width in characters (default: 70)"
    )
    
    parser.add_argument(
        "-g", "--height",
        type=int,
        default=22,
        help="Plot height in characters (default: 22)"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colored output"
    )
    
    args = parser.parse_args()
    
    # Parse ranges
    try:
        x_min, x_max = map(float, args.range.split(','))
        if x_min >= x_max:
            raise ValueError
    except ValueError:
        print("Error: Invalid X range format. Must be 'min,max' with min < max.", file=sys.stderr)
        return 1
        
    y_min, y_max = None, None
    if args.yrange:
        try:
            y_min, y_max = map(float, args.yrange.split(','))
            if y_min >= y_max:
                raise ValueError
        except ValueError:
            print("Error: Invalid Y range format. Must be 'min,max' with min < max.", file=sys.stderr)
            return 1
            
    # Validate formulas
    compiled_formulas = []
    for formula in args.formulas:
        try:
            compiled = validate_expression(formula)
            compiled_formulas.append(compiled)
        except Exception as e:
            print(f"Error validating formula '{formula}': {e}", file=sys.stderr)
            return 1
            
    try:
        plot_output = plot_graphs(
            compiled_formulas, 
            x_min, x_max, 
            y_min, y_max, 
            args.width, 
            args.height, 
            not args.no_color,
            use_unicode=True
        )
        print("\nPlotting:")
        for idx, formula in enumerate(args.formulas):
            print(f"  Curve #{idx + 1}: {formula}")
        print("\n" + plot_output + "\n")
    except UnicodeEncodeError:
        # Fallback to ASCII layout if unicode encoding is not supported in the terminal
        plot_output = plot_graphs(
            compiled_formulas, 
            x_min, x_max, 
            y_min, y_max, 
            args.width, 
            args.height, 
            not args.no_color,
            use_unicode=False
        )
        print("\nPlotting:")
        for idx, formula in enumerate(args.formulas):
            print(f"  Curve #{idx + 1}: {formula}")
        try:
            print("\n" + plot_output + "\n")
        except UnicodeEncodeError:
            # Absolute fallback: replace any remaining unicode chars
            safe_str = plot_output.encode('ascii', errors='replace').decode('ascii')
            print("\n" + safe_str + "\n")
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
