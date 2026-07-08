#!/usr/bin/env python3
"""
Python Mutable Default Arguments Linter
Static AST-based analysis tool to scan Python codebases for mutable default arguments
(such as lists, dictionaries, sets, or function calls) in function and method definitions.
"""

import argparse
import ast
import os
import sys
from typing import Dict, List, NamedTuple, Set, Tuple


class LinterViolation(NamedTuple):
    file_path: str
    line: int
    col: int
    func_name: str
    param_name: str
    expression: str
    issue_type: str  # 'list', 'dict', 'set', 'call', etc.


class MutableDefaultsVisitor(ast.NodeVisitor):
    """AST visitor to find mutable default values in function definitions."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.violations: List[LinterViolation] = []

    def check_default(self, node: ast.AST) -> Tuple[bool, str, str]:
        """
        Check if a default value node is mutable.
        Returns (is_mutable, expression_str, type_str).
        """
        if isinstance(node, ast.List):
            return True, "[]", "list literal"
        elif isinstance(node, ast.Dict):
            return True, "{}", "dict literal"
        elif isinstance(node, ast.Set):
            return True, "set()", "set literal"
        elif isinstance(node, ast.ListComp):
            return True, "[...]", "list comprehension"
        elif isinstance(node, ast.DictComp):
            return True, "{...}", "dict comprehension"
        elif isinstance(node, ast.SetComp):
            return True, "{...}", "set comprehension"
        elif isinstance(node, ast.Call):
            # Check for list(), dict(), set()
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            expr_str = f"{func_name}()" if func_name else "function_call()"
            
            # Treat common collection calls as mutable
            if func_name in ("list", "dict", "set"):
                return True, expr_str, f"mutable built-in call ({func_name})"
            
            # General function/method call defaults are also mutable/evaluated once
            return True, expr_str, "function call (evaluated once at definition time)"

        return False, "", ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function_node(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function_node(node)
        self.generic_visit(node)

    def _check_function_node(self, node: ast.AST):
        # Python stores defaults for positional-or-keyword arguments in node.args.defaults
        # and keyword-only arguments defaults in node.args.kw_defaults.
        # positional-or-keyword defaults are mapped to the end of the argument list:
        # e.g., if there are 3 args and 2 defaults, the defaults correspond to the last 2 args.
        
        args = node.args
        func_name = getattr(node, "name", "<unknown>")
        
        # 1. Positional-or-keyword defaults
        if args.defaults:
            # Match arguments to their defaults from the right
            num_args_with_defaults = len(args.defaults)
            args_with_defaults = args.args[-num_args_with_defaults:]
            
            for arg, default_node in zip(args_with_defaults, args.defaults):
                if default_node:
                    is_mutable, expr, issue_type = self.check_default(default_node)
                    if is_mutable:
                        self.violations.append(LinterViolation(
                            file_path=self.file_path,
                            line=default_node.lineno,
                            col=default_node.col_offset,
                            func_name=func_name,
                            param_name=arg.arg,
                            expression=expr,
                            issue_type=issue_type
                        ))
        
        # 2. Keyword-only defaults
        if args.kwonlyargs and args.kw_defaults:
            for arg, default_node in zip(args.kwonlyargs, args.kw_defaults):
                if default_node:
                    is_mutable, expr, issue_type = self.check_default(default_node)
                    if is_mutable:
                        self.violations.append(LinterViolation(
                            file_path=self.file_path,
                            line=default_node.lineno,
                            col=default_node.col_offset,
                            func_name=func_name,
                            param_name=arg.arg,
                            expression=expr,
                            issue_type=issue_type
                        ))


def audit_file(file_path: str) -> List[LinterViolation]:
    """Parses and audits a single Python file for mutable defaults."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=file_path)
        visitor = MutableDefaultsVisitor(file_path)
        visitor.visit(tree)
        return visitor.violations
    except SyntaxError as e:
        # Gracefully handle file syntax errors during auditing
        print(f"[-] Syntax error parsing {file_path}: Line {e.lineno}: {e.msg}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[-] Error reading {file_path}: {e}", file=sys.stderr)
        return []


def run_linter(targets: List[str], exclude_dirs: Set[str] = None) -> List[LinterViolation]:
    """Recursively audits targets and aggregates violations."""
    if exclude_dirs is None:
        exclude_dirs = {".git", "__pycache__", "venv", ".venv", ".mypy_cache", ".pytest_cache"}
        
    all_violations = []
    
    for target in targets:
        if os.path.isfile(target):
            if target.endswith(".py"):
                all_violations.extend(audit_file(target))
        elif os.path.isdir(target):
            for root, dirs, files in os.walk(target):
                # Filter out excluded directories in-place to prune walk
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file.endswith(".py"):
                        full_path = os.path.join(root, file)
                        all_violations.extend(audit_file(full_path))
                        
    return all_violations


def main():
    parser = argparse.ArgumentParser(
        description="Python Mutable Default Arguments Linter. Statically audits codebases to detect list, "
                    "dict, set, or function call expressions defined as parameter defaults."
    )
    parser.add_argument("targets", nargs="+", help="Python files or directories to scan")
    parser.add_argument("--exclude", metavar="DIR", action="append", help="Directories to exclude from scan")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print debug/verbose details")
    
    args = parser.parse_args()
    
    exclude_dirs = {".git", "__pycache__", "venv", ".venv", ".mypy_cache"}
    if args.exclude:
        exclude_dirs.update(args.exclude)
        
    if args.verbose:
        print(f"[*] Starting audit of targets: {args.targets}")
        print(f"[*] Excluding directories: {exclude_dirs}")
        
    violations = run_linter(args.targets, exclude_dirs)
    
    # Sort violations chronologically by file and line
    violations.sort(key=lambda x: (x.file_path, x.line, x.col))
    
    if not violations:
        print("[+] Success: No mutable default arguments found.")
        sys.exit(0)
        
    print(f"[-] Found {len(violations)} mutable default argument violations:")
    print("-" * 80)
    
    for v in violations:
        rel_path = os.path.relpath(v.file_path) if os.path.isabs(v.file_path) else v.file_path
        print(f"{rel_path}:{v.line}:{v.col}: in function '{v.func_name}'")
        print(f"    Parameter '{v.param_name}' has mutable default: {v.expression} ({v.issue_type})")
        print(f"    Fix: Change parameter default to None and initialize inside the function:")
        print(f"        def {v.func_name}(..., {v.param_name}=None):")
        print(f"            if {v.param_name} is None:")
        print(f"                {v.param_name} = {v.expression if not v.expression.startswith('function') else '...'}")
        print("-" * 80)
        
    sys.exit(1)


if __name__ == "__main__":
    main()
