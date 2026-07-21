#!/usr/bin/env python3
"""
Python Code Complexity Analyzer - Evaluate cyclomatic complexity and structural metrics of Python files.

This tool uses the standard library 'ast' module to analyze Python source code.
It calculates cyclomatic complexity, counts lines of code, comments, docstrings, classes,
and functions, then generates a comprehensive complexity grading report.
"""

import sys
import os
import ast
import argparse

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    """Colorize text using ANSI escapes if supported"""
    if color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

class ComplexityVisitor(ast.NodeVisitor):
    """AST Visitor to compute cyclomatic complexity of functions and classes."""
    def __init__(self):
        self.stats = []
        self.current_context = []

    def visit_FunctionDef(self, node):
        self.current_context.append(node.name)
        complexity = self._calculate_complexity(node)
        self.stats.append({
            'type': 'Function',
            'name': '.'.join(self.current_context),
            'line': node.lineno,
            'complexity': complexity
        })
        self.generic_visit(node)
        self.current_context.pop()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        self.current_context.append(node.name)
        self.generic_visit(node)
        self.current_context.pop()

    def _calculate_complexity(self, node):
        """
        Cyclomatic complexity starts at 1, incremented by:
        - branches (If, IfExp)
        - loops (For, AsyncFor, While)
        - list/dict/set/generator comprehensions (ListComp, DictComp, SetComp, GeneratorExp)
        - exception handlers (ExceptHandler)
        - boolean operators (And, Or)
        """
        complexity = 1
        for subnode in ast.walk(node):
            if isinstance(subnode, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(subnode, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += 1
            elif isinstance(subnode, ast.BoolOp):
                # An expression like 'a and b or c' adds len(values) - 1 complexity points
                complexity += len(subnode.values) - 1
        return complexity

def get_complexity_grade(score):
    """Return a colored grade and suggestion based on complexity score"""
    if score <= 5:
        return colorize("A (Simple)", 'green'), "Keep it up! The code is clean and readable."
    elif score <= 10:
        return colorize("B (Moderate)", 'green'), "Well-structured, but keep an eye on expansion."
    elif score <= 20:
        return colorize("C (Complex)", 'yellow'), "Consider refactoring or breaking down nested logic."
    elif score <= 35:
        return colorize("D (Very Complex)", 'red'), "High risk. Recommend refactoring into smaller helpers immediately."
    else:
        return colorize("F (Unmaintainable)", 'red'), "Extreme risk. Completely refactor this function immediately."

def analyze_file_metrics(filepath):
    """Compute physical metrics: LOC, blank lines, comments, docstrings"""
    metrics = {
        'total_lines': 0,
        'blank_lines': 0,
        'comment_lines': 0,
        'docstring_lines': 0,
        'code_lines': 0,
        'classes': 0,
        'functions': 0,
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        metrics['total_lines'] = len(lines)
        
        in_multiline_comment = False
        multiline_char = None
        
        for line in lines:
            stripped = line.strip()
            
            # Check blank line
            if not stripped:
                metrics['blank_lines'] += 1
                continue
                
            # Check single line comment
            if stripped.startswith('#'):
                metrics['comment_lines'] += 1
                continue
                
            # Basic multiline string/comment detection
            if not in_multiline_comment:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_multiline_comment = True
                    multiline_char = stripped[:3]
                    metrics['docstring_lines'] += 1
                    # Check if it opens and closes on the same line
                    if len(stripped) > 3 and stripped.endswith(multiline_char):
                        in_multiline_comment = False
                else:
                    metrics['code_lines'] += 1
            else:
                metrics['docstring_lines'] += 1
                if stripped.endswith(multiline_char):
                    in_multiline_comment = False
                    
        # Parse syntax tree for structural items
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content, filename=filepath)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                metrics['classes'] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics['functions'] += 1
                
        # Calculate cyclomatic complexity
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        
        return metrics, visitor.stats
        
    except SyntaxError as se:
        return {'error': f"Syntax Error: {se}"}, []
    except Exception as e:
        return {'error': f"Error: {e}"}, []

def print_report(filepath, metrics, stats, threshold):
    """Format and print the complexity analysis report"""
    print("=" * 70)
    print(colorize(f"Complexity Analysis Report for: {os.path.basename(filepath)}", 'bold'))
    print(colorize(f"Path: {filepath}", 'cyan'))
    print("=" * 70)
    
    if 'error' in metrics:
        print(colorize(metrics['error'], 'red'))
        return
        
    # Print metrics
    print(colorize("Code Statistics:", 'bold'))
    print(f"  Total Lines of Code:       {metrics['total_lines']}")
    print(f"  Source Lines of Code (LOC):{metrics['code_lines']}")
    print(f"  Comment Lines:             {metrics['comment_lines']}")
    print(f"  Docstring/Doc-lines:       {metrics['docstring_lines']}")
    print(f"  Blank Lines:               {metrics['blank_lines']}")
    print(f"  Total Classes:             {metrics['classes']}")
    print(f"  Total Functions/Methods:   {metrics['functions']}")
    print("-" * 70)
    
    # Filter stats by complexity threshold
    filtered_stats = [s for s in stats if s['complexity'] >= threshold]
    
    # Sort stats by complexity descending
    stats_sorted = sorted(stats, key=lambda x: x['complexity'], reverse=True)
    
    print(colorize(f"Function Complexity Details (Threshold >= {threshold}):", 'bold'))
    if not stats_sorted:
        print("  No functions found.")
    else:
        has_flagged = False
        print(f"  {'Line':<6} | {'Type':<10} | {'Name':<30} | {'Complexity':<10} | {'Grade':<10}")
        print("  " + "-" * 68)
        for s in stats_sorted:
            if s['complexity'] < threshold:
                continue
            has_flagged = True
            grade, _ = get_complexity_grade(s['complexity'])
            print(f"  {s['line']:<6} | {s['type']:<10} | {s['name'][:30]:<30} | {s['complexity']:<10} | {grade}")
            
        if not has_flagged:
            print(f"  All functions have complexity below the threshold of {threshold}!")
            
    # Highlight highest complexity functions
    if stats_sorted:
        highest = stats_sorted[0]
        if highest['complexity'] > 10:
            print("-" * 70)
            grade, suggestion = get_complexity_grade(highest['complexity'])
            print(colorize("Recommendation Alert 🚨", 'bold'))
            print(f"  Most complex component: '{highest['name']}' at line {highest['line']} with complexity {highest['complexity']}.")
            print(f"  Grade: {grade}")
            print(f"  Advice: {suggestion}")
            
    print("=" * 70 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description="Python Code Complexity Analyzer - Analyze structure and cyclomatic complexity."
    )
    parser.add_argument(
        "target",
        help="Path to a Python file or directory containing Python files."
    )
    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=6,
        help="Minimum cyclomatic complexity score to flag in the report (default: 6)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan directories recursively for Python files"
    )
    
    args = parser.parse_args()
    
    target = os.path.expanduser(args.target)
    
    if not os.path.exists(target):
        print(f"Error: Target path '{target}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Enable terminal VT processing on Windows
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
    if os.path.isfile(target):
        if not target.endswith('.py'):
            print("Warning: Target file does not end in '.py'. Analyzing anyway...")
        metrics, stats = analyze_file_metrics(target)
        print_report(target, metrics, stats, args.threshold)
    else:
        # Directory scan
        py_files = []
        if args.recursive:
            for root, _, files in os.walk(target):
                for f in files:
                    if f.endswith('.py'):
                        py_files.append(os.path.join(root, f))
        else:
            py_files = [os.path.join(target, f) for f in os.listdir(target) if f.endswith('.py')]
            
        if not py_files:
            print(f"No Python files found in '{target}'.")
            return
            
        print(f"Found {len(py_files)} Python files. Starting analysis...\n")
        
        for f in py_files:
            metrics, stats = analyze_file_metrics(f)
            print_report(f, metrics, stats, args.threshold)

if __name__ == "__main__":
    main()
