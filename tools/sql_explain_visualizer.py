#!/usr/bin/env python3
"""
SQL Explain Query Plan Visualizer

Runs an SQL query against a SQLite database, parses the EXPLAIN QUERY PLAN output,
and generates a hierarchical ASCII/Unicode tree diagram highlighting performance hotspots.

Usage:
    python tools/sql_explain_visualizer.py [database_file] "[sql_query]" [options]

Requirements:
    - Python 3.6+
    - SQLite3 (built-in)
"""

import sys
import os
import sqlite3
import argparse
from typing import List, Dict, Tuple, Any, Optional

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"

class PlanNode:
    def __init__(self, node_id: int, parent_id: int, detail: str):
        self.node_id = node_id
        self.parent_id = parent_id
        self.detail = detail
        self.children: List['PlanNode'] = []

    def add_child(self, child: 'PlanNode'):
        self.children.append(child)

def fetch_query_plan(db_path: str, query: str) -> List[Tuple[int, int, str]]:
    """Connect to SQLite database, execute EXPLAIN QUERY PLAN, and return rows."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Strip trailing semicolon if present
    query = query.strip().rstrip(';')
    explain_query = f"EXPLAIN QUERY PLAN {query}"
    
    try:
        cursor.execute(explain_query)
        rows = cursor.fetchall()
        col_names = [description[0].lower() for description in cursor.description]
        
        parsed_rows = []
        # Handle SQLite schema changes:
        # Modern: id (int), parent (int), notused (int), detail (text)
        # Ancient: selectid (int), order (int), from (int), detail (text)
        if "id" in col_names and "parent" in col_names:
            id_idx = col_names.index("id")
            parent_idx = col_names.index("parent")
            detail_idx = col_names.index("detail")
            for r in rows:
                parsed_rows.append((int(r[id_idx]), int(r[parent_idx]), str(r[detail_idx])))
        else:
            # Fallback mapping selectid as node_id and from as parent_id
            # Or use indices directly
            for i, r in enumerate(rows):
                # If we don't have clear parent-child IDs, we treat them as sequential sibling/child list
                # based on row index and selectid. Let's map it safely.
                node_id = r[0] if len(r) > 0 else i
                parent_id = r[2] if len(r) > 2 else 0 # 'from' or order
                detail = r[3] if len(r) > 3 else str(r[-1])
                parsed_rows.append((int(node_id), int(parent_id), str(detail)))
                
        return parsed_rows
    except sqlite3.Error as e:
        raise sqlite3.Error(f"SQLite error running EXPLAIN: {e}")
    finally:
        conn.close()

def build_plan_tree(rows: List[Tuple[int, int, str]]) -> List[PlanNode]:
    """Reconstruct parent-child tree hierarchy from SQLite plan rows."""
    nodes: Dict[int, PlanNode] = {}
    roots: List[PlanNode] = []
    
    # 1. Create nodes
    for node_id, parent_id, detail in rows:
        nodes[node_id] = PlanNode(node_id, parent_id, detail)
        
    # 2. Build relationships
    for node_id, node in nodes.items():
        parent_id = node.parent_id
        # In SQLite, parent_id of 0 is a root if there's no node with ID 0 as its parent.
        # Wait, if a node's parent_id is not in nodes, or matches parent_id == node_id,
        # or parent_id == 0 and 0 is not in nodes, then it's a root.
        if parent_id in nodes and parent_id != node_id:
            nodes[parent_id].add_child(node)
        else:
            roots.append(node)
            
    return roots

def colorize_detail(detail: str, use_color: bool) -> str:
    """Format and color-code query plan details to emphasize issues/optimizations."""
    if not use_color:
        return detail
        
    # Highlight SCAN (full table scans are generally bad)
    if "SCAN TABLE" in detail:
        detail = detail.replace("SCAN TABLE", f"{COLOR_RED}{COLOR_BOLD}SCAN TABLE{COLOR_RESET}")
        
    # Highlight SEARCH (index searches are generally good)
    elif "SEARCH TABLE" in detail:
        detail = detail.replace("SEARCH TABLE", f"{COLOR_GREEN}{COLOR_BOLD}SEARCH TABLE{COLOR_RESET}")
        
    # Highlight USING INDEX (good)
    if "USING INDEX" in detail:
        detail = detail.replace("USING INDEX", f"{COLOR_GREEN}USING INDEX{COLOR_RESET}")
    elif "USING COVERING INDEX" in detail:
        detail = detail.replace("USING COVERING INDEX", f"{COLOR_GREEN}USING COVERING INDEX{COLOR_RESET}")
        
    # Highlight TEMP B-TREE (slow, requires writing temporary indexes/tables)
    if "USE TEMP B-TREE" in detail:
        detail = detail.replace("USE TEMP B-TREE", f"{COLOR_YELLOW}{COLOR_BOLD}USE TEMP B-TREE{COLOR_RESET}")
        
    # Highlight SUBQUERY (subqueries can be hotspots)
    if "SUBQUERY" in detail:
        detail = detail.replace("SUBQUERY", f"{COLOR_CYAN}SUBQUERY{COLOR_RESET}")
        
    return detail

def render_tree(node: PlanNode, prefix: str = "", is_last: bool = True, use_color: bool = True, use_unicode: bool = True) -> List[str]:
    """Recursively render the plan tree to ASCII/Unicode format."""
    lines = []
    
    # Select markers
    if use_unicode:
        marker = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "
    else:
        marker = "`-- " if is_last else "|-- "
        child_prefix = "    " if is_last else "|   "
        
    # Format and colorize detail
    colored_detail = colorize_detail(node.detail, use_color)
    lines.append(f"{prefix}{marker}{colored_detail}")
    
    # Recurse for children
    num_children = len(node.children)
    for i, child in enumerate(node.children):
        child_is_last = (i == num_children - 1)
        lines.extend(render_tree(
            child, 
            prefix + child_prefix, 
            child_is_last, 
            use_color, 
            use_unicode
        ))
        
    return lines

def analyze_hotspots(rows: List[Tuple[int, int, str]]) -> List[str]:
    """Statically analyze query plan detail lines for performance warnings."""
    warnings = []
    for _, _, detail in rows:
        if "SCAN TABLE" in detail:
            # Extract table name
            parts = detail.split("SCAN TABLE")
            table = parts[1].strip().split()[0] if len(parts) > 1 else "unknown"
            warnings.append(f"Table Scan: '{table}' has no matching index. Row-by-row scanning performed. ({detail})")
        if "USE TEMP B-TREE" in detail:
            warnings.append(f"Temp Sorting: SQLite created a temporary B-Tree index for sorting (ORDER BY/GROUP BY). Consider adding a composite index. ({detail})")
        if "SUBQUERY" in detail:
            warnings.append(f"Correlated Subquery: Executing nested subquery. May execute once per outer row. ({detail})")
    return warnings

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualize and analyze SQLite query execution plans.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "database",
        help="Path to the SQLite database file"
    )
    parser.add_argument(
        "query",
        help="SQL query string to explain"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in output"
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Use basic ASCII characters instead of Unicode box-drawing characters"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Just print raw SQLite explain query plan table rows"
    )
    
    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty()
    use_unicode = not args.ascii
    
    try:
        rows = fetch_query_plan(args.database, args.query)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except sqlite3.Error as e:
        print(f"Error: Failed to explain query: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
        
    if not rows:
        print("Query executed, but explain query plan returned empty results.")
        return 0
        
    if args.raw:
        print(f"{'ID':<5} {'Parent':<8} {'Detail'}")
        print("-" * 60)
        for rid, pid, detail in rows:
            print(f"{rid:<5} {pid:<8} {detail}")
        return 0
        
    # Reconstruct plan tree
    roots = build_plan_tree(rows)
    
    print("\n" + "="*80)
    print("QUERY PLAN VISUALIZATION")
    print("="*80)
    print(f"Database: {args.database}")
    print(f"Query:    {args.query.strip()}")
    print("-" * 80 + "\n")
    
    for root in roots:
        tree_lines = render_tree(root, use_color=use_color, use_unicode=use_unicode)
        for line in tree_lines:
            print(line)
            
    # Analyze warnings
    warnings = analyze_hotspots(rows)
    if warnings:
        print("\n" + "="*80)
        if use_color:
            print(f"{COLOR_YELLOW}{COLOR_BOLD}PERFORMANCE AUDIT & RECOMMENDATIONS{COLOR_RESET}")
        else:
            print("PERFORMANCE AUDIT & RECOMMENDATIONS")
        print("="*80)
        for w in warnings:
            if use_color:
                print(f" {COLOR_YELLOW}* {COLOR_RESET}{w}")
            else:
                print(f" * {w}")
        print("\nTip: Run 'CREATE INDEX index_name ON table_name(column_name);' to resolve Table Scans.")
    else:
        print("\n" + "="*80)
        if use_color:
            print(f"{COLOR_GREEN}{COLOR_BOLD}PERFORMANCE AUDIT: PASS{COLOR_RESET}")
        else:
            print("PERFORMANCE AUDIT: PASS")
        print("="*80)
        print(" Nice! The query plan utilizes indexes and avoids full table scans or temp sorting.")
        
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
