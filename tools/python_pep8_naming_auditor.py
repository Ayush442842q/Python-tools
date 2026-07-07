#!/usr/bin/env python3
"""
Python PEP 8 Naming Style Auditor

Statically parses Python files using the Abstract Syntax Tree (AST) module
to check names of classes, functions, methods, parameters, local variables,
constants, and module filenames against official PEP 8 styling guidelines.

PEP 8 Naming Guidelines:
- Class names: PascalCase (e.g., MyClass)
- Function / Method names: snake_case (e.g., my_function)
- Local variables / Attributes: snake_case (e.g., my_var)
- Constants (Module scope): UPPER_CASE (e.g., MAX_RETRIES)
- Parameters: snake_case (e.g., param_name)
- Module filenames: lowercase snake_case (e.g., my_module.py)

Usage:
    python tools/python_pep8_naming_auditor.py /path/to/python/file.py
    python tools/python_pep8_naming_auditor.py /path/to/project/dir/
"""

import os
import re
import sys
import ast
import argparse
from typing import Dict, List, Set, Tuple, Any

# Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

USE_COLOR = supports_color()

def colorize(text: str, color_code: str) -> str:
    if USE_COLOR:
        return f"{color_code}{text}{COLOR_RESET}"
    return text

# Regex patterns
PASCAL_CASE_RE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
SNAKE_CASE_RE = re.compile(r'^_?[a-z_][a-z0-9_]*$')
UPPER_CASE_RE = re.compile(r'^_?[A-Z_][A-Z0-9_]*$')
DUNDER_RE = re.compile(r'^__[a-z0-9_]+__$')

class NamingViolation:
    def __init__(self, line: int, col: int, category: str, name: str, expected_style: str):
        self.line = line
        self.col = col
        self.category = category  # e.g., 'Class', 'Function', 'Variable', 'Constant'
        self.name = name
        self.expected_style = expected_style

    def __repr__(self):
        return f"L{self.line}:C{self.col} - {self.category} '{self.name}' should be in {self.expected_style}"

