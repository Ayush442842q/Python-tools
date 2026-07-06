#!/usr/bin/env python3
"""
Python Doctest Coverage Analyzer & Test Runner
------------------------------------------------
AST-based static analyzer that scans Python source files for module, class, and function
docstrings, detects embedded doctest blocks (>>>), calculates doctest coverage metrics,
and executes doctests using standard doctest module with rich execution reporting.

Author: Antigravity
License: MIT
"""

import sys
import os
import ast
import doctest
import importlib.util
import json
import argparse
from typing import List, Dict, Any, Optional

# Ensure stdout handles UTF-8 on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class DoctestVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.items: List[Dict[str, Any]] = []

    def _check_docstring(self, name: str, item_type: str, lineno: int, docstring: Optional[str]):
        has_docstring = docstring is not None and len(docstring.strip()) > 0
        has_doctest = False
        doctest_count = 0
        
        if has_docstring and docstring:
            lines = docstring.splitlines()
            doctest_lines = [l for l in lines if l.strip().startswith(">>>")]
            doctest_count = len(doctest_lines)
            has_doctest = doctest_count > 0

        self.items.append({
            "name": name,
            "type": item_type,
            "line": lineno,
            "has_docstring": has_docstring,
            "has_doctest": has_doctest,
            "doctest_count": doctest_count
        })

    def visit_Module(self, node: ast.Module):
        docstring = ast.get_docstring(node)
        self._check_docstring("<module>", "module", 1, docstring)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        docstring = ast.get_docstring(node)
        self._check_docstring(node.name, "class", node.lineno, docstring)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        docstring = ast.get_docstring(node)
        if not (node.name.startswith("__") and node.name.endswith("__")) or node.name == "__init__":
            self._check_docstring(node.name, "function", node.lineno, docstring)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        docstring = ast.get_docstring(node)
        self._check_docstring(node.name, "async_function", node.lineno, docstring)
        self.generic_visit(node)


def analyze_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Analyze a single Python file for doctest presence and AST structure."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
    except Exception as e:
        return {"file": filepath, "error": str(e)}

    visitor = DoctestVisitor(filepath)
    visitor.visit(tree)

    items = visitor.items
    total_items = len(items)
    with_docstrings = sum(1 for i in items if i["has_docstring"])
    with_doctests = sum(1 for i in items if i["has_doctest"])
    total_doctest_lines = sum(i["doctest_count"] for i in items)

    coverage_pct = round((with_doctests / total_items * 100), 1) if total_items > 0 else 0.0

    return {
        "file": filepath,
        "total_items": total_items,
        "with_docstrings": with_docstrings,
        "with_doctests": with_doctests,
        "total_doctest_lines": total_doctest_lines,
        "coverage_pct": coverage_pct,
        "items": items
    }


def run_file_doctests(filepath: str) -> Dict[str, Any]:
    """Execute doctests in a Python file and report pass/fail status."""
    module_name = f"__doctest_mod_{abs(hash(filepath))}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return {"file": filepath, "executed": False, "error": "Cannot load module spec"}
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        
        finder = doctest.DocTestFinder()
        runner = doctest.DocTestRunner(verbose=False)
        tests = finder.find(mod, filepath)
        
        failures, tests_run = 0, 0
        for test in tests:
            if test.examples:
                f, t = runner.run(test)
                failures += f
                tests_run += t

        return {
            "file": filepath,
            "executed": True,
            "tests_run": tests_run,
            "failures": failures,
            "passes": tests_run - failures
        }
    except Exception as e:
        return {"file": filepath, "executed": False, "error": str(e)}
    finally:
        if module_name in sys.modules:
            del sys.modules[module_name]


DEMO_PYTHON_CODE = '''
def add(a: int, b: int) -> int:
    """Add two numbers together.

    >>> add(2, 3)
    5
    >>> add(-1, 1)
    0
    """
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers.

    >>> multiply(3, 4)
    12
    """
    return a * b


def helper_function():
    """A helper function with no doctest."""
    pass
'''


