#!/usr/bin/env python3
"""
Python Global Variable Auditor - Scan Python codebases to audit global variables and state mutations.
"""

import ast
import argparse
import sys
import os
import glob

# ANSI colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

class GlobalVariableVisitor(ast.NodeVisitor):
    def __init__(self):
        self.globals_defined = {} # var_name -> line_no
        self.globals_mutated = {}  # var_name -> list of (line_no, type_of_mutation)
        self.globals_read = {}     # var_name -> list of line_no
        self.current_function = None
        self.local_scopes = []
        self.global_declarations = set()

    def visit_Module(self, node):
        # Scan module body for top-level assignments (global variables)
        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    # Handle basic variable assignments: x = 1
                    if isinstance(target, ast.Name):
                        self.globals_defined[target.id] = child.lineno
                    # Handle tuple/list unpacking: x, y = 1, 2
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        for element in target.elts:
                            if isinstance(element, ast.Name):
                                self.globals_defined[element.id] = child.lineno
            elif isinstance(child, ast.AnnAssign):
                # Handle annotated assignments: x: int = 1
                if isinstance(child.target, ast.Name):
                    self.globals_defined[child.target.id] = child.lineno
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.local_scopes.append(set())
        
        # Save active global declarations
        old_global_declarations = self.global_declarations.copy()
        
        # Track parameters as local variables
        for arg in node.args.args:
            self.local_scopes[-1].add(arg.arg)
        
        self.generic_visit(node)
        
        # Restore scopes
        self.local_scopes.pop()
        self.global_declarations = old_global_declarations
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Global(self, node):
        for name in node.names:
            self.global_declarations.add(name)
            if name in self.globals_defined:
                if name not in self.globals_mutated:
                    self.globals_mutated[name] = []
                self.globals_mutated[name].append((node.lineno, f"declared 'global' in '{self.current_function}'"))

    def visit_Name(self, node):
        # We only care about global variables
        var_name = node.id
        if var_name not in self.globals_defined:
            return

        # Check if it's a read or write context
        if isinstance(node.ctx, ast.Store):
            # If we are inside a function and haven't declared it global, it's actually creating a local shadow
            is_local = False
            for scope in self.local_scopes:
                if var_name in scope:
                    is_local = True
            
            if self.current_function and var_name not in self.global_declarations and not is_local:
                # Shadowing/local assignment - not mutating the global itself unless global was declared
                # But it's still a warning-worthy shadow
                pass
            elif self.current_function and var_name in self.global_declarations:
                # Modifying the global variable directly!
                if var_name not in self.globals_mutated:
                    self.globals_mutated[var_name] = []
                self.globals_mutated[var_name].append((node.lineno, f"re-assigned inside '{self.current_function}'"))
        elif isinstance(node.ctx, ast.Load):
            # Read context
            # Make sure it's not shadowed by a local parameter/variable
            is_local = False
            for scope in self.local_scopes:
                if var_name in scope:
                    is_local = True
            
            if not is_local:
                if var_name not in self.globals_read:
                    self.globals_read[var_name] = []
                self.globals_read[var_name].append(node.lineno)

    def visit_Call(self, node):
        # Check for mutation methods on global objects (like dict.update, list.append, etc.)
        # e.g., GLOBAL_LIST.append(x)
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                method_name = node.func.attr
                if var_name in self.globals_defined:
                    mutation_methods = {"append", "extend", "insert", "remove", "pop", "clear", "update", "add", "discard", "difference_update", "intersection_update"}
                    if method_name in mutation_methods:
                        if var_name not in self.globals_mutated:
                            self.globals_mutated[var_name] = []
                        context = f"mutated via .{method_name}()"
                        if self.current_function:
                            context += f" in '{self.current_function}'"
                        self.globals_mutated[var_name].append((node.lineno, context))
        self.generic_visit(node)

def audit_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f"{COLOR_RED}Error parsing '{file_path}': {e}{COLOR_RESET}")
        return None

    visitor = GlobalVariableVisitor()
    visitor.visit(tree)
    return visitor

def main():
    parser = argparse.ArgumentParser(
        description="Python Global Variable Auditor - Detect global state patterns and state mutations."
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Directories or files to scan (default: current directory)")
    parser.add_argument("--exclude", nargs="*", default=["venv", ".git", "__pycache__"], help="Directories to exclude")
    args = parser.parse_args()

    python_files = []
    for path in args.paths:
        if os.path.isfile(path) and path.endswith(".py"):
            python_files.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in args.exclude]
                for file in files:
                    if file.endswith(".py"):
                        python_files.append(os.path.join(root, file))

    if not python_files:
        print(f"{COLOR_YELLOW}No Python files found to audit.{COLOR_RESET}")
        return

    print("=" * 80)
    print(f"{COLOR_BOLD}{COLOR_HEADER}PYTHON GLOBAL VARIABLE STATE AUDIT{COLOR_RESET}")
    print("=" * 80)
    print(f"Files Scanned: {len(python_files)}")
    print("=" * 80)
    print()

    total_globals = 0
    total_mutated = 0
    total_warnings = 0

    for file_path in python_files:
        visitor = audit_file(file_path)
        if not visitor or not visitor.globals_defined:
            continue

        rel_path = os.path.relpath(file_path)
        print(f"{COLOR_BOLD}{COLOR_BLUE}File: {rel_path}{COLOR_RESET}")
        
        file_globals = 0
        for var, line in visitor.globals_defined.items():
            # Skip uppercase constants (e.g. API_KEY, DEFAULT_TIMEOUT) which are common config variables
            # and usually immutable/not mutated.
            if var.isupper():
                continue

            file_globals += 1
            total_globals += 1
            
            mutations = visitor.globals_mutated.get(var, [])
            reads = visitor.globals_read.get(var, [])
            
            # Print audit record
            status_color = COLOR_GREEN
            status_text = "OK (Read-Only/Unused)"
            
            if mutations:
                status_color = COLOR_RED
                status_text = "MUTATED STATE (Potential Race Condition/Thread Safety Risk)"
                total_mutated += 1
                total_warnings += 1
            elif not reads:
                status_color = COLOR_YELLOW
                status_text = "UNUSED GLOBAL (Dead Code)"
                total_warnings += 1

            print(f"  • {COLOR_BOLD}{var}{COLOR_RESET} (defined at Line {line})")
            print(f"    Status: {status_color}{status_text}{COLOR_RESET}")
            
            if mutations:
                print(f"    {COLOR_BOLD}Mutations ({len(mutations)}):{COLOR_RESET}")
                for m_line, m_desc in mutations:
                    print(f"      - Line {m_line}: {m_desc}")
            if reads:
                print(f"    Reads: {len(reads)} references found")
            print()

    print("=" * 80)
    print(f"{COLOR_BOLD}Audit Summary:{COLOR_RESET}")
    print(f"  Total non-constant global variables: {total_globals}")
    print(f"  Globally mutated variables          : {COLOR_RED}{total_mutated}{COLOR_RESET}")
    print(f"  Audited warnings / code smells       : {COLOR_YELLOW}{total_warnings}{COLOR_RESET}")
    print("=" * 80)

if __name__ == "__main__":
    main()
