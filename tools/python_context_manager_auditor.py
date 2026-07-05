#!/usr/bin/env python3
"""
Python Context Manager Auditor

Static analysis tool using Python AST (Abstract Syntax Tree) to detect unclosed
resource leaks (files, sockets, database connections, locks, temporary files)
instantiated outside of 'with' statements or 'try...finally' blocks.

Usage:
    python tools/python_context_manager_auditor.py tools/
    python tools/python_context_manager_auditor.py script.py --json
    python tools/python_context_manager_auditor.py . --ignore-tests
"""

import ast
import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def is_color_enabled() -> bool:
    return sys.stdout.isatty() and os.name != 'nt' or os.getenv('COLORTERM') is not None or os.name == 'nt'


def colorize(text: str, color_code: str) -> str:
    if is_color_enabled():
        return f"{color_code}{text}{COLOR_RESET}"
    return text


# Known resource allocator function / method call patterns
RESOURCE_ALLOCATORS = {
    "open": "File handle opened with open()",
    "socket.socket": "Network socket created with socket.socket()",
    "socket.create_connection": "Network connection opened with socket.create_connection()",
    "sqlite3.connect": "Database connection created with sqlite3.connect()",
    "psycopg2.connect": "PostgreSQL connection opened with psycopg2.connect()",
    "pymysql.connect": "MySQL connection opened with pymysql.connect()",
    "urllib.request.urlopen": "HTTP response stream opened with urlopen()",
    "requests.get": "HTTP request opened without context manager",
    "requests.post": "HTTP request opened without context manager",
    "tempfile.NamedTemporaryFile": "Temporary file created with NamedTemporaryFile()",
    "tempfile.TemporaryDirectory": "Temporary directory created with TemporaryDirectory()",
    "threading.Lock": "Thread lock instantiated",
    "threading.RLock": "Thread re-entrant lock instantiated",
    "threading.Semaphore": "Thread semaphore instantiated",
    "tarfile.open": "Tar archive opened with tarfile.open()",
    "zipfile.ZipFile": "Zip archive opened with zipfile.ZipFile()",
}


def get_func_name(node: ast.AST) -> Optional[str]:
    """Extract string name from call function node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        val = get_func_name(node.value)
        if val:
            return f"{val}.{node.attr}"
        return node.attr
    return None


class ResourceLeakVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, code_lines: List[str]):
        self.filename = filename
        self.code_lines = code_lines
        self.findings: List[Dict[str, Any]] = []
        # Track ancestor nodes (parents)
        self.with_stack: Set[ast.AST] = set()
        self.try_stack: Set[ast.AST] = set()
        self.current_function: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev_func

    def visit_With(self, node: ast.With):
        # Items in 'with' statement are properly managed
        for item in node.items:
            self.with_stack.add(item.context_expr)
        self.generic_visit(node)
        for item in node.items:
            self.with_stack.discard(item.context_expr)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        for item in node.items:
            self.with_stack.add(item.context_expr)
        self.generic_visit(node)
        for item in node.items:
            self.with_stack.discard(item.context_expr)

    def visit_Try(self, node: ast.Try):
        self.try_stack.add(node)
        self.generic_visit(node)
        self.try_stack.discard(node)

    def visit_Call(self, node: ast.Call):
        func_name = get_func_name(node.func)
        if func_name in RESOURCE_ALLOCATORS:
            # Check if this Call node is part of a 'with' context manager
            if node not in self.with_stack:
                # Get code snippet
                line_no = getattr(node, 'lineno', 1)
                snippet = self.code_lines[line_no - 1].strip() if 0 < line_no <= len(self.code_lines) else ""
                
                # Check if inside a try...finally block (less ideal than with, but partially managed)
                in_try_finally = len(self.try_stack) > 0

                # Suggestion snippet
                suggestion = f"with {func_name}(...) as resource:"

                self.findings.append({
                    "filename": self.filename,
                    "line": line_no,
                    "column": getattr(node, 'col_offset', 0),
                    "function": self.current_function or "<module>",
                    "allocator": func_name,
                    "description": RESOURCE_ALLOCATORS[func_name],
                    "in_try_finally": in_try_finally,
                    "snippet": snippet,
                    "suggestion": suggestion
                })

        self.generic_visit(node)


def audit_file(filepath: str) -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()

        tree = ast.parse(content, filename=filepath)
        visitor = ResourceLeakVisitor(filepath, lines)
        visitor.visit(tree)
        return visitor.findings
    except SyntaxError:
        return []
    except Exception:
        return []


def audit_directory(
    target_path: str,
    ignore_tests: bool = False
) -> Dict[str, Any]:
    path = Path(target_path)
    all_findings = []
    files_scanned = 0

    if path.is_file():
        if path.suffix == ".py":
            files_scanned += 1
            all_findings.extend(audit_file(str(path)))
    else:
        for py_file in path.glob("**/*.py"):
            if ignore_tests and ("test_" in py_file.name or "_test.py" in py_file.name or "tests" in py_file.parts):
                continue
            files_scanned += 1
            all_findings.extend(audit_file(str(py_file)))

    return {
        "target_path": str(path.resolve()),
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "findings": all_findings
    }


def print_report(results: Dict[str, Any]):
    print("=" * 72)
    print(colorize("  Python Context Manager & Resource Leak Audit Report", COLOR_BOLD + COLOR_HEADER))
    print("=" * 72)
    print(f"  Target Path:   {results['target_path']}")
    print(f"  Files Scanned: {results['files_scanned']}")
    print(f"  Resource Issues: {results['total_findings']}")
    print("-" * 72)

    if not results["findings"]:
        print(colorize("\n  ✓ No unclosed resource allocations detected! All clean.\n", COLOR_GREEN + COLOR_BOLD))
        print("=" * 72)
        return

    # Group by file
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for item in results["findings"]:
        by_file.setdefault(item["filename"], []).append(item)

    for fname, items in by_file.items():
        rel_fname = os.path.relpath(fname)
        print(f"\n[{colorize('FILE', COLOR_CYAN)}] {colorize(rel_fname, COLOR_BOLD)} ({len(items)} issue{'s' if len(items)>1 else ''}):")
        for issue in items:
            line_str = f"Line {issue['line']}"
            func_str = f"in {issue['function']}()"
            in_try = " (Inside try/finally)" if issue["in_try_finally"] else ""
            print(f"  └─ {colorize(line_str, COLOR_YELLOW)} {func_str}{in_try}:")
            print(f"     Allocated: {colorize(issue['allocator'], COLOR_RED)} - {issue['description']}")
            print(f"     Code:      {colorize(issue['snippet'], COLOR_RESET)}")
            print(f"     Fix:       {colorize(issue['suggestion'], COLOR_GREEN)}")

    print("\n" + "=" * 72)
    print(colorize(f"  Summary: Found {results['total_findings']} resource allocation(s) without 'with' statement.", COLOR_YELLOW))
    print("=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Audit Python code for unclosed files, sockets, database connections, and locks allocated without 'with' context managers."
    )
    parser.add_argument("target", nargs="?", default=".", help="File or directory path to audit (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    parser.add_argument("--ignore-tests", action="store_true", help="Exclude test files and test directories")

    args = parser.parse_args()

    results = audit_directory(args.target, ignore_tests=args.ignore_tests)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["total_findings"] == 0 else 1)


if __name__ == "__main__":
    main()
