#!/usr/bin/env python3
"""
Python Dependency Cycle Detector

Scans a directory of Python files, parses their import statements (absolute, relative,
and from-style) using AST, builds a directed dependency graph, and detects circular
imports (import cycles) that can lead to circular import errors in Python.

Usage:
    python python_dependency_cycle_detector.py [path] [options]
"""

import os
import sys
import ast
import argparse
import json

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class ImportVisitor(ast.NodeVisitor):
    def __init__(self, current_file, root_dir):
        self.current_file = current_file
        self.root_dir = root_dir
        # Set of resolved imported file paths
        self.imports = set()
        
        # Calculate current package path components for relative imports
        try:
            rel_path = os.path.relpath(current_file, root_dir)
            parts = rel_path.split(os.sep)
            # The current module name parts relative to root
            self.module_parts = parts[:-1]
            if parts[-1] != "__init__.py":
                self.module_parts.append(parts[-1][:-3]) # remove .py
        except Exception:
            self.module_parts = []

    def visit_Import(self, node):
        for alias in node.names:
            self._resolve_absolute_import(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        level = node.level or 0
        
        if level > 0:
            # Relative import
            self._resolve_relative_import(module, level)
        else:
            # Absolute import
            self._resolve_absolute_import(module)
            # Sometimes imports are like "from module import submodule" where submodule is a file
            for alias in node.names:
                self._resolve_absolute_import(f"{module}.{alias.name}")
                
        self.generic_visit(node)

    def _resolve_absolute_import(self, dotted_name):
        """Try to resolve an absolute import to a local python file."""
        parts = dotted_name.split('.')
        
        # Check standard path resolutions relative to root dir
        # E.g., if dotted_name is "tools.hello", check "tools/hello.py" or "tools/hello/__init__.py"
        # We also check direct sub-path resolution (e.g. if root is "tools", "hello" refers to "tools/hello.py")
        
        # Path option 1: Directly relative to root
        path_opt1 = os.path.join(self.root_dir, *parts)
        # Path option 2: Relative to root but skipping first package if it matches root name
        root_name = os.path.basename(self.root_dir)
        path_opt2 = None
        if parts[0] == root_name and len(parts) > 1:
            path_opt2 = os.path.join(self.root_dir, *parts[1:])
            
        for path_base in filter(None, [path_opt1, path_opt2]):
            py_file = f"{path_base}.py"
            init_file = os.path.join(path_base, "__init__.py")
            
            if os.path.isfile(py_file):
                self.imports.add(os.path.normpath(py_file))
                return
            if os.path.isfile(init_file):
                self.imports.add(os.path.normpath(init_file))
                return
                
        # Also check relative to current file's directory (absolute imports are sometimes implicitly relative in Python 2 or local execution)
        curr_dir = os.path.dirname(self.current_file)
        path_opt3 = os.path.join(curr_dir, *parts)
        py_file = f"{path_opt3}.py"
        init_file = os.path.join(path_opt3, "__init__.py")
        if os.path.isfile(py_file):
            self.imports.add(os.path.normpath(py_file))
            return
        if os.path.isfile(init_file):
            self.imports.add(os.path.normpath(init_file))
            return

    def _resolve_relative_import(self, dotted_name, level):
        """Try to resolve a relative import (from . or ..) to a local python file."""
        # level=1 means current directory, level=2 means parent directory, etc.
        if level > len(self.module_parts):
            # Out of bounds relative import
            return
            
        target_parts = self.module_parts[:-level] if level > 0 else self.module_parts
        if dotted_name:
            target_parts.extend(dotted_name.split('.'))
            
        path_base = os.path.join(self.root_dir, *target_parts)
        py_file = f"{path_base}.py"
        init_file = os.path.join(path_base, "__init__.py")
        
        if os.path.isfile(py_file):
            self.imports.add(os.path.normpath(py_file))
        elif os.path.isfile(init_file):
            self.imports.add(os.path.normpath(init_file))

def find_all_cycles(graph):
    """
    Find circular dependencies in a directed graph.
    Returns a list of unique cycles. Each cycle is represented as a tuple of nodes.
    """
    cycles = set()
    
    def dfs(node, path, visited):
        if node in path:
            # Found a cycle! Extract the cycle path
            cycle_start = path.index(node)
            cycle_path = path[cycle_start:]
            # Normalize cycle representation so that the lexically smallest node is first
            # to avoid duplicate cycles with different starting nodes (e.g. A->B->A vs B->A->B)
            min_idx = cycle_path.index(min(cycle_path))
            normalized = cycle_path[min_idx:] + cycle_path[:min_idx]
            cycles.add(tuple(normalized))
            return
            
        if node in visited:
            return
            
        visited.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            dfs(neighbor, path, visited)
            
        path.pop()
        visited.remove(node) # Unmark visited to allow other paths to find cycles passing through it

    # Run DFS from every node to ensure we cover all components
    for start_node in graph:
        dfs(start_node, [], set())
        
    return sorted(list(cycles), key=len)

def build_dependency_graph(root_dir, py_files):
    """Scan all Python files and construct a graph of dependencies."""
    graph = {}
    normalized_files = {os.path.normpath(f) for f in py_files}
    
    for filepath in py_files:
        norm_path = os.path.normpath(filepath)
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content, filepath)
            visitor = ImportVisitor(norm_path, root_dir)
            visitor.visit(tree)
            
            # Filter dependencies: keep only files that are part of the scanned files
            # to ignore standard library or external packages
            local_deps = visitor.imports.intersection(normalized_files)
            # Remove self imports if any
            local_deps.discard(norm_path)
            
            graph[norm_path] = list(local_deps)
        except Exception:
            # If syntax error or parse error, initialize with empty deps
            graph[norm_path] = []
            
    return graph

