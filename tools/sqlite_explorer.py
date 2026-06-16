#!/usr/bin/env python3
"""
SQLite Database Explorer CLI

A standalone tool to inspect SQLite database structures, view tables, 
execute SQL queries, and export results.

Usage:
    python tools/sqlite_explorer.py --db /path/to/database.db --list-tables
    python tools/sqlite_explorer.py --db /path/to/database.db --schema table_name
    python tools/sqlite_explorer.py --db /path/to/database.db --query "SELECT * FROM table"
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from typing import List, Dict, Any, Tuple

def list_tables(conn: sqlite3.Connection) -> None:
    """Lists all tables, views, and indexes in the database."""
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()
    
    # Get views
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name;")
    views = cursor.fetchall()
    
    print("=== Database Objects ===")
    print(f"\n[Tables] ({len(tables)} found):")
    for row in tables:
        print(f"  - {row[0]}")
        
    print(f"\n[Views] ({len(views)} found):")
    for row in views:
        print(f"  - {row[0]}")

def show_schema(conn: sqlite3.Connection, table_name: str) -> None:
    """Displays the schema for a specific table."""
    cursor = conn.cursor()
    try:
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            print(f"Error: Table '{table_name}' not found.")
            return

        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        # Display schema
        print(f"=== Schema for Table: {table_name} ===")
        print(f"{'CID':<5} | {'Name':<25} | {'Type':<15} | {'NotNull':<8} | {'Default':<12} | {'PK':<5}")
        print("-" * 78)
        for col in columns:
            cid, name, col_type, notnull, dflt_value, pk = col
            dflt_val_str = str(dflt_value) if dflt_value is not None else "NULL"
            print(f"{cid:<5} | {name:<25} | {col_type:<15} | {notnull:<8} | {dflt_val_str:<12} | {pk:<5}")
            
        # Get indexes
        cursor.execute(f"PRAGMA index_list({table_name});")
        indexes = cursor.fetchall()
        if indexes:
            print("\n[Indexes]:")
            for idx in indexes:
                seq, name, unique, origin, partial = idx
                unique_str = "UNIQUE" if unique else "NON-UNIQUE"
                print(f"  - {name} ({unique_str})")
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)

def execute_query(conn: sqlite3.Connection, query: str, export_path: str = None, export_format: str = 'csv') -> None:
    """Executes a SQL query and prints or exports the results."""
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        
        # Handle queries that don't return rows (e.g. UPDATE, INSERT, CREATE)
        if cursor.description is None:
            conn.commit()
            print(f"Query executed successfully. Rows affected: {cursor.rowcount}")
            return
            
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        if not rows:
            print("Query executed. No rows returned.")
            return
            
        if export_path:
            export_results(columns, rows, export_path, export_format)
        else:
            print_table(columns, rows)
            
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)

def print_table(columns: List[str], rows: List[Tuple]) -> None:
    """Prints rows in a formatted text table with automatic column sizing."""
    # Find max width of each column
    widths = [len(col) for col in columns]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val if val is not None else "NULL")))
            
    # Print header
    header = " | ".join(f"{col:<{widths[i]}}" for i, col in enumerate(columns))
    print(header)
    print("-" * len(header))
    
    # Print rows
    for row in rows:
        row_str = " | ".join(f"{str(val if val is not None else 'NULL'):<{widths[i]}}" for i, val in enumerate(row))
        print(row_str)
        
    print(f"\n({len(rows)} row(s) returned)")

def export_results(columns: List[str], rows: List[Tuple], path: str, format: str) -> None:
    """Exports query results to a CSV or JSON file."""
    try:
        if format.lower() == 'csv':
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
            print(f"Successfully exported {len(rows)} rows to CSV: {path}")
        elif format.lower() == 'json':
            data = []
            for row in rows:
                data.append(dict(zip(columns, row)))
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Successfully exported {len(rows)} rows to JSON: {path}")
        else:
            print(f"Error: Unknown export format '{format}'. Supported formats: csv, json", file=sys.stderr)
    except IOError as e:
        print(f"File write error: {e}", file=sys.stderr)

def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite Database Explorer CLI")
    parser.add_argument('--db', required=True, help="Path to SQLite database file")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list-tables', action='store_true', help="List all tables and views")
    group.add_argument('--schema', help="Show schema of a specific table")
    group.add_argument('--query', help="Execute a raw SQL SELECT query")
    
    parser.add_argument('--export', help="File path to export query results")
    parser.add_argument('--format', choices=['csv', 'json'], default='csv', help="Export format (default: csv)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"Error: Database file '{args.db}' not found.", file=sys.stderr)
        return 1
        
    try:
        # Connect to database (read-only mode if possible)
        db_uri = f"file:{args.db}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
    except sqlite3.Error:
        # Fallback to standard connection if URI mode fails
        try:
            conn = sqlite3.connect(args.db)
        except sqlite3.Error as e:
            print(f"Failed to connect to database: {e}", file=sys.stderr)
            return 1
            
    try:
        if args.list_tables:
            list_tables(conn)
        elif args.schema:
            show_schema(conn, args.schema)
        elif args.query:
            execute_query(conn, args.query, args.export, args.format)
    finally:
        conn.close()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
