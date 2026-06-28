#!/usr/bin/env python3
"""
Python Dead Code Finder - Scan codebases for unused classes, functions, and global variables

This tool recursively analyzes Python files in a directory using the AST (Abstract
Syntax Tree) module. It identifies definitions (functions, classes, global constants/variables)
and tracks references to them across the codebase to report potential dead/unused code.

Usage:
    python tools/python_dead_code_finder.py [DIRECTORY] [--exclude EXCLUDE] [--ignore-prefix PREFIX]

Example:
    python tools/python_dead_code_finder.py . --exclude venv,tests
"""

import argparse
import ast
import os
import sys
from typing import Set, Dict, List, Tuple

class CodebaseAnalyzer:
    def __init__(self, root_dir: str, excludes: List[str], ignore_prefixes: List[str]):
        self.root_dir = os.path.abspath(root_dir)
        self.excludes = [os.path.normpath(os.path.join(self.root_dir, e.strip())) for e in excludes if e.strip()]
        self.ignore_prefixes = ignore_prefixes
        
        # Maps definition key (file_path, name, type, line_no) -> reference count
        self.definitions: Dict[Tuple[str, str, str, int], int] = {}
        # Set of all names referenced anywhere in the codebase
        self.referenced_names: Set[str] = set()
        # Track imported names
        self.imports: Dict[str, Set[str]] = {}

    def is_excluded(self, path: str) -> bool:
        norm_path = os.path.normpath(path)
        for exclude in self.excludes:
            if norm_path == exclude or norm_path.startswith(exclude + os.sep):
                return True
        # Always exclude common directories
        base = os.path.basename(path)
        if base in ('.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', '.pytest_cache', '.mypy_cache'):
            return True
        return False

    def scan(self):
        py_files = []
        for root, dirs, files in os.walk(self.root_dir):
            # Prune directories in-place for os.walk
            dirs[:] = [d for d in dirs if not self.is_excluded(os.path.join(root, d))]
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    if not self.is_excluded(file_path):
                        py_files.append(file_path)

        # First pass: collect all definitions and general references
        for file_path in py_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                tree = ast.parse(content, filename=file_path)
                self._analyze_file_ast(file_path, tree)
            except SyntaxError as e:
                print(f"Syntax Error in {file_path}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error reading {file_path}: {e}", file=sys.stderr)

    def _analyze_file_ast(self, file_path: str, tree: ast.AST):
        rel_path = os.path.relpath(file_path, self.root_dir)
        
        # Track defined names in this file to avoid false positives from self-references
        local_definitions = []

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self, analyzer: 'CodebaseAnalyzer'):
                self.analyzer = analyzer
                self.in_function = False

            def visit_FunctionDef(self, node: ast.FunctionDef):
                # Don't track private or special methods (like __init__) or test functions
                if not self.should_ignore(node.name):
                    local_definitions.append((rel_path, node.name, 'Function', node.lineno))
                
                # Check decorators
                for dec in node.decorator_list:
                    self.analyzer._record_node_references(dec)
                
                # Visit arguments defaults and annotations
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation:
                        self.analyzer._record_node_references(arg.annotation)
                for default in node.args.defaults + node.args.kw_defaults:
                    if default:
                        self.analyzer._record_node_references(default)

                # Traverse body
                old_in_func = self.in_function
                self.in_function = True
                for stmt in node.body:
                    self.visit(stmt)
                self.in_function = old_in_func

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self.visit_FunctionDef(node)  # Treat async functions similarly

            def visit_ClassDef(self, node: ast.ClassDef):
                if not self.should_ignore(node.name):
                    local_definitions.append((rel_path, node.name, 'Class', node.lineno))

                # Visit base classes and decorators
                for base in node.bases:
                    self.analyzer._record_node_references(base)
                for dec in node.decorator_list:
                    self.analyzer._record_node_references(dec)

                # Traverse body
                for stmt in node.body:
                    self.visit(stmt)

            def visit_Assign(self, node: ast.Assign):
                # Check for global variables/constants (defined outside functions/classes)
                if not self.in_function:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if not self.should_ignore(target.id):
                                local_definitions.append((rel_path, target.id, 'Global Variable', target.lineno))
                self.analyzer._record_node_references(node.value)

            def visit_Name(self, node: ast.Name):
                if isinstance(node.ctx, ast.Load):
                    self.analyzer.referenced_names.add(node.id)

            def visit_Import(self, node: ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split('.')[0]
                    self.analyzer.referenced_names.add(name)

            def visit_ImportFrom(self, node: ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    self.analyzer.referenced_names.add(name)

            def should_ignore(self, name: str) -> bool:
                for prefix in self.analyzer.ignore_prefixes:
                    if name.startswith(prefix):
                        return True
                return name.startswith('__') and name.endswith('__')

        visitor = ASTVisitor(self)
        visitor.visit(tree)

        # Register local definitions
        for def_key in local_definitions:
            self.definitions[def_key] = 0

    def _record_node_references(self, node: ast.AST):
        if not node:
            return
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Name):
                self.referenced_names.add(subnode.id)

    def report(self) -> int:
        unused = []
        for (rel_path, name, def_type, lineno) in self.definitions.keys():
            # If the name is never referenced anywhere in the codebase
            if name not in self.referenced_names:
                # Also ignore entry point functions (like main) if they are in scripts
                if name == 'main' and (rel_path.endswith('main.py') or 'tools' in rel_path):
                    continue
                unused.append((rel_path, name, def_type, lineno))

        if not unused:
            print("\u2705 No dead code detected! All scanned definitions are referenced.")
            return 0

        print(f"\u26A0\ufe0f Found {len(unused)} potentially unused definitions:")
        print(f"{'-' * 80}")
        print(f"{'File Path':<40} | {'Line':<5} | {'Type':<15} | {'Unused Name'}")
        print(f"{'-' * 80}")
        
        # Sort by file path, then line number
        for rel_path, name, def_type, lineno in sorted(unused, key=lambda x: (x[0], x[3])):
            print(f"{rel_path:<40} | {lineno:<5} | {def_type:<15} | {name}")
            
        print(f"{'-' * 80}")
        print("Note: False positives can occur if names are accessed dynamically via getattr(), ")
        print("eval(), or if they are entry points/APIs called by external integrations.")
        return len(unused)

def main():
    parser = argparse.ArgumentParser(
        description="Scan Python source files recursively and find unused declarations (dead code)."
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Root directory to scan (default: current directory)'
    )
    parser.add_argument(
        '--exclude',
        default='',
        help='Comma-separated list of directories/files to exclude from analysis'
    )
    parser.add_argument(
        '--ignore-prefix',
        default='test_,_,unused_',
        help='Comma-separated list of name prefixes to ignore'
    )

    args = parser.parse_args()

    excludes = [x.strip() for x in args.exclude.split(',') if x.strip()]
    ignore_prefixes = [x.strip() for x in args.ignore_prefix.split(',') if x.strip()]

    print(f"Scanning directory: {args.directory}")
    print(f"Excluding: {excludes + ['.git', 'venv', '__pycache__']}")
    print(f"Ignoring names starting with: {ignore_prefixes}")
    print()

    analyzer = CodebaseAnalyzer(args.directory, excludes, ignore_prefixes)
    analyzer.scan()
    count = analyzer.report()
    
    return 1 if count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
