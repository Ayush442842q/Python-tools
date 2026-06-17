#!/usr/bin/env python3
"""
SQLite Database Explorer
CLI utility to inspect SQLite databases, show tables, display schema,
count rows, and execute queries with formatted tabular output.
"""

import sys
import os
import sqlite3
import argparse

def format_table(headers, rows):
    """Format tabular data into a pretty CLI table."""
    if not headers:
        return ""
        
    # Convert all cells to strings
    string_rows = [[str(cell) for cell in row] for row in rows]
    
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in string_rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
            else:
                col_widths.append(len(cell))
                
    # Build lines
    sep_line = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, col_widths)) + "|"
    
    output = [sep_line, header_line, sep_line]
    for row in string_rows:
        row_line = "|" + "|".join(f" {cell:<{w}} " for cell, w in zip(row, col_widths)) + "|"
        output.append(row_line)
    output.append(sep_line)
    
    return "\n".join(output)

def get_db_info(db_path):
    """Retrieve general information about the SQLite database."""
    size_bytes = os.path.getsize(db_path)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version();")
        version = cursor.fetchone()[0]
        
        # Get count of tables and views
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
        table_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='view';")
        view_count = cursor.fetchone()[0]
        
        conn.close()
        
        print("=== SQLite Database Info ===")
        print(f"File Path:      {db_path}")
        print(f"File Size:      {size_bytes} bytes ({size_bytes / 1024:.2f} KB)")
        print(f"SQLite Version: {version}")
        print(f"Tables:         {table_count}")
        print(f"Views:          {view_count}")
        print("============================\n")
    except sqlite3.Error as e:
        print(f"Error querying database metadata: {e}", file=sys.stderr)

def list_tables(db_path):
    """List all tables with their schema and row counts."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("No user tables found in this database.")
            conn.close()
            return
            
        headers = ["Table Name", "Row Count", "Columns Count"]
        rows = []
        
        for table in tables:
            # Row count
            try:
                cursor.execute(f"SELECT count(*) FROM [{table}];")
                row_count = cursor.fetchone()[0]
            except sqlite3.Error:
                row_count = "N/A"
                
            # Column count
            try:
                cursor.execute(f"PRAGMA table_info([{table}]);")
                col_count = len(cursor.fetchall())
            except sqlite3.Error:
                col_count = "N/A"
                
            rows.append([table, row_count, col_count])
            
        print("--- Table Summary ---")
        print(format_table(headers, rows))
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)

def show_schema(db_path, table_name):
    """Show the schema details for a specific table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"PRAGMA table_info([{table_name}]);")
        columns = cursor.fetchall()
        
        if not columns:
            # Check if table even exists
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
            exists = cursor.fetchone()[0] > 0
            if not exists:
                print(f"Error: Table '{table_name}' does not exist.", file=sys.stderr)
            else:
                print(f"No schema found for table '{table_name}'.")
            conn.close()
            return
            
        # Columns in PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        headers = ["CID", "Column Name", "Data Type", "Not Null", "Default Value", "Primary Key"]
        rows = []
        for col in columns:
            cid, name, col_type, notnull, dflt_value, pk = col
            rows.append([
                cid, 
                name, 
                col_type if col_type else "BLOB/NONE", 
                "Yes" if notnull else "No", 
                dflt_value if dflt_value is not None else "NULL", 
                "Yes" if pk else "No"
            ])
            
        print(f"--- Schema for table: {table_name} ---")
        print(format_table(headers, rows))
        
        # Also print raw CREATE statement if available
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
        create_sql = cursor.fetchone()
        if create_sql and create_sql[0]:
            print("\nRaw CREATE SQL:")
            print(create_sql[0])
            
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)

def execute_query(db_path, query):
    """Execute a query and print the output in format."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(query)
        
        if cursor.description:
            headers = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            print(f"Executed: {query}")
            print(f"Results ({len(rows)} row(s)):")
            print(format_table(headers, rows))
        else:
            conn.commit()
            print(f"Executed query successfully. Affected rows: {cursor.rowcount}")
            
        conn.close()
    except sqlite3.Error as e:
        print(f"SQL Execution Error: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="SQLite Database Explorer - Inspect schemas and run CLI queries",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("database", help="Path to SQLite database file")
    parser.add_argument("--info", "-i", action="store_true", help="Print database size, version, and general metadata")
    parser.add_argument("--list-tables", "-l", action="store_true", help="List all tables, column counts, and row counts")
    parser.add_argument("--schema", "-s", metavar="TABLE", help="Display columns and primary keys for the specified table")
    parser.add_argument("--query", "-q", metavar="SQL", help="Execute SQL statement and display formatted output")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.database):
        print(f"Error: Database file '{args.database}' does not exist.", file=sys.stderr)
        return 1
        
    if os.path.isdir(args.database):
        print(f"Error: '{args.database}' is a directory.", file=sys.stderr)
        return 1
        
    # Default behavior if no specific flags are passed
    if not (args.info or args.list_tables or args.schema or args.query):
        args.info = True
        args.list_tables = True
        
    if args.info:
        get_db_info(args.database)
        
    if args.list_tables:
        list_tables(args.database)
        
    if args.schema:
        show_schema(args.database, args.schema)
        
    if args.query:
        execute_query(args.database, args.query)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
