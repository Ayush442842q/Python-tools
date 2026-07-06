#!/usr/bin/env python3
"""
Python Module Dependency Matrix & Circular Dependency Visualizer

Scans a directory of Python files, analyzes module import relationships,
computes an N x N dependency matrix, calculates instability metrics,
detects circular dependencies, and exports to table, JSON, CSV, or Mermaid diagrams.

Usage:
    python python_module_dependency_matrix.py [directory] [options]
"""

import os
import sys
import ast
import argparse
import json
import csv
from typing import Dict, List, Set, Tuple

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class ModuleImportVisitor(ast.NodeVisitor):
    """AST visitor to extract imported module names from a Python source file."""
    def __init__(self, current_mod: str, all_modules: Set[str]):
        self.current_mod = current_mod
        self.all_modules = all_modules
        self.imported_modules: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._add_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self._add_import(node.module)
        self.generic_visit(node)

    def _add_import(self, name: str):
        # Resolve target module if it matches one of our local scanned modules
        for mod in self.all_modules:
            if mod == name or name.startswith(mod + "."):
                if mod != self.current_mod:
                    self.imported_modules.add(mod)
                break


def discover_python_modules(root_dir: str, exclude_dirs: Set[str]) -> Dict[str, str]:
    """Finds all python files in root_dir and maps module_name -> file_path."""
    modules = {}
    abs_root = os.path.abspath(root_dir)
    
    for dirpath, dirnames, filenames in os.walk(abs_root):
        # Filter out excluded directory names
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs and not d.startswith(".")]
        
        for file in filenames:
            if file.endswith(".py"):
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, abs_root)
                parts = rel_path.split(os.sep)
                
                # Remove extension
                if parts[-1].endswith(".py"):
                    parts[-1] = parts[-1][:-3]
                if parts[-1] == "__init__":
                    parts.pop()
                    
                if parts:
                    mod_name = ".".join(parts)
                    modules[mod_name] = full_path

    return modules


def build_dependency_matrix(modules: Dict[str, str]) -> Tuple[List[str], Dict[str, Dict[str, int]]]:
    """Parses files and returns (sorted_module_list, matrix_dict)."""
    mod_list = sorted(modules.keys())
    all_mods_set = set(mod_list)
    matrix = {m1: {m2: 0 for m2 in mod_list} for m1 in mod_list}

    for mod_name, file_path in modules.items():
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            visitor = ModuleImportVisitor(mod_name, all_mods_set)
            visitor.visit(tree)
            
            for target_mod in visitor.imported_modules:
                matrix[mod_name][target_mod] = 1
        except Exception:
            # Skip unparseable files gracefully
            pass

    return mod_list, matrix


def find_cycles(mod_list: List[str], matrix: Dict[str, Dict[str, int]]) -> List[List[str]]:
    """Finds elementary cycles using Tarjan's SCC / DFS approach."""
    cycles = []
    visited = set()
    stack = []
    stack_set = set()

    def dfs(node):
        visited.add(node)
        stack.append(node)
        stack_set.add(node)

        for neighbor in mod_list:
            if matrix[node][neighbor] > 0:
                if neighbor in stack_set:
                    # Found cycle
                    idx = stack.index(neighbor)
                    cycle = stack[idx:]
                    cycles.append(cycle)
                elif neighbor not in visited:
                    dfs(neighbor)

        stack.pop()
        stack_set.remove(node)

    for mod in mod_list:
        if mod not in visited:
            dfs(mod)

    return cycles


def compute_metrics(mod_list: List[str], matrix: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, float]]:
    """
    Computes module stability metrics:
    - Efferent Coupling (Ce): Number of outward dependencies
    - Afferent Coupling (Ca): Number of incoming dependencies
    - Instability (I): Ce / (Ca + Ce) [0.0 = completely stable, 1.0 = completely unstable]
    """
    metrics = {}
    for mod in mod_list:
        ce = sum(matrix[mod][target] for target in mod_list)
        ca = sum(matrix[src][mod] for src in mod_list)
        instability = round(ce / (ca + ce), 2) if (ca + ce) > 0 else 0.0
        metrics[mod] = {"Ca": ca, "Ce": ce, "Instability": instability}
    return metrics


