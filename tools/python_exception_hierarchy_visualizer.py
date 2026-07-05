#!/usr/bin/env python3
"""Python Exception Hierarchy Visualizer

Parses Python source files using AST to discover custom exception classes,
builds the exception inheritance hierarchy, traces raise statements,
and outputs ASCII, Mermaid, or JSON diagrams.
"""

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


class ExceptionClassInfo:
    def __init__(self, name: str, bases: List[str], file_path: str, line_no: int, doc: Optional[str]):
        self.name = name
        self.bases = bases
        self.file_path = file_path
        self.line_no = line_no
        self.doc = doc
        self.children: List[str] = []
        self.raise_count = 0
        self.raise_locations: List[Tuple[str, int]] = []


class ExceptionVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.classes: Dict[str, ExceptionClassInfo] = {}
        self.raises: List[Tuple[str, int]] = []  # (exception_name, line_no)

    def visit_ClassDef(self, node: ast.ClassDef):
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        doc = ast.get_docstring(node)
        info = ExceptionClassInfo(
            name=node.name,
            bases=base_names,
            file_path=self.file_path,
            line_no=node.lineno,
            doc=doc,
        )
        self.classes[node.name] = info
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        exc_name = "Unknown"
        if node.exc:
            if isinstance(node.exc, ast.Name):
                exc_name = node.exc.id
            elif isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):
                    exc_name = node.exc.func.id
                elif isinstance(node.exc.func, ast.Attribute):
                    exc_name = node.exc.func.attr
            elif isinstance(node.exc, ast.Attribute):
                exc_name = node.exc.attr

        self.raises.append((exc_name, node.lineno))
        self.generic_visit(node)


class ExceptionTreeAnalyzer:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.exceptions: Dict[str, ExceptionClassInfo] = {}
        self.all_raises: Dict[str, List[Tuple[str, int]]] = {}

    def analyze(self):
        py_files = [self.root_path] if self.root_path.is_file() else list(self.root_path.rglob("*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_file))
                visitor = ExceptionVisitor(str(py_file))
                visitor.visit(tree)

                for cls_name, info in visitor.classes.items():
                    self.exceptions[cls_name] = info

                for exc_name, line_no in visitor.raises:
                    if exc_name not in self.all_raises:
                        self.all_raises[exc_name] = []
                    self.all_raises[exc_name].append((str(py_file), line_no))

            except Exception:
                continue

        # Filter classes that inherit from Exception/BaseException or registered custom exception
        known_exceptions = set(self.exceptions.keys())
        known_exceptions.update({"Exception", "BaseException", "RuntimeError", "ValueError", "TypeError", "KeyError"})

        # Map children
        for cls_name, info in list(self.exceptions.items()):
            for b in info.bases:
                if b in self.exceptions:
                    self.exceptions[b].children.append(cls_name)

        # Update raise counts
        for exc_name, locs in self.all_raises.items():
            if exc_name in self.exceptions:
                self.exceptions[exc_name].raise_count = len(locs)
                self.exceptions[exc_name].raise_locations = locs

    def render_ascii(self) -> str:
        lines = []
        # Roots are classes whose bases are not in custom exceptions
        roots = [name for name, info in self.exceptions.items() if not any(b in self.exceptions for b in info.bases)]

        def print_node(name: str, prefix: str = "", is_last: bool = True):
            info = self.exceptions.get(name)
            connector = "└── " if is_last else "├── "
            bases_str = f" ({', '.join(info.bases)})" if info and info.bases else ""
            raises_str = f" [raised {info.raise_count}x]" if info and info.raise_count > 0 else ""
            lines.append(f"{prefix}{connector}{COLOR_BOLD}{COLOR_CYAN}{name}{COLOR_RESET}{COLOR_GREY}{bases_str}{COLOR_RESET}{COLOR_YELLOW}{raises_str}{COLOR_RESET}")

            if info and info.children:
                child_prefix = prefix + ("    " if is_last else "│   ")
                for i, child_name in enumerate(info.children):
                    print_node(child_name, child_prefix, i == len(info.children) - 1)

        for i, root in enumerate(roots):
            print_node(root, "", i == len(roots) - 1)

        return "\n".join(lines)

    def render_mermaid(self) -> str:
        lines = ["classDiagram"]
        for cls_name, info in self.exceptions.items():
            for base in info.bases:
                lines.append(f"    {base} <|-- {cls_name}")
            if info.raise_count > 0:
                lines.append(f"    class {cls_name} {{\n        +raised: {info.raise_count}\n    }}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Discover custom Python exception hierarchies and trace raise locations."
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory path to analyze (default: current directory)")
    parser.add_argument("--format", choices=["ascii", "mermaid", "json"], default="ascii", help="Output format (default: ascii)")

    args = parser.parse_args()
    target_path = Path(args.path).resolve()

    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{target_path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    analyzer = ExceptionTreeAnalyzer(target_path)
    analyzer.analyze()

    if not analyzer.exceptions:
        print(f"{COLOR_YELLOW}No custom exception classes found in '{target_path}'.{COLOR_RESET}")
        return

    print(f"{COLOR_BOLD}{COLOR_BLUE}Python Exception Hierarchy Visualizer{COLOR_RESET}")
    print(f"Target: {COLOR_BOLD}{target_path}{COLOR_RESET}\n")

    if args.format == "ascii":
        print(analyzer.render_ascii())
    elif args.format == "mermaid":
        print(f"```mermaid\n{analyzer.render_mermaid()}\n```")
    elif args.format == "json":
        data = {
            name: {
                "bases": info.bases,
                "file": info.file_path,
                "line": info.line_no,
                "children": info.children,
                "raise_count": info.raise_count,
            }
            for name, info in analyzer.exceptions.items()
        }
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