def main():
    parser = argparse.ArgumentParser(description="Python Doctest Coverage Analyzer & Test Runner")
    parser.add_argument("path", nargs="?", help="Python file or directory to scan")
    parser.add_argument("--run-tests", action="store_true", help="Execute discovered doctests and output pass/fail statistics")
    parser.add_argument("--min-coverage", type=float, default=0.0, help="Required minimum doctest coverage percentage (0-100)")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output report format")
    parser.add_argument("--output", help="Write output report to file")
    parser.add_argument("--demo", action="store_true", help="Run demo scan on synthetic Python code")

    args = parser.parse_args()

    if args.demo:
        print(f"{BOLD}{CYAN}=== Running Python Doctest Coverage Analyzer Demo ==={RESET}\n")
        demo_file = "_demo_doctest_sample.py"
        with open(demo_file, "w", encoding="utf-8") as f:
            f.write(DEMO_PYTHON_CODE)
        target_files = [demo_file]
    elif args.path:
        if os.path.isfile(args.path):
            target_files = [args.path]
        elif os.path.isdir(args.path):
            target_files = []
            for root, _, files in os.walk(args.path):
                for file in files:
                    if file.endswith(".py"):
                        target_files.append(os.path.join(root, file))
        else:
            print(f"{RED}Error: Path '{args.path}' not found.{RESET}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

    analyzed_files = []
    total_targets = 0
    total_with_doctests = 0
    total_doctest_lines = 0

    for tf in target_files:
        res = analyze_file(tf)
        if res and "error" not in res:
            analyzed_files.append(res)
            total_targets += res["total_items"]
            total_with_doctests += res["with_doctests"]
            total_doctest_lines += res["total_doctest_lines"]

    overall_coverage = round((total_with_doctests / total_targets * 100), 1) if total_targets > 0 else 0.0

    test_execution_results = []
    if args.run_tests:
        for tf in target_files:
            tr = run_file_doctests(tf)
            test_execution_results.append(tr)

    # Cleanup demo file if created
    if args.demo and os.path.exists("_demo_doctest_sample.py"):
        os.remove("_demo_doctest_sample.py")

    report_data = {
        "files_scanned": len(analyzed_files),
        "total_symbols": total_targets,
        "symbols_with_doctests": total_with_doctests,
        "total_doctest_lines": total_doctest_lines,
        "overall_coverage_pct": overall_coverage,
        "file_details": analyzed_files,
        "execution_details": test_execution_results if args.run_tests else None
    }

    if args.format == "json":
        output_str = json.dumps(report_data, indent=2)
    elif args.format == "markdown":
        lines = [
            "# Doctest Coverage Report\n",
            f"- **Files Scanned**: {len(analyzed_files)}",
            f"- **Total Symbols**: {total_targets}",
            f"- **Symbols with Doctests**: {total_with_doctests}",
            f"- **Doctest Lines**: {total_doctest_lines}",
            f"- **Overall Coverage**: **{overall_coverage}%**\n",
            "| File | Total Symbols | Doctest Symbols | Coverage |",
            "|---|---|---|---|"
        ]
        for f in analyzed_files:
            lines.append(f"| `{os.path.basename(f['file'])}` | {f['total_items']} | {f['with_doctests']} | {f['coverage_pct']}% |")
        output_str = "\n".join(lines)
    else:
        out = [
            f"{BOLD}===================================================={RESET}",
            f"{BOLD}         Python Doctest Coverage Report             {RESET}",
            f"{BOLD}===================================================={RESET}",
            f"Files Scanned:        {len(analyzed_files)}",
            f"Total Code Symbols:   {total_targets}",
            f"Symbols with Doctests:{total_with_doctests}",
            f"Total Doctest Lines:  {total_doctest_lines}",
            f"Overall Coverage:     {BOLD}{GREEN if overall_coverage >= 50 else YELLOW}{overall_coverage}%{RESET}",
            "----------------------------------------------------"
        ]
        for f in analyzed_files:
            cov_str = f"{f['coverage_pct']}%"
            out.append(f" File: {CYAN}{f['file']}{RESET} -> {f['with_doctests']}/{f['total_items']} covered ({cov_str})")
            for item in f["items"]:
                status = f"{GREEN}[HAS DOCTEST] ({item['doctest_count']} lines){RESET}" if item["has_doctest"] else f"{RED}[MISSING]{RESET}"
                out.append(f"   [{item['type'].upper()}] {item['name']} (L{item['line']}): {status}")

        if args.run_tests:
            out.append("\n" + f"{BOLD}--- Doctest Execution Results ---{RESET}")
            for tr in test_execution_results:
                if tr.get("executed"):
                    res_col = GREEN if tr['failures'] == 0 else RED
                    out.append(f" {tr['file']}: {res_col}{tr['passes']} passed, {tr['failures']} failed{RESET}")
                else:
                    out.append(f" {tr['file']}: {RED}Execution error ({tr.get('error')}){RESET}")

        output_str = "\n".join(out)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"{GREEN}Report saved to {args.output}{RESET}")
    else:
        print(output_str)

    if args.min_coverage > 0 and overall_coverage < args.min_coverage:
        print(f"\n{RED}Error: Coverage {overall_coverage}% is below required minimum {args.min_coverage}%{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
