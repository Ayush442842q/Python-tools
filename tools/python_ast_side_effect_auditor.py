#!/usr/bin/env python3
"""
Python Side-Effect & Impurity Auditor

An AST-based scanner that recursively parses Python files to check if functions/methods
are "pure" or "impure". Detects global/nonlocal mutations, parameter alterations,
file/socket operations, subprocesses, system calls, and other state mutations.
"""

import sys
import os
import ast
import argparse
from typing import Dict, List, Set, Tuple

# ANSI Color Escape Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def colored(text: str, color_code: str) -> str:
    if sys.platform == "win32":
        import os
        os.system("")
    return f"{color_code}{text}{RESET}"

# Impure standard library functions or patterns
IMPURE_BUILTINS = {
    'print', 'open', 'input', 'eval', 'exec', 'compile', 'locals', 'globals', 'vars', 'exit'
}

IMPURE_MODULES = {
    'sys', 'os', 'subprocess', 'socket', 'urllib', 'requests', 'sqlite3', 'ctypes', 'tempfile', 'shutil', 'logging'
}

# Methods that mutate objects
MUTATION_METHODS = {
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'update', 'add', 'discard', 'difference_update', 
    'intersection_update', 'symmetric_difference_update', 'reverse', 'sort'
}

class ImpurityVisitor(ast.NodeVisitor):
    def __init__(self, func_args: List[str]):
        self.func_args = set(func_args)
        self.reasons: List[str] = []
        self.has_global_decl = False
        self.has_nonlocal_decl = False
        
    def add_reason(self, node: ast.AST, msg: str):
        self.reasons.append(f"Line {node.lineno}: {msg}")

    def visit_Global(self, node: ast.Global):
        self.has_global_decl = True
        self.add_reason(node, f"Declares global variable(s) {node.names}")
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        self.has_nonlocal_decl = True
        self.add_reason(node, f"Declares nonlocal variable(s) {node.names}")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check if assigning to global/nonlocal namespace directly (if declared)
        # Or check if mutating objects via target assignment (e.g. self.x = ...)
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                # e.g., self.value = val or obj.prop = val
                attr_name = self._get_base_name(target.value)
                self.add_reason(node, f"Mutates object attribute: {attr_name}.{target.attr}")
            elif isinstance(target, ast.Subscript):
                # e.g., arr[0] = val
                sub_name = self._get_base_name(target.value)
                self.add_reason(node, f"Mutates collection index/key: {sub_name}[...]")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func = node.func
        
        # 1. Check direct name calls (e.g., print())
        if isinstance(func, ast.Name):
            func_name = func.id
            if func_name in IMPURE_BUILTINS:
                self.add_reason(node, f"Calls impure builtin function: {func_name}()")
                
        # 2. Check method calls (e.g., list.append() or sys.stdout.write())
        elif isinstance(func, ast.Attribute):
            base_name = self._get_base_name(func.value)
            method_name = func.attr
            
            # Check if mutating a function argument
            if base_name in self.func_args and method_name in MUTATION_METHODS:
                self.add_reason(node, f"Mutates parameter '{base_name}' using .{method_name}()")
            
            # Check for generic stateful attributes / modules
            if base_name in IMPURE_MODULES:
                self.add_reason(node, f"Calls method from impure module: {base_name}.{method_name}()")
            
            # Specific well-known mutations
            if base_name == 'self' or base_name == 'cls':
                self.add_reason(node, f"Mutates class/instance state: self.{method_name}()")
                
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name.split('.')[0]
            if name in IMPURE_MODULES:
                self.add_reason(node, f"Imports stateful/impure module: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            name = node.module.split('.')[0]
            if name in IMPURE_MODULES:
                self.add_reason(node, f"Imports from stateful/impure module: {node.module}")
        self.generic_visit(node)

    def _get_base_name(self, node: ast.AST) -> str:
        """Helper to extract root name from chain of attributes (e.g. self.x.y -> self)."""
        curr = node
        while isinstance(curr, ast.Attribute):
            curr = curr.value
        if isinstance(curr, ast.Name):
            return curr.id
        return ""

class FileSideEffectAuditor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.results: List[Dict[str, Any]] = []

    def audit(self) -> bool:
        if not os.path.exists(self.file_path):
            return False
            
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content, filename=self.file_path)
        except Exception as e:
            print(colored(f"[!] Error parsing {self.file_path}: {e}", RED))
            return False

        # Find all function and method definitions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                
                # Get argument names
                args = [arg.arg for arg in node.args.args]
                if node.args.vararg:
                    args.append(node.args.vararg.arg)
                if node.args.kwarg:
                    args.append(node.args.kwarg.arg)
                args.extend([arg.arg for arg in node.args.kwonlyargs])
                
                # Visit body
                visitor = ImpurityVisitor(args)
                visitor.visit(node)
                
                is_pure = len(visitor.reasons) == 0
                self.results.append({
                    "name": func_name,
                    "line": node.lineno,
                    "is_pure": is_pure,
                    "reasons": visitor.reasons
                })
        return True

def audit_directory(path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Audit all python files recursively in a directory."""
    all_results = {}
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                auditor = FileSideEffectAuditor(full_path)
                if auditor.audit() and auditor.results:
                    rel_path = os.path.relpath(full_path, path)
                    all_results[rel_path] = auditor.results
    return all_results

def print_file_report(rel_path: str, results: List[Dict[str, Any]]):
    print(colored(f"\nFile: {rel_path}", BOLD + CYAN))
    print(colored("=" * 60, BOLD))
    
    pure_count = sum(1 for r in results if r["is_pure"])
    total_count = len(results)
    
    purity_pct = (pure_count / total_count * 100) if total_count > 0 else 100
    print(f"Purity Scorecard: {pure_count}/{total_count} pure functions ({purity_pct:.1f}%)")
    print(colored("-" * 60, BOLD))
    
    for r in results:
        status_color = GREEN if r["is_pure"] else RED
        status_text = "PURE" if r["is_pure"] else "IMPURE"
        print(f"  [{colored(status_text, status_color)}] {colored(r['name'], BOLD)} (Line {r['line']})")
        if not r["is_pure"]:
            for reason in r["reasons"]:
                print(f"     ↳ {reason}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Python Side-Effect & Function Impurity Auditor")
    parser.add_argument("path", help="Path to Python file or directory of Python files to audit")
    args = parser.parse_args()
    
    if os.path.isdir(args.path):
        results = audit_directory(args.path)
        if not results:
            print(colored("No Python files with function definitions found.", RED))
            return
            
        print(colored(f"\n=== Python Codebase Impurity Audit ===", BOLD + YELLOW))
        for rel_path, file_res in results.items():
            print_file_report(rel_path, file_res)
            
    else:
        auditor = FileSideEffectAuditor(args.path)
        if auditor.audit():
            print(colored(f"\n=== Python File Impurity Audit ===", BOLD + YELLOW))
            print_file_report(args.path, auditor.results)
        else:
            print(colored(f"[!] Failed to audit file: {args.path}", RED))

if __name__ == "__main__":
    main()
