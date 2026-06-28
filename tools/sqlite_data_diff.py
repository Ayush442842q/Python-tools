#!/usr/bin/env python3
"""
SQLite Database Data Diff Tool
Compare rows of matching tables between two SQLite database files based on primary keys.
Detects added, deleted, and modified rows, and displays differences in a clean terminal layout.
"""

import argparse
import json
import os
import sqlite3
import sys
from typing import Dict, List, Set, Tuple, Any

# ANSI colors for styling
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_MAGENTA = "\033[35m"

def get_connection(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        print(f"{COLOR_RED}Error: Database file '{db_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"{COLOR_RED}Error connecting to '{db_path}': {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

def get_tables(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row['name'] for row in cursor.fetchall()]

def get_table_schema(conn: sqlite3.Connection, table_name: str) -> Tuple[List[str], List[str]]:
    """Returns (columns, primary_keys)"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    rows = cursor.fetchall()
    columns = [row['name'] for row in rows]
    pks = [row['name'] for row in rows if row['pk'] > 0]
    # Sort primary keys by their pk index in case of composite keys
    pks_sorted = sorted([row for row in rows if row['pk'] > 0], key=lambda r: r['pk'])
    pks = [row['name'] for row in pks_sorted]
    return columns, pks

def fetch_table_data(conn: sqlite3.Connection, table_name: str) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    columns, pks = get_table_schema(conn, table_name)
    if not pks:
        # If no primary key, we fallback to using all columns as a composite identifier
        # or we hash the entire row.
        pks = columns

    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()
    
    data = {}
    for row in rows:
        pk_val = tuple(row[pk] for pk in pks)
        data[pk_val] = dict(row)
    return data

def compare_tables(
    db1_conn: sqlite3.Connection, 
    db2_conn: sqlite3.Connection, 
    table_name: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[str]]:
    """Compares table data and returns (added, deleted, modified, columns, primary_keys)"""
    cols1, pks1 = get_table_schema(db1_conn, table_name)
    cols2, pks2 = get_table_schema(db2_conn, table_name)
    
    # Ensure schemas are matching enough to compare
    common_cols = list(set(cols1) & set(cols2))
    
    data1 = fetch_table_data(db1_conn, table_name)
    data2 = fetch_table_data(db2_conn, table_name)
    
    added = []
    deleted = []
    modified = []
    
    # Keys in db1 but not db2 (Deleted)
    for pk_val, row1 in data1.items():
        if pk_val not in data2:
            deleted.append(row1)
        else:
            row2 = data2[pk_val]
            diffs = {}
            for col in common_cols:
                if row1[col] != row2[col]:
                    diffs[col] = (row1[col], row2[col])
            if diffs:
                modified.append({
                    'pk': pk_val,
                    'old': row1,
                    'new': row2,
                    'diffs': diffs
                })
                
    # Keys in db2 but not db1 (Added)
    for pk_val, row2 in data2.items():
        if pk_val not in data1:
            added.append(row2)
            
    return added, deleted, modified, common_cols, pks1

def print_table_diff(
    table_name: str, 
    added: List[Dict[str, Any]], 
    deleted: List[Dict[str, Any]], 
    modified: List[Dict[str, Any]], 
    columns: List[str],
    pks: List[str],
    verbose: bool
):
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Table: {table_name} ==={COLOR_RESET}")
    print(f"Primary Key(s): {', '.join(pks) if pks else 'None (using all columns)'}")
    print(f"Summary: {COLOR_GREEN}+{len(added)} Added{COLOR_RESET} | {COLOR_RED}-{len(deleted)} Deleted{COLOR_RESET} | {COLOR_YELLOW}~{len(modified)} Modified{COLOR_RESET}")

    if not added and not deleted and not modified:
        print(f"{COLOR_GREEN}✔ Data is identical.{COLOR_RESET}")
        return

    # Helper for formatting primary key values
    def fmt_pk(row, pks):
        if len(pks) == 1:
            return str(row[pks[0]])
        return "(" + ", ".join(str(row[k]) for k in pks) + ")"

    # Display Deleted
    if deleted and (verbose or len(deleted) <= 10):
        print(f"\n{COLOR_RED}--- Deleted Rows ({len(deleted)}) ---{COLOR_RESET}")
        for row in deleted:
            pk_str = fmt_pk(row, pks)
            print(f"  Key {COLOR_BOLD}{pk_str}{COLOR_RESET}: {row}")
    elif deleted:
        print(f"\n{COLOR_RED}--- Deleted Rows ({len(deleted)}) ---{COLOR_RESET} (Use --verbose to see all)")

    # Display Added
    if added and (verbose or len(added) <= 10):
        print(f"\n{COLOR_GREEN}+++ Added Rows ({len(added)}) +++{COLOR_RESET}")
        for row in added:
            pk_str = fmt_pk(row, pks)
            print(f"  Key {COLOR_BOLD}{pk_str}{COLOR_RESET}: {row}")
    elif added:
        print(f"\n{COLOR_GREEN}+++ Added Rows ({len(added)}) +++{COLOR_RESET} (Use --verbose to see all)")

    # Display Modified
    if modified and (verbose or len(modified) <= 10):
        print(f"\n{COLOR_YELLOW}~~~ Modified Rows ({len(modified)}) ~~~{COLOR_RESET}")
        for item in modified:
            pk_str = "(" + ", ".join(str(v) for v in item['pk']) + ")" if len(pks) > 1 else str(item['pk'][0])
            print(f"  Key {COLOR_BOLD}{pk_str}{COLOR_RESET}:")
            for col, (old_val, new_val) in item['diffs'].items():
                print(f"    {col}: {COLOR_RED}{old_val}{COLOR_RESET} -> {COLOR_GREEN}{new_val}{COLOR_RESET}")
    elif modified:
        print(f"\n{COLOR_YELLOW}~~~ Modified Rows ({len(modified)}) ~~~{COLOR_RESET} (Use --verbose to see all)")

def main():
    parser = argparse.ArgumentParser(description="Compare data between matching tables of two SQLite databases.")
    parser.add_index = False  # Avoid conflicts
    parser.add_argument("db1", help="Path to the first (source) SQLite database")
    parser.add_argument("db2", help="Path to the second (target) SQLite database")
    parser.add_argument("-t", "--table", help="Specific table to compare (default: compare all matching tables)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print all added/deleted/modified rows")
    parser.add_argument("-j", "--json", help="Export diff summary to a JSON file")
    
    args = parser.parse_args()
    
    db1_conn = get_connection(args.db1)
    db2_conn = get_connection(args.db2)
    
    tables1 = set(get_tables(db1_conn))
    tables2 = set(get_tables(db2_conn))
    
    common_tables = sorted(list(tables1 & tables2))
    
    if not common_tables:
        print(f"{COLOR_RED}Error: No common tables found between the two databases.{COLOR_RESET}")
        sys.exit(1)
        
    if args.table:
        if args.table not in common_tables:
            print(f"{COLOR_RED}Error: Table '{args.table}' is not a common table.{COLOR_RESET}")
            print(f"Common tables: {', '.join(common_tables)}")
            sys.exit(1)
        tables_to_compare = [args.table]
    else:
        tables_to_compare = common_tables
        print(f"Found {len(common_tables)} common tables to compare: {', '.join(common_tables)}")

    diff_report = {}
    
    for table in tables_to_compare:
        added, deleted, modified, cols, pks = compare_tables(db1_conn, db2_conn, table)
        
        print_table_diff(table, added, deleted, modified, cols, pks, args.verbose)
        
        if args.json:
            # Prepare JSON-serializable diff representation
            diff_report[table] = {
                "summary": {
                    "added_count": len(added),
                    "deleted_count": len(deleted),
                    "modified_count": len(modified)
                },
                "added": [dict(r) for r in added],
                "deleted": [dict(r) for r in deleted],
                "modified": [
                    {
                        "pk": list(m['pk']),
                        "diffs": {col: {"old": val[0], "new": val[1]} for col, val in m['diffs'].items()}
                    } for m in modified
                ]
            }
            
    if args.json:
        try:
            with open(args.json, 'w') as f:
                json.dump(diff_report, f, indent=2)
            print(f"\n{COLOR_GREEN}✔ Diff report written to {args.json}{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error writing JSON report: {e}{COLOR_RESET}", file=sys.stderr)

    db1_conn.close()
    db2_conn.close()

if __name__ == "__main__":
    main()
