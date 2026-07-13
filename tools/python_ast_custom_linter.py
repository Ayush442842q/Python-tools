#!/usr/bin/env python3
"""
python_ast_custom_linter - Custom rule-based static analysis linter using Python AST

Traverses Python source file trees and audits them against user-defined rules
configured in a JSON file, such as blocking specific function calls (e.g. print, eval),
prohibiting certain imports, enforcing naming patterns, checking argument limits,
and requiring class/function docstrings.

Usage:
    python tools/python_ast_custom_linter.py /path/to/codebase [options]

Example:
    python tools/python_ast_custom_linter.py my_project/ --generate-config
"""

import argparse
import ast
import json
import os
import sys
import re

DEFAULT_LINTER_CONFIG = {
    "forbidden_calls": ["print", "eval", "exec", "breakpoint"],
    "forbidden_imports": ["pickle", "urllib"],
    "enforce_naming": {
        "classes": "^[A-Z][a-zA-Z0-9]*$",      # PascalCase
        "functions": "^[a-z_][a-z0-9_]*$",     # snake_case
        "methods": "^[a-z_][a-z0-9_]*$"        # snake_case
    },
    "limits": {
        "max_function_arguments": 6,
        "max_function_lines": 100
    },
    "requirements": {
        "require_class_docstring": True,
        "require_function_docstring": False,
        "no_bare_except": True
    }
}


