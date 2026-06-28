#!/usr/bin/env python3
"""
Python Docstring Generator
An AST-based command-line utility that scans Python source files, identifies
functions, methods, and classes lacking docstrings, and generates boilerplate
docstrings (Google style) with parameter types, return values, and exceptions.
"""

import argparse
import ast
import difflib
import sys

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91}m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

def print_color(text, color):
    """Print text with ANSI color if supported."""
    print(f"{color}{text}{COLOR_RESET}")

class DocstringFinder(ast.NodeVisitor):
    """AST Visitor to find functions and classes lacking docstrings."""
    def __init__(self):
        self.missing = []

    def visit_FunctionDef(self, node):
        self._check_node(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_node(node, "function")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_node(node, "class")
        self.generic_visit(node)

    def _check_node(self, node, node_type):
        docstring = ast.get_docstring(node)
        if not docstring:
            self.missing.append((node, node_type))

def analyze_function(node):
    """Analyze a function AST node to extract args, returns, and raises."""
    args_info = []
    # Positional and keyword args
    for arg in node.args.args:
        arg_name = arg.arg
        if arg_name == 'self' or arg_name == 'cls':
            continue
        type_hint = None
        if arg.annotation:
            # Simple conversion of annotation to text representation
            type_hint = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else "any"
        args_info.append((arg_name, type_hint))

    # *args and **kwargs
    if node.args.vararg:
        args_info.append((f"*{node.args.vararg.arg}", "any"))
    if node.args.kwarg:
        args_info.append((f"**{node.args.kwarg.arg}", "any"))

    # Exceptions raised
    raised_exceptions = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Raise):
            if child.exc:
                if isinstance(child.exc, ast.Name):
                    raised_exceptions.add(child.exc.id)
                elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                    raised_exceptions.add(child.exc.func.id)
                else:
                    raised_exceptions.add("Exception")
            else:
                raised_exceptions.add("Exception")

    # Return type hint
    return_type = None
    if node.returns:
        return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else None
    else:
        # Check if function has return statements returning a value
        has_val = False
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                has_val = True
                break
        if has_val:
            return_type = "any"

    return args_info, list(raised_exceptions), return_type

def generate_docstring(node, node_type, indent):
    """Generate Google-style docstring text with proper indentation."""
    lines = []
    lines.append('"""')
    lines.append(f"Description of {node.name}.")
    
    if node_type == "function":
        args, raises, returns = analyze_function(node)
        if args:
            lines.append("")
            lines.append("Args:")
            for arg_name, arg_type in args:
                type_str = f" ({arg_type})" if arg_type else ""
                lines.append(f"    {arg_name}{type_str}: Description of parameter '{arg_name}'.")
        
        if returns:
            lines.append("")
            lines.append("Returns:")
            type_str = f" {returns}" if returns != "any" else " any"
            lines.append(f"   {type_str}: Description of return value.")
            
        if raises:
            lines.append("")
            lines.append("Raises:")
            for exc in sorted(raises):
                lines.append(f"    {exc}: Description of when this is raised.")
                
    lines.append('"""')
    
    # Apply indentation
    indented_lines = []
    for i, line in enumerate(lines):
        if i == 0:
            indented_lines.append(line)  # Initial line matches the body's starting line indentation
        else:
            indented_lines.append(indent + line if line else "")
            
    return "\n".join(indented_lines)

def process_file(filepath, write=False):
    """Scans and optionally inserts docstrings into a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
            original_lines = source.splitlines()
    except Exception as e:
        print_color(f"[-] Error reading file {filepath}: {e}", COLOR_RED)
        return False

    try:
        tree = ast.parse(source)
    except Exception as e:
        print_color(f"[-] Syntax error parsing AST for {filepath}: {e}", COLOR_RED)
        return False

    finder = DocstringFinder()
    finder.visit(tree)

    if not finder.missing:
        print(f"[+] All classes and functions in {filepath} already have docstrings.")
        return True

    # We need to insert docstrings from bottom to top so that line numbers don't shift
    modified_lines = list(original_lines)
    finder.missing.sort(key=lambda x: x[0].lineno, reverse=True)

    for node, node_type in finder.missing:
        # Determine insertion line:
        # We insert right before the first statement in the body of the class/function.
        if not node.body:
            continue
        first_body_node = node.body[0]
        insert_idx = first_body_node.lineno - 1  # 0-indexed line index
        
        # Determine indentation of the body statement to align docstring
        orig_line = original_lines[insert_idx]
        indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]
        
        doc = generate_docstring(node, node_type, indent)
        
        # Insert docstring
        modified_lines.insert(insert_idx, indent + doc)
        print(f"[+] Generated docstring template for {node_type} '{node.name}' at line {node.lineno}")

    new_source = "\n".join(modified_lines) + ("\n" if source.endswith("\n") else "")

    # Print diff
    diff = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"{filepath} (original)",
        tofile=f"{filepath} (with docstrings)",
        lineterm=""
    ))
    
    if diff:
        print_color("\n[*] Unified Diff of changes:", COLOR_BOLD + COLOR_BLUE)
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                print_color(line, COLOR_GREEN)
            elif line.startswith("-") and not line.startswith("---"):
                print_color(line, COLOR_RED)
            elif line.startswith("^"):
                print_color(line, COLOR_YELLOW)
            else:
                print(line)

    if write:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_source)
            print_color(f"\n[+] Successfully updated {filepath} in-place.", COLOR_GREEN)
        except Exception as e:
            print_color(f"[-] Failed to write updates to {filepath}: {e}", COLOR_RED)
            return False
    else:
        print_color("\n[!] Run with --write to apply changes in-place.", COLOR_YELLOW)

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Python Docstring Generator - Automatically generate docstring templates using AST.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Python source file to process")
    parser.add_argument("-w", "--write", action="store_true", help="Write changes directly back to the file")

    args = parser.parse_args()
    process_file(args.file, args.write)
    return 0

if __name__ == "__main__":
    sys.exit(main())