def main():
    parser = argparse.ArgumentParser(description="Detect circular dependencies in Python source trees.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory to analyze (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Print complete import dependencies for each file")
    
    args = parser.parse_args()
    
    target_path = os.path.abspath(args.path)
    if not os.path.exists(target_path):
        print(f"Error: Path '{target_path}' does not exist.")
        sys.exit(1)
        
    # Walk and collect python files
    py_files = []
    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            py_files.append(target_path)
            root_dir = os.path.dirname(target_path)
        else:
            print("Error: Target path must be a Python script or a directory.")
            sys.exit(1)
    else:
        root_dir = target_path
        for root, _, files in os.walk(target_path):
            # Exclude standard virtualenv folders and dotfolders
            if any(part in root.split(os.sep) for part in [".git", "venv", ".venv", "env", "__pycache__", "build", "dist"]):
                continue
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
                    
    if not py_files:
        print("No Python files (.py) found to analyze.")
        sys.exit(0)
        
    print(f"Building dependency graph for {len(py_files)} Python files...")
    graph = build_dependency_graph(root_dir, py_files)
    
    # Detect cycles
    cycles = find_all_cycles(graph)
    
    # Calculate rel paths for clean reporting
    rel_graph = {}
    for node, edges in graph.items():
        rel_node = os.path.relpath(node, root_dir).replace("\\", "/")
        rel_edges = [os.path.relpath(edge, root_dir).replace("\\", "/") for edge in edges]
        rel_graph[rel_node] = rel_edges
        
    rel_cycles = []
    for cycle in cycles:
        rel_cycle = [os.path.relpath(node, root_dir).replace("\\", "/") for node in cycle]
        rel_cycles.append(rel_cycle)
        
    if args.json:
        output = {
            "summary": {
                "total_files": len(py_files),
                "cycles_found": len(cycles)
            },
            "cycles": rel_cycles,
            "dependencies": rel_graph
        }
        print(json.dumps(output, indent=2))
        
    else:
        print(f"\n{BOLD}{CYAN}=== PYTHON DEPENDENCY CYCLE DETECTOR ===={RESET}\n")
        print(f"Root Directory: {root_dir}")
        print(f"Files Analyzed: {len(py_files)}")
        print(f"Cycles Detected: {RED if len(cycles) > 0 else GREEN}{len(cycles)}{RESET}\n")
        
        if cycles:
            print(f"{BOLD}{RED}Circular Dependencies Detected:{RESET}")
            print("-" * 50)
            for idx, cycle in enumerate(rel_cycles):
                # Format: module_a -> module_b -> module_a
                cycle_str = " -> ".join(cycle) + f" -> {RED}{cycle[0]}{RESET}"
                print(f"  Cycle #{idx+1} (length {len(cycle)}):")
                print(f"    {cycle_str}")
            print("-" * 50)
            print(f"{YELLOW}Warning: Circular imports can cause unexpected ImportError/AttributeError at runtime!{RESET}")
        else:
            print(f"{GREEN}✔ No circular dependencies found! Base import tree is a clean DAG (Directed Acyclic Graph).{RESET}")
            
        if args.verbose:
            print(f"\n{BOLD}Parsed Local Module Dependencies:{RESET}")
            for node, edges in sorted(rel_graph.items()):
                if edges:
                    print(f"  {node} imports:")
                    for edge in sorted(edges):
                        print(f"    ↳ {edge}")
                else:
                    print(f"  {node} (no local dependencies)")
        print()
        
    if cycles:
        sys.exit(1)

if __name__ == "__main__":
    main()