class CustomLinterVisitor(ast.NodeVisitor):
    def __init__(self, config, filename):
        self.config = config
        self.filename = filename
        self.violations = []
        
        # Precompile naming regexes
        self.naming_regexes = {}
        for key, pattern in self.config.get("enforce_naming", {}).items():
            if pattern:
                try:
                    self.naming_regexes[key] = re.compile(pattern)
                except re.error as e:
                    print(f"Warning: Invalid naming regex pattern for '{key}': {e}")

    def add_violation(self, node, code, message):
        """Record a linter violation with location info."""
        self.violations.append({
            "file": self.filename,
            "line": node.lineno,
            "col": node.col_offset,
            "code": code,
            "message": message
        })

    def visit_Import(self, node):
        """Check for forbidden module imports."""
        forbidden_imports = self.config.get("forbidden_imports", [])
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module in forbidden_imports:
                self.add_violation(
                    node,
                    "E001",
                    f"Forbidden import: '{alias.name}' is prohibited by configuration"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Check for forbidden from-imports."""
        forbidden_imports = self.config.get("forbidden_imports", [])
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module in forbidden_imports:
                self.add_violation(
                    node,
                    "E001",
                    f"Forbidden import: 'from {node.module} ...' is prohibited by configuration"
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        """Check for forbidden function/method calls."""
        forbidden_calls = self.config.get("forbidden_calls", [])
        func_name = None
        
        # simple call like print()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        # method call like obj.func()
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            
        if func_name and func_name in forbidden_calls:
            self.add_violation(
                node,
                "E002",
                f"Forbidden call: call to function/method '{func_name}' is blocked"
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Validate class structure (docstrings, naming)."""
        requirements = self.config.get("requirements", {})
        
        # 1. Check docstrings
        if requirements.get("require_class_docstring"):
            docstring = ast.get_docstring(node)
            if not docstring:
                self.add_violation(
                    node,
                    "E003",
                    f"Missing docstring: Class '{node.name}' has no docstring definition"
                )

        # 2. Check naming convention
        class_regex = self.naming_regexes.get("classes")
        if class_regex and not class_regex.match(node.name):
            self.add_violation(
                node,
                "E004",
                f"Naming convention mismatch: Class '{node.name}' does not match pattern '{class_regex.pattern}'"
            )
            
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Validate function and method definitions."""
        requirements = self.config.get("requirements", {})
        limits = self.config.get("limits", {})
        
        # Determine if it is a method or standard function
        # A simple check: if parent node is class definition, it's a method
        # (Though in nested functions this might differ, it suffices for standard linting)
        is_method = False
        
        # 1. Check docstrings
        if requirements.get("require_function_docstring"):
            docstring = ast.get_docstring(node)
            if not docstring:
                self.add_violation(
                    node,
                    "E003",
                    f"Missing docstring: Function '{node.name}' has no docstring definition"
                )

        # 2. Check naming convention
        pattern_key = "methods" if is_method else "functions"
        func_regex = self.naming_regexes.get(pattern_key)
        if func_regex and not func_regex.match(node.name):
            self.add_violation(
                node,
                "E004",
                f"Naming convention mismatch: {'Method' if is_method else 'Function'} '{node.name}' does not match pattern '{func_regex.pattern}'"
            )

        # 3. Check arguments limit
        max_args = limits.get("max_function_arguments")
        if max_args is not None:
            # sum all kinds of arguments
            total_args = len(node.args.args) + len(node.args.kwonlyargs)
            # Subtract 'self' or 'cls' for methods
            if is_method and total_args > 0:
                total_args -= 1
            if total_args > max_args:
                self.add_violation(
                    node,
                    "E005",
                    f"Argument limit exceeded: '{node.name}' has {total_args} arguments (max allowed: {max_args})"
                )

        # 4. Check function length
        max_lines = limits.get("max_function_lines")
        if max_lines is not None:
            func_lines = node.end_lineno - node.lineno + 1
            if func_lines > max_lines:
                self.add_violation(
                    node,
                    "E006",
                    f"Function too long: '{node.name}' spans {func_lines} lines (max allowed: {max_lines})"
                )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        """Validate exception handlers (bare excepts)."""
        requirements = self.config.get("requirements", {})
        if requirements.get("no_bare_except") and node.type is None:
            self.add_violation(
                node,
                "E007",
                "Bare except handler: catching all exceptions without type is prohibited (use Exception)"
            )
        self.generic_visit(node)


def audit_file(file_path, config):
    """Parse a python file and run the linter visitor on its AST."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=file_path)
        visitor = CustomLinterVisitor(config, file_path)
        visitor.visit(tree)
        return visitor.violations
    except Exception as e:
        return [{
            "file": file_path,
            "line": 0,
            "col": 0,
            "code": "ERROR",
            "message": f"Failed to parse or analyze file: {e}"
        }]


def main():
    parser = argparse.ArgumentParser(
        description="Static analysis Python linter utilizing AST to enforce custom rules"
    )
    parser.add_argument(
        "path",
        help="Python file or directory structure to scan recursively"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to the custom JSON linter configuration file"
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Write a default configuration file 'python_linter_config.json' and exit"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose details of checked files"
    )

    args = parser.parse_args()

    if args.generate_config:
        filename = "python_linter_config.json"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_LINTER_CONFIG, f, indent=4)
            print(f"Successfully generated default configuration in '{filename}'")
            return 0
        except Exception as e:
            print(f"Error generating config file: {e}")
            return 1

    # Load config
    config = DEFAULT_LINTER_CONFIG
    if args.config:
        if os.path.exists(args.config):
            try:
                with open(args.config, "r", encoding="utf-8") as f:
                    config = json.load(f)
                print(f"Loaded linter config from: {args.config}")
            except Exception as e:
                print(f"Error reading config: {e}. Using default linter configuration.")
        else:
            print(f"Config path '{args.config}' not found. Using default rules.")

    target_path = os.path.abspath(args.path)
    all_violations = []

    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            if args.verbose:
                print(f"Scanning file: {target_path}")
            all_violations.extend(audit_file(target_path, config))
    elif os.path.isdir(target_path):
        print(f"Scanning directory: {target_path}")
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    if args.verbose:
                        print(f"Scanning: {file_path}")
                    all_violations.extend(audit_file(file_path, config))
    else:
        print(f"Error: Path '{target_path}' is not valid.")
        return 1

    # Print results
    violations_count = len(all_violations)
    if violations_count > 0:
        print(f"\nFound {violations_count} linter violations:\n")
        # Sort by file and line number
        sorted_violations = sorted(all_violations, key=lambda x: (x["file"], x["line"]))
        
        current_file = None
        for v in sorted_violations:
            if v["file"] != current_file:
                current_file = v["file"]
                print(f"\033[1m{current_file}\033[0m")
            
            loc = f"{v['line']}:{v['col']}"
            print(f"  [{loc:<8}] {v['code']} - {v['message']}")
        
        print(f"\nAudit failed. {violations_count} issues found.")
        return 1
    else:
        print("\nAudit passed! No violations found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
