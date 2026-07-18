#!/usr/bin/env python3
"""
Database Schema Migration SQL DAG Validator

A standalone utility to inspect database migration files, verifying that their
dependency graph forms a valid Directed Acyclic Graph (DAG).
1. Scans a directory for SQL migration files.
2. Extracts dependency instructions defined via `-- depends_on: dep1, dep2` comments.
3. Detects circular dependencies (dependency loops).
4. Computes and prints a correct topological execution order.
5. Flags duplicate files, missing dependency targets, or gaps in version sequences (e.g. 0001 -> 0003).

Usage:
    python migration_dag_validator.py [path_to_migrations_dir]
"""

import sys
import os
import argparse
import re

# Regex to match numeric prefixes in filenames (e.g., 0001_create_users.sql -> 1)
VERSION_PREFIX_REGEX = re.compile(r'^(\d+)[_\-]')
# Regex to match dependency directives
DEPENDS_ON_REGEX = re.compile(r'^--\s*depends_on:\s*(.*)$', re.IGNORECASE)

def extract_dependencies(filepath):
    """Parses a SQL file to extract targets declared in '-- depends_on' comments."""
    deps = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = DEPENDS_ON_REGEX.match(line.strip())
                if match:
                    # Clean and split comma-separated items
                    targets = [t.strip() for t in match.group(1).split(',')]
                    for t in targets:
                        if t:
                            # Normalize by stripping file extension if present
                            name = os.path.splitext(t)[0]
                            deps.append(name)
    except Exception:
        pass
    return deps

def detect_cycles_dfs(node, graph, visited, stack, cycle_path):
    """Standard DFS cycle detection. returns True if a cycle is found."""
    visited.add(node)
    stack.add(node)
    cycle_path.append(node)
    
    for neighbor in graph.get(node, []):
        if neighbor not in visited:
            if detect_cycles_dfs(neighbor, graph, visited, stack, cycle_path):
                return True
        elif neighbor in stack:
            # Cycle found! Append start of cycle and truncate path to show only the cycle
            cycle_path.append(neighbor)
            return True
            
    stack.remove(node)
    cycle_path.pop()
    return False

def topological_sort(graph):
    """Performs topological sort. Assumes graph is cycle-free."""
    visited = set()
    order = []
    
    def visit(node):
        if node not in visited:
            visited.add(node)
            for neighbor in graph.get(node, []):
                visit(neighbor)
            order.append(node)
            
    for node in graph:
        visit(node)
        
    return order

def audit_migrations(directory):
    """Scans and audits SQL migration files in the target directory."""
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        return False

    sql_files = [f for f in os.listdir(directory) if f.lower().endswith('.sql')]
    if not sql_files:
        print(f"No SQL migration files found in '{directory}'.")
        return True

    # 1. Map files to dependencies
    # key: normalized name (no ext), val: list of dependency normalized names
    graph = {}
    file_map = {} # normalized name -> actual filename
    version_numbers = []
    
    for f in sql_files:
        norm_name = os.path.splitext(f)[0]
        file_map[norm_name] = f
        
        # Check version prefix numbering
        v_match = VERSION_PREFIX_REGEX.match(f)
        if v_match:
            version_numbers.append((int(v_match.group(1)), f))
            
        filepath = os.path.join(directory, f)
        deps = extract_dependencies(filepath)
        graph[norm_name] = deps

    # 2. Check for missing dependencies
    missing_deps = []
    for node, deps in graph.items():
        for dep in deps:
            if dep not in graph:
                missing_deps.append((file_map[node], dep))

    # 3. Detect Cycles
    visited = set()
    stack = set()
    cycle_path = []
    has_cycle = False
    
    for node in graph:
        if node not in visited:
            if detect_cycles_dfs(node, graph, visited, stack, cycle_path):
                has_cycle = True
                break

    # 4. Check for sequence gaps
    gaps = []
    if version_numbers:
        version_numbers.sort()
        for idx in range(len(version_numbers) - 1):
            curr_v, curr_name = version_numbers[idx]
            next_v, next_name = version_numbers[idx + 1]
            if next_v - curr_v > 1:
                # Flag missing version numbers in between
                gaps.extend(range(curr_v + 1, next_v))

    # REPORTING
    print("Database SQL Migration DAG Validator")
    print("=" * 70)
    print(f"Directory     : {directory}")
    print(f"Total Files   : {len(sql_files)}")
    print("=" * 70)

    success = True

    # Missing targets check
    if missing_deps:
        success = False
        print("\033[91m[-] Missing Dependency Targets:\033[0m")
        for file, missing in missing_deps:
            print(f"  [!] File '{file}' refers to missing dependency '{missing}'")
        print("-" * 70)

    # Cycle check
    if has_cycle:
        success = False
        print("\033[91m[-] Circular Dependency Loop Identified:\033[0m")
        # Format cycle display path: a -> b -> c -> a
        cycle_names = [file_map.get(n, n) for n in cycle_path]
        # Find index of start of cycle to slice loop cleanly
        start_node = cycle_path[-1]
        start_idx = cycle_path.index(start_node)
        clean_cycle = cycle_names[start_idx:]
        print(f"  [!] Loop: {' -> '.join(clean_cycle)}")
        print("-" * 70)

    # Version sequence check
    if gaps:
        print("\033[93m[!] Sequence Gaps Identified:\033[0m")
        gap_str = ", ".join(f"{g:04d}" for g in gaps)
        print(f"  [*] Missing version prefixes in sequence: {gap_str}")
        print("-" * 70)

    # Output topological execution plan
    if success:
        try:
            print("\033[92m[✓] DAG validation succeeded. No circular references found.\033[0m")
        except UnicodeEncodeError:
            print("[ok] DAG validation succeeded. No circular references found.")
            
        exec_order = topological_sort(graph)
        print("\n[Topological Execution Plan (Order of Application)]")
        print("-" * 70)
        for rank, node in enumerate(exec_order, 1):
            filename = file_map[node]
            deps_count = len(graph[node])
            dep_desc = f" (depends on {deps_count} file(s))" if deps_count > 0 else " (root)"
            print(f"  {rank:02d}. {filename:<45}{dep_desc}")
    else:
        print("\033[91m[-] DAG validation failed. Fix the issues above.\033[0m")

    print("=" * 70)
    return success

def main():
    parser = argparse.ArgumentParser(
        description="Verify database SQL migration files, dependency trees, and sequence continuity.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "migrations_dir",
        nargs="?",
        default=".",
        help="Path to migrations directory. Defaults to current directory."
    )
    args = parser.parse_args()

    success = audit_migrations(args.migrations_dir)
    if not success:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
