#!/usr/bin/env python3
"""
python_type_coverage_analyzer - Python Type Annotation Coverage Analyzer

Scans Python source files or entire directories using AST parsing to compute type hint
coverage metrics across function parameters, return values, and variable assignments.

Usage:
    python tools/python_type_coverage_analyzer.py <path_or_file> [options]

Examples:
    python tools/python_type_coverage_analyzer.py tools/
    python tools/python_type_coverage_analyzer.py script.py --fail-under 80.0
    python tools/python_type_coverage_analyzer.py src/ --format json --output coverage.json
"""

import argparse
import ast
import json
import os
import sys
from typing import List, Dict, Any, Tuple


class TypeHintVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.functions_count = 0
        self.functions_annotated = 0
        self.params_count = 0
        self.params_annotated = 0
        self.returns_count = 0
        self.returns_annotated = 0
        self.variables_count = 0
        self.variables_annotated = 0
        self.unannotated_details: List[Dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._inspect_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._inspect_function(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.variables_count += 1
        self.variables_annotated += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Count top-level/class module variables without type annotations
        self.variables_count += 1
        self.generic_visit(node)

    def _inspect_function(self, node):
        self.functions_count += 1
        is_fully_annotated = True
        missing_params = []

        # Check return type annotation
        self.returns_count += 1
        has_return_annotation = node.returns is not None
        if has_return_annotation:
            self.returns_annotated += 1
        else:
            is_fully_annotated = False

        # Check arguments annotation
        args_list = node.args.args + node.args.kwonlyargs
        if node.args.vararg:
            args_list.append(node.args.vararg)
        if node.args.kwarg:
            args_list.append(node.args.kwarg)

        for arg in args_list:
            if arg.arg in ('self', 'cls'):
                continue
            self.params_count += 1
            if arg.annotation is not None:
                self.params_annotated += 1
            else:
                is_fully_annotated = False
                missing_params.append(arg.arg)

        if is_fully_annotated:
            self.functions_annotated += 1
        else:
            self.unannotated_details.append({
                'function': node.name,
                'line': node.lineno,
                'missing_return': not has_return_annotation,
                'missing_params': missing_params
            })


def analyze_file(filepath: str) -> Dict[str, Any]:
    """Parse a Python file and calculate type annotation coverage metrics."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
    except Exception as e:
        return {
            'filename': filepath,
            'error': str(e),
            'functions_count': 0, 'functions_annotated': 0,
            'params_count': 0, 'params_annotated': 0,
            'returns_count': 0, 'returns_annotated': 0,
            'coverage_pct': 0.0,
            'unannotated_details': []
        }

    visitor = TypeHintVisitor(filepath)
    visitor.visit(tree)

    total_items = visitor.params_count + visitor.returns_count
    annotated_items = visitor.params_annotated + visitor.returns_annotated
    coverage_pct = (annotated_items / total_items * 100.0) if total_items > 0 else 100.0

    return {
        'filename': filepath,
        'functions_count': visitor.functions_count,
        'functions_annotated': visitor.functions_annotated,
        'params_count': visitor.params_count,
        'params_annotated': visitor.params_annotated,
        'returns_count': visitor.returns_count,
        'returns_annotated': visitor.returns_annotated,
        'total_items': total_items,
        'annotated_items': annotated_items,
        'coverage_pct': round(coverage_pct, 2),
        'unannotated_details': visitor.unannotated_details
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scans Python codebases to measure type hint coverage across functions, parameters, and return types."
    )
    parser.add_argument("target", help="Python file or directory to scan")
    parser.add_argument("--fail-under", type=float, default=0.0, help="Minimum acceptable overall type coverage percentage (0-100)")
    parser.add_argument("-f", "--format", choices=['text', 'json', 'summary'], default='text', help="Output format (default: text)")
    parser.add_argument("-o", "--output", help="Save coverage report to output file")
    parser.add_argument("--ignore", help="Comma-separated patterns or directory names to skip")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"Error: Target path '{args.target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    ignore_patterns = [p.strip() for p in args.ignore.split(',')] if args.ignore else ['.venv', 'venv', '__pycache__', 'build', 'dist']

    python_files = []
    if os.path.isfile(args.target):
        if args.target.endswith('.py'):
            python_files.append(args.target)
    else:
        for root, dirs, files in os.walk(args.target):
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))

    if not python_files:
        print("No Python files found to analyze.")
        sys.exit(0)

    results = []
    tot_params = tot_params_ann = 0
    tot_returns = tot_returns_ann = 0
    tot_funcs = tot_funcs_ann = 0

    for filepath in sorted(python_files):
        res = analyze_file(filepath)
        results.append(res)
        tot_params += res.get('params_count', 0)
        tot_params_ann += res.get('params_annotated', 0)
        tot_returns += res.get('returns_count', 0)
        tot_returns_ann += res.get('returns_annotated', 0)
        tot_funcs += res.get('functions_count', 0)
        tot_funcs_ann += res.get('functions_annotated', 0)

    overall_total = tot_params + tot_returns
    overall_annotated = tot_params_ann + tot_returns_ann
    overall_coverage = (overall_annotated / overall_total * 100.0) if overall_total > 0 else 100.0
    overall_coverage = round(overall_coverage, 2)

    report_data = {
        'overall_coverage_pct': overall_coverage,
        'summary': {
            'total_files': len(python_files),
            'total_functions': tot_funcs,
            'annotated_functions': tot_funcs_ann,
            'total_parameters': tot_params,
            'annotated_parameters': tot_params_ann,
            'total_returns': tot_returns,
            'annotated_returns': tot_returns_ann,
        },
        'files': results
    }

    if args.format == 'json':
        output_str = json.dumps(report_data, indent=2)
    elif args.format == 'summary':
        output_str = f"Type Coverage: {overall_coverage}% ({overall_annotated}/{overall_total} hints across {tot_funcs} functions in {len(python_files)} files)"
    else:
        lines = []
        lines.append("=" * 70)
        lines.append(f"PYTHON TYPE ANNOTATION COVERAGE REPORT: {args.target}")
        lines.append("=" * 70)
        lines.append(f"Overall Coverage: {overall_coverage}% ({overall_annotated}/{overall_total} annotations)")
        lines.append(f"Functions fully annotated: {tot_funcs_ann}/{tot_funcs} ({(tot_funcs_ann/tot_funcs*100):.1f}%)" if tot_funcs else "Functions: 0")
        lines.append(f"Parameters annotated: {tot_params_ann}/{tot_params}")
        lines.append(f"Return types annotated: {tot_returns_ann}/{tot_returns}")
        lines.append("-" * 70)
        lines.append(f"{'File':<45} | {'Coverage':<10} | {'Unannotated Funcs'}")
        lines.append("-" * 70)
        for res in results:
            fname = res['filename']
            if len(fname) > 44:
                fname = "..." + fname[-41:]
            cov = f"{res['coverage_pct']}%"
            unann_cnt = len(res.get('unannotated_details', []))
            lines.append(f"{fname:<45} | {cov:<10} | {unann_cnt}")
        lines.append("=" * 70)
        output_str = "\n".join(lines)

    print(output_str)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"\n[+] Coverage report saved to: {args.output}")

    if args.fail_under > 0.0 and overall_coverage < args.fail_under:
        print(f"\n[-] FAILURE: Overall coverage ({overall_coverage}%) is below required threshold ({args.fail_under}%).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
