#!/usr/bin/env python3
"""
Python Import Visualizer & Dependency Graph Generator

Analyzes Python source files in a directory, extracts their imports using AST,
resolves them into local, standard library, or third-party categories, and
visualizes the internal dependency graph as a terminal tree or Mermaid.js markup.

Usage:
    python tools/python_import_visualizer.py <directory_path>
    python tools/python_import_visualizer.py . --exclude-stdlib --exclude-external
    python tools/python_import_visualizer.py tools/ --mermaid
"""

import os
import sys
import ast
import argparse
import sysconfig
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Fetch standard library module names dynamically
STDLIB_MODULES = set(sys.builtin_module_names)
# Add names from standard library directory
stdlib_dir = sysconfig.get_path('stdlib')
if stdlib_dir and os.path.exists(stdlib_dir):
    for entry in os.listdir(stdlib_dir):
        name = os.path.splitext(entry)[0]
        if name.isalnum() and not name.startswith('_'):
            STDLIB_MODULES.add(name)

# Hardcoded common stdlib fallbacks
COMMON_STDLIB = {
    "os", "sys", "math", "datetime", "collections", "itertools", "re", "json", "argparse",
    "pathlib", "shutil", "tempfile", "subprocess", "threading", "multiprocessing", "socket",
    "urllib", "http", "sqlite3", "hashlib", "hmac", "uuid", "logging", "time", "ast", "typing",
    "enum", "random", "zipfile", "tarfile", "csv", "xml", "unittest", "functools", "weakref",
    "copy", "pickle", "ctypes", "glob", "platform", "traceback", "inspect", "warnings", "abc"
}
STDLIB_MODULES.update(COMMON_STDLIB)

class ImportExtractor(ast.NodeVisitor):
    """AST Visitor to extract all imports from a file."""
    def __init__(self, current_module_parts: List[str]):
        self.imports: List[Tuple[str, int]] = [] # list of (module_name, level)
        self.current_module_parts = current_module_parts

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((alias.name, 0))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module_name = node.module if node.module else ""
        level = node.level if node.level is not None else 0
        self.imports.append((module_name, level))
        self.generic_visit(node)

def get_module_name_from_path(file_path: str, base_dir: str) -> str:
    """Converts a file path to its dot-separated Python module representation."""
    rel_path = os.path.relpath(file_path, base_dir)
    root, _ = os.path.splitext(rel_path)
    parts = root.replace(os.sep, '/').split('/')
    if parts[-1] == '__init__':
        parts.pop()
    return ".".join(parts)

def find_all_py_files(base_dir: str) -> List[str]:
    """Recursively finds all Python files in a directory."""
    py_files = []
    for root, _, files in os.walk(base_dir):
        # Skip hidden folders and virtual environments
        if any(part.startswith('.') or part in ('venv', '.venv', 'env', 'node_modules', '__pycache__') for part in root.split(os.sep)):
            continue
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files

def resolve_import(imported_name: str, level: int, current_module: str, local_modules: Set[str]) -> Tuple[str, str]:
    """
    Resolves an import to its target module name and classifies it as
    'local', 'stdlib', or 'external'.
    """
    if level > 0:
        # Relative import
        parts = current_module.split('.')
        # level=1 is current directory, level=2 is parent, etc.
        slice_idx = len(parts) - level + 1
        if slice_idx < 0:
            slice_idx = 0
        parent_parts = parts[:slice_idx]
        if imported_name:
            resolved_name = ".".join(parent_parts + [imported_name])
        else:
            resolved_name = ".".join(parent_parts)
        return resolved_name, "local"

    # Absolute import
    first_part = imported_name.split('.')[0]
    
    # Check if it matches any local module
    # Local module match could be exact, or sub-module of a local package
    is_local = False
    for loc in local_modules:
        if imported_name == loc or imported_name.startswith(loc + '.'):
            is_local = True
            break
            
    if is_local:
        return imported_name, "local"
        
    if first_part in STDLIB_MODULES:
        return imported_name, "stdlib"
        
    # Check if first part corresponds to a local folder or file in parent dir context
    if first_part in local_modules:
        return imported_name, "local"

    return imported_name, "external"

