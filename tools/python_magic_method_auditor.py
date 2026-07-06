#!/usr/bin/env python3
"""
Python Class Magic Method Contract Auditor
Statically checks class magic methods (__eq__, __hash__, __len__, etc.) for specification contracts.
"""

import argparse
import ast
import os
import sys
from typing import List, Dict, Set, Any

class MagicMethodAuditor(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[Dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        methods: Dict[str, ast.FunctionDef] = {}
        has_total_ordering = False
        hash_assigned_none = False

        # Scan decorators
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "total_ordering":
                has_total_ordering = True
            elif isinstance(dec, ast.Name) and dec.id == "total_ordering":
                has_total_ordering = True

        # Scan body for methods and class-level variable assignments
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[item.name] = item
            elif isinstance(item, ast.Assign):
                # Check for explicit __hash__ = None
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__hash__":
                        if isinstance(item.value, ast.Constant) and item.value.value is None:
                            hash_assigned_none = True

        # 1. Check __eq__ vs __hash__ contract
        if "__eq__" in methods and "__hash__" not in methods and not hash_assigned_none:
            self.violations.append({
                "class": class_name,
                "line": node.lineno,
                "type": "HASH_EQ_CONTRACT",
                "message": (
                    f"Class '{class_name}' defines '__eq__' but not '__hash__'. "
                    "Instances will be unhashable in Python 3. If this is intentional, "
                    "explicitly set '__hash__ = None' in the class body."
                )
            })

        # 2. Check rich comparison / total ordering contract
        comp_methods = {"__lt__", "__le__", "__gt__", "__ge__"}
        defined_comps = comp_methods.intersection(methods.keys())
        if defined_comps and len(defined_comps) < 4 and not has_total_ordering:
            self.violations.append({
                "class": class_name,
                "line": node.lineno,
                "type": "TOTAL_ORDERING_CONTRACT",
                "message": (
                    f"Class '{class_name}' defines some comparison methods ({', '.join(defined_comps)}) "
                    "but not all. Add the missing comparison methods or use the "
                    "'@functools.total_ordering' class decorator."
                )
            })

        # 3. Check __init__ return statements
        if "__init__" in methods:
            init_func = methods["__init__"]
            for sub_node in ast.walk(init_func):
                if isinstance(sub_node, ast.Return) and sub_node.value is not None:
                    # An explicit return statement returning a value in __init__ is a runtime TypeError
                    # Check if return value is a constant None (which is allowed)
                    is_none = False
                    if isinstance(sub_node.value, ast.Constant) and sub_node.value.value is None:
                        is_none = True
                    if not is_none:
                        self.violations.append({
                            "class": class_name,
                            "line": sub_node.lineno,
                            "type": "INIT_RETURN_CONTRACT",
                            "message": (
                                f"Class '{class_name}.__init__' contains a return statement returning a non-None value "
                                f"({ast.unparse(sub_node.value)}). __init__ must only return None."
                            )
                        })

        # 4. Check Context Manager (__enter__ / __exit__) protocol
        if ("__enter__" in methods or "__exit__" in methods) and not ("__enter__" in methods and "__exit__" in methods):
            missing = "__exit__" if "__enter__" in methods else "__enter__"
            self.violations.append({
                "class": class_name,
                "line": node.lineno,
                "type": "CONTEXT_MANAGER_CONTRACT",
                "message": (
                    f"Class '{class_name}' implements a partial context manager protocol. "
                    f"It defines '{'__enter__' if missing == '__exit__' else '__exit__'}' but is missing '{missing}'."
                )
            })

        # Check __exit__ argument signature
        if "__exit__" in methods:
            exit_func = methods["__exit__"]
            # __exit__ must accept exactly 4 arguments: (self, exc_type, exc_val, exc_tb)
            # We check total args including defaults and varargs
            total_args = len(exit_func.args.args)
            if total_args != 4:
                self.violations.append({
                    "class": class_name,
                    "line": exit_func.lineno,
                    "type": "EXIT_SIGNATURE_CONTRACT",
                    "message": (
                        f"Class '{class_name}.__exit__' should accept exactly 4 parameters: "
                        f"(self, exc_type, exc_val, exc_tb), but accepts {total_args}."
                    )
                })

        # 5. Check __len__ return type contract
        if "__len__" in methods:
            len_func = methods["__len__"]
            for sub_node in ast.walk(len_func):
                if isinstance(sub_node, ast.Return) and sub_node.value is not None:
                    val = sub_node.value
                    # If returning a constant that is not a non-negative integer
                    if isinstance(val, ast.Constant):
                        if not isinstance(val.value, int) or val.value < 0:
                            self.violations.append({
                                "class": class_name,
                                "line": sub_node.lineno,
                                "type": "LEN_RETURN_CONTRACT",
                                "message": (
                                    f"Class '{class_name}.__len__' returns a constant value '{val.value}' which is not a "
                                    "non-negative integer. __len__ must return an integer >= 0."
                                )
                            })

        # 6. Check __str__ and __repr__ return type contracts
        for m_name in ("__str__", "__repr__"):
            if m_name in methods:
                m_func = methods[m_name]
                for sub_node in ast.walk(m_func):
                    if isinstance(sub_node, ast.Return) and sub_node.value is not None:
                        val = sub_node.value
                        if isinstance(val, ast.Constant) and not isinstance(val.value, str):
                            self.violations.append({
                                "class": class_name,
                                "line": sub_node.lineno,
                                "type": f"{m_name.upper()[2:-2]}_RETURN_CONTRACT",
                                "message": (
                                    f"Class '{class_name}.{m_name}' returns a non-string constant '{val.value}'. "
                                    f"{m_name} must return a string."
                                )
                            })

        self.generic_visit(node)

def audit_file(filepath: str):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
    except SyntaxError as e:
        print(f"Syntax Error in Python file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    auditor = MagicMethodAuditor()
    auditor.visit(tree)

    print(f"Auditing class magic method contracts in: {filepath}\n" + "=" * 60)
    
    if not auditor.violations:
        print("\033[1;32m✓ All classes adhere to magic method contracts. No violations found.\033[0m")
    else:
        print(f"\033[1;31mFound {len(auditor.violations)} violation(s):\033[0m")
        for v in auditor.violations:
            print(f"\n[{v['type']}] Line {v['line']}, Class: {v['class']}")
            print(f"  \033[0;33m{v['message']}\033[0m")

def main():
    parser = argparse.ArgumentParser(
        description="Python Class Magic Method Contract Auditor - Verifies correctness of class protocol magic methods."
    )
    parser.add_argument("filepath", help="Path to the Python file to audit")
    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("color")

    audit_file(args.filepath)

if __name__ == "__main__":
    main()
