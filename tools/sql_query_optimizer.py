#!/usr/bin/env python3
"""
SQL Query Optimizer & Refactoring Advisor

Statically analyzes SQL queries (SELECT, UPDATE, DELETE) for common performance bottlenecks
such as sargability violations, leading wildcards in LIKE, SELECT * overhead, missing LIMIT clauses,
Cartesian products, and OR clause index-bypasses. Optionally connects to a local SQLite database
to run 'EXPLAIN QUERY PLAN' for dynamic visual execution diagnostics.

Usage:
    python tools/sql_query_optimizer.py "SELECT * FROM users WHERE LOWER(username) = 'admin'"
    python tools/sql_query_optimizer.py -f query.sql --db local.db
"""

import argparse
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

# ANSI color codes for rich reporting
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def strip_ansi(text: str) -> str:
    """Helper to remove ANSI escape sequences for text files or plain-text environments."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class SQLAdvisor:
    """Class to analyze SQL query structures and suggest performance optimizations."""
    def __init__(self, query: str) -> None:
        self.raw_query = query
        self.clean_query = self._clean_query(query)
        self.issues: List[Dict[str, str]] = []
        self.index_recommendations: List[str] = []

    def _clean_query(self, query: str) -> str:
        """Removes comment lines and normalizes whitespaces."""
        # Remove single-line comments
        lines = [re.sub(r'--.*$', '', line) for line in query.splitlines()]
        # Remove multi-line comments
        cleaned = re.sub(r'/\*.*?\*/', '', '\n'.join(lines), flags=re.DOTALL)
        # Normalize whitespace
        return ' '.join(cleaned.split())

    def analyze(self) -> None:
        """Run all static checks against the SQL query."""
        self._check_select_star()
        self._check_leading_wildcard()
        self._check_sargability()
        self._check_implicit_joins()
        self._check_or_clauses()
        self._check_missing_limit()
        self._generate_index_suggestions()

    def _check_select_star(self) -> None:
        """Checks for 'SELECT *' usage."""
        if re.search(r'\bSELECT\s+\*\b', self.clean_query, re.IGNORECASE):
            self.issues.append({
                "category": "SELECT * Overhead",
                "severity": "Low",
                "description": "Using 'SELECT *' fetches all columns from the table.",
                "remedy": "Specify only the columns you need (e.g. 'SELECT id, username'). This reduces network payload, memory usage, and allows index-only scans."
            })

    def _check_leading_wildcard(self) -> None:
        """Checks for LIKE patterns starting with % or _."""
        matches = re.findall(r"\bLIKE\s+['\"]([%_][^'\"]*)['\"]", self.clean_query, re.IGNORECASE)
        if matches:
            for match in matches:
                self.issues.append({
                    "category": "Leading Wildcard in LIKE",
                    "severity": "High",
                    "description": f"The pattern '{match}' starts with a wildcard character (% or _).",
                    "remedy": "Leading wildcards prevent B-Tree indexes from performing range scans, forcing a full table scan. If possible, use prefix matches (e.g. 'LIKE \"pattern%\"'), index substring columns, or use full-text search indexes (FTS)."
                })

    def _check_sargability(self) -> None:
        """Checks for function calls or arithmetic calculations on column names in WHERE clauses."""
        # Matches: WHERE LOWER(col) = 'val' or WHERE YEAR(col) = 2023 or WHERE col + 1 = 10
        # Common functions: LOWER, UPPER, TRIM, YEAR, DATE, SUBSTR, ROUND, COALESCE
        func_patterns = [
            (r"\b(LOWER|UPPER|TRIM|SUBSTR|DATE|YEAR|ROUND|COALESCE)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)\s*[=<>]", "Function applied to column"),
            (r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[\+\-\*\/]\s*\d+\s*[=<>]", "Arithmetic applied to column")
        ]
        
        where_match = re.search(r"\bWHERE\b(.*)", self.clean_query, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            for pattern, name in func_patterns:
                matches = re.findall(pattern, where_clause, re.IGNORECASE)
                if matches:
                    for match in matches:
                        col_affected = match[1] if isinstance(match, tuple) else match
                        self.issues.append({
                            "category": "Non-Sargable Query Condition",
                            "severity": "Medium",
                            "description": f"Function or arithmetic is applied to column '{col_affected}' inside the WHERE clause.",
                            "remedy": f"Applying functions to columns disables standard index searches. Refactor the comparison. E.g., instead of 'LOWER(name) = \"val\"', use case-insensitive collations. Instead of 'col + 1 = 10', use 'col = 9'."
                        })

    def _check_implicit_joins(self) -> None:
        """Checks for legacy implicit joins (comma-separated tables in FROM)."""
        # Matches: FROM table1, table2, table3
        from_match = re.search(r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)+)\b", self.clean_query, re.IGNORECASE)
        if from_match:
            self.issues.append({
                "category": "Implicit Comma Join",
                "severity": "Medium",
                "description": f"Tables are joined implicitly using commas: '{from_match.group(1)}'.",
                "remedy": "Use explicit JOIN syntax (e.g. 'INNER JOIN ... ON ...'). Comma-separated joins can easily slip into accidental Cartesian products (cross joins) if a join predicate is omitted in the WHERE clause."
            })

    def _check_or_clauses(self) -> None:
        """Checks if multiple conditions are joined via OR, which can invalidate single-column indexes."""
        where_match = re.search(r"\bWHERE\b(.*)", self.clean_query, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            if re.search(r"\bOR\b", where_clause, re.IGNORECASE) and not re.search(r"\bLIMIT\b", self.clean_query, re.IGNORECASE):
                self.issues.append({
                    "category": "OR Clause Index Bypass",
                    "severity": "Low",
                    "description": "Query contains an 'OR' operator in the WHERE clause.",
                    "remedy": "OR conditions often make the query planner fall back to full table scans. Consider split queries combined via UNION or UNION ALL, or verify that composite indexes cover all OR conditions."
                })

    def _check_missing_limit(self) -> None:
        """Checks if SELECT statement lacks a LIMIT clause on potentially large datasets."""
        if re.match(r"^SELECT\b", self.clean_query, re.IGNORECASE):
            if not re.search(r"\bLIMIT\b", self.clean_query, re.IGNORECASE):
                self.issues.append({
                    "category": "Missing LIMIT Clause",
                    "severity": "Low",
                    "description": "Select statement doesn't specify a LIMIT restriction.",
                    "remedy": "If the underlying table is large, querying it without a LIMIT can saturate server memory and take excessive I/O. Add a LIMIT clause unless you explicitly need to fetch the entire dataset."
                })

    def _generate_index_suggestions(self) -> None:
        """Finds target columns in WHERE, JOIN, and GROUP/ORDER BY clauses to suggest indexes."""
        # Find table name
        table_match = re.search(r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", self.clean_query, re.IGNORECASE)
        if not table_match:
            return
        table_name = table_match.group(1)

        # Extract columns in WHERE clauses (e.g. username = 'admin' -> username)
        where_match = re.search(r"\bWHERE\b(.*)", self.clean_query, re.IGNORECASE)
        columns = []
        if where_match:
            where_clause = where_match.group(1)
            # Find words followed by operator =, <, >, !=, LIKE, IN
            candidates = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|!=|<|>|LIKE|IN)\b", where_clause, re.IGNORECASE)
            for col in candidates:
                if col.upper() not in ("SELECT", "AND", "OR", "IN", "LIKE", "NULL", "NOT"):
                    columns.append(col.lower())

        # Extract JOIN columns
        join_matches = re.findall(r"\bJOIN\s+[a-zA-Z_][a-zA-Z0-9_]*\s+ON\s+([a-zA-Z_0-9\.\s=]+)", self.clean_query, re.IGNORECASE)
        for join_on in join_matches:
            candidates = re.findall(r"\b(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)\b", join_on)
            for col in candidates:
                if col.upper() not in ("ON", "AND", "OR", "SELECT"):
                    columns.append(col.lower())

        unique_cols = sorted(list(set(columns)))
        if unique_cols:
            cols_str = "_".join(unique_cols)
            idx_name = f"idx_{table_name}_{cols_str}"
            cols_list = ", ".join(unique_cols)
            self.index_recommendations.append(
                f"CREATE INDEX {idx_name} ON {table_name} ({cols_list});"
            )

    def print_report(self) -> None:
        """Print the audit report to stdout."""
        print(f"\n{COLOR_BOLD}=== SQL QUERY OPTIMIZATION REPORT ==={COLOR_RESET}")
        print(f"{COLOR_CYAN}Analyzed Query:{COLOR_RESET} {self.raw_query.strip()}")
        
        if not self.issues:
            print(f"\n{COLOR_GREEN}✔ No performance bottlenecks detected statically!{COLOR_RESET}")
        else:
            print(f"\nFound {len(self.issues)} potential issues:")
            for i, issue in enumerate(self.issues, 1):
                severity_color = COLOR_RED if issue["severity"] == "High" else (COLOR_YELLOW if issue["severity"] == "Medium" else COLOR_CYAN)
                print(f"\n  {i}. [{severity_color}{issue['severity']} Severity{COLOR_RESET}] {COLOR_BOLD}{issue['category']}{COLOR_RESET}")
                print(f"     Description: {issue['description']}")
                print(f"     Remedy:      {issue['remedy']}")

        if self.index_recommendations:
            print(f"\n{COLOR_BOLD}=== SUGGESTED INDEXES ==={COLOR_RESET}")
            for rec in self.index_recommendations:
                print(f"  {COLOR_GREEN}{rec}{COLOR_RESET}")
        print("=" * 45)

def analyze_sqlite_explain(db_path: str, query: str) -> None:
    """Connect to a SQLite DB and run EXPLAIN QUERY PLAN."""
    print(f"\n{COLOR_BOLD}=== SQLITE DYNAMIC EXPLAIN PLAN ==={COLOR_RESET}")
    print(f"Connecting to: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"{COLOR_RED}Error: Database file '{db_path}' not found.{COLOR_RESET}", file=sys.stderr)
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SQLite explain statement prefix
        explain_query = f"EXPLAIN QUERY PLAN {query}"
        cursor.execute(explain_query)
        rows = cursor.fetchall()
        
        if not rows:
            print("  No plan returned.")
            return

        print(f"{COLOR_CYAN}Detailed Execution Path:{COLOR_RESET}")
        # Columns returned: selectid (0), order (1), from (2), detail (3) or id, parent, notused, detail in newer versions
        for row in rows:
            # Format depends on SQLite version. Usually (id, parent, notused, detail) or (selectid, order, from, detail)
            detail = row[-1]
            indent = "  " * int(row[1]) if len(row) > 2 else "  "
            
            # Highlight warnings
            if "SCAN TABLE" in detail:
                detail_colored = f"{COLOR_RED}{detail} (Forces Full Scan){COLOR_RESET}"
            elif "SEARCH TABLE" in detail:
                detail_colored = f"{COLOR_GREEN}{detail} (Uses Index Scan){COLOR_RESET}"
            elif "USING INDEX" in detail:
                detail_colored = f"{COLOR_GREEN}{detail}{COLOR_RESET}"
            else:
                detail_colored = detail
                
            print(f"{indent}└─ {detail_colored}")
            
    except sqlite3.Error as e:
        print(f"{COLOR_RED}SQLite error running EXPLAIN: {e}{COLOR_RESET}", file=sys.stderr)
    finally:
        if 'conn' in locals():
            conn.close()
    print("=" * 45)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SQL Query Optimizer & Refactoring Advisor"
    )
    parser.add_argument(
        "query", nargs="?", help="SQL Query statement to analyze"
    )
    parser.add_argument(
        "-f", "--file", help="Read SQL query from a text file"
    )
    parser.add_argument(
        "--db", help="Path to local SQLite database to execute dynamic EXPLAIN query plans"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )

    args = parser.parse_args()

    # Resolve query source
    query_text = ""
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            query_text = f.read()
    elif args.query:
        query_text = args.query
    else:
        print("Error: Please provide a SQL query string or specify a file (-f).", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if not query_text.strip():
        print("Error: SQL query is empty.", file=sys.stderr)
        sys.exit(1)

    # Disable colors if requested
    if args.no-color or sys.platform == "win32":
        # Windows CMD/Powershell doesn't always render ANSI colors natively unless configured
        # We can strip them out, or keep them if standard terminal supports them.
        # Let's check if the user asked to strip them.
        if args.no_color:
            global COLOR_GREEN, COLOR_YELLOW, COLOR_RED, COLOR_CYAN, COLOR_BOLD, COLOR_RESET
            COLOR_GREEN = COLOR_YELLOW = COLOR_RED = COLOR_CYAN = COLOR_BOLD = COLOR_RESET = ""

    advisor = SQLAdvisor(query_text)
    advisor.analyze()
    advisor.print_report()

    if args.db:
        analyze_sqlite_explain(args.db, query_text)

if __name__ == "__main__":
    main()
