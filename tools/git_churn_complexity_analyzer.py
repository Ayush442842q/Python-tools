#!/usr/bin/env python3
"""
Git Churn & Complexity Analyzer

Correlates Git commit frequency (churn) with Python code complexity (AST-based cyclomatic complexity)
to locate "hotspots" in the codebase—files that change frequently and are complex.
These files are the primary targets for refactoring and test coverage improvements.

Usage:
    python tools/git_churn_complexity_analyzer.py
    python tools/git_churn_complexity_analyzer.py --limit 10
"""

import argparse
import ast
import os
import subprocess
import sys

# Color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def get_git_churn():
    """
    Returns a dictionary mapping relative file paths to their commit count (churn)
    """
    try:
        # Run git log to get name of files modified in each commit
        # Filter for Python files only to save processing time
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:"],
            capture_output=True,
            text=True,
            check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"{COLOR_RED}Error: Git is not installed or this directory is not a Git repository.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    churn = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and line.endswith(".py") and os.path.exists(line):
            churn[line] = churn.get(line, 0) + 1
    return churn

def calculate_complexity(filepath):
    """
    Calculates cyclomatic complexity (AST-based) and lines of code for a Python file.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception:
        return 0, 0

    # Count total lines and lines of code (ignoring empty lines)
    total_lines = len(code.splitlines())
    
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback to simple line-based estimation if syntax is invalid
        return total_lines // 10 + 1, total_lines

    complexity = 1  # Base complexity of 1 for any module/script

    # Traversal to count branches
    for node in ast.walk(tree):
        # branching constructs
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler)):
            complexity += 1
        # boolean operators
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        # comprehensions (list, dict, set, generator expressions)
        elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            complexity += len(node.generators)

    return complexity, total_lines

def draw_ascii_plot(hotspots):
    """
    Renders a simple ASCII scatter plot representing Churn (Y) vs Complexity (X).
    """
    if not hotspots:
        return

    # Filter out files with 0 churn
    data = [(h["complexity"], h["churn"], h["name"]) for h in hotspots if h["churn"] > 0]
    if not data:
        return

    max_x = max(d[0] for d in data)
    max_y = max(d[1] for d in data)
    
    # Grid dimensions
    width = 60
    height = 15

    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Plot points
    for x, y, name in data:
        px = int((x / max_x) * (width - 1)) if max_x > 0 else 0
        py = int((y / max_y) * (height - 1)) if max_y > 0 else 0
        # Invert Y so high values are at the top
        py = (height - 1) - py
        # Represent hotspot points: '*' for normal, 'H' for top hotspots (high churn & complexity)
        is_high = (x > max_x * 0.5) and (y > max_y * 0.5)
        grid[py][px] = "H" if is_high else "*"

    print(f"\n{COLOR_BOLD}Hotspot Scatter Plot (Y=Churn, X=Complexity){COLOR_RESET}")
    print("  +" + "-" * width + "+")
    for r in range(height):
        # Y axis labels
        y_val = int(((height - 1 - r) / (height - 1)) * max_y) if height > 1 else 0
        label = f"{y_val:3d} |"
        print(label + "".join(grid[r]) + "|")
    print("  +" + "-" * width + "+")
    print(f"     0" + " " * (width - 6) + f"{max_x}")
    print(f"  Note: {COLOR_RED}H{COLOR_RESET} represents high-risk hotspots (High Churn & High Complexity)\n")

def main():
    parser = argparse.ArgumentParser(description="Git Churn & Complexity Hotspot Analyzer")
    parser.add_argument("--limit", type=int, default=15, help="Number of hotspots to display in list (default: 15)")
    parser.add_argument("--min-churn", type=int, default=1, help="Minimum git churn to include a file (default: 1)")
    parser.add_argument("--min-complexity", type=int, default=1, help="Minimum complexity to include a file (default: 1)")
    parser.add_argument("--no-plot", action="store_true", help="Disable printing ASCII scatter plot")
    
    args = parser.parse_args()

    print(f"{COLOR_BOLD}Scanning Git history and calculating code complexity...{COLOR_RESET}")
    
    churn_dict = get_git_churn()
    hotspots = []

    for filepath, churn in churn_dict.items():
        if churn < args.min_churn:
            continue
            
        complexity, loc = calculate_complexity(filepath)
        if complexity < args.min_complexity:
            continue

        # Hotspot score = Churn * Complexity (standard correlation metric)
        score = churn * complexity

        hotspots.append({
            "path": filepath,
            "name": os.path.basename(filepath),
            "churn": churn,
            "complexity": complexity,
            "loc": loc,
            "score": score
        })

    # Sort hotspots by score descending
    hotspots.sort(key=lambda h: h["score"], reverse=True)

    if not hotspots:
        print("No Python files matching criteria were found.")
        return 0

    if not args.no_plot:
        draw_ascii_plot(hotspots)

    print(f"{COLOR_BOLD}Top {min(args.limit, len(hotspots))} Refactoring Hotspots:{COLOR_RESET}")
    print("-" * 100)
    print(f"{'Hotspot Score':15} | {'File Path':45} | {'Churn':8} | {'Complexity':10} | {'Lines of Code':12}")
    print("-" * 100)

    for h in hotspots[:args.limit]:
        score_label = f"{h['score']:14d}"
        path_label = h['path']
        
        # Color code based on hotspot score
        if h['score'] > 100:
            color = COLOR_RED
        elif h['score'] > 30:
            color = COLOR_YELLOW
        else:
            color = COLOR_CYAN

        if sys.stdout.isatty():
            path_label = f"{color}{path_label}{COLOR_RESET}"
            score_label = f"{COLOR_BOLD}{color}{score_label}{COLOR_RESET}"

        print(f"{score_label} | {path_label:45} | {h['churn']:8d} | {h['complexity']:10d} | {h['loc']:12d}")

    print("-" * 100)
    print(f"Analyzed {len(hotspots)} Python files with Git history.")
    print("Explanation: Hotspot Score = (Commit Churn) * (AST Cyclomatic Complexity).")
    print("Files with scores > 100 are high risk and recommended for refactoring.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
