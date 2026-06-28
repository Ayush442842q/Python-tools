#!/usr/bin/env python3
"""
SQLite Index Advisor
Analyzes SQLite database files to recommend performance optimizations:
- Identifies tables without Primary Keys
- Finds foreign key columns that lack indexes (which slows down JOINs)
- Identifies redundant or duplicate indexes
- Runs EXPLAIN QUERY PLAN on specified SQL queries and recommends indexes to fix full table scans

License: MIT
"""

import os
import sys
import sqlite3
import re
import argparse

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}[i] {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}[✗] Error: {msg}{Colors.ENDC}", file=sys.stderr)

def get_db_schema(conn):
    """Gathers tables, columns, primary keys, foreign keys, and indexes from the SQLite db."""
    cursor = conn.cursor()
    schema = {}
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        # Get column details
        cursor.execute(f"PRAGMA table_info('{table}');")
        cols_info = cursor.fetchall()
        
        columns = []
        pks = []
        for col in cols_info:
            col_name = col[1]
            col_type = col[2]
            is_pk = col[5] > 0
            columns.append({'name': col_name, 'type': col_type})
            if is_pk:
                pks.append(col_name)
                
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list('{table}');")
        fks_info = cursor.fetchall()
        fks = []
        for fk in fks_info:
            fks.append({
                'from': fk[3],
                'to_table': fk[2],
                'to': fk[4]
            })
            
        # Get indexes
        cursor.execute(f"PRAGMA index_list('{table}');")
        indexes_info = cursor.fetchall()
        indexes = {}
        
        for idx in indexes_info:
            idx_name = idx[1]
            is_unique = idx[2] == 1
            
            # Get columns in index
            cursor.execute(f"PRAGMA index_info('{idx_name}');")
            idx_cols = [row[2] for row in cursor.fetchall()]
            
            indexes[idx_name] = {
                'columns': idx_cols,
                'unique': is_unique
            }
            
        schema[table] = {
            'columns': columns,
            'primary_keys': pks,
            'foreign_keys': fks,
            'indexes': indexes
        }
        
    return schema

def analyze_schema(schema):
    """Performs schema rules check to recommend primary keys, FK indexes, and redundant index removals."""
    print_header("Schema Analysis & Advisor")
    issues_found = 0

    for table, info in schema.items():
        print(f"\n{Colors.BOLD}Table: {table}{Colors.ENDC}")
        table_issues = 0
        
        # 1. Check Primary Key
        if not info['primary_keys']:
            print(f"  {Colors.RED}✘ No Primary Key{Colors.ENDC}: Table does not define a primary key.")
            print(f"    {Colors.BLUE}Tip:{Colors.ENDC} Adding an INTEGER PRIMARY KEY provides a fast rowid alias and guarantees identity.")
            table_issues += 1
            issues_found += 1
            
        # 2. Check Unindexed Foreign Keys
        for fk in info['foreign_keys']:
            fk_col = fk['from']
            # Search if any index covers this foreign key column as the leading column
            covered = False
            for idx_name, idx_info in info['indexes'].items():
                if idx_info['columns'] and idx_info['columns'][0] == fk_col:
                    covered = True
                    break
            
            # Also check if it's the primary key (PKs are indexed automatically)
            if info['primary_keys'] and info['primary_keys'][0] == fk_col:
                covered = True
                
            if not covered:
                print(f"  {Colors.YELLOW}! Unindexed Foreign Key{Colors.ENDC}: Column '{fk_col}' references '{fk['to_table']}({fk['to']})' but has no index.")
                print(f"    {Colors.BLUE}Recommendation:{Colors.ENDC} CREATE INDEX idx_{table}_{fk_col} ON {table}({fk_col});")
                table_issues += 1
                issues_found += 1

        # 3. Check Redundant Indexes
        indexes = info['indexes']
        idx_names = list(indexes.keys())
        for i in range(len(idx_names)):
            for j in range(len(idx_names)):
                if i == j:
                    continue
                name_a = idx_names[i]
                name_b = idx_names[j]
                cols_a = indexes[name_a]['columns']
                cols_b = indexes[name_b]['columns']
                
                # If index A's columns are a prefix of index B's columns, index A is redundant
                # (unless A is unique and B is not, in which case A enforces a constraint)
                if len(cols_a) < len(cols_b) and cols_b[:len(cols_a)] == cols_a:
                    if not indexes[name_a]['unique']:
                        print(f"  {Colors.YELLOW}! Redundant Index{Colors.ENDC}: Index '{name_a}' {cols_a} is redundant because it is a prefix of '{name_b}' {cols_b}.")
                        print(f"    {Colors.BLUE}Recommendation:{Colors.ENDC} DROP INDEX {name_a};")
                        table_issues += 1
                        issues_found += 1
                        
        if table_issues == 0:
            print(f"  {Colors.GREEN}✓ Schema looks optimal.{Colors.ENDC}")
            
    return issues_found

