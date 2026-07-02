#!/usr/bin/env python3
"""
Python Decorator Explorer & Analyzer
Author: Antigravity

Scans Python source files recursively using AST, analyzes decorator usages,
checks custom decorators for best practices (like @functools.wraps), and
prints a visual summary of decorator relationships.
"""

import argparse
import ast
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any

class DecoratorVisitor(ast.NodeVisitor):
    """AST visitor to find decorator declarations and applications."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        # Maps decorator name -> list of functions it decorates (func_name, line)
        self.usages = defaultdict(list)
        # Custom decorators defined in this file (decorator_name, wraps_found)
        self.definitions = []
        # Trace of functions and their decorators: func_name -> list of decorators
        self.function_decorators = {}

    def get_decorator_name(self, node: ast.AST) -> str:
        """Extracts decorator name from AST nodes (handles names, attributes, calls)."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self.get_decorator_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self.get_decorator_name(node.func)
        return "Unknown"

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 1. Check if this function itself acts as a decorator (custom decorator definition)
        # Typically a decorator returns a callable. We look for nested functions.
        nested_funcs = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if nested_funcs:
            # Check if any nested function is decorated with 'wraps' or 'functools.wraps'
            wraps_found = False
            for nf in nested_funcs:
                for dec in nf.decorator_list:
                    dec_name = self.get_decorator_name(dec)
                    if "wraps" in dec_name:
                        wraps_found = True
                        break
            self.definitions.append({
                "name": node.name,
                "line": node.lineno,
                "wraps_found": wraps_found,
                "has_wrapper": len(nested_funcs) > 0
            })

        # 2. Check decorators applied to this function
        if node.decorator_list:
            decs = []
            for dec in node.decorator_list:
                name = self.get_decorator_name(dec)
                decs.append(name)
                self.usages[name].append({
                    "target": node.name,
                    "target_type": "function",
                    "line": node.lineno
                })
            self.function_decorators[node.name] = decs

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Async functions can be decorated too
        if node.decorator_list:
            decs = []
            for dec in node.decorator_list:
                name = self.get_decorator_name(dec)
                decs.append(name)
                self.usages[name].append({
                    "target": node.name,
                    "target_type": "async_function",
                    "line": node.lineno
                })
            self.function_decorators[node.name] = decs
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Classes can have class decorators
        if node.decorator_list:
            decs = []
            for dec in node.decorator_list:
                name = self.get_decorator_name(dec)
                decs.append(name)
                self.usages[name].append({
                    "target": node.name,
                    "target_type": "class",
                    "line": node.lineno
                })
            self.function_decorators[node.name] = decs
        self.generic_visit(node)

def analyze_file(filepath: str) -> Tuple[DecoratorVisitor, int]:
    """Parses a file and runs the AST analyzer on it."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
        visitor = DecoratorVisitor(filepath)
        visitor.visit(tree)
        # Return lines count as well
        return visitor, len(code.splitlines())
    except SyntaxError as e:
        print(f"Syntax error parsing {filepath}: {e}", file=sys.stderr)
        return None, 0
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None, 0

def main():
    parser = argparse.ArgumentParser(
        description="Python Decorator Explorer & Analyzer - Scan codebase to map and audit decorator declarations and applications."
    )
    parser.add_argument("path", help="File or directory path to analyze")
    parser.add_argument("--detail", action="store_true", help="Print details of decorated functions and method mappings")
    args = parser.parse_args()

    files_to_analyze = []
    if os.path.isfile(args.path):
        if args.path.endswith(".py"):
            files_to_analyze.append(args.path)
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".py"):
                    files_to_analyze.append(os.path.join(root, file))
    else:
        print(f"Error: Path '{args.path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not files_to_analyze:
        print("No Python files (.py) found to analyze.")
        sys.exit(0)

    print(f"Scanning {len(files_to_analyze)} file(s)...")

    all_usages = defaultdict(list)
    all_definitions = []
    all_fn_decorators = {}
    total_lines = 0

    for fp in files_to_analyze:
        visitor, lines = analyze_file(fp)
        if visitor:
            total_lines += lines
            # Merge usages
            for dec, targets in visitor.usages.items():
                for t in targets:
                    t["file"] = fp
                    all_usages[dec].append(t)
            # Merge definitions
            for df in visitor.definitions:
                df["file"] = fp
                all_definitions.append(df)
            # Merge function/class mapping
            for name, decs in visitor.function_decorators.items():
                all_fn_decorators[f"{os.path.basename(fp)}:{name}"] = decs

    print(f"Analyzed {total_lines} lines of code.")

    # 1. Summary statistics
    print("\n" + "=" * 80)
    print(" DECORATOR ANALYSIS SUMMARY ".center(80, "="))
    print("=" * 80)
    print(f"Total Unique Decorators Found: {len(all_usages)}")
    print(f"Total Decorator Applications:  {sum(len(v) for v in all_usages.values())}")
    print(f"Custom Decorators Defined:     {len(all_definitions)}")

    # 2. Custom decorator best practices audit
    print("\n" + "=" * 80)
    print(" CUSTOM DECORATOR AUDIT ".center(80, "="))
    print("=" * 80)
    if all_definitions:
        warnings_count = 0
        for df in all_definitions:
            status = "PASS"
            warn_str = ""
            if df["has_wrapper"] and not df["wraps_found"]:
                status = "WARN"
                warn_str = " (Lacks @functools.wraps - will lose metadata/docstrings!)"
                warnings_count += 1
            print(f"  [{status}] {df['name']} at {df['file']}:{df['line']}{warn_str}")
        if warnings_count > 0:
            print(f"\n  (!) Found {warnings_count} custom decorator(s) without @functools.wraps protection.")
        else:
            print("\n  All custom decorators are using best practices.")
    else:
        print("  No custom decorators defined in the analyzed files.")

    # 3. Top Decorators by Usage
    print("\n" + "=" * 80)
    print(" MOST FREQUENTLY USED DECORATORS ".center(80, "="))
    print("=" * 80)
    sorted_usages = sorted(all_usages.items(), key=lambda x: len(x[1]), reverse=True)
    for dec, targets in sorted_usages[:15]:
        print(f"  @{dec:<30} | {len(targets):>4} usages")
    if not sorted_usages:
        print("  No decorator usages found.")

    # 4. Detailed mapping if requested
    if args.detail:
        print("\n" + "=" * 80)
        print(" DECORATOR APPLICATION MAP ".center(80, "="))
        print("=" * 80)
        # Group by files
        file_mappings = defaultdict(list)
        for target, decs in all_fn_decorators.items():
            fname, fn = target.split(":", 1)
            file_mappings[fname].append((fn, decs))

        for fname, mappings in file_mappings.items():
            print(f"\nFile: {fname}")
            for fn, decs in mappings:
                stacked_chain = " -> ".join(f"@{d}" for d in decs)
                print(f"  {fn:<30} decorated by: {stacked_chain}")

if __name__ == "__main__":
    main()
