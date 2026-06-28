#!/usr/bin/env python3
"""
SQL Dependency Analyzer
Parses SQL schema files to map table and view dependencies, detect circular
references, and determine the correct execution order for creation and teardown.

Usage:
    python tools/sql_dependency_analyzer.py schema.sql
    python tools/sql_dependency_analyzer.py schema.sql --mermaid
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple


# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


class SQLDependencyAnalyzer:
    def __init__(self):
        # Maps table -> set of tables it directly depends on
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        # Set of all tables/views defined
        self.nodes: Set[str] = set()
        # Track types (table vs view)
        self.node_types: Dict[str, str] = {}

    def clean_name(self, name: str) -> str:
        """Strip quotes, brackets, and schema qualifiers from table/view names."""
        name = name.strip().strip('"`[]')
        # Remove schema qualifier, e.g., "public.users" -> "users"
        if "." in name:
            name = name.split(".")[-1].strip('"`[]')
        return name

    def parse_sql_file(self, file_path: str):
        """Read and parse SQL file contents to discover tables, views, and dependencies."""
        if not os.path.exists(file_path):
            print_colored(f"[!] File not found: {file_path}", COLOR_FAIL)
            sys.exit(1)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Remove single-line comments and multi-line comments
        content = re.sub(r"--.*?\n", "\n", content)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

        # Split into statements using semicolons (rough split, but handles most schemas)
        statements = content.split(";")

        for stmt in statements:
            stmt_clean = stmt.strip()
            if not stmt_clean:
                continue

            # Check for CREATE TABLE
            table_match = re.search(
                r"CREATE\s+(?:TEMP\s+|TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.\"`\[\]]+)",
                stmt_clean,
                re.IGNORECASE
            )
            if table_match:
                table_name = self.clean_name(table_match.group(1))
                self.nodes.add(table_name)
                self.node_types[table_name] = "TABLE"
                self.parse_table_dependencies(table_name, stmt_clean)
                continue

            # Check for CREATE VIEW
            view_match = re.search(
                r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([a-zA-Z0-9_.\"`\[\]]+)\s+AS",
                stmt_clean,
                re.IGNORECASE
            )
            if view_match:
                view_name = self.clean_name(view_match.group(1))
                self.nodes.add(view_name)
                self.node_types[view_name] = "VIEW"
                self.parse_view_dependencies(view_name, stmt_clean)
                continue

            # Check for ALTER TABLE ADD FOREIGN KEY
            alter_match = re.search(
                r"ALTER\s+TABLE\s+(?:ONLY\s+)?([a-zA-Z0-9_.\"`\[\]]+)",
                stmt_clean,
                re.IGNORECASE
            )
            if alter_match:
                table_name = self.clean_name(alter_match.group(1))
                # Look for foreign key references within the ALTER statement
                fk_matches = re.finditer(
                    r"FOREIGN\s+KEY\s*\(.*?\)\s*REFERENCES\s+([a-zA-Z0-9_.\"`\[\]]+)",
                    stmt_clean,
                    re.IGNORECASE
                )
                for fk in fk_matches:
                    ref_table = self.clean_name(fk.group(1))
                    self.nodes.add(table_name)
                    self.nodes.add(ref_table)
                    self.dependencies[table_name].add(ref_table)

    def parse_table_dependencies(self, table_name: str, statement: str):
        """Extract foreign keys defined inline or as table constraints in CREATE TABLE."""
        # Search for REFERENCES table_name(column)
        # Matches: REFERENCES table_name, REFERENCES table_name (col), REFERENCES [table_name]
        ref_matches = re.finditer(
            r"REFERENCES\s+([a-zA-Z0-9_.\"`\[\]]+)",
            statement,
            re.IGNORECASE
        )
        for match in ref_matches:
            ref_table = self.clean_name(match.group(1))
            # Don't depend on itself
            if ref_table != table_name:
                self.dependencies[table_name].add(ref_table)

    def parse_view_dependencies(self, view_name: str, statement: str):
        """Estimate view dependencies by finding table names mentioned in SELECT queries."""
        # Find tables after FROM or JOIN clauses
        # Matches: FROM table_name, JOIN table_name, etc.
        from_join_matches = re.finditer(
            r"(?:FROM|JOIN)\s+([a-zA-Z0-9_.\"`\[\]]+)",
            statement,
            re.IGNORECASE
        )
        for match in from_join_matches:
            ref_table = self.clean_name(match.group(1))
            # Filter out SQL keywords that might be matched accidentally
            keywords = {"select", "where", "group", "having", "order", "left", "right", "inner", "outer", "cross", "join"}
            if ref_table.lower() not in keywords and ref_table != view_name:
                self.dependencies[view_name].add(ref_table)

    def find_cycles(self) -> List[List[str]]:
        """Detect all cycles (circular dependencies) in the graph using DFS."""
        visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited
        cycles = []

        def dfs(node: str, path: List[str]):
            visited[node] = 1  # visiting
            path.append(node)

            for neighbor in self.dependencies[node]:
                # If neighbor is not in self.nodes, add it to self.nodes (external reference)
                if neighbor not in self.nodes:
                    continue

                state = visited.get(neighbor, 0)
                if state == 1:  # Cycle detected!
                    cycle_start_idx = path.index(neighbor)
                    cycles.append(path[cycle_start_idx:] + [neighbor])
                elif state == 0:
                    dfs(neighbor, path)

            path.pop()
            visited[node] = 2  # visited

        for node in self.nodes:
            if visited.get(node, 0) == 0:
                dfs(node, [])

        return cycles

    def topological_sort(self) -> List[str]:
        """Perform topological sorting to determine schema creation order."""
        visited = set()
        stack = []

        def dfs(node: str):
            visited.add(node)
            for neighbor in self.dependencies[node]:
                if neighbor in self.nodes and neighbor not in visited:
                    dfs(neighbor)
            stack.append(node)

        for node in sorted(self.nodes):  # Sorted for deterministic results
            if node not in visited:
                dfs(node)

        return stack

    def generate_mermaid(self) -> str:
        """Generate a Mermaid.js diagram definition representing the schema graph."""
        lines = ["graph TD"]
        # Add nodes with style classes
        for node in sorted(self.nodes):
            ntype = self.node_types.get(node, "TABLE")
            if ntype == "VIEW":
                lines.append(f"    {node}([{node} :: View])")
            else:
                lines.append(f"    {node}[{node}]")

        # Add edges
        for node, deps in sorted(self.dependencies.items()):
            for dep in sorted(deps):
                if dep in self.nodes:
                    lines.append(f"    {node} --> {dep}")
        return "\n".join(lines)

    def print_text_report(self):
        """Display a formatted textual summary of the schema dependencies."""
        print_colored(f"\n{COLOR_BOLD}SQL Dependency Analysis Summary{COLOR_END}", COLOR_CYAN)
        print(f"Total Objects Analyzed: {len(self.nodes)} ({list(self.node_types.values()).count('TABLE')} tables, {list(self.node_types.values()).count('VIEW')} views)")
        print("-" * 60)

        # Print direct dependencies
        print_colored("Direct Object Dependencies:", COLOR_BOLD + COLOR_BLUE)
        for node in sorted(self.nodes):
            ntype = self.node_types.get(node, "TABLE")
            deps = self.dependencies[node]
            deps_filtered = [d for d in deps if d in self.nodes]
            if deps_filtered:
                print(f"  - {node} ({ntype}) depends on: {', '.join(deps_filtered)}")
            else:
                print(f"  - {node} ({ntype}) has no internal dependencies")

        # Check and print cycles
        cycles = self.find_cycles()
        print("-" * 60)
        if cycles:
            print_colored("⚠️  CRITICAL: Circular Dependencies Detected!", COLOR_BOLD + COLOR_WARNING)
            for cycle in cycles:
                print(f"   Cycle: {' -> '.join(cycle)}")
            print("   (Warning: Circular foreign keys will block standard schema migrations!)")
        else:
            print_colored("✅ No circular dependencies detected.", COLOR_GREEN)

        # Topological sorting (Creation order)
        try:
            creation_order = self.topological_sort()
            print("-" * 60)
            print_colored("Recommended Creation Order (leaves first):", COLOR_BOLD + COLOR_GREEN)
            for idx, node in enumerate(creation_order, 1):
                ntype = self.node_types.get(node, "TABLE")
                print(f"  {idx:2d}. {node} ({ntype})")

            # Teardown order (reverse creation order)
            print("-" * 60)
            print_colored("Recommended Teardown Order (dependent objects first):", COLOR_BOLD + COLOR_FAIL)
            for idx, node in enumerate(reversed(creation_order), 1):
                ntype = self.node_types.get(node, "TABLE")
                print(f"  {idx:2d}. {node} ({ntype})")
        except Exception as e:
            print_colored(f"\n[!] Failed to compute clean order: {e}", COLOR_FAIL)


def main():
    parser = argparse.ArgumentParser(
        description="SQL Schema Dependency Analyzer - Map table and view dependencies.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sql_file", help="Path to SQL schema definition or dump file")
    parser.add_argument("--mermaid", "-m", action="store_true", help="Output a Mermaid.js diagram instead of a text report")

    args = parser.parse_args()

    analyzer = SQLDependencyAnalyzer()
    analyzer.parse_sql_file(args.sql_file)

    if args.mermaid:
        print(analyzer.generate_mermaid())
    else:
        analyzer.print_text_report()


if __name__ == "__main__":
    main()
