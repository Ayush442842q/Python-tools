#!/usr/bin/env python3
"""
SQLite Database to CSV / JSON Exporter
A CLI utility to export tables or SQL query results from SQLite database files into CSV, TSV, or JSON format.

Features:
- Export individual tables or custom SELECT query results.
- Export all tables in a database simultaneously into an output directory.
- Output formats: CSV, TSV, JSON array of objects.
- Handles NULL values, header inclusion, custom column delimiters, and row limits.
"""

import sys
import os
import csv
import json
import sqlite3
import argparse
from typing import List, Dict, Any

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def get_tables(conn: sqlite3.Connection) -> List[str]:
    """Retrieves list of user tables from SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]


def export_query(conn: sqlite3.Connection, query: str, output_path: str, fmt: str, delimiter: str = ",", limit: int = -1) -> int:
    """Executes SQL query and exports result set to file. Returns row count."""
    cursor = conn.cursor()
    if limit > 0:
        query = f"SELECT * FROM ({query}) LIMIT {limit}"

    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()

    if fmt in ("csv", "tsv"):
        sep = "\t" if fmt == "tsv" else delimiter
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=sep)
            writer.writerow(columns)
            writer.writerows(rows)
    elif fmt == "json":
        data = [dict(zip(columns, row)) for row in rows]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SQLite tables or SQL query results to CSV, TSV, or JSON.")
    parser.add_argument("db_path", help="Path to SQLite database file.")
    parser.add_argument("-t", "--table", type=str, help="Table name to export.")
    parser.add_argument("-q", "--query", type=str, help="Custom SQL SELECT query to export.")
    parser.add_argument("--all-tables", action="store_true", help="Export all tables into specified output directory.")
    parser.add_argument("-o", "--output", type=str, help="Output file path (or output directory if --all-tables).")
    parser.add_argument("-f", "--format", choices=["csv", "tsv", "json"], default="csv", help="Export format (default: csv).")
    parser.add_argument("--delimiter", type=str, default=",", help="CSV field delimiter (default: ',').")
    parser.add_argument("--limit", type=int, default=-1, help="Limit maximum rows exported.")

    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database file '{args.db_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        conn = sqlite3.connect(args.db_path)
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.all_tables:
            tables = get_tables(conn)
            out_dir = args.output or "."
            os.makedirs(out_dir, exist_ok=True)
            print(f"Exporting {len(tables)} tables to '{out_dir}'...")
            for tbl in tables:
                out_file = os.path.join(out_dir, f"{tbl}.{args.format}")
                count = export_query(conn, f"SELECT * FROM \"{tbl}\"", out_file, args.format, args.delimiter, args.limit)
                print(f"  - Table '{tbl}': {count} rows exported to {out_file}")
        elif args.table:
            out_file = args.output or f"{args.table}.{args.format}"
            count = export_query(conn, f"SELECT * FROM \"{args.table}\"", out_file, args.format, args.delimiter, args.limit)
            print(f"Successfully exported {count} rows from table '{args.table}' to {out_file}")
        elif args.query:
            out_file = args.output or f"query_result.{args.format}"
            count = export_query(conn, args.query, out_file, args.format, args.delimiter, args.limit)
            print(f"Successfully exported {count} rows to {out_file}")
        else:
            tables = get_tables(conn)
            print("Available tables in database:")
            for t in tables:
                print(f"  - {t}")
            print("\nSpecify -t <table>, -q <query>, or --all-tables to export data.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
