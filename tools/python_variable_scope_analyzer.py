#!/usr/bin/env python3
"""Python Variable Scope Analyzer

Scan Python files or directories using AST to detect scope anomalies,
variable shadowing of builtins or outer scopes, unused local variables,
and global/nonlocal state modifications.
"""

import argparse
import ast
import builtins
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

BUILTIN_NAMES = set(dir(builtins))


class ScopeVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.findings: List[Dict[str, Any]] = []
        self.scope_stack: List[Dict[str, Any]] = []
        # Initial global scope
        self.push_scope("<module>", "module", lineno=1)

    def push_scope(self, name: str, scope_type: str, lineno: int):
        self.scope_stack.append({
            "name": name,
            "type": scope_type,
            "lineno": lineno,
            "globals": set(),
            "nonlocals": set(),
            "assigned": dict(),  # var_name -> lineno
            "used": set(),       # var_name
            "params": set(),     # var_name
        })

    def pop_scope(self):
        current = self.scope_stack.pop()
        # Analyze current function or class scope before discarding
        if current["type"] in ("function", "async_function"):
            params = current["params"]
            assigned = current["assigned"]
            used = current["used"]
            globals_decl = current["globals"]
            nonlocals_decl = current["nonlocals"]

            # 1. Detect unused variables/parameters
            for var_name, lineno in assigned.items():
                if var_name.startswith("_") or var_name in globals_decl or var_name in nonlocals_decl:
                    continue
                if var_name not in used:
                    issue = "Unused parameter" if var_name in params else "Unused local variable"
                    self.findings.append({
                        "file": self.filepath,
                        "line": lineno,
                        "scope": current["name"],
                        "type": issue,
                        "variable": var_name,
                        "details": f"'{var_name}' is assigned/defined in {current['name']} but never read."
                    })

            # 2. Detect built-in shadowing
            all_defined = set(assigned.keys()) | params
            for var_name in all_defined:
                if var_name in BUILTIN_NAMES and var_name not in {"id", "type", "input", "format", "dir", "list", "dict", "set", "str", "int", "float", "bool", "len", "range", "min", "max", "sum", "open", "hash", "slice", "object"}:
                    # Ignore very common shadow names if intended, but report notable builtins
                    pass
                elif var_name in BUILTIN_NAMES and var_name not in {"_", "file"}:
                    lineno = assigned.get(var_name, current["lineno"])
                    self.findings.append({
                        "file": self.filepath,
                        "line": lineno,
                        "scope": current["name"],
                        "type": "Built-in Shadowing",
                        "variable": var_name,
                        "details": f"'{var_name}' shadows Python built-in function/type '{var_name}'."
                    })

            # 3. Detect outer scope shadowing
            outer_vars: Set[str] = set()
            for s in self.scope_stack:
                outer_vars.update(s["assigned"].keys())
                outer_vars.update(s["params"])
            for var_name in all_defined:
                if var_name in outer_vars and var_name not in globals_decl and var_name not in nonlocals_decl:
                    lineno = assigned.get(var_name, current["lineno"])
                    self.findings.append({
                        "file": self.filepath,
                        "line": lineno,
                        "scope": current["name"],
                        "type": "Outer Scope Shadowing",
                        "variable": var_name,
                        "details": f"'{var_name}' in '{current['name']}' shadows variable with same name in outer scope."
                    })

    def current_scope(self) -> Dict[str, Any]:
        return self.scope_stack[-1]

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.push_scope(node.name, "function", node.lineno)
        # Collect parameters
        for arg in node.args.args + node.args.kwonlyargs:
            self.current_scope()["params"].add(arg.arg)
        if node.args.vararg:
            self.current_scope()["params"].add(node.args.vararg.arg)
        if node.args.kwarg:
            self.current_scope()["params"].add(node.args.kwarg.arg)
        self.generic_visit(node)
        self.pop_scope()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.push_scope(node.name, "async_function", node.lineno)
        for arg in node.args.args + node.args.kwonlyargs:
            self.current_scope()["params"].add(arg.arg)
        if node.args.vararg:
            self.current_scope()["params"].add(node.args.vararg.arg)
        if node.args.kwarg:
            self.current_scope()["params"].add(node.args.kwarg.arg)
        self.generic_visit(node)
        self.pop_scope()

    def visit_ClassDef(self, node: ast.ClassDef):
        self.push_scope(node.name, "class", node.lineno)
        self.generic_visit(node)
        self.pop_scope()

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.current_scope()["globals"].add(name)
            self.findings.append({
                "file": self.filepath,
                "line": node.lineno,
                "scope": self.current_scope()["name"],
                "type": "Global Declaration",
                "variable": name,
                "details": f"Explicit 'global {name}' declaration in scope '{self.current_scope()['name']}'."
            })
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        for name in node.names:
            self.current_scope()["nonlocals"].add(name)
            self.findings.append({
                "file": self.filepath,
                "line": node.lineno,
                "scope": self.current_scope()["name"],
                "type": "Nonlocal Declaration",
                "variable": name,
                "details": f"Explicit 'nonlocal {name}' declaration in scope '{self.current_scope()['name']}'."
            })
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        scope = self.current_scope()
        if isinstance(node.ctx, ast.Store):
            if node.id not in scope["assigned"]:
                scope["assigned"][node.id] = node.lineno
        elif isinstance(node.ctx, ast.Load):
            scope["used"].add(node.id)


