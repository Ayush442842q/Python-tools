#!/usr/bin/env python3
"""
C/C++ Preprocessor #include Dependency Graph Visualizer

A standalone static analysis tool to map and audit header file inclusion networks.
1. Recursively scans directories for C/C++ files (.c, .cpp, .cc, .h, .hpp).
2. Parses `#include` directives to distinguish between local ("file.h") and system (<file.h>) inclusions.
3. Detects circular header inclusions (inclusion cycles).
4. Highlights missing or unresolved local headers.
5. Outputs includes as an interactive nested ASCII tree or a Mermaid graph format.

Usage:
    python cpp_include_graph.py [path_to_source_dir]
    python cpp_include_graph.py --format mermaid [path_to_source_dir]
"""

import sys
import os
import argparse
import re

# Regex for local and system headers
INCLUDE_REGEX = re.compile(r'^\s*#\s*include\s+(?:"([^"]+)"|<([^>]+)>)')

def scan_file_includes(filepath):
    """Parses C/C++ file to extract local and system includes."""
    local_includes = []
    system_includes = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = INCLUDE_REGEX.match(line)
                if match:
                    local, system = match.groups()
                    if local:
                        local_includes.append(local)
                    elif system:
                        system_includes.append(system)
    except Exception:
        pass
    return local_includes, system_includes

def find_file_in_workspace(header_name, search_dirs):
    """Attempts to find a local header file in target directories."""
    for s_dir in search_dirs:
        # Check direct path
        target = os.path.join(s_dir, header_name)
        if os.path.isfile(target):
            return os.path.abspath(target)
            
        # Recursive lookup in subfolders
        for root, _, files in os.walk(s_dir):
            if header_name in files:
                return os.path.abspath(os.path.join(root, header_name))
    return None

def build_include_graph(source_dir):
    """Builds a dependency graph from the source directory files."""
    graph = {}
    sys_graph = {}
    abs_to_rel = {}
    
    file_extensions = ('.c', '.cpp', '.cc', '.h', '.hpp', '.cxx', '.hxx')
    all_files = []
    
    # 1. Gather all C/C++ files
    for root, _, files in os.walk(source_dir):
        for f in files:
            if f.lower().endswith(file_extensions):
                full_path = os.path.abspath(os.path.join(root, f))
                all_files.append(full_path)
                rel_path = os.path.relpath(full_path, source_dir)
                abs_to_rel[full_path] = rel_path

    # Search folders include source root
    search_folders = [source_dir]

    # 2. Extract includes for each file
    for filepath in all_files:
        rel_src = abs_to_rel[filepath]
        locals_found, systems_found = scan_file_includes(filepath)
        
        resolved_locals = []
        unresolved_locals = []
        
        for loc in locals_found:
            # First look in same directory as the source file
            local_dir = os.path.dirname(filepath)
            direct_target = os.path.join(local_dir, loc)
            if os.path.isfile(direct_target):
                resolved_abs = os.path.abspath(direct_target)
                resolved_rel = os.path.relpath(resolved_abs, source_dir)
                resolved_locals.append(resolved_rel)
                abs_to_rel[resolved_abs] = resolved_rel
            else:
                # Search broader workspace
                workspace_target = find_file_in_workspace(loc, search_folders)
                if workspace_target:
                    resolved_rel = os.path.relpath(workspace_target, source_dir)
                    resolved_locals.append(resolved_rel)
                    abs_to_rel[workspace_target] = resolved_rel
                else:
                    unresolved_locals.append(loc)
                    
        graph[rel_src] = {
            'includes': resolved_locals,
            'unresolved': unresolved_locals,
            'system': systems_found
        }
        
    return graph, abs_to_rel

def detect_cycles_dfs(node, graph, visited, stack, cycle_path):
    """DFS helper to find circular inclusions."""
    visited.add(node)
    stack.add(node)
    cycle_path.append(node)
    
    if node in graph:
        for neighbor in graph[node]['includes']:
            if neighbor not in visited:
                if detect_cycles_dfs(neighbor, graph, visited, stack, cycle_path):
                    return True
            elif neighbor in stack:
                cycle_path.append(neighbor)
                return True
                
    stack.remove(node)
    cycle_path.pop()
    return False

