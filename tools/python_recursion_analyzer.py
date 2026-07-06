#!/usr/bin/env python3
"""
Python Recursion Analyzer & Safety Guard
Statically analyzes Python source code to detect recursive functions, verify base cases,
analyze recursion arguments, and identify risks of stack overflow or infinite recursion.
"""

import argparse
import ast
import os
import sys
from typing import List, Dict, Any, Optional

class RecursionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_function: Optional[str] = None
        self.functions: Dict[str, Dict[str, Any]] = {}
        self.func_args: Dict[str, List[str]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_function = self.current_function
        self.current_function = node.name
        self.functions[node.name] = {
            "name": node.name,
            "line": node.lineno,
            "recursive_calls": [],
            "base_cases": [],
            "args": [arg.arg for arg in node.args.args],
            "has_return_path": False,
            "multiple_calls": False,
            "lru_cached": False,
        }
        self.func_args[node.name] = [arg.arg for arg in node.args.args]

        # Check for lru_cache decorator
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id in ("lru_cache", "cache"):
                self.functions[node.name]["lru_cached"] = True
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id in ("lru_cache", "cache"):
                self.functions[node.name]["lru_cached"] = True

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Async recursion works similarly
        old_function = self.current_function
        self.current_function = node.name
        self.functions[node.name] = {
            "name": node.name,
            "line": node.lineno,
            "recursive_calls": [],
            "base_cases": [],
            "args": [arg.arg for arg in node.args.args],
            "has_return_path": False,
            "multiple_calls": False,
            "lru_cached": False,
        }
        self.func_args[node.name] = [arg.arg for arg in node.args.args]
        self.generic_visit(node)
        self.current_function = old_function

    def visit_Call(self, node: ast.Call):
        if self.current_function and isinstance(node.func, ast.Name) and node.func.id == self.current_function:
            # We found a recursive call
            call_info = {
                "line": node.lineno,
                "args": []
            }
            # Try to analyze the arguments passed to the recursive call
            for arg in node.args:
                if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Sub, ast.Add)):
                    left = arg.left.id if isinstance(arg.left, ast.Name) else None
                    op = "-" if isinstance(arg.op, ast.Sub) else "+"
                    right = arg.right.value if isinstance(arg.right, ast.Constant) else None
                    if left and right:
                        call_info["args"].append(f"{left} {op} {right}")
                    else:
                        call_info["args"].append(ast.unparse(arg))
                elif isinstance(arg, ast.Name):
                    call_info["args"].append(arg.id)
                elif isinstance(arg, ast.Constant):
                    call_info["args"].append(str(arg.value))
                else:
                    call_info["args"].append(ast.unparse(arg))

            self.functions[self.current_function]["recursive_calls"].append(call_info)
            if len(self.functions[self.current_function]["recursive_calls"]) > 1:
                self.functions[self.current_function]["multiple_calls"] = True

        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        if self.current_function:
            # Check if this If branch contains a return statement that doesn't make a recursive call
            # This is a strong indicator of a base case/termination path
            if self._has_non_recursive_return(node):
                cond = ast.unparse(node.test)
                self.functions[self.current_function]["base_cases"].append({
                    "line": node.lineno,
                    "condition": cond
                })
        self.generic_visit(node)

    def _has_non_recursive_return(self, node: ast.AST) -> bool:
        # Helper to search for a Return statement that doesn't call current_function
        returns = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                returns.append(child)

        for ret in returns:
            # Analyze if the return value contains a call to the current function
            contains_rec = False
            if ret.value:
                for sub in ast.walk(ret.value):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == self.current_function:
                        contains_rec = True
                        break
            if not contains_rec:
                return True
        return False

def analyze_recursion_safety(func_info: Dict[str, Any]) -> List[str]:
    warnings = []
    
    if not func_info["recursive_calls"]:
        return warnings

    # 1. Check for lack of base case
    if not func_info["base_cases"]:
        warnings.append(
            "CRITICAL: No base case (termination condition) was statically detected. "
            "This will likely cause an infinite recursion / stack overflow."
        )

    # 2. Check recursive calls arguments vs parameter names
    param_names = func_info["args"]
    for call in func_info["recursive_calls"]:
        call_args = call["args"]
        if len(call_args) == len(param_names):
            unchanged = []
            for idx, (p, ca) in enumerate(zip(param_names, call_args)):
                if p == ca:
                    unchanged.append(p)
            if len(unchanged) == len(param_names) and len(param_names) > 0:
                warnings.append(
                    f"WARNING (Line {call['line']}): Recursive call passes arguments completely unchanged: "
                    f"({', '.join(unchanged)}). This will lead to infinite loops unless global/mutable state changes."
                )

    # 3. Check for multiple recursive calls (Fibonacci style) and recommend caching
    if func_info["multiple_calls"] and not func_info["lru_cached"]:
        warnings.append(
            "PERFORMANCE: Multiple recursive calls detected in function body without @lru_cache. "
            "This may result in exponential O(2^N) time complexity. Consider adding @functools.lru_cache."
        )

    return warnings

def scan_file(filepath: str, verbose: bool = False):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return

    print(f"Analyzing recursion safety in: {filepath}\n" + "=" * 50)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
    except SyntaxError as e:
        print(f"Syntax Error while parsing Python file: {e}", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return

    visitor = RecursionVisitor()
    visitor.visit(tree)

    recursive_funcs_found = 0

    for name, func in visitor.functions.items():
        if not func["recursive_calls"]:
            continue
        
        recursive_funcs_found += 1
        print(f"\nFunction: \033[1;36m{name}()\033[0m (Line {func['line']})")
        print(f"  Parameters: ({', '.join(func['args'])})")
        print(f"  Recursive calls: {len(func['recursive_calls'])}")
        for c in func["recursive_calls"]:
            print(f"    - Line {c['line']}: {name}({', '.join(c['args'])})")

        print(f"  Detected Base Cases: {len(func['base_cases'])}")
        for b in func["base_cases"]:
            print(f"    - Line {b['line']}: if {b['condition']}: ...")

        warnings = analyze_recursion_safety(func)
        if warnings:
            print("  \033[1;31mSafety Hazards / Warnings:\033[0m")
            for w in warnings:
                print(f"    - {w}")
        else:
            print("  \033[1;32m✓ Recursion structure looks standard and safe.\033[0m")

    if recursive_funcs_found == 0:
        print("\033[1;32mNo recursive functions found in file.\033[0m")
    else:
        print(f"\nAnalysis complete. Found {recursive_funcs_found} recursive function(s).")

def main():
    parser = argparse.ArgumentParser(
        description="Python Recursion Analyzer & Safety Guard - Static AST analyzer for recursive functions."
    )
    parser.add_argument("filepath", help="Path to the Python source file to scan")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose parser details")
    
    args = parser.parse_args()
    
    # Configure colored outputs for Windows console if possible
    if sys.platform == "win32":
        os.system("color")

    scan_file(args.filepath, args.verbose)

if __name__ == "__main__":
    main()
