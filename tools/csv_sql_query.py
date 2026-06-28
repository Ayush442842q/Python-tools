#!/usr/bin/env python3
"""
CSV SQL Query Runner
Allows running standard SQL queries directly against one or more CSV files.
Loads CSVs as tables in an in-memory SQLite database.
"""

import os
import re
import sys
import csv
import json
import sqlite3
import argparse
from typing import List, Tuple, Dict, Any

def sanitize_table_name(filename: str) -> str:
    """Convert filename to a valid SQL table name (alphanumeric and underscores only)."""
    base = os.path.splitext(os.path.basename(filename))[0]
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', base)
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized.lower()

def sanitize_column_name(col_name: str, index: int) -> str:
    """Convert header name to a valid SQL column name."""
    col_name = col_name.strip()
    if not col_name:
        return f"col_{index}"
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', col_name)
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized.lower()

def infer_type(val_str: str) -> str:
    """Infer SQLite data type from string value."""
    val_str = val_str.strip()
    if not val_str:
        return "TEXT"
    # Integer check
    try:
        int(val_str)
        return "INTEGER"
    except ValueError:
        pass
    # Real check
    try:
        float(val_str)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"

def load_csv_to_db(conn: sqlite3.Connection, filepath: str, delimiter: str, no_headers: bool) -> str:
    """Load a CSV file into the SQLite database as a table. Returns the table name."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    table_name = sanitize_table_name(filepath)
    
    with open(filepath, 'r', newline='', encoding='utf-8-sig') as f:
        # Detect delimiter if not explicitly provided
        if not delimiter:
            try:
                sample = f.read(2048)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ','

        reader = csv.reader(f, delimiter=delimiter)
        
        # Read header or generate default columns
        try:
            first_row = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file is empty: {filepath}")

        # Determine column names
        if no_headers:
            headers = [f"col_{i+1}" for i in range(len(first_row))]
            rows_to_insert = [first_row]
        else:
            headers = [sanitize_column_name(h, i+1) for i, h in enumerate(first_row)]
            rows_to_insert = []

        # Read remaining rows to scan and infer column types
        all_rows = list(reader)
        rows_to_insert.extend(all_rows)
        
        if not rows_to_insert:
            # Table has headers but no rows, default all columns to TEXT
            col_types = ["TEXT"] * len(headers)
        else:
            # Infer column types based on the first few rows
            col_types = []
            for col_idx in range(len(headers)):
                types_in_col = set()
                # Scan up to 100 rows to infer type
                for row in rows_to_insert[:100]:
                    if col_idx < len(row):
                        types_in_col.add(infer_type(row[col_idx]))
                
                if "TEXT" in types_in_col or not types_in_col:
                    col_types.append("TEXT")
                elif "REAL" in types_in_col:
                    col_types.append("REAL")
                else:
                    col_types.append("INTEGER")

        # Create table
        cols_def = ", ".join(f'"{h}" {t}' for h, t in zip(headers, col_types))
        create_sql = f'CREATE TABLE "{table_name}" ({cols_def})'
        
        cursor = conn.cursor()
        cursor.execute(create_sql)

        # Insert rows
        placeholders = ", ".join(["?"] * len(headers))
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
        
        # Pad or truncate rows to match column count
        normalized_rows = []
        for row in rows_to_insert:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            normalized_rows.append(row)

        cursor.executemany(insert_sql, normalized_rows)
        conn.commit()

        return table_name

def print_text_table(headers: List[str], rows: List[List[Any]]) -> None:
    """Print results in a clean aligned text table."""
    if not headers:
        return
        
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(str(val if val is not None else "")))

    # Border templates
    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, widths)) + " |"
    
    print(border)
    print(header_line)
    print(border)
    
    for row in rows:
        row_str = []
        for val, w in zip(row, widths):
            v = str(val if val is not None else "")
            # Right-align numbers, left-align text
            try:
                float(v)
                row_str.append(f"{v:>{w}}")
            except ValueError:
                row_str.append(f"{v:<{w}}")
        print("| " + " | ".join(row_str) + " |")
        
    print(border)

def print_markdown(headers: List[str], rows: List[List[Any]]) -> None:
    """Print results in GitHub Flavored Markdown table format."""
    if not headers:
        return
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(str(val if val is not None else "") for val in row) + " |")

def print_csv(headers: List[str], rows: List[List[Any]]) -> None:
    """Print results as CSV."""
    writer = csv.writer(sys.stdout)
    writer.writerow(headers)
    writer.writerows(rows)

def print_json(headers: List[str], rows: List[List[Any]]) -> None:
    """Print results as pretty JSON array of objects."""
    output = []
    for row in rows:
        obj = {}
        for h, v in zip(headers, row):
            obj[h] = v
        output.append(obj)
    print(json.dumps(output, indent=2))

def main():
    parser = argparse.ArgumentParser(
        description="CSV SQL Query Runner. Query local CSV files using SQLite SQL syntax.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/csv_sql_query.py -f users.csv orders.csv -q "SELECT u.name, sum(o.amount) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name"
  python tools/csv_sql_query.py -f sales.csv -q "SELECT category, count(*) FROM sales GROUP BY category" --format markdown
        """
    )
    parser.add_argument("-f", "--files", nargs="+", required=True, help="One or more CSV files to load as SQL tables")
    parser.add_argument("-q", "--query", help="SQL query to execute. If omitted, lists schemas of loaded tables")
    parser.add_argument("-d", "--delimiter", help="CSV field delimiter (defaults to auto-detect)")
    parser.add_argument("--no-headers", action="store_true", help="Treat first row as data, generating default columns (col_1, col_2...)")
    parser.add_argument("-o", "--format", choices=["table", "markdown", "csv", "json"], default="table", help="Output format (default: table)")

    args = parser.parse_args()

    conn = sqlite3.connect(":memory:")
    
    # Load all tables
    table_mappings = []
    for filepath in args.files:
        try:
            table_name = load_csv_to_db(conn, filepath, args.delimiter, args.no_headers)
            table_mappings.append((filepath, table_name))
        except Exception as e:
            print(f"Error loading {filepath}: {e}", file=sys.stderr)
            sys.exit(1)

    # If no query is provided, show the available tables, their schemas, and row counts
    if not args.query:
        print("\n--- Loaded Tables & Schema ---")
        cursor = conn.cursor()
        for filepath, table_name in table_mappings:
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
            row_count = cursor.fetchone()[0]
            print(f"\nTable: {table_name} ({filepath}) - {row_count} rows")
            
            cursor.execute(f"PRAGMA table_info(\"{table_name}\")")
            columns = cursor.fetchall()
            col_list = []
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                col_list.append(f"  {col_name} ({col_type})")
            print("\n".join(col_list))
        print("\nTo query these tables, use the -q/--query argument.")
        sys.exit(0)

    # Run SQL Query
    try:
        cursor = conn.cursor()
        cursor.execute(args.query)
        
        # Extract headers from cursor description
        if cursor.description:
            headers = [desc[0] for desc in cursor.description]
        else:
            headers = []
            
        rows = cursor.fetchall()
        
        # Display output in requested format
        if args.format == "table":
            print_text_table(headers, rows)
        elif args.format == "markdown":
            print_markdown(headers, rows)
        elif args.format == "csv":
            print_csv(headers, rows)
        elif args.format == "json":
            print_json(headers, rows)

    except sqlite3.Error as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
