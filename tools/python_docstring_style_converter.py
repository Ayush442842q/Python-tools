#!/usr/bin/env python3
"""
Python Docstring Style Converter
--------------------------------
Converts docstring styles (Google, NumPy, reStructuredText) in Python functions,
classes, and modules using AST analysis and structural text re-formatting.

Author: Antigravity
License: MIT
"""

import sys
import os
import ast
import re
import json
import argparse
from typing import List, Dict, Any, Tuple, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def detect_docstring_style(docstring: str) -> str:
    if not docstring or not docstring.strip():
        return "Unknown"

    if re.search(r'^\s*Parameters\s*\n\s*----------', docstring, re.MULTILINE):
        return "NumPy"
    if re.search(r'^\s*Args:\s*$', docstring, re.MULTILINE) or re.search(r'^\s*Returns:\s*$', docstring, re.MULTILINE):
        return "Google"
    if re.search(r':param\s+\w+:', docstring) or re.search(r':returns?:', docstring):
        return "reST"

    return "Plain"


def convert_rest_to_google(docstring: str) -> str:
    lines = docstring.split("\n")
    new_lines = []
    params = []
    returns = []
    raises = []
    
    in_desc = True

    for line in lines:
        param_match = re.match(r'^\s*:param\s+(\w+):\s*(.*)', line)
        type_match = re.match(r'^\s*:type\s+(\w+):\s*(.*)', line)
        return_match = re.match(r'^\s*:returns?:\s*(.*)', line)
        raises_match = re.match(r'^\s*:raises\s+(\w+):\s*(.*)', line)

        if param_match:
            name, desc = param_match.groups()
            params.append((name, "", desc))
            in_desc = False
        elif return_match:
            ret_desc = return_match.group(1)
            returns.append(ret_desc)
            in_desc = False
        elif raises_match:
            exc, exc_desc = raises_match.groups()
            raises.append((exc, exc_desc))
            in_desc = False
        elif in_desc:
            new_lines.append(line)

    if params:
        new_lines.append("\nArgs:")
        for name, ptype, desc in params:
            type_str = f" ({ptype})" if ptype else ""
            new_lines.append(f"    {name}{type_str}: {desc}")

    if returns:
        new_lines.append("\nReturns:")
        for r in returns:
            new_lines.append(f"    {r}")

    if raises:
        new_lines.append("\nRaises:")
        for exc, desc in raises:
            new_lines.append(f"    {exc}: {desc}")

    return "\n".join(new_lines).strip()


def convert_google_to_rest(docstring: str) -> str:
    lines = docstring.split("\n")
    new_lines = []
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped == "Args:":
            current_section = "Args"
            continue
        elif stripped == "Returns:":
            current_section = "Returns"
            continue
        elif stripped == "Raises:":
            current_section = "Raises"
            continue
        elif stripped and not line.startswith(" ") and not line.startswith("\t"):
            current_section = None

        if current_section == "Args":
            m = re.match(r'^\s*(\w+)(?:\s*\((.*?)\))?:\s*(.*)', line)
            if m:
                name, ptype, desc = m.groups()
                new_lines.append(f":param {name}: {desc}")
                if ptype:
                    new_lines.append(f":type {name}: {ptype}")
                continue
        elif current_section == "Returns":
            if stripped:
                new_lines.append(f":returns: {stripped}")
                continue
        elif current_section == "Raises":
            m = re.match(r'^\s*(\w+):\s*(.*)', line)
            if m:
                exc, desc = m.groups()
                new_lines.append(f":raises {exc}: {desc}")
                continue

        new_lines.append(line)

    return "\n".join(new_lines).strip()


class DocstringAnalyzerVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.docstrings: List[Dict[str, Any]] = []

    def _add_docstring(self, node: ast.AST, name: str, node_type: str):
        doc = ast.get_docstring(node)
        if doc:
            style = detect_docstring_style(doc)
            self.docstrings.append({
                "file": self.filename,
                "name": name,
                "type": node_type,
                "line": getattr(node, "lineno", 1),
                "style": style,
                "docstring": doc
            })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._add_docstring(node, node.name, "Function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._add_docstring(node, node.name, "AsyncFunction")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._add_docstring(node, node.name, "Class")
        self.generic_visit(node)

    def visit_Module(self, node: ast.Module):
        self._add_docstring(node, "module", "Module")
        self.generic_visit(node)


def analyze_file(filepath: str) -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        visitor = DocstringAnalyzerVisitor(filepath)
        visitor.visit(tree)
        return visitor.docstrings
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Python Docstring Style Converter - Analyze and convert Python docstring formats."
    )
    parser.add_argument("target", help="Python file or directory to scan.")
    parser.add_argument("--target-style", choices=["google", "rest"], default="google", help="Target docstring format style.")
    parser.add_argument("--convert", action="store_true", help="Perform docstring conversion in output.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Error: Path '{args.target}' does not exist.{RESET}")
        sys.exit(1)

    items = []
    if os.path.isdir(args.target):
        for root, _, files in os.walk(args.target):
            for f in files:
                if f.endswith(".py"):
                    items.extend(analyze_file(os.path.join(root, f)))
    else:
        items = analyze_file(args.target)

    if args.convert:
        for item in items:
            orig_style = item["style"]
            orig_doc = item["docstring"]
            if args.target_style == "google" and orig_style == "reST":
                item["converted_docstring"] = convert_rest_to_google(orig_doc)
            elif args.target_style == "rest" and orig_style == "Google":
                item["converted_docstring"] = convert_google_to_rest(orig_doc)
            else:
                item["converted_docstring"] = orig_doc

    if args.json:
        print(json.dumps(items, indent=2))
        return

    print(f"{BOLD}{CYAN}=== Python Docstring Style Audit & Converter ==={RESET}")
    print(f"Target: {args.target}")
    print(f"Total Docstrings Found: {len(items)}\n")

    if not items:
        print(f"{YELLOW}[!] No docstrings detected in target.{RESET}")
        return

    style_counts: Dict[str, int] = {}
    for item in items:
        s = item["style"]
        style_counts[s] = style_counts.get(s, 0) + 1

    print(f"{BOLD}Style Breakdown:{RESET}")
    for style, count in style_counts.items():
        print(f"  - {style}: {count}")
    print("-" * 60)

    for item in items[:10]:
        print(f"  {CYAN}{item['type']} '{item['name']}'{RESET} ({item['file']}:{item['line']})")
        print(f"    Detected Style: {BOLD}{item['style']}{RESET}")
        if args.convert and "converted_docstring" in item:
            print(f"    {GREEN}Converted ({args.target_style}):{RESET}")
            for l in item["converted_docstring"].split("\n")[:4]:
                print(f"      {l}")
        print()


if __name__ == "__main__":
    main()
