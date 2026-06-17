#!/usr/bin/env python3
"""
SQLite Query Profiler & Index Suggester

Executes database queries, runs timing benchmarks, extracts query plans (EXPLAIN
QUERY PLAN) to detect full table scans, and automatically suggests index
creations to improve execution speeds. All queries are rolled back by default to
prevent accidental modification.

Usage:
    python tools/sqlite_query_profiler.py -d test.db -q "SELECT * FROM users WHERE email = 'test@example.com'"
    python tools/sqlite_query_profiler.py --db my_app.db --file query.sql --runs 10
    python tools/sqlite_query_profiler.py -d test.db -q "INSERT INTO logs (level) VALUES ('info')" --commit
"""

import os
import sys
import time
import sqlite3
import argparse
import statistics
import re
from typing import Dict, List, Tuple, Any, Optional

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

def get_query_plan(conn: sqlite3.Connection, query: str) -> List[Tuple[int, int, int, str]]:
    """Retrieves the SQLite query plan using EXPLAIN QUERY PLAN."""
    plan_rows = []
    try:
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {query}")
        plan_rows = cursor.fetchall()
    except Exception as e:
        # Some queries might not support EXPLAIN (e.g. empty or administrative commands)
        pass
    return plan_rows

def parse_tables_from_query(query: str) -> List[str]:
    """Extracts potential table names from simple SQL queries using regex."""
    # Normalize query whitespace
    normalized = re.sub(r'\s+', ' ', query).lower()
    
    # Simple regex to find names after FROM or JOIN
    matches = re.findall(r'\b(?:from|join)\s+([a-zA-Z0-9_"]+)', normalized)
    
    tables = []
    for m in matches:
        # Strip quotes
        table = m.replace('"', '').replace('`', '')
        if table not in tables:
            tables.append(table)
    return tables

