#!/usr/bin/env python3
"""
Python Type Hint Remover
An AST-based code refactoring utility to strip type annotations and typing imports
from Python source files, producing clean, annotation-free code.
"""

import os
import sys
import ast
import argparse


class TypeHintStripper(ast.NodeTransformer):
    """AST NodeTransformer that removes type annotations and type comments."""
    
    def __init__(self, remove_typing_imports=False):
        super().__init__()
        self.remove_typing_imports = remove_typing_imports

    def visit_FunctionDef(self, node):
        # Remove return type annotation
        node.returns = None
        # Remove type comment from function header
        if hasattr(node, 'type_comment'):
            node.type_comment = None

        # Remove annotations from all arguments
        for arg in node.args.args:
            arg.annotation = None
            if hasattr(arg, 'type_comment'):
                arg.type_comment = None

        for arg in node.args.kwonlyargs:
            arg.annotation = None
            if hasattr(arg, 'type_comment'):
                arg.type_comment = None

        if node.args.vararg:
            node.args.vararg.annotation = None
            if hasattr(node.args.vararg, 'type_comment'):
                node.args.vararg.type_comment = None

        if node.args.kwarg:
            node.args.kwarg.annotation = None
            if hasattr(node.args.kwarg, 'type_comment'):
                node.args.kwarg.type_comment = None

        # Continue traversing function body
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_AnnAssign(self, node):
        """Transform annotated assignments (x: int = 5) to standard assignments (x = 5)."""
        # AnnAssign represents x: int = 5 or x: int
        if node.value:
            # Convert to standard Assign
            # ast.Assign requires targets (list of targets) and a value
            new_node = ast.Assign(
                targets=[node.target],
                value=node.value,
                lineno=node.lineno,
                col_offset=node.col_offset
            )
            # Set type comment to None just in case
            if hasattr(new_node, 'type_comment'):
                new_node.type_comment = None
            return new_node
        else:
            # x: int with no value is just a type declaration. Remove it.
            return None

    def visit_Assign(self, node):
        # Remove type comments on standard assignments
        if hasattr(node, 'type_comment'):
            node.type_comment = None
        return self.generic_visit(node)

    def visit_Import(self, node):
        """Remove 'import typing' if remove_typing_imports is enabled."""
        if not self.remove_typing_imports:
            return node
        
        # Filter names
        new_names = [alias for alias in node.names if alias.name != 'typing']
        if not new_names:
            return None  # Remove entire import statement
        
        node.names = new_names
        return node

    def visit_ImportFrom(self, node):
        """Remove 'from typing import ...' if remove_typing_imports is enabled."""
        if not self.remove_typing_imports:
            return node
        
        if node.module == 'typing':
            return None  # Remove entire import statement
        
        return node


def remove_type_hints_from_str(code_str, remove_imports=False):
    """Parses Python code, strips type hints, and unparses back to code string."""
    parsed_ast = ast.parse(code_str)
    
    transformer = TypeHintStripper(remove_typing_imports=remove_imports)
    modified_ast = transformer.visit(parsed_ast)
    ast.fix_missing_locations(modified_ast)
    
    # ast.unparse is available in Python 3.9+
    if hasattr(ast, 'unparse'):
        return ast.unparse(modified_ast)
    else:
        raise RuntimeError("Python 3.9 or higher is required to use ast.unparse().")


def process_file(file_path, output_path=None, in_place=False, remove_imports=False, dry_run=False):
    """Processes a single Python file, removing type hints."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        stripped_content = remove_type_hints_from_str(content, remove_imports=remove_imports)

        if dry_run:
            print(f"--- Dry Run: {file_path} ---")
            print(stripped_content[:500])
            if len(stripped_content) > 500:
                print("... [truncated] ...")
            print("-------------------------")
            return True

        target_path = file_path if in_place else (output_path or file_path + ".clean.py")
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(stripped_content)
        
        print(f"Processed: {file_path} -> {target_path}")
        return True
    except Exception as e:
        sys.stderr.write(f"Error processing {file_path}: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Python Type Hint Remover - Strips type annotations from Python code."
    )
    parser.add_argument(
        "path",
        help="Path to Python file or directory to process"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save output file (defaults to file_path.clean.py). Ignored for directory/in-place runs."
    )
    parser.add_argument(
        "-i", "--in-place",
        action="store_true",
        help="Modify Python file(s) in-place (overwrites original file)"
    )
    parser.add_argument(
        "--remove-imports",
        action="store_true",
        help="Attempt to remove 'typing' module import statements"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stripped code preview without writing changes to disk"
    )

    args = parser.parse_args()
    target_path = args.path

    if not os.path.exists(target_path):
        sys.stderr.write(f"Path does not exist: {target_path}\n")
        sys.exit(1)

    if os.path.isfile(target_path):
        process_file(
            target_path,
            output_path=args.output,
            in_place=args.in_place,
            remove_imports=args.remove_imports,
            dry_run=args.dry_run
        )
    elif os.path.isdir(target_path):
        if not args.in_place and not args.dry_run:
            sys.stderr.write("For directory processing, --in-place or --dry-run is required.\n")
            sys.exit(1)
            
        success_count = 0
        file_count = 0
        
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith('.py'):
                    file_count += 1
                    full_path = os.path.join(root, file)
                    if process_file(
                        full_path,
                        in_place=True,
                        remove_imports=args.remove_imports,
                        dry_run=args.dry_run
                    ):
                        success_count += 1
                        
        print(f"Processed {success_count}/{file_count} Python files successfully.")


if __name__ == "__main__":
    main()
