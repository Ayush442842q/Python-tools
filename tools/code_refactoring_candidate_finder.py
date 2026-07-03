#!/usr/bin/env python3
"""
Code Refactoring Candidate Finder
---------------------------------
Recursively scans a directory for Python files, computes several complexity
and readability metrics (Cyclomatic Complexity, Nesting Depth, Line Counts,
Comment Density, and TODOs) using Python's AST parser, and compiles a weighted
"Code Debt Score" for each file. It outputs a colorized dashboard of the top
candidates for refactoring.

Author: Antigravity
License: MIT
"""

import os
import sys
import ast
import argparse
from pathlib import Path

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class MetricVisitor(ast.NodeVisitor):
    def __init__(self):
        self.complexity = 1
        self.max_nesting = 0
        self.current_nesting = 0

    def visit_control_flow(self, node):
        self.complexity += 1
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_If(self, node):
        self.visit_control_flow(node)

    def visit_For(self, node):
        self.visit_control_flow(node)

    def visit_While(self, node):
        self.visit_control_flow(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        # Except handler increases complexity but doesn't necessarily count as deeper control nesting
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # e.g., a and b and c has complexity incremented by 2
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

def analyze_file(filepath):
    """Analyzes a Python file for lines, comments, TODOs, complexity, and nesting."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return None

    raw_loc = len(lines)
    blank_lines = 0
    comments = 0
    todos = 0
    code_lines = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
        elif stripped.startswith("#"):
            comments += 1
            if any(token in stripped.upper() for token in ["TODO", "FIXME", "HACK", "XXX"]):
                todos += 1
        else:
            code_lines += 1
            # Check for inline comments and TODOs
            if "#" in stripped:
                comment_part = stripped.split("#", 1)[1]
                if any(token in comment_part.upper() for token in ["TODO", "FIXME", "HACK", "XXX"]):
                    todos += 1

    try:
        content = "".join(lines)
        tree = ast.parse(content)
        visitor = MetricVisitor()
        visitor.visit(tree)
        complexity = visitor.complexity
        max_nesting = visitor.max_nesting
    except Exception:
        # Fallback if AST parsing fails (e.g. syntax error in file)
        complexity = 1
        max_nesting = 0

    comment_density = (comments / code_lines * 100) if code_lines > 0 else 0
    
    # Calculate Code Debt Score (0 - 100)
    # Weights: Complexity (35%), Nesting (25%), Code Lines (20%), Comments Ratio (10%), TODOs (10%)
    # Complexity normalization: 1-15 is normal, >50 is critical
    comp_score = min(100, (complexity / 40.0) * 100)
    # Nesting normalization: 0-3 normal, >6 critical
    nest_score = min(100, (max_nesting / 6.0) * 100)
    # LOC normalization: <100 normal, >1000 critical
    loc_score = min(100, (code_lines / 800.0) * 100)
    # Comment density penalty (too low <5% or too high >50% is bad, target 10-30%)
    if comment_density < 5:
        comm_score = 100
    elif comment_density > 50:
        comm_score = 50
    else:
        comm_score = 0
    # TODOs normalization: 0 normal, >10 critical
    todo_score = min(100, (todos / 10.0) * 100)

    debt_score = (
        comp_score * 0.35 +
        nest_score * 0.25 +
        loc_score * 0.20 +
        comm_score * 0.10 +
        todo_score * 0.10
    )

    return {
        "path": filepath,
        "raw_loc": raw_loc,
        "loc": code_lines,
        "comments": comments,
        "comment_density": comment_density,
        "todos": todos,
        "complexity": complexity,
        "max_nesting": max_nesting,
        "debt_score": debt_score
    }

def print_row(path, loc, comp, nest, comm, todo, score, width=110):
    # Colorize the score
    if score >= 70:
        score_str = f"{RED}{score:5.1f}{RESET}"
    elif score >= 40:
        score_str = f"{YELLOW}{score:5.1f}{RESET}"
    else:
        score_str = f"{GREEN}{score:5.1f}{RESET}"

    path_part = path[-40:] if len(path) > 40 else path
    print(f"| {path_part:<40} | {loc:>6} | {comp:>10} | {nest:>9} | {comm:>7.1f}% | {todo:>5} | {score_str} |")

def main():
    parser = argparse.ArgumentParser(
        description="Scans Python files to identify potential refactoring candidates based on structural code debt.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory).")
    parser.add_argument("--limit", type=int, default=15, help="Limit output to top N candidates (default: 15).")
    parser.add_argument("--min-score", type=float, default=20.0, help="Exclude files with a debt score lower than this (default: 20.0).")
    parser.add_argument("--exclude", nargs="*", default=[], help="Directories/files to ignore (glob support).")
    
    args = parser.parse_args()
    
    target_dir = Path(args.path)
    if not target_dir.exists():
        print(f"{RED}Error: Path '{args.path}' does not exist.{RESET}")
        sys.exit(1)
        
    print(f"{BOLD}[*] Scanning directory: {target_dir.resolve()}{RESET}")
    
    python_files = []
    exclude_dirs = {".git", "__pycache__", "venv", ".venv", "env", ".env", "node_modules", "build", "dist"}
    exclude_dirs.update(args.exclude)

    for root, dirs, files in os.walk(target_dir):
        # Modifying dirs in-place to prune excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
                
    if not python_files:
        print(f"{YELLOW}No Python (.py) files found.{RESET}")
        sys.exit(0)
        
    print(f"[*] Found {len(python_files)} files. Analyzing structural metrics...")
    
    results = []
    for filepath in python_files:
        analysis = analyze_file(filepath)
        if analysis:
            # Get relative path for clean display
            try:
                rel_path = os.path.relpath(filepath, target_dir)
            except Exception:
                rel_path = filepath
            analysis["display_path"] = rel_path
            results.append(analysis)
            
    # Filter and sort
    results = [r for r in results if r["debt_score"] >= args.min_score]
    results.sort(key=lambda x: x["debt_score"], reverse=True)
    
    if not results:
        print(f"{GREEN}[+] Excellent! No files met the minimum debt score threshold of {args.min_score}.{RESET}")
        sys.exit(0)
        
    top_candidates = results[:args.limit]
    
    print("\n" + "=" * 105)
    print(f"{BOLD}{'CODE REFACTORING CANDIDATES DIRECTORY SUMMARY':^105}{RESET}")
    print("=" * 105)
    print(f"| {'File Path':<40} | {'LOC':>6} | {'Complexity':>10} | {'Max Depth':>9} | {'Comments':>8} | {'TODOs':>5} | {'Score':>5} |")
    print("-" * 105)
    
    for r in top_candidates:
        print_row(
            r["display_path"],
            r["loc"],
            r["complexity"],
            r["max_nesting"],
            r["comment_density"],
            r["todos"],
            r["debt_score"]
        )
        
    print("=" * 105)
    print(f"\n{BOLD}Top Refactoring Recommendation Details:{RESET}")
    
    for idx, r in enumerate(top_candidates[:3], 1):
        score = r["debt_score"]
        color = RED if score >= 70 else (YELLOW if score >= 40 else GREEN)
        print(f"\n{idx}. {BOLD}{r['display_path']}{RESET} (Debt Score: {color}{score:.1f}{RESET})")
        
        reasons = []
        if r["complexity"] > 25:
            reasons.append(f"High Cyclomatic Complexity ({r['complexity']}): Contains too many branches and decision points.")
        if r["max_nesting"] > 4:
            reasons.append(f"Deep Nesting Depth ({r['max_nesting']}): Highly nested code block makes it hard to read and test.")
        if r["loc"] > 500:
            reasons.append(f"Large File Size ({r['loc']} lines of code): Consider breaking modules down into smaller utility files.")
        if r["comment_density"] < 8:
            reasons.append(f"Low Documentation ({r['comment_density']:.1f}% comments): Code contains few comments explaining the logic.")
        if r["todos"] > 5:
            reasons.append(f"High technical debt annotations ({r['todos']} TODOs/FIXMEs): Outstanding developer issues remaining.")
            
        if not reasons:
            reasons.append("Moderate overall metric warnings; review general structural cleanup.")
            
        for reason in reasons:
            print(f"   - {reason}")
            
    print(f"\n{CYAN}[i] Tip: Target functions with high complexity and pull them out into standalone, pure functions.{RESET}")

if __name__ == "__main__":
    main()
