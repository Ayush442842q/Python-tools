#!/usr/bin/env python3
"""
Python Function Call Graph Generator
Uses Python's AST module to parse Python files, map function/method call hierarchies,
and output them as a text hierarchy or a Mermaid.js flowchart.

Usage:
    python tools/python_call_graph.py my_script.py
    python tools/python_call_graph.py src/ --mermaid
"""

import argparse
import ast
import os
import sys
from typing import Dict, List, Set, Tuple

# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


class CallGraphVisitor(ast.NodeVisitor):
    """AST Visitor to extract function definitions and calls."""
    
    def __init__(self):
        # current_function_stack keeps track of which function we are currently inside
        self.current_function = None
        self.class_context = None
        # function_name -> set of function_names called
        self.calls: Dict[str, Set[str]] = {}
        # List of all discovered local functions
        self.defined_functions: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.class_context
        self.class_context = node.name
        self.generic_visit(node)
        self.class_context = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = node.name
        if self.class_context:
            qualified_name = f"{self.class_context}.{func_name}"
        else:
            qualified_name = func_name
            
        self.defined_functions.add(qualified_name)
        self.calls.setdefault(qualified_name, set())
        
        old_func = self.current_function
        self.current_function = qualified_name
        
        self.generic_visit(node)
        
        self.current_function = old_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Handle async functions exactly like regular ones
        func_name = node.name
        if self.class_context:
            qualified_name = f"{self.class_context}.{func_name}"
        else:
            qualified_name = func_name
            
        self.defined_functions.add(qualified_name)
        self.calls.setdefault(qualified_name, set())
        
        old_func = self.current_function
        self.current_function = qualified_name
        self.generic_visit(node)
        self.current_function = old_func

    def visit_Call(self, node: ast.Call):
        if self.current_function:
            called_name = self._get_call_name(node.func)
            if called_name:
                self.calls[self.current_function].add(called_name)
        self.generic_visit(node)

    def _get_call_name(self, node: ast.AST) -> str:
        """Resolve call node to function name string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Check if it is self.method() or class.method()
            value_name = self._get_call_name(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
            return node.attr
        return ""


def parse_file(file_path: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Parses a single Python file to extract call relationships."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=file_path)
    except Exception as e:
        print_colored(f"[!] Error parsing '{file_path}': {e}", COLOR_FAIL)
        return set(), {}
        
    visitor = CallGraphVisitor()
    visitor.visit(tree)
    return visitor.defined_functions, visitor.calls


def build_graph(path: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Walks the path and builds a unified call graph."""
    all_defs: Set[str] = set()
    all_calls: Dict[str, Set[str]] = {}
    
    if os.path.isfile(path):
        if path.endswith(".py"):
            return parse_file(path)
        return set(), {}
        
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                defs, calls = parse_file(full_path)
                all_defs.update(defs)
                for func, targets in calls.items():
                    all_calls.setdefault(func, set()).update(targets)
                    
    # Clean targets to only include local defined functions or methods
    cleaned_calls: Dict[str, Set[str]] = {}
    for func, targets in all_calls.items():
        cleaned_targets = set()
        for t in targets:
            # Match direct names or class methods
            # e.g., if target is 'self.my_method', translate to 'ClassName.my_method'
            if "." in func and t.startswith("self."):
                class_name = func.split(".")[0]
                resolved = f"{class_name}.{t.split('.')[1]}"
                if resolved in all_defs:
                    cleaned_targets.add(resolved)
            elif t in all_defs:
                cleaned_targets.add(t)
            elif "." in t:
                # Class method calls like ClassName.method or instance.method
                parts = t.split(".")
                # Check matches on method name if we don't know the exact class
                matching_defs = [d for d in all_defs if d.endswith(f".{parts[-1]}")]
                if len(matching_defs) == 1:
                    cleaned_targets.add(matching_defs[0])
                    
        cleaned_calls[func] = cleaned_targets
        
    return all_defs, cleaned_calls


def render_tree(func: str, calls: Dict[str, Set[str]], visited: Set[str], depth: int = 0):
    """Recursively prints calls as an indentation-based tree."""
    indent = "  " * depth
    if func in visited:
        print(f"{indent}--> {func} (circular)")
        return
        
    visited.add(func)
    print(f"{indent}{func}")
    
    targets = calls.get(func, set())
    for target in sorted(targets):
        render_tree(target, calls, visited.copy(), depth + 1)


def generate_mermaid(defs: Set[str], calls: Dict[str, Set[str]]) -> str:
    """Generates Mermaid.js flowchart code."""
    lines = ["graph TD"]
    
    # Map functions to clean IDs
    func_ids = {f: f"func_{idx}" for idx, f in enumerate(sorted(defs))}
    
    # Group class methods in subgraphs
    classes: Dict[str, List[str]] = {}
    globals_list: List[str] = []
    
    for func in sorted(defs):
        if "." in func:
            class_name = func.split(".")[0]
            classes.setdefault(class_name, []).append(func)
        else:
            globals_list.append(func)
            
    # Subgraphs for classes
    for class_name, methods in classes.items():
        lines.append(f"\n    subgraph class_{class_name} [Class: {class_name}]")
        for m in methods:
            lines.append(f'        {func_ids[m]}["{m.split(".")[1]}"]')
        lines.append("    end")
        
    # Globals
    if globals_list:
        lines.append("\n    %% Global Functions")
        for f in globals_list:
            lines.append(f'    {func_ids[f]}["{f}"]')
            
    # Edges
    lines.append("\n    %% Calls")
    for src, dests in sorted(calls.items()):
        for dest in sorted(dests):
            if src in func_ids and dest in func_ids:
                lines.append(f"    {func_ids[src]} --> {func_ids[dest]}")
                
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Python Function Call Graph Generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", nargs="?", default=".", help="File or folder path to parse (default: current directory)")
    parser.add_argument("--mermaid", "-m", action="store_true", help="Output a Mermaid.js diagram definition")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print_colored(f"[!] Path does not exist: {args.path}", COLOR_FAIL)
        sys.exit(1)
        
    defs, calls = build_graph(args.path)
    
    if not defs:
        print_colored("[*] No python function definitions found.", COLOR_WARNING)
        sys.exit(0)
        
    if args.mermaid:
        mermaid_code = generate_mermaid(defs, calls)
        print(mermaid_code)
    else:
        print_colored(f"\n{COLOR_BOLD}=== Python Call Graph (Hierarchy) ==={COLOR_END}", COLOR_HEADER)
        # Find root functions (functions that are not called by any other function)
        called_functions = set()
        for targets in calls.values():
            called_functions.update(targets)
            
        roots = defs - called_functions
        
        # If no roots (everything is recursive/cyclic), use all defs
        display_roots = sorted(roots) if roots else sorted(defs)
        
        for root in display_roots:
            render_tree(root, calls, set())
            print()
            
        # Isolated / Dead Code detection helper
        unused = roots - {f for f, targets in calls.items() if targets}
        if unused and roots:
            print_colored(f"{COLOR_BOLD}=== Unused/Isolated Functions (Potential Dead Code) ==={COLOR_END}", COLOR_WARNING)
            for f in sorted(unused):
                print(f"  - {f}")


if __name__ == "__main__":
    main()
