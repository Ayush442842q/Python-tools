#!/usr/bin/env python3
"""Dependency Analyzer Tool

This tool analyses a Python file or package and lists its top-level import dependencies.
Usage example:
  python tools/dependency_analyzer.py path/to/module.py
"""

import argparse
import ast
import sys
from pathlib import Path


def find_dependencies(source_path: Path):
    """Parse the file and return a set of imported module names."""
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
    return imports


def main():
    parser = argparse.ArgumentParser(description="Analyze Python file imports.")
    parser.add_argument("path", help="Path to Python file or directory.")
    args = parser.parse_args()
    src = Path(args.path)
    if not src.exists():
        parser.error("File or directory does not exist.")
    all_imports = set()
    if src.is_file():
        all_imports.update(find_dependencies(src))
    else:
        for p in src.rglob("*.py"):
            all_imports.update(find_dependencies(p))
    if not all_imports:
        print("No imports found.")
    else:
        print("Imports:")
        for m in sorted(all_imports):
            print(f"- {m}")

if __name__ == "__main__":
    main()