def analyze_file(filepath: Path) -> List[Dict[str, Any]]:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(filepath))
        visitor = ScopeVisitor(str(filepath))
        visitor.visit(tree)
        # Flush top level
        visitor.pop_scope()
        return visitor.findings
    except SyntaxError as e:
        return [{
            "file": str(filepath),
            "line": e.lineno or 1,
            "scope": "<module>",
            "type": "Syntax Error",
            "variable": "N/A",
            "details": f"SyntaxError parsing file: {e.msg}"
        }]
    except Exception as e:
        return [{
            "file": str(filepath),
            "line": 1,
            "scope": "<module>",
            "type": "Parse Error",
            "variable": "N/A",
            "details": f"Error parsing file: {str(e)}"
        }]


def run_tests():
    """Self-test routine for python_variable_scope_analyzer."""
    sample_code = '''
def outer_func(x):
    type = "shadowing builtin"
    x = 10
    unused_var = 42
    def inner_func():
        nonlocal x
        x = 20
        print(type)
    return inner_func
'''
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(sample_code)
        tmp_name = f.name

    try:
        findings = analyze_file(Path(tmp_name))
        assert any(f["type"] == "Built-in Shadowing" and f["variable"] == "type" for f in findings), "Test failed: Built-in Shadowing not detected"
        assert any(f["type"] == "Unused local variable" and f["variable"] == "unused_var" for f in findings), "Test failed: Unused variable not detected"
        assert any(f["type"] == "Nonlocal Declaration" and f["variable"] == "x" for f in findings), "Test failed: Nonlocal declaration not detected"
        print(f"{COLOR_GREEN}All tests passed successfully!{COLOR_RESET}")
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def main():
    parser = argparse.ArgumentParser(
        description="Scan Python files for variable scope anomalies, shadowing, and unused variables."
    )
    parser.add_argument("target", nargs="?", default=".", help="File or directory path to analyze (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return 0

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{target_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        return 1

    py_files: List[Path] = []
    if target_path.is_file() and target_path.suffix == ".py":
        py_files.append(target_path)
    elif target_path.is_dir():
        py_files = sorted([p for p in target_path.rglob("*.py") if not any(part.startswith(".") or part in ("venv", "build", "dist", "__pycache__") for part in p.parts)])

    all_findings: List[Dict[str, Any]] = []
    for fpath in py_files:
        all_findings.extend(analyze_file(fpath))

    if args.json:
        print(json.dumps(all_findings, indent=2))
        return 0

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Python Variable Scope Analyzer ==={COLOR_RESET}")
    print(f"Analyzed {len(py_files)} file(s). Found {len(all_findings)} item(s).\n")

    if not all_findings:
        print(f"{COLOR_GREEN}No scope anomalies or shadowing detected!{COLOR_RESET}\n")
        return 0

    for item in all_findings:
        color = COLOR_YELLOW
        if "Error" in item["type"]:
            color = COLOR_RED
        elif "Shadowing" in item["type"]:
            color = COLOR_CYAN
        elif "Declaration" in item["type"]:
            color = COLOR_BLUE

        print(f"{COLOR_BOLD}{item['file']}:{item['line']}{COLOR_RESET} [{item['scope']}]")
        print(f"  {color}▸ [{item['type']}]{COLOR_RESET} Variable '{COLOR_BOLD}{item['variable']}{COLOR_RESET}'")
        print(f"    {item['details']}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
