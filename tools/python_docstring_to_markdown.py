#!/usr/bin/env python3
"""
Python Docstring to Markdown Documentation Generator

Statically extracts docstrings, type annotations, and signatures from Python source files 
using AST (Abstract Syntax Trees) and formats them into clean, structured Markdown API docs.

Features:
- AST parsing: Safe and fast, no code execution required
- Module overview and docstring extraction
- Class documentation with inheritance, method signatures, and class docstrings
- Standalone function documentation with parameter lists and return type annotations
- Interactive Table of Contents generation
- Directory recursive mode to generate docs for entire packages
- Optional inclusion/exclusion of private methods (__name__ or _name)

Usage:
    python python_docstring_to_markdown.py script.py -o API_DOCS.md
    python python_docstring_to_markdown.py ./my_package --out-dir ./docs/
"""

import os
import sys
import ast
import argparse
from typing import List, Dict, Any, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"


def format_ast_expr(node: Optional[ast.AST]) -> str:
    """Helper to convert AST expression nodes back to code string."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def get_docstring(node: ast.AST) -> str:
    """Extracts raw docstring from an AST node."""
    doc = ast.get_docstring(node)
    return doc.strip() if doc else ""


def format_args(args_node: ast.arguments) -> str:
    """Formats function arguments and annotations into signature string."""
    params = []
    
    # Positional args
    for arg in args_node.args:
        p = arg.arg
        if arg.annotation:
            ann = format_ast_expr(arg.annotation)
            p += f": {ann}"
        params.append(p)
        
    # *args
    if args_node.vararg:
        v = f"*{args_node.vararg.arg}"
        if args_node.vararg.annotation:
            v += f": {format_ast_expr(args_node.vararg.annotation)}"
        params.append(v)
        
    # **kwargs
    if args_node.kwarg:
        k = f"**{args_node.kwarg.arg}"
        if args_node.kwarg.annotation:
            k += f": {format_ast_expr(args_node.kwarg.annotation)}"
        params.append(k)

    return ", ".join(params)


class PythonDocExtractor(ast.NodeVisitor):
    """AST Visitor to extract classes, functions, and docstrings from Python AST."""

    def __init__(self, include_private: bool = False):
        self.include_private = include_private
        self.module_doc: str = ""
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []

    def visit_Module(self, node: ast.Module):
        self.module_doc = get_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.include_private and node.name.startswith("_") and not node.name.startswith("__"):
            return

        bases = [format_ast_expr(b) for b in node.bases]
        methods = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self.include_private and item.name.startswith("_") and item.name != "__init__":
                    continue

                sig_args = format_args(item.args)
                returns = format_ast_expr(item.returns) if item.returns else ""
                
                methods.append({
                    "name": item.name,
                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                    "args": sig_args,
                    "returns": returns,
                    "docstring": get_docstring(item)
                })

        self.classes.append({
            "name": node.name,
            "bases": bases,
            "docstring": get_docstring(node),
            "methods": methods
        })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Only top-level functions (parent is Module)
        self._visit_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_func(node, is_async=True)

    def _visit_func(self, node: Any, is_async: bool):
        if not self.include_private and node.name.startswith("_"):
            return
            
        sig_args = format_args(node.args)
        returns = format_ast_expr(node.returns) if node.returns else ""

        self.functions.append({
            "name": node.name,
            "is_async": is_async,
            "args": sig_args,
            "returns": returns,
            "docstring": get_docstring(node)
        })


def generate_markdown_doc(filename: str, source_code: str, include_private: bool = False) -> str:
    """Parses Python source code and builds Markdown documentation."""
    try:
        tree = ast.parse(source_code, filename=filename)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in {filename}: {e}")

    extractor = PythonDocExtractor(include_private=include_private)
    
    # We only want top-level functions in extractor.functions
    # So we visit top-level nodes manually
    extractor.module_doc = get_docstring(tree)
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            extractor.visit_ClassDef(stmt)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(stmt, ast.FunctionDef):
                extractor.visit_FunctionDef(stmt)
            else:
                extractor.visit_AsyncFunctionDef(stmt)

    mod_name = os.path.basename(filename)
    lines = [f"# Module `{mod_name}`\n"]

    if extractor.module_doc:
        lines.append(f"{extractor.module_doc}\n")

    # Table of Contents
    lines.append("## Table of Contents\n")
    if extractor.classes:
        lines.append("- **Classes**")
        for cls in extractor.classes:
            lines.append(f"  - [{cls['name']}](#class-{cls['name'].lower()})")
    if extractor.functions:
        lines.append("- **Functions**")
        for fn in extractor.functions:
            lines.append(f"  - [{fn['name']}](#function-{fn['name'].lower()})")
    lines.append("")

    # Classes
    if extractor.classes:
        lines.append("---")
        lines.append("## Classes\n")
        for cls in extractor.classes:
            bases_str = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
            lines.append(f"### Class `<a id=\"class-{cls['name'].lower()}\"></a>{cls['name']}{bases_str}`\n")
            if cls["docstring"]:
                lines.append(f"{cls['docstring']}\n")

            if cls["methods"]:
                lines.append("#### Methods\n")
                for m in cls["methods"]:
                    async_prefix = "async " if m["is_async"] else ""
                    ret_str = f" -> {m['returns']}" if m["returns"] else ""
                    lines.append(f"```python\n{async_prefix}{m['name']}({m['args']}){ret_str}\n```")
                    if m["docstring"]:
                        lines.append(f"{m['docstring']}\n")
                    lines.append("")

    # Functions
    if extractor.functions:
        lines.append("---")
        lines.append("## Functions\n")
        for fn in extractor.functions:
            async_prefix = "async " if fn["is_async"] else ""
            ret_str = f" -> {fn['returns']}" if fn["returns"] else ""
            lines.append(f"### Function `<a id=\"function-{fn['name'].lower()}\"></a>{fn['name']}`\n")
            lines.append(f"```python\n{async_prefix}{fn['name']}({fn['args']}){ret_str}\n```")
            if fn["docstring"]:
                lines.append(f"\n{fn['docstring']}\n")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Python Docstring to Markdown Documentation Generator"
    )
    parser.add_argument("target", help="Path to Python file (.py) or package directory")
    parser.add_argument("--output", "-o", help="Path to save output Markdown file")
    parser.add_argument("--out-dir", help="Output directory when scanning packages/folders")
    parser.add_argument(
        "--include-private", action="store_true",
        help="Include private classes and methods starting with '_'"
    )

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Target path does not exist: {args.target}{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        if os.path.isfile(args.target):
            with open(args.target, "r", encoding="utf-8") as f:
                content = f.read()

            md_doc = generate_markdown_doc(
                filename=args.target,
                source_code=content,
                include_private=args.include_private
            )

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f_out:
                    f_out.write(md_doc + "\n")
                print(f"{GREEN}Documentation generated and saved to: {args.output}{RESET}")
            else:
                print(f"\n{BOLD}{CYAN}=== Generated Markdown Output ==={RESET}\n")
                print(md_doc)

        elif os.path.isdir(args.target):
            out_dir = args.out_dir or "docs"
            os.makedirs(out_dir, exist_ok=True)
            count = 0

            for root, _, files in os.walk(args.target):
                for file in files:
                    if file.endswith(".py") and not file.startswith("."):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, args.target)
                        doc_filename = rel_path.replace(os.sep, "_").replace(".py", ".md")
                        out_path = os.path.join(out_dir, doc_filename)

                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        try:
                            md_doc = generate_markdown_doc(
                                filename=file_path,
                                source_code=content,
                                include_private=args.include_private
                            )
                            with open(out_path, "w", encoding="utf-8") as f_out:
                                f_out.write(md_doc + "\n")
                            count += 1
                        except Exception as err:
                            print(f"{YELLOW}Skipped {file_path}: {err}{RESET}")

            print(f"{GREEN}Successfully generated {count} Markdown documentation files in '{out_dir}'{RESET}")

    except Exception as e:
        print(f"{RED}Error generating documentation: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
