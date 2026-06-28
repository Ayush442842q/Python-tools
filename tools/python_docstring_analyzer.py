#!/usr/bin/env python3
"""
Python Docstring Coverage Analyzer

Recursively scans a directory or single file for Python scripts, parses their AST,
calculates docstring coverage for modules, classes, and functions, and displays
a summary with letter grades.

Usage:
    python python_docstring_analyzer.py [path] [options]
"""

import os
import sys
import ast
import argparse
import json

# ANSI color codes for pretty output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class DocstringVisitor(ast.NodeVisitor):
    def __init__(self, include_private=False):
        self.include_private = include_private
        # List of tuple: (type, name, has_docstring, line_no)
        self.stats = []
        self.current_class = None

    def _is_private(self, name):
        # Exclude special/dunder methods (like __init__) from being classed as "private ignore"
        if name.startswith("__") and name.endswith("__"):
            return False
        return name.startswith("_")

    def visit_Module(self, node):
        doc = ast.get_docstring(node)
        self.stats.append(("module", "Module", doc is not None, 1))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        if self._is_private(node.name) and not self.include_private:
            return
        
        doc = ast.get_docstring(node)
        self.stats.append(("class", node.name, doc is not None, node.lineno))
        
        # Track context for methods
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        if self._is_private(node.name) and not self.include_private:
            return
            
        doc = ast.get_docstring(node)
        node_type = "method" if self.current_class else "function"
        full_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        self.stats.append((node_type, full_name, doc is not None, node.lineno))
        
        # Don't recurse into nested functions unless specifically desired
        # Usually nested functions don't require public docstrings

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

