#!/usr/bin/env python3
import os
import re
import argparse
import sys
from collections import defaultdict

# Simple ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

def clean_sql_comments(content):
    """
    Removes single-line (--) and multi-line (/* ... */) SQL comments.
    """
    # Remove single line comments
    content = re.sub(r'--.*$', '', content, flags=re.MULTILINE)
    # Remove block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    return content

def parse_sql_dependencies(sql_content):
    """
    Parses SQL schema DDL and extracts dependency relationships.
    Returns: dict of table_name -> set of referenced_tables
    """
    dependencies = defaultdict(set)
    sql_content = clean_sql_comments(sql_content)
    
    # 1. Parse CREATE TABLE statements
    # We match: CREATE TABLE <name> ( <body> )
    # Using a nested paren tracker or a block parser to find matches.
    # To keep it robust, we look for matches of CREATE TABLE followed by table name,
    # and then grab content up to the matching closing parenthesis of that table block.
    table_blocks = []
    create_table_regex = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:["`]?\w+["`]?\.)?["`]?(\w+)["`]?\s*\(', re.IGNORECASE)
    
    for match in create_table_regex.finditer(sql_content):
        table_name = match.group(1)
        # Find closing paren matching the start paren of this CREATE TABLE
        start_idx = match.end() - 1
        paren_count = 0
        end_idx = -1
        for i in range(start_idx, len(sql_content)):
            char = sql_content[i]
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                if paren_count == 0:
                    end_idx = i
                    break
        
        if end_idx != -1:
            body = sql_content[start_idx+1:end_idx]
            table_blocks.append((table_name, body))
            
    # 2. Extract inline references from CREATE TABLE bodies
    # Example: REFERENCES other_table(col) or REFERENCES other_table (col)
    references_regex = re.compile(r'REFERENCES\s+(?:["`]?\w+["`]?\.)?["`]?(\w+)["`]?\s*(?:\([^)]*\))?', re.IGNORECASE)
    
    for table_name, body in table_blocks:
        # Scan body for REFERENCES
        for ref_match in references_regex.finditer(body):
            ref_table = ref_match.group(1)
            # Avoid self-references
            if ref_table.lower() != table_name.lower():
                dependencies[table_name].add(ref_table)

    # 3. Parse ALTER TABLE statements with FOREIGN KEY addition
    # Example: ALTER TABLE child ADD CONSTRAINT fk FOREIGN KEY (col) REFERENCES parent (col)
    alter_regex = re.compile(
        r'ALTER\s+TABLE\s+(?:["`]?\w+["`]?\.)?["`]?(\w+)["`]?\s+ADD\s+(?:CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY\s*\([^)]*\)\s*REFERENCES\s+(?:["`]?\w+["`]?\.)?["`]?(\w+)["`]?',
        re.IGNORECASE
    )
    
    for match in alter_regex.finditer(sql_content):
        table_name = match.group(1)
        ref_table = match.group(2)
        if ref_table.lower() != table_name.lower():
            dependencies[table_name].add(ref_table)

    return dependencies

def find_cycles(graph):
    """
    Finds all simple cycles in a directed graph using DFS.
    Returns: list of lists representing cycles.
    """
    cycles = []
    visited = {}
    path = []

    def dfs(node):
        visited[node] = 1 # Visiting
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if visited.get(neighbor, 0) == 1:
                # Cycle detected!
                cycle_start_idx = path.index(neighbor)
                cycle = path[cycle_start_idx:] + [neighbor]
                cycles.append(cycle)
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor)
                
        path.pop()
        visited[node] = 2 # Visited

    for node in graph:
        if visited.get(node, 0) == 0:
            dfs(node)

    return cycles

def generate_mermaid(graph):
    """
    Generates Mermaid JS graph representation of table dependencies.
    """
    lines = ["graph TD"]
    for node, targets in graph.items():
        for target in targets:
            lines.append(f"    {node} --> {target}")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Scan SQL schemas for foreign key circular dependency cycles."
    )
    parser.add_argument("path", help="Path to SQL DDL file or directory of SQL files")
    parser.add_argument(
        "-m", "--mermaid", 
        action="store_true", 
        help="Output Mermaid JS diagram to stdout if cycles are found"
    )
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting SQL Schema Circular Dependency Auditor...{COLOR_RESET}")
    print("-" * 65)

    all_dependencies = defaultdict(set)

    if os.path.isfile(args.path):
        try:
            with open(args.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            deps = parse_sql_dependencies(content)
            for k, v in deps.items():
                all_dependencies[k].update(v)
        except Exception as e:
            print(f"{COLOR_RED}Error reading {args.path}: {e}{COLOR_RESET}")
            sys.exit(1)
    else:
        for root, _, files in os.walk(args.path):
            if "node_modules" in root or ".git" in root:
                continue
            for file in files:
                if file.lower().endswith(".sql"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        deps = parse_sql_dependencies(content)
                        for k, v in deps.items():
                            all_dependencies[k].update(v)
                    except Exception as e:
                        print(f"{COLOR_YELLOW}Warning: Error reading {file_path}: {e}{COLOR_RESET}")

    # Standardize keys/values to string lists
    graph = {k: list(v) for k, v in all_dependencies.items()}
    
    # Track all referenced nodes that might not have dependencies of their own
    all_nodes = set(graph.keys())
    for targets in graph.values():
        all_nodes.update(targets)
    for node in all_nodes:
        if node not in graph:
            graph[node] = []

    cycles = find_cycles(graph)

    print(f"{COLOR_BOLD}Analysis Results:{COLOR_RESET}")
    print(f"  Total tables detected: {len(all_nodes)}")
    
    if cycles:
        print(f"  {COLOR_RED}Result: Detected {len(cycles)} circular dependency loops!{COLOR_RESET}")
        for idx, cycle in enumerate(cycles, 1):
            path_str = " -> ".join(f"'{n}'" for n in cycle)
            print(f"    Cycle #{idx}: {path_str}")
        
        if args.mermaid:
            print(f"\n{COLOR_CYAN}Mermaid Diagram Structure:{COLOR_RESET}")
            print(generate_mermaid(graph))
            
        sys.exit(1)
    else:
        print(f"  {COLOR_GREEN}Result: No circular dependency cycles found. Clean schema topology.{COLOR_RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
