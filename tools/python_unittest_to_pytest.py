#!/usr/bin/env python3
"""
Python Unittest to Pytest Converter
An AST-based refactoring utility to migrate legacy unittest-style test cases
(classes inheriting from unittest.TestCase) and self.assertXXX calls to modern pytest style.
"""

import os
import sys
import ast
import argparse


class UnittestToPytestTransformer(ast.NodeTransformer):
    """AST NodeTransformer to rewrite unittest style tests to pytest style."""

    def __init__(self):
        super().__init__()
        self.transformed_any = False

    def visit_ClassDef(self, node):
        # 1. Strip unittest.TestCase inheritance
        is_testcase = False
        new_bases = []
        for base in node.bases:
            is_case = False
            # Check for Name 'TestCase'
            if isinstance(base, ast.Name) and base.id == 'TestCase':
                is_case = True
            # Check for Attribute 'unittest.TestCase'
            elif isinstance(base, ast.Attribute) and base.attr == 'TestCase':
                if isinstance(base.value, ast.Name) and base.value.id == 'unittest':
                    is_case = True
            
            if is_case:
                is_testcase = True
            else:
                new_bases.append(base)

        if is_testcase:
            node.bases = new_bases
            self.transformed_any = True
            
            # 2. Rename setUp/tearDown to setup_method/teardown_method
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == 'setUp':
                        item.name = 'setup_method'
                    elif item.name == 'tearDown':
                        item.name = 'teardown_method'
                    elif item.name == 'setUpClass':
                        item.name = 'setup_class'
                    elif item.name == 'tearDownClass':
                        item.name = 'teardown_class'
                        
        return self.generic_visit(node)

    def visit_Call(self, node):
        # Convert self.assertXXX(...) assertions
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
            method_name = node.func.attr
            if method_name.startswith('assert'):
                new_node = self.transform_assertion(method_name, node.args)
                if new_node:
                    self.transformed_any = True
                    return new_node
        return self.generic_visit(node)

    def visit_With(self, node):
        # Convert with self.assertRaises(Error): to with pytest.raises(Error):
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
                if isinstance(expr.func.value, ast.Name) and expr.func.value.id == 'self':
                    if expr.func.attr == 'assertRaises':
                        expr.func = ast.Attribute(
                            value=ast.Name(id='pytest', ctx=ast.Load()),
                            attr='raises',
                            ctx=ast.Load()
                        )
                        self.transformed_any = True
        return self.generic_visit(node)

    def transform_assertion(self, method, args):
        """Converts unittest assert calls into plain AST Assert nodes."""
        # Mapping assertion methods
        if method == 'assertEqual' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.Eq()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        elif method == 'assertNotEqual' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.NotEq()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        elif method == 'assertTrue' and len(args) >= 1:
            return ast.Assert(
                test=args[0],
                msg=args[1] if len(args) >= 2 else None
            )
        elif method == 'assertFalse' and len(args) >= 1:
            return ast.Assert(
                test=ast.UnaryOp(op=ast.Not(), operand=args[0]),
                msg=args[1] if len(args) >= 2 else None
            )
        elif method == 'assertIsNone' and len(args) >= 1:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.Is()], comparators=[ast.Constant(value=None)]),
                msg=args[1] if len(args) >= 2 else None
            )
        elif method == 'assertIsNotNone' and len(args) >= 1:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.IsNot()], comparators=[ast.Constant(value=None)]),
                msg=args[1] if len(args) >= 2 else None
            )
        elif method == 'assertIn' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.In()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        elif method == 'assertNotIn' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.NotIn()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        elif method == 'assertIs' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.Is()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        elif method == 'assertIsNot' and len(args) >= 2:
            return ast.Assert(
                test=ast.Compare(left=args[0], ops=[ast.IsNot()], comparators=[args[1]]),
                msg=args[2] if len(args) >= 3 else None
            )
        return None


def convert_unittest_to_pytest(code_str):
    """Transforms unittest syntax in Python code string to pytest syntax."""
    parsed_ast = ast.parse(code_str)
    
    # Check if pytest is already imported
    has_pytest_import = False
    for node in parsed_ast.body:
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name == 'pytest':
                    has_pytest_import = True
        elif isinstance(node, ast.ImportFrom) and node.module == 'pytest':
            has_pytest_import = True

    transformer = UnittestToPytestTransformer()
    modified_ast = transformer.visit(parsed_ast)
    
    # Prepend 'import pytest' to the AST if we made changes and it's not imported
    if transformer.transformed_any and not has_pytest_import:
        import_pytest_node = ast.Import(names=[ast.alias(name='pytest', asname=None)])
        modified_ast.body.insert(0, import_pytest_node)

    ast.fix_missing_locations(modified_ast)
    
    if hasattr(ast, 'unparse'):
        return ast.unparse(modified_ast)
    else:
        raise RuntimeError("Python 3.9 or higher is required to use ast.unparse().")


def process_file(file_path, output_path=None, in_place=False, dry_run=False):
    """Processes a single test file, rewriting assertions and TestCase classes."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        converted_content = convert_unittest_to_pytest(content)

        if dry_run:
            print(f"--- Dry Run: {file_path} ---")
            print(converted_content[:500])
            if len(converted_content) > 500:
                print("... [truncated] ...")
            print("-------------------------")
            return True

        target_path = file_path if in_place else (output_path or file_path + ".pytest.py")
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(converted_content)
        
        print(f"Migrated: {file_path} -> {target_path}")
        return True
    except Exception as e:
        sys.stderr.write(f"Error migrating {file_path}: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Python Unittest to Pytest Converter - Migrates legacy test cases to modern pytest style."
    )
    parser.add_argument(
        "path",
        help="Path to Python test file or directory to convert"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save converted file (defaults to file_path.pytest.py). Ignored for directory/in-place runs."
    )
    parser.add_argument(
        "-i", "--in-place",
        action="store_true",
        help="Modify Python file(s) in-place (overwrites original file)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print migrated code preview without writing changes to disk"
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
            dry_run=args.dry_run
        )
    elif os.path.isdir(target_path):
        if not args.in_place and not args.dry_run:
            sys.stderr.write("For directory conversion, --in-place or --dry-run is required.\n")
            sys.exit(1)
            
        success_count = 0
        file_count = 0
        
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith('.py') and (file.startswith('test_') or file.endswith('_test.py')):
                    file_count += 1
                    full_path = os.path.join(root, file)
                    if process_file(
                        full_path,
                        in_place=True,
                        dry_run=args.dry_run
                    ):
                        success_count += 1
                        
        print(f"Processed {success_count}/{file_count} test files successfully.")


if __name__ == "__main__":
    main()