class Pep8NamingVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[NamingViolation] = []
        self.scope_stack: List[str] = ['module']  # 'module', 'class', 'function'

    def visit_ClassDef(self, node: ast.ClassDef):
        # Class names must be PascalCase
        if not PASCAL_CASE_RE.match(node.name):
            self.violations.append(NamingViolation(
                node.lineno, node.col_offset, "Class", node.name, "PascalCase (e.g. MyClassName)"
            ))
            
        self.scope_stack.append('class')
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function_name(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function_name(node)

    def _check_function_name(self, node: Any):
        name = node.name
        # Allow dunder names like __init__, __str__
        if DUNDER_RE.match(name):
            pass
        elif not SNAKE_CASE_RE.match(name):
            # Check if inside a class and name might be PascalCase (could be an error, but let's check)
            self.violations.append(NamingViolation(
                node.lineno, node.col_offset, "Function/Method", name, "snake_case (e.g. my_function_name)"
            ))

        # Check function parameters
        for arg in node.args.args:
            arg_name = arg.arg
            if arg_name == 'self' or arg_name == 'cls':
                continue
            if not SNAKE_CASE_RE.match(arg_name):
                self.violations.append(NamingViolation(
                    arg.lineno, arg.col_offset, "Parameter", arg_name, "snake_case (e.g. param_name)"
                ))

        # Check keyword-only arguments
        for arg in node.args.kwonlyargs:
            arg_name = arg.arg
            if not SNAKE_CASE_RE.match(arg_name):
                self.violations.append(NamingViolation(
                    arg.lineno, arg.col_offset, "Parameter (kw-only)", arg_name, "snake_case (e.g. param_name)"
                ))

        self.scope_stack.append('function')
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Assign(self, node: ast.Assign):
        self._check_assignment_targets(node.targets, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self._check_assignment_targets([node.target], node.lineno)
        self.generic_visit(node)

    def _check_assignment_targets(self, targets: List[ast.AST], lineno: int):
        for target in targets:
            if isinstance(target, ast.Name):
                name = target.id
                col = target.col_offset
                
                # Global/Module scope assignments
                if self.scope_stack[-1] == 'module':
                    # Can be UPPER_CASE (constant) or snake_case (global variable)
                    if not (UPPER_CASE_RE.match(name) or SNAKE_CASE_RE.match(name)):
                        self.violations.append(NamingViolation(
                            lineno, col, "Global Variable/Constant", name, "UPPER_CASE (for constants) or snake_case (for globals)"
                        ))
                
                # Class scope assignments
                elif self.scope_stack[-1] == 'class':
                    # Can be snake_case or UPPER_CASE (class constants)
                    if not (SNAKE_CASE_RE.match(name) or UPPER_CASE_RE.match(name)):
                        self.violations.append(NamingViolation(
                            lineno, col, "Class Attribute", name, "snake_case or UPPER_CASE (for class constants)"
                        ))
                
                # Local scope (inside functions)
                elif self.scope_stack[-1] == 'function':
                    # Local variables should be snake_case
                    if not SNAKE_CASE_RE.match(name):
                        # Some people use UPPER_CASE for local config/constants, let's warn if it's mixed casing
                        if not UPPER_CASE_RE.match(name):
                            self.violations.append(NamingViolation(
                                lineno, col, "Local Variable", name, "snake_case"
                            ))

            elif isinstance(target, ast.Attribute):
                # Attribute assignment, e.g., self.foo = 1
                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                    name = target.attr
                    col = target.col_offset
                    if not SNAKE_CASE_RE.match(name):
                        self.violations.append(NamingViolation(
                            lineno, col, "Instance Attribute", name, "snake_case"
                        ))

def audit_file(file_path: str) -> List[NamingViolation]:
    violations: List[NamingViolation] = []
    
    # 1. Audit filename first
    filename = os.path.basename(file_path)
    module_name, ext = os.path.splitext(filename)
    if ext == '.py' and module_name != '__init__' and module_name != '__main__':
        if not SNAKE_CASE_RE.match(module_name):
            violations.append(NamingViolation(
                1, 0, "Module Filename", filename, "snake_case (lowercase with underscores)"
            ))

    # 2. Audit contents via AST
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        visitor = Pep8NamingVisitor()
        visitor.visit(tree)
        violations.extend(visitor.violations)
    except SyntaxError as se:
        violations.append(NamingViolation(
            se.lineno or 1, se.offset or 0, "Syntax Error", f"Cannot parse file due to syntax error: {se.msg}", ""
        ))
    except Exception as e:
        violations.append(NamingViolation(
            1, 0, "Read Error", f"Cannot read file: {e}", ""
        ))

    return violations

def main():
    parser = argparse.ArgumentParser(description="Audit Python codebase for PEP 8 naming convention compliance.")
    parser.add_argument("path", help="Path to a Python file or directory containing Python files.")
    parser.add_argument("--exclude", nargs="*", default=[], help="Directories or files to exclude.")
    
    args = parser.parse_args()
    
    target_files = []
    if os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            # Apply exclusion filter on dirs
            dirs[:] = [d for d in dirs if d not in args.exclude and not d.startswith('.')]
            for file in files:
                if file.endswith('.py'):
                    target_files.append(os.path.join(root, file))
    elif os.path.isfile(args.path):
        target_files.append(args.path)
    else:
        print(colorize(f"Error: Path '{args.path}' does not exist.", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    if not target_files:
        print("No Python files found to audit.")
        sys.exit(0)

    total_violations = 0
    print(colorize(f"=== Auditing PEP 8 Naming Conventions in {len(target_files)} file(s) ===", COLOR_BOLD + COLOR_BLUE))
    
    for file in target_files:
        rel_path = os.path.relpath(file)
        violations = audit_file(file)
        
        if not violations:
            continue
            
        print(f"\n{colorize('[VIOLATIONS]', COLOR_YELLOW)} {colorize(rel_path, COLOR_BOLD)}")
        for v in sorted(violations, key=lambda x: (x.line, x.col)):
            location = f"Line {v.line:<4} Col {v.col:<2}"
            category_str = f"[{v.category}]"
            
            if v.expected_style:
                msg = f"{v.name} -> Expected {v.expected_style}"
            else:
                msg = v.name  # Fallback for errors
                
            print(f"  {location} {colorize(category_str, COLOR_BLUE)} {msg}")
            total_violations += 1

    print("\n" + "=" * 50)
    print(f"Audit completed. Total naming violations found: {total_violations}")
    sys.exit(0)

if __name__ == "__main__":
    main()
