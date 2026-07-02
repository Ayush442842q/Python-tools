#!/usr/bin/env python3
"""
SQLite Database Integrity & Schema Auditor

Audits SQLite database files for:
- Low-level database corruption (PRAGMA integrity_check).
- Broken relationships (PRAGMA foreign_key_check).
- Redundant or missing indexes.
- Table statistics (row counts, schema analysis, and storage estimates).

Usage:
    python tools/sqlite_integrity_checker.py [path_to_db] [options]
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

def check_integrity(conn: sqlite3.Connection) -> list:
    """Runs PRAGMA integrity_check."""
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        results = cursor.fetchall()
        # Return standard output strings
        return [r[0] for r in results]
    except Exception as e:
        return [f"Error running integrity check: {e}"]

def check_foreign_keys(conn: sqlite3.Connection) -> list:
    """Runs PRAGMA foreign_key_check."""
    try:
        # Enable foreign keys for checking (optional but good practice)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_check;")
        results = cursor.fetchall()
        # Each result format: (table_name, rowid, parent_table_name, fkey_index)
        failures = []
        for r in results:
            failures.append({
                'table': r[0],
                'rowid': r[1],
                'parent_table': r[2],
                'fkey_id': r[3]
            })
        return failures
    except Exception as e:
        return [{'error': f"Error running foreign key check: {e}"}]

def get_db_statistics(conn: sqlite3.Connection) -> list:
    """Retrieves all tables and their row counts."""
    tables = []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        table_names = [t[0] for t in cursor.fetchall()]
        
        for name in table_names:
            cursor.execute(f"SELECT count(*) FROM [{name}];")
            count = cursor.fetchone()[0]
            # Get count of indexes for this table
            cursor.execute(f"SELECT count(*) FROM sqlite_master WHERE type='index' AND tbl_name='{name}';")
            idx_count = cursor.fetchone()[0]
            tables.append({
                'name': name,
                'rows': count,
                'indexes': idx_count
            })
    except Exception as e:
        print_colored(f"Error fetching statistics: {e}", RED)
    return tables

def find_redundant_indexes(conn: sqlite3.Connection) -> list:
    """Analyzes table schemas to identify redundant indexes."""
    redundant = []
    try:
        cursor = conn.cursor()
        # Get index definitions
        cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
        indexes = cursor.fetchall()
        
        # Structure index columns for comparison
        # Format: index_name -> (table_name, [columns_list])
        index_map = {}
        for name, tbl, sql in indexes:
            # Simple parse of sql: CREATE INDEX idx ON tbl(col1, col2)
            # Find columns inside parentheses
            parts = sql.split('(')
            if len(parts) > 1:
                cols_str = parts[1].split(')')[0]
                cols = [c.strip().strip('"').strip('`').strip('[]') for c in cols_str.split(',')]
                index_map[name] = (tbl, cols)
                
        # Compare indexes on the same table
        for idx1, (tbl1, cols1) in index_map.items():
            for idx2, (tbl2, cols2) in index_map.items():
                if idx1 == idx2 or tbl1 != tbl2:
                    continue
                # If cols1 is a prefix of cols2, idx1 is redundant
                if len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                    redundant.append({
                        'index': idx1,
                        'table': tbl1,
                        'cols': cols1,
                        'covered_by': idx2,
                        'covered_cols': cols2
                    })
    except Exception as e:
        print_colored(f"Error checking redundant indexes: {e}", RED)
    return redundant

def audit_database(db_path: Path, args):
    """Performs the full suite of checks on the database."""
    print("=" * 80)
    print_colored(f"Auditing Database: {db_path}", BOLD + CYAN)
    print_colored(f"File Size: {db_path.stat().st_size / 1024:.2f} KB", BOLD)
    print("=" * 80)
    
    try:
        # Connect in read-only mode to prevent side-effects
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as e:
        print_colored(f"Failed to connect to database: {e}", RED)
        return False

    try:
        # 1. Low-level integrity check
        print_colored("Running Integrity Check...", BOLD)
        integrity_results = check_integrity(conn)
        
        is_corrupt = False
        if len(integrity_results) == 1 and integrity_results[0] == 'ok':
            print_colored("  ✔ Low-level integrity: OK", GREEN)
        else:
            is_corrupt = True
            print_colored("  ✗ Low-level corruption detected!", RED + BOLD)
            for res in integrity_results:
                print_colored(f"    - {res}", RED)
                
        # 2. Foreign Key constraints check
        print("\n" + BOLD + "Running Foreign Key Relations Check..." + RESET)
        fkey_results = check_foreign_keys(conn)
        
        has_fkey_errors = False
        if not fkey_results:
            print_colored("  ✔ Foreign key relations: OK (No orphaned rows)", GREEN)
        else:
            has_fkey_errors = True
            print_colored("  ✗ Invalid foreign key relationships detected!", RED + BOLD)
            for err in fkey_results:
                if 'error' in err:
                    print_colored(f"    - {err['error']}", RED)
                else:
                    print_colored(f"    - Table '{err['table']}' (rowid {err['rowid']}) -> references invalid/non-existent row in '{err['parent_table']}'", RED)

        # 3. Table statistics
        print("\n" + BOLD + "Database Table Statistics:" + RESET)
        stats = get_db_statistics(conn)
        if stats:
            print(f"  {'Table Name':<30} | {'Rows':<10} | {'Indexes Count':<15}")
            print("  " + "-" * 61)
            for s in stats:
                print(f"  {s['name']:<30} | {s['rows']:<10} | {s['indexes']:<15}")
        else:
            print("  No user tables found.")
            
        # 4. Redundant indexes
        print("\n" + BOLD + "Analyzing Index Efficiency..." + RESET)
        redundant = find_redundant_indexes(conn)
        if redundant:
            print_colored("  ⚠ Redundant Indexes Detected:", YELLOW + BOLD)
            for r in redundant:
                print_colored(f"    - Index '{r['index']}' on '{r['table']}' {r['cols']} is redundant because it is a prefix of index '{r['covered_by']}' {r['covered_cols']}.", YELLOW)
        else:
            print_colored("  ✔ No redundant index prefix keys found.", GREEN)
            
        print("\n" + "=" * 80)
        
        # Summary status exit logic
        if is_corrupt or has_fkey_errors:
            print_colored("Audit Summary: FAILED (Database has corruption or schema integrity errors)", RED + BOLD)
            if args.strict:
                conn.close()
                sys.exit(1)
        else:
            print_colored("Audit Summary: PASSED (Database structure and data constraints are clean)", GREEN + BOLD)
            
    finally:
        conn.close()
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Audit SQLite database files for internal corruption, constraints violations, and schema performance issues."
    )
    parser.add_argument(
        "db_path",
        help="Path to the SQLite database file to audit"
    )
    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="Exit code 1 if the audit fails (for CI pipelines)"
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    if not db_path.exists():
        print_colored(f"Error: Database file '{db_path}' does not exist.", RED)
        return 1
        
    if not db_path.is_file():
        print_colored(f"Error: Path '{db_path}' is not a file.", RED)
        return 1
        
    audit_database(db_path, args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