def render_table(mod_list: List[str], matrix: Dict[str, Dict[str, int]], metrics: Dict[str, Dict[str, float]]):
    """Prints ANSI formatted ASCII table of dependency matrix."""
    if not mod_list:
        print(f"{YELLOW}No Python modules found.{RESET}")
        return

    print(f"\n{BOLD}{CYAN}=== Python Module Dependency Matrix ({len(mod_list)} Modules) ==={RESET}\n")
    
    # Header
    short_names = [m.split(".")[-1][:6] for m in mod_list]
    header_str = f"{'Module':<35} | " + " ".join(f"{s:>6}" for s in short_names) + " | Ca  Ce  Inst"
    print(BOLD + header_str + RESET)
    print("-" * len(header_str))

    for mod in mod_list:
        row_cells = []
        for target in mod_list:
            val = matrix[mod][target]
            if val > 0:
                row_cells.append(f"{RED}  1   {RESET}" if matrix[target][mod] > 0 else f"{GREEN}  1   {RESET}")
            else:
                row_cells.append(f"{CYAN}  .   {RESET}")
                
        m = metrics[mod]
        mod_label = mod[:34]
        print(f"{mod_label:<35} |" + "".join(row_cells) + f"| {m['Ca']:>3} {m['Ce']:>3} {m['Instability']:>5.2f}")

    print("\n" + f"{BOLD}Legend:{RESET} {GREEN}1{RESET} = Outward dependency, {RED}1{RESET} = Mutual/Circular dependency, {CYAN}.{RESET} = No direct import\n")


def export_mermaid(mod_list: List[str], matrix: Dict[str, Dict[str, int]]) -> str:
    """Generates Mermaid.js flowchart string."""
    lines = ["graph TD;"]
    for src in mod_list:
        src_id = src.replace(".", "_")
        lines.append(f'  {src_id}["{src}"]')
        for target in mod_list:
            if matrix[src][target] > 0:
                target_id = target.replace(".", "_")
                lines.append(f"  {src_id} --> {target_id}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Python Module Dependency Matrix & Circular Dependency Visualizer")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan for Python modules (default: current dir)")
    parser.add_argument("--exclude", nargs="*", default=["venv", ".venv", "__pycache__", "tests", "build", "dist"], help="Directories to exclude")
    parser.add_argument("--format", choices=["table", "json", "csv", "mermaid"], default="table", help="Output format (default: table)")
    parser.add_argument("--output", "-o", help="Save output to file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"{RED}Error: Directory '{args.directory}' does not exist.{RESET}")
        sys.exit(1)

    exclude_set = set(args.exclude)
    modules = discover_python_modules(args.directory, exclude_set)
    mod_list, matrix = build_dependency_matrix(modules)
    metrics = compute_metrics(mod_list, matrix)
    cycles = find_cycles(mod_list, matrix)

    if args.format == "table":
        render_table(mod_list, matrix, metrics)
        if cycles:
            print(f"{BOLD}{RED}=== Circular Dependency Cycles Detected ({len(cycles)}) ==={RESET}")
            for idx, c in enumerate(cycles, 1):
                cycle_str = " -> ".join(c) + f" -> {c[0]}"
                print(f"  {idx}. {YELLOW}{cycle_str}{RESET}")
            print()
        else:
            print(f"{GREEN}No circular dependency cycles detected.{RESET}\n")

    elif args.format == "json":
        data = {
            "modules": mod_list,
            "matrix": matrix,
            "metrics": metrics,
            "cycles": cycles
        }
        output_str = json.dumps(data, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"{GREEN}Saved JSON report to {args.output}{RESET}")
        else:
            print(output_str)

    elif args.format == "csv":
        output_rows = []
        header = ["Source_Module"] + mod_list + ["Ca", "Ce", "Instability"]
        output_rows.append(header)
        for mod in mod_list:
            row = [mod] + [matrix[mod][t] for t in mod_list] + [metrics[mod]["Ca"], metrics[mod]["Ce"], metrics[mod]["Instability"]]
            output_rows.append(row)
            
        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(output_rows)
            print(f"{GREEN}Saved CSV matrix to {args.output}{RESET}")
        else:
            writer = csv.writer(sys.stdout)
            writer.writerows(output_rows)

    elif args.format == "mermaid":
        mermaid_str = export_mermaid(mod_list, matrix)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(mermaid_str)
            print(f"{GREEN}Saved Mermaid diagram to {args.output}{RESET}")
        else:
            print(mermaid_str)


if __name__ == "__main__":
    main()