def analyze_query(conn, query):
    """Runs EXPLAIN QUERY PLAN on the query and recommends missing indexes."""
    print_header("Query Performance Advisor")
    print_info(f"Analyzing query: {query}")
    
    cursor = conn.cursor()
    try:
        cursor.execute(f"EXPLAIN QUERY PLAN {query}")
        plan = cursor.fetchall()
    except Exception as e:
        print_error(f"Failed to explain query: {e}")
        return

    print(f"\n{Colors.BOLD}Query Execution Plan:{Colors.ENDC}")
    scan_tables = []
    
    for row in plan:
        # Columns in plan: selectid, order, from, detail
        detail = row[3]
        indent = "  " * row[0]
        
        # Color plan lines
        if "SCAN" in detail:
            print(f"{indent}{Colors.RED}{detail}{Colors.ENDC}")
            # Extract table name: SCAN TABLE <table_name>
            match = re.search(r'SCAN TABLE\s+([a-zA-Z0-9_\-]+)', detail)
            if match:
                scan_tables.append(match.group(1))
        elif "SEARCH" in detail:
            print(f"{indent}{Colors.GREEN}{detail}{Colors.ENDC}")
        else:
            print(f"{indent}{detail}")

    if not scan_tables:
        print(f"\n{Colors.GREEN}✓ No full table scans detected. Query is fully indexed!{Colors.ENDC}")
        return

    print_header("Query Index Recommendations")
    print_warning(f"Full table scan(s) detected on: {', '.join(set(scan_tables))}")
    print("Full scans read every row in the table, which scales poorly as data grows.")
    
    # Inspect the query to find WHERE / JOIN columns of the scanned tables
    # Simplistic SQL parsing using regex to suggest columns
    for table in set(scan_tables):
        candidates = set()
        
        # Look for table.column or column references in query
        # Matches formats like table.column = ... or column = ...
        where_pattern = rf'(?:{table}\.)?([a-zA-Z0-9_\-]+)\s*(?:==|=|<|>|>=|<=|LIKE|IN)'
        matches = re.findall(where_pattern, query, re.IGNORECASE)
        for col in matches:
            if col.upper() not in ('SELECT', 'FROM', 'JOIN', 'WHERE', 'AND', 'OR', 'ON', 'LIMIT', 'ORDER', 'GROUP'):
                candidates.add(col)
                
        # Look for JOIN conditions
        join_pattern = rf'(?:{table}\.)?([a-zA-Z0-9_\-]+)\s*=\s*(?:[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)'
        matches_join = re.findall(join_pattern, query, re.IGNORECASE)
        for col in matches_join:
            if col.upper() not in ('SELECT', 'FROM', 'JOIN', 'WHERE', 'AND', 'OR', 'ON', 'LIMIT', 'ORDER', 'GROUP'):
                candidates.add(col)

        if candidates:
            cols_str = ", ".join(candidates)
            idx_name = f"idx_{table}_" + "_".join(candidates)
            print(f"\n{Colors.BOLD}For table '{table}':{Colors.ENDC}")
            print(f"  Suggested Single/Composite Index covering columns: {Colors.CYAN}{list(candidates)}{Colors.ENDC}")
            print(f"  {Colors.GREEN}SQL to create:{Colors.ENDC} CREATE INDEX {idx_name} ON {table}({cols_str});")
        else:
            print(f"\n{Colors.BOLD}For table '{table}':{Colors.ENDC}")
            print("  Could not automatically extract WHERE/JOIN columns. Inspect query clauses (WHERE, JOIN, ORDER BY) to find candidate columns.")

def main():
    parser = argparse.ArgumentParser(
        description="SQLite Database Schema and Query Index Advisor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze database schema
  python sqlite_index_advisor.py database.db
  
  # Analyze execution plan and get index suggestions for a query
  python sqlite_index_advisor.py database.db -q "SELECT * FROM users WHERE email = 'test@example.com'"
        """
    )
    
    parser.add_argument("db", help="Path to SQLite database file")
    parser.add_argument("-q", "--query", help="SQL query to analyze for index suggestions")
    
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print_error(f"Database file does not exist: {db_path}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print_error(f"Failed to connect to SQLite database: {e}")
        sys.exit(1)

    try:
        schema = get_db_schema(conn)
        
        # Step 1: Analyze schema general health
        issues = analyze_schema(schema)
        
        # Step 2: Analyze query if provided
        if args.query:
            analyze_query(conn, args.query)
            
    except Exception as e:
        print_error(f"An unexpected error occurred during analysis: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
