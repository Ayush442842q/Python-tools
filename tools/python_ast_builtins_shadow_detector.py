#!/usr/bin/env python3
"""
Python AST Builtins Shadow Detector

A static analysis tool that parses Python files using the standard `ast` module
to detect when variables, function names, class names, parameters, or imports
shadow Python's built-in functions or constants (e.g., `id`, `list`, `sum`,
`type`, `input`, `open`). Shadowing built-ins is a common source of bugs,
readability issues, and namespace pollution.

Usage:
    python tools/python_ast_builtins_shadow_detector.py [paths] [options]

Options:
    paths                 One or more Python files or directories to scan (default: current directory)
    -r, --recursive       Recursively scan subdirectories for Python files
    -e, --exclude PATHS   Comma-separated list of directories/files to exclude
    -h, --help            Show this help message and exit
"""

import argparse
import ast
import builtins
import os
import sys
from typing import List, Set, Dict, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def supports_color() -> bool:
    """Returns True if the terminal supports ANSI colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty


def color_text(text: str, color_code: str) -> str:
    """Colors text for terminal output if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text


# Gather list of actual Python builtins
BUILTIN_NAMES = set(dir(builtins))


class BuiltinShadowVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.shadows: List[Dict[str, any]] = []
        # Keep track of active scopes (e.g., "module", "class Name", "function name")
        self.scope_stack: List[str] = ["global"]

    @property
    def current_scope(self) -> str:
        return " -> ".join(self.scope_stack)

    def register_shadow(self, name: str, node: ast.AST, shadow_type: str):
        """Registers a detected builtin shadowing case."""
        if name in BUILTIN_NAMES:
            self.shadows.append({
                "name": name,
                "line": node.lineno,
                "col": node.col_offset,
                "type": shadow_type,
                "scope": self.current_scope
            })

    def visit_Assign(self, node: ast.Assign):
        # Scan assignment targets (e.g., x = 1, (y, z) = (2, 3))
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        # Scan annotated assignment (e.g., x: int = 1)
        self._check_target(node.target)
        self.generic_visit(node)

    def _check_target(self, target: ast.AST):
        if isinstance(target, ast.Name):
            self.register_shadow(target.id, target, "Variable Assignment")
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._check_target(element)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check function name itself
        self.register_shadow(node.name, node, "Function Declaration")
        
        # Enter function scope
        self.scope_stack.append(f"def {node.name}")
        
        # Check function arguments
        for arg in node.args.args:
            self.register_shadow(arg.arg, arg, "Function Parameter")
        for arg in node.args.kwonlyargs:
            self.register_shadow(arg.arg, arg, "Function Parameter")
        if node.args.vararg:
            self.register_shadow(node.args.vararg.arg, node.args.vararg, "Function Parameter")
        if node.args.kwarg:
            self.register_shadow(node.args.kwarg.arg, node.args.kwarg, "Function Parameter")

        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Check async function name itself
        self.register_shadow(node.name, node, "Async Function Declaration")
        
        # Enter function scope
        self.scope_stack.append(f"async def {node.name}")
        
        # Check function arguments
        for arg in node.args.args:
            self.register_shadow(arg.arg, arg, "Function Parameter")
        for arg in node.args.kwonlyargs:
            self.register_shadow(arg.arg, arg, "Function Parameter")
        if node.args.vararg:
            self.register_shadow(node.args.vararg.arg, node.args.vararg, "Function Parameter")
        if node.args.kwarg:
            self.register_shadow(node.args.kwarg.arg, node.args.kwarg, "Function Parameter")

        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check class name itself
        self.register_shadow(node.name, node, "Class Declaration")
        
        # Enter class scope
        self.scope_stack.append(f"class {node.name}")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import):
        # Check aliased or standard imports (e.g. import id)
        for alias in node.names:
            imported_name = alias.asname or alias.name.split('.')[0]
            self.register_shadow(imported_name, node, "Module Import")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # Check imported items (e.g. from module import id)
        for alias in node.names:
            imported_name = alias.asname or alias.name
            self.register_shadow(imported_name, node, "From Import")
        self.generic_visit(node)


