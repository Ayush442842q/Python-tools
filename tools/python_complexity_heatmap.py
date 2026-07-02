#!/usr/bin/env python3
"""
Python Complexity Heatmap Generator
A standalone utility that scans Python source code files, calculates cyclomatic
complexity (McCabe) and LOC for functions and methods using AST parsing, and renders
a colored CLI heatmap and standalone HTML refactoring dashboard.
"""

import argparse
import ast
import os
import sys

# ANSI color codes for TUI formatting
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


class ComplexityVisitor(ast.NodeVisitor):
    """AST NodeVisitor to measure cyclomatic complexity and lines of code."""
    def __init__(self, source_lines):
        self.source_lines = source_lines
        self.stats = []
        self.current_class = None

    def visit_ClassDef(self, node):
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        self.analyze_function(node)

    def visit_AsyncFunctionDef(self, node):
        self.analyze_function(node)

    def analyze_function(self, node):
        # Calculate complexity: base complexity of 1 + decision points
        complexity = 1
        
        # Decision points in Python AST
        decision_nodes = (
            ast.If, ast.While, ast.For, ast.AsyncFor,
            ast.ExceptHandler, ast.With, ast.AsyncWith
        )
        
        for subnode in ast.walk(node):
            # Check statements
            if isinstance(subnode, decision_nodes):
                complexity += 1
            # Check boolean operators (and, or)
            elif isinstance(subnode, ast.BoolOp):
                complexity += len(subnode.values) - 1
            # Check conditional expressions (x if y else z)
            elif isinstance(subnode, ast.IfExp):
                complexity += 1
            # Check list/dict/set comprehensions and generator expressions
            elif isinstance(subnode, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                # Each comprehension clause acts as a loop decision point
                complexity += len(subnode.generators)

        # Calculate Lines of Code (LOC)
        # Use node.end_lineno if available (Python 3.8+)
        if hasattr(node, "end_lineno"):
            loc = node.end_lineno - node.lineno + 1
        else:
            # Fallback estimation
            loc = len(self.source_lines[node.lineno - 1:])

        # Get function name representation (with class context if any)
        name = node.name
        if self.current_class:
            name = f"{self.current_class}.{name}"

        self.stats.append({
            "name": name,
            "complexity": complexity,
            "loc": loc,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno)
        })


