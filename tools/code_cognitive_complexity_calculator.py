#!/usr/bin/env python3
"""
Python Cognitive Complexity Calculator
--------------------------------------
Calculates SonarSource-style Cognitive Complexity metrics for Python functions, methods, and modules.
Unlike Cyclomatic Complexity (which measures test paths), Cognitive Complexity measures how difficult code
is to comprehend by penalizing nested control structures, logical operator chains, and breaks in linear execution flow.

Author: Antigravity
License: MIT
"""

import sys
import os
import ast
import json
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


class CognitiveComplexityVisitor(ast.NodeVisitor):
    def __init__(self, func_name: str = "module"):
        self.func_name = func_name
        self.score = 0
        self.details: List[Tuple[int, str, int]] = []  # (lineno, reason, score_added)
        self.nesting_level = 0

    def _increment(self, node: ast.AST, reason: str, is_nesting_increment: bool = True):
        added = 1 + (self.nesting_level if is_nesting_increment else 0)
        self.score += added
        lineno = getattr(node, "lineno", 0)
        self.details.append((lineno, reason, added))

    def visit_If(self, node: ast.If):
        # Check if this node is an 'elif' (parent was an 'If' and this node is in parent's orelse)
        is_elif = getattr(node, "is_elif", False)
        if is_elif:
            self._increment(node, "elif", is_nesting_increment=False)
        else:
            self._increment(node, "if")

        self.visit(node.test)

        self.nesting_level += 1
        for stmt in node.body:
            self.visit(stmt)
        self.nesting_level -= 1

        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # Mark child as elif
                node.orelse[0].is_elif = True
                self.visit(node.orelse[0])
            else:
                self._increment(node.orelse[0], "else", is_nesting_increment=False)
                self.nesting_level += 1
                for stmt in node.orelse:
                    self.visit(stmt)
                self.nesting_level -= 1

    def visit_For(self, node: ast.For):
        self._increment(node, "for loop")
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node: ast.While):
        self._increment(node, "while loop")
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self._increment(node, "except handler")
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_BoolOp(self, node: ast.BoolOp):
        # Penalize sequences of different logical operators
        op_name = node.op.__class__.__name__
        self._increment(node, f"boolean operator ({op_name})", is_nesting_increment=False)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Recursion check
        if isinstance(node.func, ast.Name) and node.func.id == self.func_name:
            self._increment(node, f"recursive call to '{self.func_name}'", is_nesting_increment=False)
        self.generic_visit(node)


def calculate_function_complexity(func_node: ast.FunctionDef, source_lines: List[str]) -> Dict[str, Any]:
    visitor = CognitiveComplexityVisitor(func_name=func_node.name)
    for stmt in func_node.body:
        visitor.visit(stmt)

    end_lineno = getattr(func_node, "end_lineno", func_node.lineno + len(func_node.body))
    line_count = end_lineno - func_node.lineno + 1

    # Grade allocation
    # 0-5: Simple (A), 6-10: Moderate (B), 11-15: Complex (C), 16-25: High (D), >25: Extreme (F)
    score = visitor.score
    if score <= 5:
        grade = "A (Simple)"
    elif score <= 10:
        grade = "B (Moderate)"
    elif score <= 15:
        grade = "C (Complex)"
    elif score <= 25:
        grade = "D (High Risk)"
    else:
        grade = "F (Extreme Complexity)"

    return {
        "name": func_node.name,
        "lineno": func_node.lineno,
        "end_lineno": end_lineno,
        "line_count": line_count,
        "score": score,
        "grade": grade,
        "details": visitor.details,
    }


def analyze_file(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    source_lines = content.splitlines()
    tree = ast.parse(content, filename=filepath)

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_info = calculate_function_complexity(node, source_lines)
            functions.append(fn_info)

    functions.sort(key=lambda x: x["score"], reverse=True)
    total_score = sum(f["score"] for f in functions)

    return {
        "filepath": filepath,
        "total_functions": len(functions),
        "total_score": total_score,
        "average_score": round(total_score / len(functions), 2) if functions else 0.0,
        "functions": functions,
    }


def main():
    parser = argparse.ArgumentParser(description="Python Cognitive Complexity Calculator")
    parser.add_argument("path", nargs="?", help="Python file or directory to analyze")
    parser.add_argument("--min-score", "-m", type=int, default=0, help="Only display functions with score >= min-score")
    parser.add_argument("--details", "-d", action="store_true", help="Show line-by-line breakdown of complexity penalties")
    parser.add_argument("--json", action="store_true", help="Output analysis in JSON format")

    args = parser.parse_args()

    if not args.path:
        print(f"{YELLOW}No file specified. Running demonstration with sample Python snippet:{RESET}\n")
        sample_code = '''
def process_data(data, options):
    result = []
    if data is not None:                  # +1 (if)
        for item in data:                 # +2 (nested for: 1 + 1 depth)
            if item.is_valid():           # +3 (nested if: 1 + 2 depth)
                if options.get("fast") or options.get("cached"): # +4 (nested if + bool op)
                    result.append(item.value)
            elif item.is_fallback():      # +1 (elif)
                result.append(item.default)
            else:                         # +1 (else)
                print("Skipped invalid item")
    return result
'''
        print(f"{CYAN}{BOLD}Sample Code:{RESET}")
        print(sample_code)

        tree = ast.parse(sample_code)
        fn_node = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]
        res = calculate_function_complexity(fn_node, sample_code.splitlines())

        print(f"{BOLD}{BLUE}Cognitive Complexity Result:{RESET}")
        print(f"  Function: {BOLD}{res['name']}{RESET}")
        print(f"  Score: {BOLD}{RED if res['score'] > 10 else GREEN}{res['score']}{RESET} [{res['grade']}]")
        print(f"\n{CYAN}Complexity Penalties Breakdown:{RESET}")
        for lineno, reason, score_added in res["details"]:
            print(f"  Line {lineno:<3} | +{score_added} penalty for: {reason}")
        return

    target_files = []
    if os.path.isfile(args.path):
        target_files.append(args.path)
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".py"):
                    target_files.append(os.path.join(root, file))

    if not target_files:
        print(f"{RED}No Python files found at '{args.path}'.{RESET}", file=sys.stderr)
        sys.exit(1)

    reports = []
    for fpath in target_files:
        try:
            reports.append(analyze_file(fpath))
        except Exception as e:
            print(f"{YELLOW}Warning: Failed to parse {fpath}: {e}{RESET}", file=sys.stderr)

    if args.json:
        print(json.dumps(reports, indent=2))
        return

    print(f"\n{BOLD}{BLUE}=== Python Cognitive Complexity Report ==={RESET}\n")

    for rep in reports:
        filtered_fns = [f for f in rep["functions"] if f["score"] >= args.min_score]
        if not filtered_fns and args.min_score > 0:
            continue

        print(f"{BOLD}File: {CYAN}{rep['filepath']}{RESET}")
        print(f"  Total Functions: {rep['total_functions']} | Total Score: {rep['total_score']} | Avg Score: {rep['average_score']}\n")

        for fn in filtered_fns:
            score_color = GREEN if fn["score"] <= 5 else (YELLOW if fn["score"] <= 12 else RED)
            print(f"  {score_color}● {fn['name']:<30}{RESET} Line {fn['lineno']:<4} Score: {score_color}{fn['score']:<3}{RESET} Grade: {fn['grade']}")

            if args.details and fn["details"]:
                for lineno, reason, score_added in fn["details"]:
                    print(f"      ├─ Line {lineno:<4} +{score_added} for {reason}")

        print("-" * 60)


if __name__ == "__main__":
    main()