def analyze_file(filepath, include_private=False):
    """Analyze a single Python file and return docstring stats."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        
        tree = ast.parse(source, filepath)
        visitor = DocstringVisitor(include_private=include_private)
        visitor.visit(tree)
        return visitor.stats
    except SyntaxError as e:
        return [("error", f"Syntax Error: {e.msg}", False, e.lineno)]
    except Exception as e:
        return [("error", str(e), False, 0)]

def get_grade(percentage):
    """Return a letter grade based on coverage percentage."""
    if percentage >= 95:
        return f"{GREEN}A+{RESET}"
    elif percentage >= 90:
        return f"{GREEN}A{RESET}"
    elif percentage >= 85:
        return f"{GREEN}B+{RESET}"
    elif percentage >= 80:
        return f"{GREEN}B{RESET}"
    elif percentage >= 75:
        return f"{YELLOW}C+{RESET}"
    elif percentage >= 70:
        return f"{YELLOW}C{RESET}"
    elif percentage >= 60:
        return f"{YELLOW}D{RESET}"
    else:
        return f"{RED}F{RESET}"

def get_grade_plain(percentage):
    """Return a plain letter grade for JSON output."""
    if percentage >= 95: return "A+"
    elif percentage >= 90: return "A"
    elif percentage >= 85: return "B+"
    elif percentage >= 80: return "B"
    elif percentage >= 75: return "C+"
    elif percentage >= 70: return "C"
    elif percentage >= 60: return "D"
    else: return "F"

def main():
    parser = argparse.ArgumentParser(description="Analyze Python docstring coverage.")
    parser.add_argument("path", nargs="?", default=".", help="File or directory path to scan (default: current directory)")
    parser.add_argument("--include-private", action="store_true", help="Include private functions/classes starting with '_'")
    parser.add_argument("--min-coverage", type=float, default=0.0, help="Fail if coverage falls below this percentage")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--only-missing", action="store_true", help="Only list files and functions that are missing docstrings")
    
    args = parser.parse_args()
    
    target_path = args.path
    if not os.path.exists(target_path):
        print(f"Error: Path '{target_path}' does not exist.")
        sys.exit(1)
        
    py_files = []
    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            py_files.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            # Ignore standard virtual envs and dot folders
            if any(part in root.split(os.sep) for part in [".git", "venv", ".venv", "env", "__pycache__", "build", "dist"]):
                continue
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
                    
    if not py_files:
        print("No Python files (.py) found to analyze.")
        sys.exit(0)
        
    results = {}
    total_items = 0
    documented_items = 0
    
    type_counts = {"module": [0, 0], "class": [0, 0], "function": [0, 0], "method": [0, 0]}
    
    for filepath in sorted(py_files):
        stats = analyze_file(filepath, include_private=args.include_private)
        
        file_items = []
        file_documented = 0
        file_total = 0
        
        for item_type, name, has_doc, lineno in stats:
            if item_type == "error":
                file_items.append({
                    "type": "error",
                    "name": name,
                    "has_docstring": False,
                    "line": lineno
                })
                continue
                
            file_total += 1
            if has_doc:
                file_documented += 1
                
            # Global aggregations
            total_items += 1
            if has_doc:
                documented_items += 1
                
            if item_type in type_counts:
                type_counts[item_type][1] += 1
                if has_doc:
                    type_counts[item_type][0] += 1
                    
            file_items.append({
                "type": item_type,
                "name": name,
                "has_docstring": has_doc,
                "line": lineno
            })
            
        if file_total > 0:
            rel_path = os.path.relpath(filepath, target_path)
            results[rel_path] = {
                "total": file_total,
                "documented": file_documented,
                "coverage": (file_documented / file_total) * 100,
                "items": file_items
            }

    overall_coverage = (documented_items / total_items * 100) if total_items > 0 else 0.0
    
    if args.json:
        # Construct JSON output
        json_output = {
            "summary": {
                "total_files": len(py_files),
                "total_items": total_items,
                "documented_items": documented_items,
                "undocumented_items": total_items - documented_items,
                "overall_coverage": overall_coverage,
                "grade": get_grade_plain(overall_coverage),
                "breakdown": {
                    t: {
                        "total": type_counts[t][1],
                        "documented": type_counts[t][0],
                        "coverage": (type_counts[t][0] / type_counts[t][1] * 100) if type_counts[t][1] > 0 else 0
                    } for t in type_counts
                }
            },
            "files": results
        }
        print(json.dumps(json_output, indent=2))
        
    else:
        # Console Output
        print(f"\n{BOLD}{CYAN}=== PYTHON DOCSTRING COVERAGE ANALYZER ===={RESET}\n")
        print(f"Target Path: {target_path}")
        print(f"Files Found: {len(py_files)}\n")
        
        # File details
        print(f"{BOLD}{'File Path':<50} {'Coverage':<12} {'Documented':<12} {'Missing':<8}{RESET}")
        print("-" * 85)
        
        for file_rel, stats in results.items():
            cov_str = f"{stats['coverage']:.1f}%"
            missing = stats['total'] - stats['documented']
            doc_ratio = f"{stats['documented']}/{stats['total']}"
            
            if stats['coverage'] >= 90:
                color = GREEN
            elif stats['coverage'] >= 70:
                color = YELLOW
            else:
                color = RED
                
            print(f"{file_rel:<50} {color}{cov_str:<12}{RESET} {doc_ratio:<12} {missing:<8}")
            
            # List missing elements
            if missing > 0:
                for item in stats['items']:
                    if not item['has_docstring'] and item['type'] != "error":
                        print(f"  {RED}↳ Line {item['line']:<4} [{item['type']}] {item['name']}{RESET}")
            
            # If syntax error
            for item in stats['items']:
                if item['type'] == "error":
                    print(f"  {RED}↳ Line {item['line']:<4} {item['name']}{RESET}")
                    
            if not args.only_missing and missing == 0:
                print(f"  {GREEN}↳ 100% Documented!{RESET}")
                
        # Overall Summary
        print("\n" + "="*50)
        print(f"{BOLD}OVERALL SUMMARY:{RESET}")
        print(f"  Total Code Items:  {total_items}")
        print(f"  Documented Items:  {GREEN}{documented_items}{RESET}")
        print(f"  Undocumented Items: {RED}{total_items - documented_items}{RESET}")
        print(f"  Docstring Coverage: {BOLD}{overall_coverage:.2f}%{RESET}")
        print(f"  Coverage Grade:     {get_grade(overall_coverage)}")
        print("="*50)
        
        print(f"\n{BOLD}Breakdown by Type:{RESET}")
        for item_type, counts in type_counts.items():
            doc, tot = counts
            cov = (doc / tot * 100) if tot > 0 else 0
            cov_bar = "#" * int(cov // 10) + " " * (10 - int(cov // 10))
            print(f"  {item_type.capitalize():<10} [{cov_bar}] {cov:6.1f}% ({doc}/{tot})")
        print()

    if overall_coverage < args.min_coverage:
        print(f"{RED}Error: Overall coverage {overall_coverage:.2f}% is below required minimum of {args.min_coverage:.2f}%{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
