#!/usr/bin/env python3
"""
python_ast_grepper - Semantic Source Code Finder using Abstract Syntax Trees (AST)

This tool scans Python source files recursively and queries their structural AST
representation. It allows queries that are difficult or impossible to perform
using standard text-based regex tools (e.g. finding classes inheriting from a
particular class, functions with a specific decorator, or function calls passing
particular keyword arguments).

Query options:
  --decorator NAME     Find function definitions decorated with NAME
  --inherits NAME      Find class definitions inheriting from NAME
  --calls NAME         Find function calls to NAME
  --imports NAME       Find files importing module or member NAME
  --assigns NAME       Find assignments to target variable/attribute NAME

Usage:
    python tools/python_ast_grepper.py <path> [options]

Example:
    python tools/python_ast_grepper.py tools/ --inherits object
"""

import argparse
import ast
import os
import sys
from typing import List, Dict, Any, Tuple, Optional


class ASTQueryVisitor(ast.NodeVisitor):
    """Custom AST visitor to audit nodes matching specific criteria."""
    
    def __init__(self, query_params: Dict[str, Any]):
        self.query_params = query_params
        self.matches: List[Tuple[int, str, str]] = []  # (lineno, match_type, description)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check decorators
        target_decorator = self.query_params.get("decorator")
        if target_decorator:
            for decorator in node.decorator_list:
                name = self._get_decorator_name(decorator)
                if name == target_decorator:
                    self.matches.append((
                        node.lineno,
                        "decorator",
                        f"Function '{node.name}' is decorated with '@{target_decorator}'"
                    ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check base classes (inheritance)
        target_base = self.query_params.get("inherits")
        if target_base:
            for base in node.bases:
                name = self._get_node_name(base)
                if name == target_base:
                    self.matches.append((
                        node.lineno,
                        "inherits",
                        f"Class '{node.name}' inherits from '{target_base}'"
                    ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check function calls
        target_call = self.query_params.get("calls")
        if target_call:
            name = self._get_node_name(node.func)
            if name == target_call:
                self.matches.append((
                    node.lineno,
                    "calls",
                    f"Call to function '{target_call}'"
                ))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        # Check imports like "import foo, bar"
        target_import = self.query_params.get("imports")
        if target_import:
            for alias in node.names:
                if alias.name == target_import or alias.name.startswith(f"{target_import}."):
                    self.matches.append((
                        node.lineno,
                        "imports",
                        f"Imports module '{alias.name}'"
                    ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # Check imports like "from foo import bar"
        target_import = self.query_params.get("imports")
        if target_import:
            if node.module == target_import:
                self.matches.append((
                    node.lineno,
                    "imports",
                    f"Imports from module '{node.module}'"
                ))
            else:
                for alias in node.names:
                    if alias.name == target_import:
                        self.matches.append((
                            node.lineno,
                            "imports",
                            f"Imports member '{alias.name}' from module '{node.module}'"
                        ))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check assignments like "x = 42"
        target_assign = self.query_params.get("assigns")
        if target_assign:
            for target in node.targets:
                name = self._get_node_name(target)
                if name == target_assign:
                    self.matches.append((
                        node.lineno,
                        "assigns",
                        f"Variable/attribute '{target_assign}' is assigned a value"
                    ))
        self.generic_visit(node)

    def _get_node_name(self, node: ast.AST) -> Optional[str]:
        """Convert basic AST expressions like Name, Attribute to strings."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._get_node_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return None

    def _get_decorator_name(self, node: ast.AST) -> Optional[str]:
        """Resolve decorator names including attributes or calls."""
        if isinstance(node, ast.Call):
            return self._get_node_name(node.func)
        return self._get_node_name(node)


def scan_file(filepath: str, query_params: Dict[str, Any]) -> List[Tuple[int, str, str]]:
    """Parse python source and run AST Query Visitor."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
            
        tree = ast.parse(source, filename=filepath)
        visitor = ASTQueryVisitor(query_params)
        visitor.visit(tree)
        return visitor.matches
    except SyntaxError as se:
        # Silently skip syntax errors or report them if verbose
        return []
    except Exception as e:
        return []


def print_match(filepath: str, line_no: int, match_type: str, desc: str) -> None:
    """Print matching line details."""
    # Read the specific line of code
    code_line = ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if i == line_no:
                    code_line = line.strip()
                    break
    except Exception:
        pass
        
    color_blue = "\033[1;34m"
    color_green = "\033[1;32m"
    color_reset = "\033[0m"
    
    if not sys.stdout.isatty():
        color_blue = color_green = color_reset = ""
        
    print(f"{color_blue}{filepath}:{line_no}{color_reset} [{match_type}] - {desc}")
    if code_line:
        print(f"  {color_green}>{color_reset} {code_line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AST-Based Python Source Code Grepper",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", default=".", nargs="?", help="Directory or file path to scan")
    parser.add_argument("--decorator", help="Find functions decorated with specific decorator name")
    parser.add_argument("--inherits", help="Find classes inheriting from specific base class name")
    parser.add_argument("--calls", help="Find function calls matching target name")
    parser.add_argument("--imports", help="Find files importing specific module or member")
    parser.add_argument("--assigns", help="Find statements assigning a value to target name")
    
    args = parser.parse_args()
    
    # Pack parameters
    query_params = {
        "decorator": args.decorator,
        "inherits": args.inherits,
        "calls": args.calls,
        "imports": args.imports,
        "assigns": args.assigns
    }
    
    # Check that at least one query parameter is provided
    if not any(query_params.values()):
        parser.print_help()
        print("\n[!] Error: Please specify at least one query filter option (e.g., --inherits, --calls).", file=sys.stderr)
        return 1

    target_path = args.path
    if not os.path.exists(target_path):
        print(f"[!] Error: Path '{target_path}' does not exist.", file=sys.stderr)
        return 1

    total_matches = 0
    total_files = 0
    
    # Process files
    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            total_files += 1
            matches = scan_file(target_path, query_params)
            for lineno, mtype, desc in matches:
                print_match(target_path, lineno, mtype, desc)
                total_matches += 1
    else:
        for root, _, files in os.walk(target_path):
            # Skip hidden folders
            if any(part.startswith(".") for part in root.split(os.sep)):
                continue
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    total_files += 1
                    matches = scan_file(filepath, query_params)
                    for lineno, mtype, desc in matches:
                        print_match(filepath, lineno, mtype, desc)
                        total_matches += 1

    print()
    print(f"[*] Done. Scanned {total_files} file(s). Found {total_matches} matching AST construct(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