def build_dependency_graph(base_dir: str) -> Tuple[Dict[str, Set[str]], Dict[str, Dict[str, str]], Dict[str, str]]:
    """
    Analyzes all Python files in base_dir and returns:
      1. graph: Maps local modules to their resolved dependencies (local and external).
      2. edge_types: Maps local modules -> dependency -> 'local'/'stdlib'/'external'
      3. file_mappings: Maps module name to physical file path.
    """
    py_files = find_all_py_files(base_dir)
    local_modules = set()
    file_mappings = {}

    for py_file in py_files:
        mod_name = get_module_name_from_path(py_file, base_dir)
        local_modules.add(mod_name)
        file_mappings[mod_name] = py_file

    graph = defaultdict(set)
    edge_types = defaultdict(dict)

    for mod_name, file_path in file_mappings.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=file_path)
            extractor = ImportExtractor(mod_name.split('.'))
            extractor.visit(tree)
            
            for imp_name, level in extractor.imports:
                if not imp_name and level == 0:
                    continue
                
                resolved, classification = resolve_import(imp_name, level, mod_name, local_modules)
                if resolved == mod_name:
                    continue # Ignore self-imports
                
                graph[mod_name].add(resolved)
                edge_types[mod_name][resolved] = classification
        except Exception as e:
            # Silently ignore syntax errors in broken scripts
            pass

    return graph, edge_types, file_mappings

def print_mermaid_graph(graph: Dict[str, Set[str]], edge_types: Dict[str, Dict[str, str]], 
                        exclude_stdlib: bool, exclude_external: bool):
    """Prints the graph in Mermaid TD syntax."""
    print("\n" + color_text("--- Mermaid.js Graph Code ---", COLOR_CYAN))
    print("```mermaid")
    print("graph TD")
    
    # Class styles
    print("    classDef local fill:#d4edda,stroke:#28a745,stroke-width:2px;")
    print("    classDef stdlib fill:#fff3cd,stroke:#ffc107,stroke-width:1px;")
    print("    classDef external fill:#f8d7da,stroke:#dc3545,stroke-width:1px;")
    
    printed_nodes = set()
    edges = []
    
    for src, targets in graph.items():
        if src not in printed_nodes:
            print(f'    {src}["{src}"]:::local')
            printed_nodes.add(src)
            
        for tgt in targets:
            classification = edge_types[src][tgt]
            if classification == 'stdlib' and exclude_stdlib:
                continue
            if classification == 'external' and exclude_external:
                continue
                
            if tgt not in printed_nodes:
                if classification == 'local':
                    print(f'    {tgt}["{tgt}"]:::local')
                elif classification == 'stdlib':
                    print(f'    {tgt}["{tgt}"]:::stdlib')
                else:
                    print(f'    {tgt}["{tgt}"]:::external')
                printed_nodes.add(tgt)
                
            edges.append((src, tgt, classification))

    for src, tgt, classification in edges:
        if classification == 'local':
            print(f"    {src} --> {tgt}")
        elif classification == 'stdlib':
            print(f"    {src} -.->|stdlib| {tgt}")
        else:
            print(f"    {src} ==>|ext| {tgt}")
            
    print("```")
    print("-" * 50)