def get_table_indexes(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    """Retrieves index information for a specific table."""
    indexes = []
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA index_list({table})")
        idx_list = cursor.fetchall()
        for idx in idx_list:
            seq, name, unique, origin, partial = idx
            # Get index details (columns)
            cursor.execute(f"PRAGMA index_info({name})")
            cols = [row[2] for row in cursor.fetchall()]
            indexes.append({
                "name": name,
                "unique": bool(unique),
                "columns": cols
            })
    except Exception:
        pass
    return indexes

def analyze_query_plan(plan: List[Tuple[int, int, int, str]], query: str, conn: sqlite3.Connection) -> List[str]:
    """Analyzes the query plan and suggests database optimization indices."""
    suggestions = []
    
    # We parse plan details. A typical plan record contains: (id, parent, notused, detail)
    for row in plan:
        detail = row[3] if len(row) > 3 else str(row)
        
        # Look for SCAN TABLE or SEARCH TABLE detail
        # Example detail: "SCAN TABLE users" or "SEARCH TABLE users USING INDEX sqlite_autoindex_users_1 (id=?)"
        scan_match = re.search(r'\bSCAN TABLE\s+([a-zA-Z0-9_"]+)', detail)
        if scan_match:
            table = scan_match.group(1).replace('"', '').replace('`', '')
            
            # Extract WHERE clause variables to suggest column index
            where_match = re.search(r'\bwhere\s+(.*?)(?:\border\s+by|\blimit|\bgroup\s+by|$)', query, re.IGNORECASE)
            suggested_cols = []
            if where_match:
                where_clause = where_match.group(1)
                # Find columns being compared: e.g. column = ? or column = 'val'
                col_matches = re.findall(r'\b([a-zA-Z0-9_]+)\s*(?:=|!=|<|>|<=|>=|like|in)\b', where_clause)
                for col in col_matches:
                    if col.lower() not in ('null', 'true', 'false', 'and', 'or') and col not in suggested_cols:
                        suggested_cols.append(col)
            
            # Also check if there's an ORDER BY column
            order_match = re.search(r'\border\s+by\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
            if order_match:
                order_col = order_match.group(1)
                if order_col not in suggested_cols:
                    suggested_cols.append(order_col)
                    
            if suggested_cols:
                # Retrieve current indices to check if one already covers this
                existing = get_table_indexes(conn, table)
                covered = False
                for idx in existing:
                    # If the first column of an existing index matches our main filter column, it's mostly covered
                    if idx["columns"] and idx["columns"][0] == suggested_cols[0]:
                        covered = True
                        break
                        
                if not covered:
                    cols_str = ", ".join(suggested_cols[:2]) # suggest single or composite index
                    idx_name = f"idx_{table}_{'_'.join(suggested_cols[:2])}"
                    s = f"CREATE INDEX {idx_name} ON {table}({cols_str});"
                    suggestions.append(f"Table '{table}' is scanned fully (SCAN TABLE). Consider creating index:\n   {color_text(s, COLOR_GREEN)}")
            else:
                suggestions.append(f"Table '{table}' is scanned fully (SCAN TABLE). Try adding indexes on columns used in WHERE/JOIN conditions.")
                
    return suggestions

def profile_query(db_path: str, query: str, runs: int, commit: bool) -> Dict[str, Any]:
    """Runs timing benchmarks, retrieves query plan and stats."""
    result = {
        "query": query,
        "runs": runs,
        "success": False,
        "error": "",
        "timings": [],
        "avg_time_ms": 0.0,
        "min_time_ms": 0.0,
        "max_time_ms": 0.0,
        "std_dev_ms": 0.0,
        "rows_returned": 0,
        "plan": [],
        "suggestions": [],
        "involved_tables": []
    }
    
    # Establish connection
    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        result["error"] = f"Failed to connect to database: {str(e)}"
        return result

    try:
        # 1. Warm up and verify query syntax/returns
        # We wrap in transaction
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()
        
        start_warm = time.perf_counter()
        cursor.execute(query)
        rows = cursor.fetchall()
        end_warm = time.perf_counter()
        
        result["rows_returned"] = len(rows)
        # Always rollback the warmup query
        conn.execute("ROLLBACK;")
        
        # 2. Benchmark runs
        timings = []
        for i in range(runs):
            conn.execute("BEGIN TRANSACTION;")
            cursor = conn.cursor()
            
            t_start = time.perf_counter()
            cursor.execute(query)
            cursor.fetchall()
            t_end = time.perf_counter()
            
            # Rollback to keep environment clean
            conn.execute("ROLLBACK;")
            
            timings.append((t_end - t_start) * 1000.0) # convert to milliseconds
            
        result["timings"] = timings
        result["avg_time_ms"] = statistics.mean(timings)
        result["min_time_ms"] = min(timings)
        result["max_time_ms"] = max(timings)
        result["std_dev_ms"] = statistics.stdev(timings) if len(timings) > 1 else 0.0
        
        # 3. Retrieve query plan
        result["plan"] = get_query_plan(conn, query)
        
        # 4. Resolve tables and suggest indexes
        result["involved_tables"] = parse_tables_from_query(query)
        result["suggestions"] = analyze_query_plan(result["plan"], query, conn)
        
        # 5. Optional real commit
        if commit:
            try:
                conn.execute("BEGIN TRANSACTION;")
                cursor = conn.cursor()
                cursor.execute(query)
                conn.commit()
                result["committed"] = True
            except Exception as commit_err:
                conn.execute("ROLLBACK;")
                result["committed"] = False
                result["commit_error"] = str(commit_err)
                
        result["success"] = True

    except Exception as e:
        result["error"] = f"SQL Execution Error: {str(e)}"
        try:
            conn.execute("ROLLBACK;")
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()
        
    return result

def main():
    parser = argparse.ArgumentParser(
        description="SQLite query performance benchmark, plan debugger, and index advisor.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-d", "--db", required=True, help="Path to SQLite database file.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-q", "--query", help="SQL query string to profile.")
    group.add_argument("-f", "--file", help="Path to a .sql file containing the query.")
    
    parser.add_argument("-r", "--runs", type=int, default=5, help="Number of benchmark iterations (default: 5).")
    parser.add_argument("--commit", action="store_true", help="Actually commit mutations to the database after benchmarking.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(color_text(f"Error: Database file '{args.db}' not found.", COLOR_RED), file=sys.stderr)
        return 1

    sql_query = args.query
    if args.file:
        if not os.path.exists(args.file):
            print(color_text(f"Error: SQL file '{args.file}' not found.", COLOR_RED), file=sys.stderr)
            return 1
        with open(args.file, 'r', encoding='utf-8') as f:
            sql_query = f.read()

    sql_query = sql_query.strip()
    if not sql_query:
        print(color_text("Error: Query string is empty.", COLOR_RED), file=sys.stderr)
        return 1
        
    if args.runs < 1:
        print(color_text("Error: Runs must be at least 1.", COLOR_RED), file=sys.stderr)
        return 1
        
    print(f"Profiling query against: {os.path.abspath(args.db)}")
    print(f"Benchmark iterations:    {args.runs}")
    print("-" * 80)
    print(f"{color_text('Target Query:', COLOR_BOLD)}")
    print(color_text(sql_query, COLOR_CYAN))
    print("-" * 80)

    report = profile_query(args.db, sql_query, args.runs, args.commit)
    
    if not report["success"]:
        print(color_text(f"Error: {report['error']}", COLOR_RED), file=sys.stderr)
        return 2

    # Output stats
    print(f"{color_text('Performance Benchmark Results:', COLOR_BOLD)}")
    print(f"  Rows Returned:       {report['rows_returned']}")
    print(f"  Average Time:        {color_text(f'{report['avg_time_ms']:.4f} ms', COLOR_GREEN if report['avg_time_ms'] < 10 else COLOR_YELLOW)}")
    print(f"  Minimum Time:        {report['min_time_ms']:.4f} ms")
    print(f"  Maximum Time:        {report['max_time_ms']:.4f} ms")
    if args.runs > 1:
        print(f"  Standard Deviation:  {report['std_dev_ms']:.4f} ms")
        
    if args.commit:
        if report.get("committed"):
            print(color_text("  Database Mutation:   Changes successfully COMMITTED.", COLOR_GREEN))
        else:
            print(color_text(f"  Database Mutation:   Commit FAILED! Details: {report.get('commit_error')}", COLOR_RED))
    else:
        print("  Database Mutation:   None (Transactions rolled back safely).")
        
    print("-" * 80)

    # Output Query Plan
    if report["plan"]:
        print(f"{color_text('SQLite Explain Query Plan:', COLOR_BOLD)}")
        # Format of EXPLAIN QUERY PLAN details in modern SQLite:
        # selectid, order, from, detail OR id, parent, notused, detail
        for row in report["plan"]:
            # Display hierarchy using indent based on parent-child IDs if possible
            row_id = row[0]
            parent_id = row[1]
            detail = row[3] if len(row) > 3 else str(row)
            
            # Calculate simple indent level
            indent = "  "
            if parent_id > 0:
                indent = "    " * min(parent_id, 4)
                
            if "SCAN TABLE" in detail:
                print(f"{indent}{color_text('→', COLOR_RED)} {color_text(detail, COLOR_RED)}")
            elif "SEARCH TABLE" in detail:
                print(f"{indent}{color_text('→', COLOR_GREEN)} {color_text(detail, COLOR_GREEN)}")
            else:
                print(f"{indent}• {detail}")
        print("-" * 80)
        
    # Output Suggestions
    if report["suggestions"]:
        print(f"{color_text('Advisor Recommendations & Optimization Suggestions:', COLOR_BOLD)}")
        for idx, s in enumerate(report["suggestions"], 1):
            print(f" {idx}. {s}\n")
    else:
        print(color_text("✓ Index Advisor: No obvious full-table scans found or tables are indexed properly!", COLOR_GREEN))
        
    print("-" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