def scan_file(filepath: str) -> List[Dict[str, any]]:
    """Parses a Python file and returns a list of shadowed builtins."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        
        tree = ast.parse(code, filename=filepath)
        visitor = BuiltinShadowVisitor(filepath)
        visitor.visit(tree)
        return visitor.shadows
    except SyntaxError as e:
        print(color_text(f"Syntax Error in '{filepath}': {str(e)}", COLOR_RED), file=sys.stderr)
        return []
    except Exception as e:
        print(color_text(f"Failed to scan '{filepath}': {str(e)}", COLOR_RED), file=sys.stderr)
        return []


def get_all_python_files(paths: List[str], recursive: bool, excludes: Set[str]) -> List[str]:
    """Resolves inputs to a list of Python files."""
    py_files = []
    
    for path in paths:
        if not os.path.exists(path):
            print(color_text(f"Warning: Path '{path}' does not exist.", COLOR_YELLOW), file=sys.stderr)
            continue
            
        if os.path.isfile(path):
            if path.endswith(".py"):
                py_files.append(path)
        elif os.path.isdir(path):
            if recursive:
                for root, _, files in os.walk(path):
                    # Check exclusions
                    if any(exclude in root for exclude in excludes):
                        continue
                    for file in files:
                        if file.endswith(".py"):
                            full_path = os.path.join(root, file)
                            if not any(ex in full_path for ex in excludes):
                                py_files.append(full_path)
            else:
                for file in os.listdir(path):
                    full_path = os.path.join(path, file)
                    if os.path.isfile(full_path) and file.endswith(".py"):
                        if not any(ex in full_path for ex in excludes):
                            py_files.append(full_path)
                            
    return py_files


def main():
    parser = argparse.ArgumentParser(
        description="Scan Python source files for variables, parameters, classes, "
                    "or imports that shadow built-in Python names."
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to scan (default: current directory)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively scan folders")
    parser.add_argument("-e", "--exclude", default="", help="Comma-separated strings of path parts to exclude (e.g. .venv,tests)")
    
    args = parser.parse_args()
    
    excludes = {x.strip() for x in args.exclude.split(",") if x.strip()}
    excludes.add(".git")
    excludes.add("__pycache__")
    excludes.add(".venv")
    excludes.add("venv")
    excludes.add(".agents")
    excludes.add(".gemini")

    py_files = get_all_python_files(args.paths, args.recursive, excludes)
    
    if not py_files:
        print(color_text("No Python files found to scan.", COLOR_YELLOW))
        sys.exit(0)

    print(color_text(f"Scanning {len(py_files)} Python file(s) for builtin namespace shadowing...\n", COLOR_CYAN))
    
    total_shadows = 0
    files_with_shadows = 0
    
    for filepath in sorted(py_files):
        # Show clean path relative to CWD if possible
        display_path = os.path.relpath(filepath)
        shadows = scan_file(filepath)
        
        if shadows:
            files_with_shadows += 1
            total_shadows += len(shadows)
            print(f"File: {color_text(display_path, COLOR_BOLD)}")
            for shadow in shadows:
                loc = f"L{shadow['line']}:{shadow['col']}"
                name_colored = color_text(shadow['name'], COLOR_RED)
                type_colored = color_text(shadow['type'], COLOR_YELLOW)
                scope_colored = color_text(shadow['scope'], COLOR_CYAN)
                
                print(f"  [{loc}] Shadows built-in {name_colored} in {scope_colored} ({type_colored})")
            print()

    # Print summary report
    print(color_text("=== Builtin Shadowing Audit Report ===", COLOR_BOLD))
    print(f"Files Scanned      : {len(py_files)}")
    print(f"Files with Shadows : {files_with_shadows}")
    print(f"Total Shadow Cases : {color_text(str(total_shadows), COLOR_RED if total_shadows > 0 else COLOR_GREEN)}")
    
    if total_shadows > 0:
        print(color_text("\n[Suggestion] Consider renaming variables, parameters, or functions to avoid "
                         "shadowing Python built-ins. For example, use 'id_' or 'item_id' instead of 'id'.", COLOR_YELLOW))
        sys.exit(1)
    else:
        print(color_text("\n✓ Clean Namespace! No builtin name shadowing detected.", COLOR_GREEN))
        sys.exit(0)


if __name__ == "__main__":
    main()
