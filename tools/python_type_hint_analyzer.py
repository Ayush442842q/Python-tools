#!/usr/bin/env python3
"""
Python Type Hint Coverage Analyzer
Parses Python source files using the AST (Abstract Syntax Tree) module.
Calculates the type hint annotation coverage score for functions, methods, and parameters,
pointing out missing annotations with exact line numbers.
"""

import argparse
import ast
import os
import sys

# ANSI Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
END = "\033[0m"

def log_info(msg):
    print(f"{BLUE}[INFO]{END} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{END} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{END} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{END} {msg}", file=sys.stderr)

class TypeHintVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.current_class = None

    def visit_ClassDef(self, node):
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        self.process_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.process_function(node)
        self.generic_visit(node)

    def process_function(self, node):
        # Exclude internal double underscore methods except __init__
        if node.name.startswith("__") and node.name.endswith("__") and node.name != "__init__":
            return

        func_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        
        args = node.args
        all_args = []
        
        # Positional and Keyword-only arguments
        all_args.extend(args.args)
        all_args.extend(args.kwonlyargs)
        if args.vararg:
            all_args.append(args.vararg)
        if args.kwarg:
            all_args.append(args.kwarg)

        # Filter out self/cls for class methods
        filtered_args = []
        for i, arg in enumerate(all_args):
            if i == 0 and self.current_class and arg.arg in {"self", "cls"}:
                continue
            filtered_args.append(arg)

        total_annotated = 0
        unannotated_args = []
        
        for arg in filtered_args:
            if arg.annotation is not None:
                total_annotated += 1
            else:
                unannotated_args.append(arg.arg)

        # Check return annotation
        has_return_hint = node.returns is not None
        if has_return_hint:
            total_annotated += 1

        total_possible = len(filtered_args) + 1 # args + return type

        self.functions.append({
            "name": func_name,
            "line": node.lineno,
            "total_args": len(filtered_args),
            "unannotated_args": unannotated_args,
            "has_return_hint": has_return_hint,
            "annotated_count": total_annotated,
            "total_count": total_possible,
            "coverage": (total_annotated / total_possible) if total_possible > 0 else 1.0
        })

def analyze_file(file_path):
    """Analyzes a single Python file and returns type hint statistics."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        log_error(f"Failed to read file {file_path}: {e}")
        return None

    try:
        tree = ast.parse(code, filename=file_path)
    except SyntaxError as e:
        log_error(f"Syntax error in {file_path} at line {e.lineno}: {e.msg}")
        return None
    except Exception as e:
        log_error(f"Failed to parse AST for {file_path}: {e}")
        return None

    visitor = TypeHintVisitor()
    visitor.visit(tree)
    
    return visitor.functions

def print_file_report(file_path, functions, show_all=False):
    """Prints a beautiful console report for a single file."""
    if not functions:
        log_info(f"No functions/methods found in {file_path}")
        return

    # Sort by line number
    functions.sort(key=lambda x: x["line"])

    total_annotated = sum(f["annotated_count"] for f in functions)
    total_possible = sum(f["total_count"] for f in functions)
    overall_coverage = (total_annotated / total_possible * 100) if total_possible > 0 else 100.0

    print(f"\n{BOLD}{CYAN}File: {file_path}{END}")
    print(f"{BOLD}Overall Type Hint Coverage: {overall_coverage:.1f}% ({total_annotated}/{total_possible} hints annotations){END}\n")

    # Table Header
    print(f"  {BOLD}{'Line':<5} | {'Function / Method':<30} | {'Coverage':<8} | {'Details':<30}{END}")
    print("  " + "-" * 83)

    for f in functions:
        if f["coverage"] == 1.0 and not show_all:
            continue
            
        color = GREEN if f["coverage"] == 1.0 else (YELLOW if f["coverage"] >= 0.5 else RED)
        cov_str = f"{f['coverage']*100:.0f}%"
        
        details = []
        if f["unannotated_args"]:
            details.append(f"Missing args: {', '.join(f['unannotated_args'])}")
        if not f["has_return_hint"]:
            details.append("Missing return hint")
            
        details_str = "; ".join(details) if details else "None"
        func_display_name = f["name"][:30]
        
        print(f"  {f['line']:<5} | {func_display_name:<30} | {color}{cov_str:<8}{END} | {details_str}")

def main():
    parser = argparse.ArgumentParser(
        description="Python Type Hint Annotation Coverage Analyzer."
    )
    parser.add_argument("path", help="Path to Python file or directory to scan recursively")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Show all functions, including those with 100% type coverage")
    parser.add_argument("-m", "--min-coverage", type=float, default=100.0,
                        help="Alert/exit if overall coverage is below this threshold (0.0 to 100.0)")

    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("")

    target_path = args.path
    if not os.path.exists(target_path):
        log_error(f"Path does not exist: {target_path}")
        sys.exit(1)

    all_files_stats = {}
    
    if os.path.isfile(target_path):
        if not target_path.endswith(".py"):
            log_warning("Target file does not have .py extension. Proceeding anyway.")
        stats = analyze_file(target_path)
        if stats is not None:
            all_files_stats[target_path] = stats
            print_file_report(target_path, stats, show_all=args.all)
    elif os.path.isdir(target_path):
        log_info(f"Scanning directory: {target_path}")
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    stats = analyze_file(full_path)
                    if stats:
                        all_files_stats[full_path] = stats
                        
        # Summary for directories
        total_annotated = 0
        total_possible = 0
        total_funcs = 0
        
        print(f"\n{BOLD}{CYAN}=== Type Hint Directory Scan Summary ==={END}\n")
        print(f"  {BOLD}{'File':<50} | {'Coverage':<8} | {'Funcs':<6}{END}")
        print("  " + "-" * 69)
        
        for file_path, funcs in sorted(all_files_stats.items()):
            file_annotated = sum(f["annotated_count"] for f in funcs)
            file_possible = sum(f["total_count"] for f in funcs)
            file_cov = (file_annotated / file_possible * 100) if file_possible > 0 else 100.0
            
            total_annotated += file_annotated
            total_possible += file_possible
            total_funcs += len(funcs)
            
            color = GREEN if file_cov == 100.0 else (YELLOW if file_cov >= 50.0 else RED)
            # Display relative path for cleanliness
            rel_path = os.path.relpath(file_path, target_path)
            rel_display = rel_path[:50]
            print(f"  {rel_display:<50} | {color}{file_cov:>.1f}%{END} | {len(funcs):<6}")
            
        overall_cov = (total_annotated / total_possible * 100) if total_possible > 0 else 100.0
        color = GREEN if overall_cov == 100.0 else (YELLOW if overall_cov >= 50.0 else RED)
        
        print("\n" + "=" * 70)
        print(f"{BOLD}Total Files Scanned:{END}   {len(all_files_stats)}")
        print(f"{BOLD}Total Functions:{END}       {total_funcs}")
        print(f"{BOLD}Overall Coverage:{END}      {color}{overall_cov:.1f}%{END} ({total_annotated}/{total_possible} hints annotated)")
        print("=" * 70)
        
        # Exit with error if below threshold
        if overall_cov < args.min_coverage:
            log_error(f"Overall coverage {overall_cov:.1f}% is below threshold of {args.min_coverage}%.")
            sys.exit(1)

if __name__ == "__main__":
    main()