def print_tree(graph: Dict[str, Set[str]], edge_types: Dict[str, Dict[str, str]], 
               exclude_stdlib: bool, exclude_external: bool):
    """Prints a tree visualization of dependencies for each local module."""
    def _print_tree_node(node: str, prefix: str, is_last: bool, visited: Set[str], depth: int):
        if depth > 4: # Stop deep recursions
            print(f"{prefix}{'└── ' if is_last else '├── '}{color_text('...', COLOR_YELLOW)}")
            return
            
        classification = "local"
        # Find classification of this node from parent
        # We search parent references in edge_types
        for parent, targets in edge_types.items():
            if node in targets:
                classification = targets[node]
                break

        node_display = node
        if classification == "local":
            node_display = color_text(node, COLOR_GREEN)
        elif classification == "stdlib":
            node_display = color_text(node + " (stdlib)", COLOR_YELLOW)
        elif classification == "external":
            node_display = color_text(node + " (external)", COLOR_RED)

        marker = "└── " if is_last else "├── "
        print(f"{prefix}{marker}{node_display}")
        
        # Child modules
        if classification != "local":
            return
            
        children = sorted([
            tgt for tgt in graph[node]
            if not (edge_types[node][tgt] == 'stdlib' and exclude_stdlib)
            and not (edge_types[node][tgt] == 'external' and exclude_external)
        ])
        
        if not children:
            return

        new_prefix = prefix + ("    " if is_last else "│   ")
        
        # Avoid circular dependencies stack overflow
        if node in visited:
            print(f"{new_prefix}└── {color_text('[Circular Dependency]', COLOR_RED)}")
            return
            
        visited.add(node)
        for i, child in enumerate(children):
            _print_tree_node(child, new_prefix, i == len(children) - 1, visited.copy(), depth + 1)

    print("\n" + color_text("--- Module Import Tree ---", COLOR_CYAN))
    local_nodes = sorted(list(graph.keys()))
    if not local_nodes:
        print("No local Python modules found.")
        return
        
    for node in local_nodes:
        # If this is a root node (nobody imports it locally), display it
        # Or display everything if they are small
        is_imported = False
        for parent, targets in graph.items():
            if node != parent and node in targets:
                is_imported = True
                break
                
        if not is_imported:
            print(color_text(node, COLOR_BOLD + COLOR_GREEN))
            children = sorted([
                tgt for tgt in graph[node]
                if not (edge_types[node][tgt] == 'stdlib' and exclude_stdlib)
                and not (edge_types[node][tgt] == 'external' and exclude_external)
            ])
            for i, child in enumerate(children):
                _print_tree_node(child, "", i == len(children) - 1, {node}, 1)
            print()

def main():
    parser = argparse.ArgumentParser(
        description="Scan Python files, map internal import dependency networks, and display module hierarchies.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory).")
    parser.add_argument("--exclude-stdlib", action="store_true", help="Exclude standard library modules from graph.")
    parser.add_argument("--exclude-external", action="store_true", help="Exclude external third-party libraries.")
    parser.add_argument("--mermaid", action="store_true", help="Generate Mermaid.js markup for graph visualization.")
    
    args = parser.parse_args()
    
    target_dir = os.path.abspath(args.directory)
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        print(color_text(f"Error: Directory '{args.directory}' does not exist or is not a directory.", COLOR_RED), file=sys.stderr)
        return 1
        
    print(f"Scanning directory: {target_dir}")
    graph, edge_types, file_mappings = build_dependency_graph(target_dir)
    
    # Calculate stats
    local_count = len(file_mappings)
    stdlib_edges = sum(1 for src in edge_types for tgt, t in edge_types[src].items() if t == 'stdlib')
    external_edges = sum(1 for src in edge_types for tgt, t in edge_types[src].items() if t == 'external')
    local_edges = sum(1 for src in edge_types for tgt, t in edge_types[src].items() if t == 'local')
    
    print("-" * 50)
    print(color_text(f"Summary Statistics:", COLOR_BOLD))
    print(f"  Local Modules Found:   {local_count}")
    print(f"  Local-to-Local Imports: {local_edges}")
    print(f"  Standard Library Refs:  {stdlib_edges}")
    print(f"  Third-Party Package Refs: {external_edges}")
    print("-" * 50)
    
    if args.mermaid:
        print_mermaid_graph(graph, edge_types, args.exclude_stdlib, args.exclude_external)
    else:
        print_tree(graph, edge_types, args.exclude_stdlib, args.exclude_external)
        print(color_text("\nTip: Run with --mermaid to get Mermaid.js diagrams to copy/paste.", COLOR_CYAN))
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
