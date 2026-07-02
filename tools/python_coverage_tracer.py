#!/usr/bin/env python3
"""
Python Code Coverage Tracer

A standalone CLI utility that executes a target Python script and traces line-level 
coverage using `sys.settrace`. It parses the target file's AST (Abstract Syntax Tree) 
to locate all executable statements and reports exactly which lines were executed 
versus missed with colorized console output.
"""

import argparse
import ast
import os
import sys
from typing import Set, Dict, List, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def log_success(msg: str):
    print(color_text("[+] " + msg, COLOR_GREEN))

def log_info(msg: str):
    print(color_text("[*] " + msg, COLOR_CYAN))

def log_warning(msg: str):
    print(color_text("[!] " + msg, COLOR_YELLOW))

def log_error(msg: str):
    print(color_text("[-] ERROR: " + msg, COLOR_RED), file=sys.stderr)

# --- AST Statement Line Analyzer ---

class ExecutableLineFinder(ast.NodeVisitor):
    """AST Visitor to extract the line numbers of all executable statements."""
    def __init__(self):
        self.executable_lines: Set[int] = set()

    def visit_Module(self, node: ast.Module):
        body = node.body
        # Skip module docstring
        start_idx = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.Str)):
            start_idx = 1
        for child in body[start_idx:]:
            self.visit(child)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.executable_lines.add(node.lineno)
        body = node.body
        # Skip function docstring
        start_idx = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.Str)):
            start_idx = 1
        for child in body[start_idx:]:
            self.visit(child)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.executable_lines.add(node.lineno)
        body = node.body
        # Skip class docstring
        start_idx = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.Str)):
            start_idx = 1
        for child in body[start_idx:]:
            self.visit(child)
        self.generic_visit(node)

    # Core statements and expressions that are executed
    def visit_Assign(self, node: ast.Assign):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr):
        # Avoid standalone strings (not docstrings but other standalone literals)
        if not isinstance(node.value, (ast.Constant, ast.Str)):
            self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        self.executable_lines.add(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        self.executable_lines.add(node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self.executable_lines.add(node.lineno)

    def visit_Global(self, node: ast.Global):
        self.executable_lines.add(node.lineno)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        self.executable_lines.add(node.lineno)

    def visit_Pass(self, node: ast.Pass):
        self.executable_lines.add(node.lineno)

    def visit_Break(self, node: ast.Break):
        self.executable_lines.add(node.lineno)

    def visit_Continue(self, node: ast.Continue):
        self.executable_lines.add(node.lineno)

# --- Tracing Runner ---

def run_script_with_trace(script_path: str, script_args: List[str]) -> Set[int]:
    """Runs a target Python script and records executed line numbers."""
    abs_script_path = os.path.abspath(script_path)
    executed_lines: Set[int] = set()

    # The trace callback function
    def trace_lines(frame, event, arg):
        if event == 'line':
            filename = os.path.abspath(frame.f_code.co_filename)
            if filename == abs_script_path:
                executed_lines.add(frame.f_lineno)
        return trace_lines

    # Prepare environment for execution
    original_argv = sys.argv
    original_path = sys.path
    
    # Mock argv to match script's context
    sys.argv = [script_path] + script_args
    # Add script's directory to python path
    sys.path.insert(0, os.path.dirname(abs_script_path))

    log_info(f"Executing script: '{script_path}' with trace...")
    
    sys.settrace(trace_lines)
    try:
        with open(abs_script_path, 'r', encoding='utf-8') as f:
            code_str = f.read()
        compiled = compile(code_str, abs_script_path, 'exec')
        globals_dict = {
            '__name__': '__main__',
            '__file__': abs_script_path,
            '__builtins__': __builtins__,
        }
        # Run script
        exec(compiled, globals_dict)
    except SystemExit as exit_err:
        # Script exited normally via sys.exit()
        log_info(f"Target script exited with code {exit_err.code}")
    except Exception as run_err:
        log_error(f"Target script raised exception: {run_err}")
    finally:
        sys.settrace(None)
        sys.argv = original_argv
        sys.path = original_path

    return executed_lines

# --- Output Report ---

def print_coverage_report(script_path: str, executable: Set[int], executed: Set[int]):
    """Reads script and displays a colorized, line-by-line coverage report."""
    with open(script_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print("\n" + color_text(f"=== COVERAGE REPORT FOR {os.path.basename(script_path)} ===", COLOR_BOLD))
    
    covered_count = 0
    total_executable = len(executable)
    
    # Headers
    print(f"{'Line':<6} | {'Cov':<3} | {'Code'}")
    print("-" * 60)
    
    for idx, line_text in enumerate(lines, start=1):
        line_stripped = line_text.rstrip('\r\n')
        status_symbol = " "
        color = COLOR_RESET
        
        if idx in executable:
            if idx in executed:
                status_symbol = "+"
                color = COLOR_GREEN
                covered_count += 1
            else:
                status_symbol = "!"
                color = COLOR_RED
        
        line_num_str = f"{idx:<6}"
        cov_status_str = f"[{status_symbol}]"
        
        print(f"{line_num_str} | {color_text(cov_status_str, color)} | {color_text(line_stripped, color)}")
        
    print("-" * 60)
    coverage_pct = (covered_count / total_executable * 100) if total_executable > 0 else 100.0
    
    log_success(f"Executed: {covered_count} / {total_executable} statements ({coverage_pct:.2f}% coverage)")
    
    # List missed lines explicitly for quick review
    missed = sorted(list(executable - executed))
    if missed:
        print(color_text(f"Missed statements on lines: {', '.join(map(str, missed))}", COLOR_YELLOW))

def main():
    parser = argparse.ArgumentParser(
        description="Line-Level Code Coverage Tracer for Python Scripts"
    )
    parser.add_argument("script", help="Path to the target Python script to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed directly to the target script")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.script):
        log_error(f"Target script not found: {args.script}")
        sys.exit(1)
        
    # Analyze AST for executable lines before running
    try:
        with open(args.script, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=args.script)
        finder = ExecutableLineFinder()
        finder.visit(tree)
        executable_lines = finder.executable_lines
    except Exception as parse_err:
        log_error(f"Failed to parse target script AST: {parse_err}")
        sys.exit(1)
        
    if not executable_lines:
        log_warning("No executable statements found in target script.")
        
    # Run script and trace executed lines
    executed_lines = run_script_with_trace(args.script, args.args)
    
    # Output coverage results
    print_coverage_report(args.script, executable_lines, executed_lines)

if __name__ == "__main__":
    main()