def analyze_file(filepath):
    """Parses a Python file and returns complexity statistics."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}", file=sys.stderr)
        return []

    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error parsing {filepath}:{e.lineno}: {e.msg}", file=sys.stderr)
        return []

    visitor = ComplexityVisitor(lines)
    visitor.visit(tree)
    
    # Enrich stats with filename
    for s in visitor.stats:
        s["file"] = filepath

    return visitor.stats


def get_heatmap_color(complexity, loc):
    """Categorizes the risk level and returns an ANSI color + rating description."""
    if complexity > 10 or loc > 60:
        return COLOR_RED, "HIGH RISK (Complex / Bloated)"
    elif complexity > 5 or loc > 30:
        return COLOR_YELLOW, "MODERATE RISK (Warning)"
    return COLOR_GREEN, "LOW RISK (Clean)"


def generate_html_report(stats, output_path):
    """Generates a standalone, beautiful HTML dashboard report."""
    rows = []
    for s in sorted(stats, key=lambda x: x["complexity"], reverse=True):
        risk_class = "risk-low"
        risk_text = "Low Risk"
        if s["complexity"] > 10 or s["loc"] > 60:
            risk_class = "risk-high"
            risk_text = "High Risk"
        elif s["complexity"] > 5 or s["loc"] > 30:
            risk_class = "risk-mod"
            risk_text = "Moderate Risk"

        rel_path = os.path.basename(s["file"])
        rows.append(f"""
        <tr class="{risk_class}">
            <td>{rel_path}</td>
            <td><code>{s['name']}</code></td>
            <td class="num">{s['complexity']}</td>
            <td class="num">{s['loc']}</td>
            <td>L{s['line_start']}-L{s['line_end']}</td>
            <td><span class="badge">{risk_text}</span></td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Python Complexity Heatmap Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 40px;
            background-color: #f6f8fa;
            color: #24292e;
        }}
        h1 {{
            border-bottom: 1px solid #e1e4e8;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .summary {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            flex: 1;
            background: white;
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(27,31,35,0.12);
            text-align: center;
        }}
        .card h2 {{
            margin-top: 0;
            color: #586069;
            font-size: 14px;
            text-transform: uppercase;
        }}
        .card .value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(27,31,35,0.12);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e1e4e8;
        }}
        th {{
            background-color: #f1f8ff;
            color: #0366d6;
        }}
        tr:hover {{
            background-color: #f6f8fa;
        }}
        .num {{
            text-align: right;
            font-family: monospace;
            font-size: 14px;
        }}
        .risk-high {{
            border-left: 5px solid #d73a49;
        }}
        .risk-high .badge {{
            background: #ffeef0;
            color: #d73a49;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .risk-mod {{
            border-left: 5px solid #e3b341;
        }}
        .risk-mod .badge {{
            background: #fff8e6;
            color: #b08500;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .risk-low {{
            border-left: 5px solid #28a745;
        }}
        .risk-low .badge {{
            background: #dcffe4;
            color: #28a745;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <h1>Python Complexity Heatmap Dashboard</h1>
    
    <div class="summary">
        <div class="card" style="border-top: 4px solid #0366d6;">
            <h2>Total Functions Analyzed</h2>
            <div class="value">{len(stats)}</div>
        </div>
        <div class="card" style="border-top: 4px solid #d73a49;">
            <h2>High Risk Hotspots</h2>
            <div class="value" style="color: #d73a49;">{sum(1 for s in stats if s['complexity'] > 10 or s['loc'] > 60)}</div>
        </div>
        <div class="card" style="border-top: 4px solid #e3b341;">
            <h2>Moderate Risk Warnings</h2>
            <div class="value" style="color: #b08500;">{sum(1 for s in stats if (5 < s['complexity'] <= 10 or 30 < s['loc'] <= 60) and not (s['complexity'] > 10 or s['loc'] > 60))}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Function/Method</th>
                <th class="num">Complexity (McCabe)</th>
                <th class="num">LOC</th>
                <th>Lines</th>
                <th>Risk Level</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</body>
</html>
"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nHTML dashboard report generated: {output_path}")
    except Exception as e:
        print(f"Error writing HTML report: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Scan Python projects, analyze McCabe complexity & LOC, and build refactoring hotspots heatmaps."
    )
    parser.add_argument("targets", nargs="+", help="Files or directories to scan recursively.")
    parser.add_argument("-s", "--sort", choices=["complexity", "loc", "file"], default="complexity", help="Sort results by metric.")
    parser.add_argument("--html", help="Path to generate a visual HTML report dashboard.")
    parser.add_argument("--min-complexity", type=int, default=1, help="Only show functions with complexity >= this value.")
    parser.add_argument("--min-loc", type=int, default=1, help="Only show functions with LOC >= this value.")

    args = parser.parse_args()

    all_files = []
    for target in args.targets:
        if os.path.isdir(target):
            for root, _, filenames in os.walk(target):
                for f in filenames:
                    if f.endswith(".py"):
                        all_files.append(os.path.join(root, f))
        elif os.path.isfile(target) and target.endswith(".py"):
            all_files.append(target)

    if not all_files:
        print("No Python files found to analyze.", file=sys.stderr)
        return 1

    print(f"Scanning {len(all_files)} files...")
    all_stats = []
    for filepath in all_files:
        all_stats.extend(analyze_file(filepath))

    if not all_stats:
        print("No function or method definitions analyzed in the specified targets.", file=sys.stderr)
        return 0

    # Filter stats
    filtered_stats = [
        s for s in all_stats 
        if s["complexity"] >= args.min_complexity and s["loc"] >= args.min_loc
    ]

    # Sort stats
    if args.sort == "complexity":
        filtered_stats.sort(key=lambda x: x["complexity"], reverse=True)
    elif args.sort == "loc":
        filtered_stats.sort(key=lambda x: x["loc"], reverse=True)
    elif args.sort == "file":
        filtered_stats.sort(key=lambda x: (x["file"], x["line_start"]))

    # Render Terminal Heatmap
    print("\n" + COLOR_BOLD + "=== PYTHON REFACTORING HEATMAP ===" + COLOR_RESET)
    print(f"{'File':<25} | {'Function/Method':<30} | {'Complexity':<10} | {'LOC':<5} | {'Risk Rating'}")
    print("-" * 90)

    for s in filtered_stats:
        col, rating = get_heatmap_color(s["complexity"], s["loc"])
        short_file = os.path.basename(s["file"])
        if len(short_file) > 25:
            short_file = short_file[-22:] + "..."

        short_name = s["name"]
        if len(short_name) > 30:
            short_name = short_name[:27] + "..."

        print(f"{short_file:<25} | {short_name:<30} | {col}{s['complexity']:<10}{COLOR_RESET} | {col}{s['loc']:<5}{COLOR_RESET} | {col}{rating}{COLOR_RESET}")

    # Generate HTML report if requested
    if args.html:
        generate_html_report(filtered_stats, args.html)

    return 0


if __name__ == "__main__":
    sys.exit(main())
