#!/usr/bin/env python3
"""
Python Unused Argument & Variable Detector
Static AST analyzer to scan Python code for unused function arguments, method parameters,
lambda arguments, and loop control variables.
"""

import argparse
import ast
import json
import os
import sys

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class UnusedArgVisitor(ast.NodeVisitor):
    def __init__(self, filename, lines, ignore_underscored=True):
        self.filename = filename
        self.lines = lines
        self.ignore_underscored = ignore_underscored
        self.findings = []
        self.scope_stack = []

    def visit_FunctionDef(self, node):
        self._analyze_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._analyze_function(node)
        self.generic_visit(node)

    def _analyze_function(self, node):
        # Collect parameter names
        args_to_check = []
        all_args = (
            node.args.posonlyargs
            + node.args.args
            + node.args.kwonlyargs
        )
        
        for arg in all_args:
            name = arg.arg
            if name in ("self", "cls"):
                continue
            if self.ignore_underscored and name.startswith("_"):
                continue
            args_to_check.append((name, arg.lineno, arg.col_offset))

        if node.args.vararg and not (self.ignore_underscored and node.args.vararg.arg.startswith("_")):
            args_to_check.append((node.args.vararg.arg, node.args.vararg.lineno, node.args.vararg.col_offset))
            
        if node.args.kwarg and not (self.ignore_underscored and node.args.kwarg.arg.startswith("_")):
            args_to_check.append((node.args.kwarg.arg, node.args.kwarg.lineno, node.args.kwarg.col_offset))

        # Check usage inside function body
        body_names = set()
        for body_node in ast.walk(node):
            if body_node is node:
                continue
            if isinstance(body_node, ast.Name):
                body_names.add(body_node.id)

        for name, lineno, col_offset in args_to_check:
            if name not in body_names:
                source_line = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "filename": self.filename,
                    "function": node.name,
                    "arg_name": name,
                    "type": "unused_function_argument",
                    "line": lineno,
                    "col": col_offset,
                    "source": source_line,
                    "suggestion": f"Prefix '{name}' with '_' or remove it"
                })

    def visit_For(self, node):
        self._analyze_loop_target(node)
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self._analyze_loop_target(node)
        self.generic_visit(node)

    def _analyze_loop_target(self, node):
        targets = []
        if isinstance(node.target, ast.Name):
            targets.append((node.target.id, node.target.lineno, node.target.col_offset))
        elif isinstance(node.target, (ast.Tuple, ast.List)):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    targets.append((elt.id, elt.lineno, elt.col_offset))

        body_names = set()
        for body_node in ast.walk(node):
            if body_node is node.target:
                continue
            if isinstance(body_node, ast.Name):
                body_names.add(body_node.id)

        for name, lineno, col_offset in targets:
            if self.ignore_underscored and name.startswith("_"):
                continue
            if name not in body_names:
                source_line = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "filename": self.filename,
                    "function": "<loop>",
                    "arg_name": name,
                    "type": "unused_loop_variable",
                    "line": lineno,
                    "col": col_offset,
                    "source": source_line,
                    "suggestion": f"Use '_{name}' or '_' for unused loop target"
                })


def analyze_code(content, filename="<string>", ignore_underscored=True):
    lines = content.splitlines()
    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError as e:
        return None, f"Syntax error at line {e.lineno}: {e.msg}"

    visitor = UnusedArgVisitor(filename, lines, ignore_underscored=ignore_underscored)
    visitor.visit(tree)
    return visitor.findings, None


def analyze_file(filepath, ignore_underscored=True):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return analyze_code(content, filepath, ignore_underscored)
    except Exception as e:
        return None, str(e)


def run_demo():
    sample_code = '''
def process_user_data(user_id, raw_payload, format_version, verbose=False):
    # format_version and verbose are unused
    print(f"Processing user {user_id}")
    return {"status": "ok"}

class DataHandler:
    def handle_request(self, request, headers, context):
        # headers is unused
        return request.get("data")

def calculate_totals(items):
    total = 0
    for idx, item in enumerate(items):
        # idx is unused
        total += item["price"]
    return total
'''
    print(f"{BOLD}{CYAN}=== Python Unused Argument Detector Demo ==={RESET}\n")
    print(f"{BOLD}Analyzing sample Python code:{RESET}")
    print(sample_code)
    print(f"\n{BOLD}{YELLOW}Scan Findings:{RESET}")

    findings, error = analyze_code(sample_code, "demo_script.py")
    if error:
        print(f"{RED}Error: {error}{RESET}")
        return

    for idx, item in enumerate(findings, 1):
        print(f"{BOLD}{idx}. [{item['type'].upper()}]{RESET} in function '{CYAN}{item['function']}{RESET}'")
        print(f"   Variable: {RED}{item['arg_name']}{RESET} (Line {item['line']})")
        print(f"   Source  : {item['source']}")
        print(f"   Fix     : {GREEN}{item['suggestion']}{RESET}\n")

    print(f"{BOLD}{GREEN}Scan completed. Found {len(findings)} unused argument(s)/variable(s).{RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Scan Python files for unused function arguments, method parameters, and loop target variables."
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to scan")
    parser.add_argument("--check-underscored", action="store_true", help="Also flag parameters starting with '_'")
    parser.add_argument("--json", action="store_true", help="Output findings in JSON format")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demo")

    args = parser.parse_args()

    if args.demo or not args.paths:
        if not args.paths and not args.demo:
            print(f"{YELLOW}No path specified. Running demo mode...{RESET}\n")
        run_demo()
        return

    ignore_underscored = not args.check_underscored
    all_findings = []

    for path in args.paths:
        if os.path.isfile(path):
            if path.endswith(".py"):
                findings, err = analyze_file(path, ignore_underscored)
                if err:
                    print(f"{RED}Error scanning {path}: {err}{RESET}", file=sys.stderr)
                elif findings:
                    all_findings.extend(findings)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".py"):
                        full_path = os.path.join(root, file)
                        findings, err = analyze_file(full_path, ignore_underscored)
                        if err:
                            print(f"{RED}Error scanning {full_path}: {err}{RESET}", file=sys.stderr)
                        elif findings:
                            all_findings.extend(findings)

    if args.json:
        print(json.dumps(all_findings, indent=2))
        return

    print(f"\n{BOLD}{CYAN}=== Python Unused Argument Detector Summary ==={RESET}\n")
    if not all_findings:
        print(f"{GREEN}No unused arguments or loop variables found!{RESET}")
        return

    for item in all_findings:
        print(f"{BOLD}{item['filename']}:{item['line']}:{item['col']}{RESET}")
        print(f"  Unused {item['type'].replace('_', ' ')} '{RED}{item['arg_name']}{RESET}' in '{CYAN}{item['function']}{RESET}'")
        print(f"  Line: {item['source']}")
        print(f"  Suggestion: {GREEN}{item['suggestion']}{RESET}\n")

    print(f"{BOLD}Total issues detected: {len(all_findings)}{RESET}")


if __name__ == "__main__":
    main()
