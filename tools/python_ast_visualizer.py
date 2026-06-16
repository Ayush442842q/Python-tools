#!/usr/bin/env python3
"""
Python AST Visualizer

Parses a Python source file and renders its Abstract Syntax Tree (AST) in a 
structured ASCII tree or exports it as a Mermaid.js diagram.
Helps developers inspect code structure, find imports, classes, functions, and variables.

Usage:
    python tools/python_ast_visualizer.py tools/hello.py
    python tools/python_ast_visualizer.py my_script.py --depth 3
    python tools/python_ast_visualizer.py my_script.py --mermaid
"""

import argparse
import ast
import os
import sys
from typing import List, Any, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def get_node_details(node: ast.AST) -> str:
    """Extracts interesting values from AST nodes for display."""
    if isinstance(node, ast.FunctionDef):
        return f"name='{node.name}'"
    elif isinstance(node, ast.ClassDef):
        return f"name='{node.name}'"
    elif isinstance(node, ast.Name):
        return f"id='{node.id}'"
    elif isinstance(node, ast.Constant):
        val = node.value
        # Truncate representation if too long
        val_repr = repr(val)
        if len(val_repr) > 25:
            val_repr = val_repr[:22] + "..."
        return f"value={val_repr}"
    elif isinstance(node, ast.Attribute):
        return f"attr='{node.attr}'"
    elif isinstance(node, ast.alias):
        alias_str = f"name='{node.name}'"
        if node.asname:
            alias_str += f" as='{node.asname}'"
        return alias_str
    elif isinstance(node, ast.arg):
        arg_str = f"arg='{node.arg}'"
        if node.annotation:
            arg_str += " (annotated)"
        return arg_str
    elif isinstance(node, ast.Import):
        return f"names=[{', '.join(a.name for a in node.names)}]"
    elif isinstance(node, ast.ImportFrom):
        return f"module='{node.module}', names=[{', '.join(a.name for a in node.names)}]"
    return ""

def color_node_name(name: str) -> str:
    """Colors node names by category for readability."""
    if not supports_color():
        return name
        
    structural = {"Module", "ClassDef", "FunctionDef", "arguments", "arg"}
    statements = {"Assign", "Expr", "Return", "If", "For", "While", "Import", "ImportFrom", "Pass", "With"}
    expressions = {"Call", "Name", "Attribute", "Constant", "BinOp", "Compare", "List", "Dict", "Subscript"}
    
    if name in structural:
        return color_text(name, COLOR_GREEN + COLOR_BOLD)
    elif name in statements:
        return color_text(name, COLOR_CYAN)
    elif name in expressions:
        return color_text(name, COLOR_YELLOW)
    return name

def supports_unicode() -> bool:
    """Checks if standard output can encode Unicode tree-drawing characters."""
    try:
        "└── │".encode(sys.stdout.encoding or 'ascii')
        return True
    except Exception:
        return False

def render_ascii_tree(node: ast.AST, max_depth: int, show_lines: bool, 
                      depth: int = 0, prefix: str = "", is_last: bool = True):
    """Recursively prints the AST node structure in ASCII format."""
    unicode_ok = supports_unicode()
    conn_last = "└── " if unicode_ok else "`-- "
    conn_mid = "├── " if unicode_ok else "|-- "
    pipe_char = "│   " if unicode_ok else "|   "
    
    if depth > max_depth:
        # If we exceed depth, draw a truncated line
        connector = conn_last if is_last else conn_mid
        print(f"{prefix}{connector}{color_text('...', COLOR_DIM)}")
        return
        
    node_name = node.__class__.__name__
    details = get_node_details(node)
    
    # Optional line number prefix
    line_prefix = ""
    if show_lines and hasattr(node, 'lineno'):
        line_prefix = color_text(f"L{node.lineno:<3} ", COLOR_DIM)
        
    connector = conn_last if is_last else conn_mid
    detail_str = color_text(f" ({details})", COLOR_DIM) if details else ""
    
    print(f"{line_prefix}{prefix}{connector}{color_node_name(node_name)}{detail_str}")
    
    # Find child nodes
    children = list(ast.iter_child_nodes(node))
    new_prefix = prefix + ("    " if is_last else pipe_char)
    
    for i, child in enumerate(children):
        child_is_last = (i == len(children) - 1)
        render_ascii_tree(child, max_depth, show_lines, depth + 1, new_prefix, child_is_last)


def generate_mermaid(node: ast.AST, lines: List[str], max_depth: int, depth: int = 0, parent_id: Optional[str] = None):
    """Recursively populates lines array with Mermaid flowchart nodes and relationships."""
    if depth > max_depth:
        return
        
    node_id = f"ast_{id(node)}"
    node_name = node.__class__.__name__
    details = get_node_details(node)
    
    # Replace quotes and brackets to keep Mermaid parser happy
    clean_details = details.replace('"', "'").replace('[', '(').replace(']', ')')
    label = f"{node_name}\\n{clean_details}" if clean_details else node_name
    
    # Node definition
    lines.append(f'    {node_id}["{label}"]')
    
    # Link to parent
    if parent_id:
        lines.append(f"    {parent_id} --> {node_id}")
        
    for child in ast.iter_child_nodes(node):
        generate_mermaid(child, lines, max_depth, depth + 1, node_id)

def main():
    parser = argparse.ArgumentParser(
        description="Python AST Visualizer: View source code structure as an AST tree or Mermaid diagram.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("file", help="Python source file to parse")
    parser.add_argument("-d", "--depth", type=int, default=4, help="Maximum recursion depth to show (default: 4)")
    parser.add_argument("-l", "--lines", action="store_true", help="Display line numbers for statement nodes")
    parser.add_argument("-m", "--mermaid", action="store_true", help="Output a Mermaid.js diagram definition instead of ASCII")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(color_text(f"[-] File not found: {args.file}", COLOR_RED), file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            code = f.read()
            
        tree = ast.parse(code, filename=args.file)
    except Exception as e:
        print(color_text(f"[-] Parse error: {e}", COLOR_RED), file=sys.stderr)
        sys.exit(1)
        
    if args.mermaid:
        mermaid_lines = ["flowchart TD"]
        generate_mermaid(tree, mermaid_lines, args.depth)
        print("\n" + "\n".join(mermaid_lines) + "\n")
    else:
        print("\n" + color_text(f"AST for: {args.file} (Max Depth: {args.depth})", COLOR_BOLD + COLOR_CYAN))
        print(color_text("=" * 60, COLOR_DIM))
        render_ascii_tree(tree, args.depth, args.lines)
        print(color_text("=" * 60, COLOR_DIM))

if __name__ == "__main__":
    main()
