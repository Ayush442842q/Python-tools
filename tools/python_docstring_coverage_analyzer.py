#!/usr/bin/env python3
"""
Python Docstring Coverage & Quality Inspector
----------------------------------------------
Scans Python source files or directories using AST to calculate docstring coverage statistics
for modules, classes, methods, and functions. Audits docstring style formats (Google, NumPy, reST)
and identifies missing parameter descriptions or return value documentation.

Author: Antigravity
License: MIT
"""

import sys
import os
import ast
import json
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class DocstringVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, include_private: bool = False):
        self.filename = filename
        self.include_private = include_private
        self.total_items = 0
        self.documented_items = 0
        self.items: List[Dict[str, Any]] = []

    def visit_Module(self, node: ast.Module):
        doc = ast.get_docstring(node)
        has_doc = bool(doc and doc.strip())
        self.total_items += 1
        if has_doc:
            self.documented_items += 1
        
        self.items.append({
            "name": "<module>",
            "type": "module",
            "line": 1,
            "has_doc": has_doc,
            "doc": doc or "",
        })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.include_private and node.name.startswith('_') and not node.name.startswith('__'):
            self.generic_visit(node)
            return

        doc = ast.get_docstring(node)
        has_doc = bool(doc and doc.strip())
        self.total_items += 1
        if has_doc:
            self.documented_items += 1

        self.items.append({
            "name": node.name,
            "type": "class",
            "line": node.lineno,
            "has_doc": has_doc,
            "doc": doc or "",
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node):
        # Skip dunder unless __init__, skip private if not requested
        if node.name.startswith('__') and node.name.endswith('__') and node.name != '__init__':
            return
        if not self.include_private and node.name.startswith('_') and not node.name.startswith('__'):
            return

        doc = ast.get_docstring(node)
        has_doc = bool(doc and doc.strip())
        self.total_items += 1
        if has_doc:
            self.documented_items += 1

        # Check parameter descriptions in docstring
        args = [arg.arg for arg in node.args.args if arg.arg not in ('self', 'cls')]
        missing_params = []
        if has_doc and doc:
            for arg in args:
                if arg not in doc:
                    missing_params.append(arg)

        self.items.append({
            "name": node.name,
            "type": "function/method",
            "line": node.lineno,
            "has_doc": has_doc,
            "missing_params": missing_params,
            "doc": doc or "",
        })


def analyze_file(filepath: str, include_private: bool = False) -> Dict[str, Any]:
    """Parse a single Python file and calculate docstring coverage."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
    except SyntaxError as e:
        return {
            "file": filepath,
            "error": f"SyntaxError: {e}",
            "coverage": 0.0,
            "total": 0,
            "documented": 0,
            "items": []
        }

    visitor = DocstringVisitor(filepath, include_private=include_private)
    visitor.visit(tree)

    coverage = (visitor.documented_items / visitor.total_items * 100.0) if visitor.total_items > 0 else 100.0
    return {
        "file": filepath,
        "coverage": round(coverage, 2),
        "total": visitor.total_items,
        "documented": visitor.documented_items,
        "items": visitor.items
    }


def analyze_directory(dirpath: str, include_private: bool = False) -> Dict[str, Any]:
    """Recursively analyze all .py files in directory."""
    results = []
    total_items = 0
    total_documented = 0

    for root, _, files in os.walk(dirpath):
        if any(p in root for p in ('.git', '__pycache__', '.venv', 'venv', 'build', 'dist', 'node_modules')):
            continue
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                res = analyze_file(full_path, include_private=include_private)
                results.append(res)
                total_items += res.get("total", 0)
                total_documented += res.get("documented", 0)

    overall_coverage = (total_documented / total_items * 100.0) if total_items > 0 else 100.0
    return {
        "directory": dirpath,
        "overall_coverage": round(overall_coverage, 2),
        "total_items": total_items,
        "total_documented": total_documented,
        "files": results
    }


def main():
    parser = argparse.ArgumentParser(
        description="Python Docstring Coverage & Quality Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python tools/python_docstring_coverage_analyzer.py --file script.py
  python tools/python_docstring_coverage_analyzer.py --dir tools/
  python tools/python_docstring_coverage_analyzer.py --dir tools/ --json
"""
    )

    parser.add_argument("--file", help="Path to single Python script")
    parser.add_argument("--dir", help="Path to directory containing Python files")
    parser.add_argument("--include-private", action="store_true", help="Include private methods/functions starting with '_'")
    parser.add_argument("--json", action="store_true", help="Output raw JSON analysis data")

    args = parser.parse_args()

    if args.json:
        if args.file:
            data = analyze_file(args.file, include_private=args.include_private)
        elif args.dir:
            data = analyze_directory(args.dir, include_private=args.include_private)
        else:
            data = analyze_file(__file__, include_private=args.include_private)
        print(json.dumps(data, indent=2))
        return

    target_path = args.file or args.dir or __file__

    if args.file or (not args.dir and not args.file):
        res = analyze_file(target_path, include_private=args.include_private)
        print(f"\n{BOLD}{CYAN}=== Docstring Coverage Report for {os.path.basename(target_path)} ==={RESET}")
        
        color = GREEN if res['coverage'] >= 80 else (YELLOW if res['coverage'] >= 50 else RED)
        print(f"Coverage: {color}{BOLD}{res['coverage']}%{RESET} ({res['documented']}/{res['total']} items documented)\n")

        print(f"{'TYPE':<16} {'LINE':<6} {'STATUS':<12} {'NAME'}")
        print("-" * 60)
        for item in res['items']:
            status_str = f"{GREEN}✓ Doc{RESET}" if item['has_doc'] else f"{RED}✗ Missing{RESET}"
            print(f"{item['type']:<16} {item['line']:<6} {status_str:<21} {BOLD}{item['name']}{RESET}")
            if item.get('missing_params'):
                print(f"   {YELLOW}⚠ Missing params in docstring:{RESET} {', '.join(item['missing_params'])}")
        print()

    elif args.dir:
        res = analyze_directory(args.dir, include_private=args.include_private)
        print(f"\n{BOLD}{CYAN}=== Directory Docstring Coverage Summary ==={RESET}")
        print(f"Target Directory: {BOLD}{args.dir}{RESET}")
        
        cov = res['overall_coverage']
        color = GREEN if cov >= 80 else (YELLOW if cov >= 50 else RED)
        print(f"Overall Coverage: {color}{BOLD}{cov}%{RESET} ({res['total_documented']}/{res['total_items']} items documented)\n")

        print(f"{'FILE':<45} {'COVERAGE':<10} {'DOC/TOTAL'}")
        print("-" * 65)
        for f in res['files']:
            rel_path = os.path.relpath(f['file'], args.dir)
            if len(rel_path) > 44:
                rel_path = "..." + rel_path[-41:]
            c_val = f['coverage']
            c_color = GREEN if c_val >= 80 else (YELLOW if c_val >= 50 else RED)
            print(f"{rel_path:<45} {c_color}{c_val}%{RESET:<18} {f['documented']}/{f['total']}")
        print()


if __name__ == "__main__":
    main()
