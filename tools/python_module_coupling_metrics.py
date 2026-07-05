#!/usr/bin/env python3
"""
Python Module Coupling Metrics & Package Structure Analyzer

Analyzes Python source files in a directory or package using AST parsing to compute
coupling metrics and software design architecture statistics:
  - Afferent Coupling (Ca): Number of external modules that depend on a module.
  - Efferent Coupling (Ce): Number of external modules that a module depends on.
  - Instability (I): I = Ce / (Ca + Ce) (0 = highly stable, 1 = highly unstable).
  - Abstractness (A): Ratio of abstract classes/interfaces to total classes.
  - Distance from Main Sequence (D): D = |A + I - 1| (measures architectural balance).

Output formats include colored ASCII summary tables, detailed module reports, JSON export,
and Mermaid package dependency diagrams.

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import ast
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional


class ModuleASTVisitor(ast.NodeVisitor):
    def __init__(self, current_module: str, known_modules: Set[str]):
        self.current_module = current_module
        self.known_modules = known_modules
        self.imports: Set[str] = set()
        self.total_classes: int = 0
        self.abstract_classes: int = 0

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            imported = alias.name.split('.')[0]
            if imported in self.known_modules and imported != self.current_module:
                self.imports.add(imported)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            imported = node.module.split('.')[0]
            if imported in self.known_modules and imported != self.current_module:
                self.imports.add(imported)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.total_classes += 1
        is_abstract = False
        
        # Check base classes for ABC or Abstract
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in ('ABC', 'Interface'):
                is_abstract = True
            elif isinstance(base, ast.Attribute) and base.attr in ('ABC', 'Interface'):
                is_abstract = True
        
        # Check decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and 'abstract' in decorator.id.lower():
                is_abstract = True

        # Check body for @abstractmethod
        for body_item in node.body:
            if isinstance(body_item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in body_item.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id == 'abstractmethod':
                        is_abstract = True
                    elif isinstance(dec, ast.Attribute) and dec.attr == 'abstractmethod':
                        is_abstract = True

        if is_abstract:
            self.abstract_classes += 1

        self.generic_visit(node)


def analyze_codebase(root_path: Path, exclude_tests: bool = False) -> Dict[str, dict]:
    py_files: Dict[str, Path] = {}
    
    for path in root_path.rglob('*.py'):
        if exclude_tests and ('test' in path.name.lower() or 'tests' in path.parts):
            continue
        rel_path = path.relative_to(root_path)
        mod_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
        if mod_name.endswith('.__init__'):
            mod_name = mod_name[:-9]
        if not mod_name:
            mod_name = root_path.name
        py_files[mod_name] = path

    known_modules = set(py_files.keys())
    
    # Store per-module stats
    module_data = {
        mod: {
            'imports': set(),
            'imported_by': set(),
            'total_classes': 0,
            'abstract_classes': 0,
            'loc': 0
        }
        for mod in known_modules
    }

    for mod_name, file_path in py_files.items():
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            module_data[mod_name]['loc'] = len(content.splitlines())
            
            tree = ast.parse(content, filename=str(file_path))
            visitor = ModuleASTVisitor(mod_name, known_modules)
            visitor.visit(tree)

            module_data[mod_name]['imports'] = visitor.imports
            module_data[mod_name]['total_classes'] = visitor.total_classes
            module_data[mod_name]['abstract_classes'] = visitor.abstract_classes

            for imp in visitor.imports:
                if imp in module_data:
                    module_data[imp]['imported_by'].add(mod_name)
        except Exception as e:
            # Skip invalid syntax files gracefully
            pass

    # Compute metrics
    metrics = {}
    for mod, data in module_data.items():
        ca = len(data['imported_by'])  # Afferent
        ce = len(data['imports'])      # Efferent
        
        total_c = data['total_classes']
        abs_c = data['abstract_classes']
        
        instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0
        abstractness = abs_c / total_c if total_c > 0 else 0.0
        distance = abs(abstractness + instability - 1.0)

        metrics[mod] = {
            'path': str(py_files[mod]),
            'loc': data['loc'],
            'ca': ca,
            'ce': ce,
            'instability': round(instability, 3),
            'abstractness': round(abstractness, 3),
            'distance': round(distance, 3),
            'classes': total_c,
            'abstract_classes': abs_c,
            'depends_on': sorted(list(data['imports'])),
            'depended_by': sorted(list(data['imported_by']))
        }

    return metrics


def format_table(metrics: Dict[str, dict], sort_by: str = 'distance') -> str:
    sorted_mods = sorted(metrics.items(), key=lambda x: x[1].get(sort_by, 0), reverse=True)
    
    headers = ["Module Name", "LOC", "Ca", "Ce", "Instability (I)", "Abstractness (A)", "Distance (D)"]
    widths = [32, 6, 4, 4, 15, 16, 12]
    
    def row_str(cols):
        return "| " + " | ".join(f"{str(c):<{w}}" for c, w in zip(cols, widths)) + " |"

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    
    lines = [sep, row_str(headers), sep]
    for mod, data in sorted_mods:
        cols = [
            mod[:32],
            data['loc'],
            data['ca'],
            data['ce'],
            f"{data['instability']:.3f}",
            f"{data['abstractness']:.3f}",
            f"{data['distance']:.3f}"
        ]
        lines.append(row_str(cols))
    lines.append(sep)
    return "\n".join(lines)


def generate_mermaid(metrics: Dict[str, dict]) -> str:
    lines = ["graph TD;"]
    for mod, data in metrics.items():
        safe_mod = mod.replace('.', '_')
        lines.append(f'  {safe_mod}["{mod}<br/>I={data["instability"]} D={data["distance"]}"]')
        for dep in data['depends_on']:
            safe_dep = dep.replace('.', '_')
            lines.append(f'  {safe_mod} --> {safe_dep}')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Python codebase module coupling, instability, and abstractness metrics."
    )
    parser.add_argument("path", nargs="?", default=".", help="Path to Python project/directory (default: current directory)")
    parser.add_argument("--exclude-tests", action="store_true", help="Exclude test files from analysis")
    parser.add_argument("--sort", choices=["distance", "instability", "abstractness", "ca", "ce", "loc"], default="distance", help="Sort metrics table by field")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--mermaid", action="store_true", help="Output Mermaid.js dependency graph")
    parser.add_argument("--output", "-o", help="Save output to specified file path")

    args = parser.parse_args()
    target_path = Path(args.path).resolve()

    if not target_path.exists():
        print(f"Error: Target path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    metrics = analyze_codebase(target_path, exclude_tests=args.exclude_tests)

    if not metrics:
        print("No Python modules found for analysis.")
        sys.exit(0)

    if args.json:
        output_str = json.dumps(metrics, indent=2)
    elif args.mermaid:
        output_str = generate_mermaid(metrics)
    else:
        avg_instability = sum(m['instability'] for m in metrics.values()) / len(metrics)
        avg_distance = sum(m['distance'] for m in metrics.values()) / len(metrics)
        
        summary = (
            f"--- Python Module Coupling Architecture Report ---\n"
            f"Analyzed Directory : {target_path}\n"
            f"Total Modules      : {len(metrics)}\n"
            f"Average Instability: {avg_instability:.3f}\n"
            f"Average Distance D : {avg_distance:.3f} (Ideal D = 0.000)\n\n"
        )
        output_str = summary + format_table(metrics, sort_by=args.sort)

    if args.output:
        out_file = Path(args.output)
        out_file.write_text(output_str, encoding='utf-8')
        print(f"Report successfully saved to '{out_file}'.")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
