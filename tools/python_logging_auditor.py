#!/usr/bin/env python3
"""
Python Logging Auditor

Scans Python source files to audit the usage of standard 'logging' vs bare 'print()'
statements and direct writes to sys.stdout/sys.stderr. Helps codebase migration to
structured logging.

Usage:
    python tools/python_logging_auditor.py [path_to_code_or_dir] [options]
"""

import os
import ast
import sys
import argparse
from pathlib import Path

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

class LogAuditVisitor(ast.NodeVisitor):
    def __init__(self):
        self.prints = []
        self.sys_writes = []
        self.log_imports = []
        self.logger_definitions = []
        self.log_calls = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == 'logging':
                self.log_imports.append((node.lineno, 'import logging'))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == 'logging':
            self.log_imports.append((node.lineno, f'from logging import ...'))
        self.generic_visit(node)

    def visit_Call(self, node):
        # 1. Check for print(...)
        if isinstance(node.func, ast.Name) and node.func.id == 'print':
            self.prints.append(node)
            
        # 2. Check for sys.stdout/stderr.write(...)
        elif (isinstance(node.func, ast.Attribute) and 
              node.func.attr == 'write' and 
              isinstance(node.func.value, ast.Attribute) and 
              node.func.value.attr in ('stdout', 'stderr') and 
              isinstance(node.func.value.value, ast.Name) and 
              node.func.value.value.id == 'sys'):
            self.sys_writes.append(node)
            
        # 3. Check for logger calls (e.g. logger.info, logging.debug, self.logger.warning)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr.lower()
            if attr_name in ('debug', 'info', 'warning', 'warn', 'error', 'critical', 'exception'):
                # Check if it resembles a logger method call
                self.log_calls.append(node)
                
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Check logger definitions like: logger = logging.getLogger(__name__)
        # or log = getLogger()
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Attribute) and func.attr == 'getLogger') or \
               (isinstance(func, ast.Name) and func.id == 'getLogger'):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.logger_definitions.append((node.lineno, target.id))
        self.generic_visit(node)

def audit_file(filepath: Path, args) -> dict:
    """Audits a single python file and returns violation information."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        print_colored(f"Error reading {filepath}: {e}", RED)
        return None

    try:
        tree = ast.parse(code, filename=str(filepath))
    except SyntaxError as se:
        print_colored(f"Syntax Error in {filepath}:{se.lineno}:{se.offset} - {se.text.strip() if se.text else ''}", RED)
        return None

    visitor = LogAuditVisitor()
    visitor.visit(tree)

    violations = []
    
    # Process prints
    for node in visitor.prints:
        violations.append({
            'line': node.lineno,
            'col': node.col_offset,
            'type': 'print',
            'desc': 'Bare print() statement'
        })
        
    # Process sys.stdout/stderr writes
    for node in visitor.sys_writes:
        # Reconstruct name for write call
        stream = node.func.value.attr
        violations.append({
            'line': node.lineno,
            'col': node.col_offset,
            'type': 'sys_write',
            'desc': f'Direct write to sys.{stream}'
        })

    result = {
        'filepath': filepath,
        'has_logging_import': len(visitor.log_imports) > 0,
        'logger_names': [name for _, name in visitor.logger_definitions],
        'log_calls_count': len(visitor.log_calls),
        'violations': sorted(violations, key=lambda x: (x['line'], x['col'])),
        'code_lines': code.splitlines()
    }
    
    return result

def print_audit_report(results: list, args):
    """Generates the final terminal output report."""
    total_files = len(results)
    total_violations = 0
    clean_files = 0
    
    print("=" * 80)
    print_colored(f"Python Logging Audit Report", BOLD + CYAN)
    print("=" * 80)
    
    for r in results:
        v_count = len(r['violations'])
        total_violations += v_count
        
        if v_count == 0:
            clean_files += 1
            if args.verbose:
                print_colored(f"✔ {r['filepath']} (Clean, Logging status: {'Configured' if r['has_logging_import'] else 'None'})", GREEN)
            continue
            
        print_colored(f"\n✗ {r['filepath']} ({v_count} violation(s))", RED + BOLD)
        print_colored(f"  Logging Imported: {r['has_logging_import']} | Loggers Defined: {r['logger_names'] if r['logger_names'] else 'None'} | Log Calls: {r['log_calls_count']}", CYAN)
        
        for v in r['violations']:
            line_idx = v['line'] - 1
            code_line = r['code_lines'][line_idx].strip() if line_idx < len(r['code_lines']) else ''
            print(f"  Line {v['line']}:{v['col']} - {v['desc']}")
            print_colored(f"    > {code_line}", YELLOW)
            
    print("\n" + "=" * 80)
    print_colored("Summary Statistics:", BOLD)
    print(f"  Total scanned files: {total_files}")
    print(f"  Clean files:         {clean_files} ({(clean_files/total_files)*100:.1f}%)")
    print(f"  Violated files:      {total_files - clean_files} ({((total_files - clean_files)/total_files)*100:.1f}%)")
    print(f"  Total violations:    {total_violations}")
    print("=" * 80)
    
    if args.fail_under and (clean_files / total_files * 100) < args.fail_under:
        print_colored(f"Audit Failed: Clean file ratio is below required {args.fail_under}%.", RED)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Audit Python files for bare print() calls and encourage migration to structured logging."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to a Python file or directory containing Python files (default: current directory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Include clean files in output report"
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["venv", ".git", "__pycache__", "build", "dist"],
        help="Directories to exclude from scanning (default: standard virtualenvs, git files)"
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        help="Exit code 1 if clean file percentage is below this threshold (e.g. 90.0)"
    )
    
    args = parser.parse_args()
    
    target_path = Path(args.path)
    if not target_path.exists():
        print_colored(f"Error: path '{target_path}' does not exist.", RED)
        return 1
        
    py_files = []
    if target_path.is_file():
        if target_path.suffix == '.py':
            py_files.append(target_path)
    else:
        # Exclude directories
        exclude_set = set(args.exclude)
        for root, dirs, files in os.walk(target_path):
            # Prune directory searches in place
            dirs[:] = [d for d in dirs if d not in exclude_set]
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
                    
    if not py_files:
        print_colored("No Python files found to audit.", YELLOW)
        return 0
        
    print_colored(f"Auditing {len(py_files)} Python file(s) for print statements...", BOLD)
    
    results = []
    for file in py_files:
        res = audit_file(file, args)
        if res:
            results.append(res)
            
    print_audit_report(results, args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