def print_tree(node, graph, depth=0, visited_nodes=None):
    """Renders inclusion paths as an ASCII tree."""
    if visited_nodes is None:
        visited_nodes = set()
        
    indent = "  " * depth
    marker = "└── " if depth > 0 else ""
    
    try:
        if node in visited_nodes:
            print(f"{indent}{marker}{node} (circular link)")
            return
        print(f"{indent}{marker}{node}")
    except UnicodeEncodeError:
        fallback_marker = "\\-- " if depth > 0 else ""
        if node in visited_nodes:
            print(f"{indent}{fallback_marker}{node} (circular link)")
            return
        print(f"{indent}{fallback_marker}{node}")
    
    if node in graph:
        visited_nodes.add(node)
        for inc in graph[node]['includes']:
            print_tree(inc, graph, depth + 1, visited_nodes.copy())

def generate_mermaid(graph):
    """Compiles include graph into Mermaid Flowchart code."""
    lines = ["graph TD"]
    # Keep track of added relations to avoid duplicates
    relations = set()
    
    for src, info in graph.items():
        src_label = os.path.basename(src)
        lines.append(f'    id_{hash(src):X}["{src_label}"]')
        for inc in info['includes']:
            inc_label = os.path.basename(inc)
            rel = (src, inc)
            if rel not in relations:
                relations.add(rel)
                lines.append(f'    id_{hash(src):X} --> id_{hash(inc):X}')
    return "\n".join(lines)

def run_auditor(source_dir, fmt='tree'):
    """Performs static inclusion audit."""
    if not os.path.exists(source_dir):
        print(f"Error: Directory '{source_dir}' does not exist.", file=sys.stderr)
        return 1

    graph, abs_to_rel = build_include_graph(source_dir)
    
    if not graph:
        print("No C/C++ source or header files found in the directory.")
        return 0

    # 1. Detect cycles
    visited = set()
    stack = set()
    cycle_path = []
    has_cycle = False
    
    for node in graph:
        if node not in visited:
            if detect_cycles_dfs(node, graph, visited, stack, cycle_path):
                has_cycle = True
                break

    # 2. Gather unresolved headers
    unresolved_map = {}
    for node, info in graph.items():
        if info['unresolved']:
            unresolved_map[node] = info['unresolved']

    # REPORTING
    if fmt == 'mermaid':
        print(generate_mermaid(graph))
        return 0

    print("C/C++ #include Dependency Graph Visualizer")
    print("=" * 75)
    print(f"Source Directory: {source_dir}")
    print(f"Total files parsed: {len(graph)}")
    print("=" * 75)

    if has_cycle:
        print("\033[91m[-] Circular Inclusion Loop Detected:\033[0m")
        # Find index of start of cycle to slice loop cleanly
        start_node = cycle_path[-1]
        start_idx = cycle_path.index(start_node)
        clean_cycle = cycle_path[start_idx:]
        print(f"  [!] Loop: {' -> '.join(clean_cycle)}")
        print("-" * 75)

    if unresolved_map:
        print("\033[93m[!] Unresolved Local Headers (Not found in project folders):\033[0m")
        for src, headers in sorted(unresolved_map.items()):
            print(f"  [*] In '{src}':")
            for h in headers:
                print(f"      └── #include \"{h}\"")
        print("-" * 75)

    print("\n[Header Inclusion Tree Layout]")
    print("-" * 75)
    # Print trees for root files (files that are not included by any other file)
    included_files = set()
    for info in graph.values():
        for inc in info['includes']:
            included_files.add(inc)
            
    root_files = [f for f in graph.keys() if f not in included_files]
    if not root_files:
        # If all files are mutually included (or cyclic), just print all files
        root_files = list(graph.keys())
        
    for root in sorted(root_files):
        print_tree(root, graph)
        print()
        
    print("=" * 75)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Extract, trace, and audit C/C++ #include dependencies statically.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source_dir",
        nargs="?",
        default=".",
        help="Path to source directory. Defaults to current directory."
    )
    parser.add_argument(
        "-f", "--format",
        choices=['tree', 'mermaid'],
        default='tree',
        help="Output visualization format. Choices are 'tree' or 'mermaid' graph flowchart."
    )
    args = parser.parse_args()

    return run_auditor(args.source_dir, args.format)

if __name__ == "__main__":
    sys.exit(main())
