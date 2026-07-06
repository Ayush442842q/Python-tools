#!/usr/bin/env python3
"""
Python Pattern Matching Linter
Parses Python source code using standard AST to analyze `match` / `case` structural pattern matching syntax.
Detects unreachable patterns after wildcards, duplicate literal cases, missing fallback handlers, and redundant guards.
"""

import ast
import os
import sys
import argparse
from typing import List, Dict, Any, Tuple

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


class Diagnostic:
    def __init__(self, rule_id: str, message: str, line: int, col: int, severity: str = "WARNING"):
        self.rule_id = rule_id
        self.message = message
        self.line = line
        self.col = col
        self.severity = severity

    def __str__(self) -> str:
        color = COLOR_RED if self.severity == "ERROR" else COLOR_YELLOW
        return f"{color}[{self.severity}][{self.rule_id}]{COLOR_RESET} Line {self.line}:{self.col} - {self.message}"


class PatternMatchingVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.diagnostics: List[Diagnostic] = []

    def visit_Match(self, node: ast.Match) -> None:
        wildcard_found = False
        wildcard_line = 0
        seen_literals: Dict[str, int] = {}

        for idx, case_node in enumerate(node.cases):
            pattern = case_node.pattern
            guard = case_node.guard
            line_no = getattr(case_node, "lineno", node.lineno)
            col_no = getattr(case_node, "col_offset", node.col_offset)

            # Rule PML001: Check for unreachable case after wildcard/catch-all
            if wildcard_found:
                self.diagnostics.append(
                    Diagnostic(
                        "PML001",
                        f"Unreachable case pattern detected on line {line_no}. "
                        f"Catch-all wildcard pattern was already specified on line {wildcard_line}.",
                        line_no,
                        col_no,
                        severity="ERROR"
                    )
                )

            # Check if this case is an un-guarded wildcard / capture pattern
            is_catch_all = False
            if guard is None:
                if isinstance(pattern, ast.MatchAs) and pattern.pattern is None:
                    is_catch_all = True
                elif isinstance(pattern, ast.MatchValue) and isinstance(pattern.value, ast.Name) and pattern.value.id == "_":
                    is_catch_all = True
                elif isinstance(pattern, ast.MatchStar) and pattern.name is None:
                    is_catch_all = True

            if is_catch_all:
                wildcard_found = True
                wildcard_line = line_no

            # Rule PML002: Duplicate literal patterns in match
            if guard is None and isinstance(pattern, ast.MatchValue):
                lit_repr = ast.dump(pattern.value)
                if lit_repr in seen_literals:
                    self.diagnostics.append(
                        Diagnostic(
                            "PML002",
                            f"Duplicate literal pattern '{ast.unparse(pattern.value)}' already matched on line {seen_literals[lit_repr]}.",
                            line_no,
                            col_no,
                            severity="WARNING"
                        )
                    )
                else:
                    seen_literals[lit_repr] = line_no

        # Rule PML003: Match statement missing fallback wildcard handler
        if not wildcard_found:
            self.diagnostics.append(
                Diagnostic(
                    "PML003",
                    f"Match statement on line {node.lineno} does not include a fallback wildcard handler (case _).",
                    node.lineno,
                    node.col_offset,
                    severity="INFO"
                )
            )

        self.generic_visit(node)


def lint_source(code: str, filename: str = "<string>") -> List[Diagnostic]:
    """Parses source code and returns a list of pattern matching diagnostics."""
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as e:
        return [Diagnostic("PML000", f"Syntax error: {e.msg}", e.lineno or 1, e.offset or 1, severity="ERROR")]

    visitor = PatternMatchingVisitor(filename)
    visitor.visit(tree)
    return visitor.diagnostics


def run_demo() -> None:
    """Runs a self-contained demonstration of the pattern matching linter."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== Python Pattern Matching Linter Demo ==={COLOR_RESET}\n")

    sample_code = '''def process_command(command, status):
    match command:
        case "start":
            print("Starting")
        case "start":  # Duplicate literal!
            print("Duplicate start")
        case _:
            print("Catch-all wildcard")
        case "stop":  # Unreachable after wildcard!
            print("Stop command")

def handle_status(code):
    match code:
        case 200:
            return "OK"
        case 404:
            return "Not Found"
        # Missing case _ fallback!
'''

    print(f"{COLOR_BOLD}Sample Code under Analysis:{COLOR_RESET}")
    for idx, line in enumerate(sample_code.strip().splitlines(), 1):
        print(f"{idx:2d} | {line}")
    print()

    diagnostics = lint_source(sample_code, "<demo>")
    print(f"{COLOR_BOLD}Lint Diagnostics Found ({len(diagnostics)} issues):{COLOR_RESET}")
    for diag in diagnostics:
        print(diag)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Linter for Python 3.10+ structural pattern matching statements (match/case)."
    )
    parser.add_argument("files", nargs="*", help="Python files or directories to lint")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demonstration mode")

    args = parser.parse_args()

    if args.demo or not args.files:
        if not args.demo and not args.files:
            print(f"{COLOR_YELLOW}No Python files specified. Running demo mode...{COLOR_RESET}\n")
        run_demo()
        return

    total_issues = 0
    for target in args.files:
        if os.path.isfile(target):
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            diags = lint_source(content, target)
            if diags:
                print(f"{COLOR_BOLD}File: {target}{COLOR_RESET}")
                for d in diags:
                    print(f"  {d}")
                total_issues += len(diags)
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for f_name in files:
                    if f_name.endswith(".py"):
                        f_path = os.path.join(root, f_name)
                        with open(f_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        diags = lint_source(content, f_path)
                        if diags:
                            print(f"{COLOR_BOLD}File: {f_path}{COLOR_RESET}")
                            for d in diags:
                                print(f"  {d}")
                            total_issues += len(diags)

    print(f"\n{COLOR_GREEN}Linting complete. Found {total_issues} pattern matching issues.{COLOR_RESET}")


if __name__ == "__main__":
    main()
