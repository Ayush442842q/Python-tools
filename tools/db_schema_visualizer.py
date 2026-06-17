#!/usr/bin/env python3
"""
SQLite Schema Visualizer - Extracts schema information from a SQLite database
and formats it into an ASCII report or a Mermaid Entity-Relationship Diagram.
"""

import argparse
import os
import sqlite3
import sys


def get_db_schema(db_path):
    """Retrieves tables, columns, and foreign key relations from a SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cursor.fetchall()]

    schema = {}
    
    for table in tables:
        # Get column info
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        # Columns: (cid, name, type, notnull, dflt_value, pk)

        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table});")
        fkeys = cursor.fetchall()
        # Fkeys: (id, seq, table, from, to, on_update, on_delete, match)

        schema[table] = {
            "columns": [
                {
                    "name": col[1],
                    "type": col[2] or "BLOB",
                    "notnull": bool(col[3]),
                    "default": col[4],
                    "pk": bool(col[5])
                }
                for col in columns
            ],
            "foreign_keys": [
                {
                    "to_table": fk[2],
                    "from_col": fk[3],
                    "to_col": fk[4]
                }
                for fk in fkeys
            ]
        }

    # Retrieve triggers
    cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger';")
    triggers = [
        {"name": r[0], "table": r[1], "sql": r[2]}
        for r in cursor.fetchall()
    ]

    # Retrieve views
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    views = [
        {"name": r[0], "sql": r[1]}
        for r in cursor.fetchall()
    ]

    conn.close()
    return schema, triggers, views


def generate_mermaid_er(schema):
    """Generates a Mermaid Entity-Relationship Diagram string from the schema."""
    lines = ["erDiagram"]
    
    # 1. Define entities and their attributes
    for table, details in schema.items():
        lines.append(f"    {table} {{")
        for col in details["columns"]:
            col_type = col["type"].replace(" ", "_").replace("(", "_").replace(")", "_")
            pk_flag = " PK" if col["pk"] else ""
            not_null_flag = " \"NOT NULL\"" if col["notnull"] else ""
            lines.append(f"        {col_type} {col['name']}{pk_flag}{not_null_flag}")
        lines.append("    }")

    # 2. Define relationships
    relationships_added = set()
    for table, details in schema.items():
        for fk in details["foreign_keys"]:
            to_table = fk["to_table"]
            # To avoid redundant lines or syntax errors, order alphabetically
            rel_key = tuple(sorted([table, to_table]))
            if rel_key not in relationships_added:
                # Add relationship line (zero-or-more to one-or-more representation)
                lines.append(f"    {to_table} ||--o{{ {table} : \"references\"")
                relationships_added.add(rel_key)

    return "\n".join(lines)


def generate_ascii_report(schema, triggers, views):
    """Generates a text report showing tables and their details."""
    out = []
    out.append("=" * 60)
    out.append(" DATABASE SCHEMA REPORT")
    out.append("=" * 60 + "\n")

    out.append(f"Tables count: {len(schema)}")
    out.append(f"Views count: {len(views)}")
    out.append(f"Triggers count: {len(triggers)}\n")

    out.append("--- TABLES ---")
    for table, details in schema.items():
        out.append(f"\nTable: {table}")
        out.append("-" * (len(table) + 7))
        
        # Columns table headers
        out.append(f"{'Column Name':<20} | {'Type':<12} | {'PK':<4} | {'Not Null':<8} | {'Default':<10}")
        out.append("-" * 65)
        for col in details["columns"]:
            pk = "Yes" if col["pk"] else "No"
            nn = "Yes" if col["notnull"] else "No"
            dflt = str(col["default"]) if col["default"] is not None else "NULL"
            out.append(f"{col['name']:<20} | {col['type']:<12} | {pk:<4} | {nn:<8} | {dflt:<10}")

        # Foreign keys listing
        if details["foreign_keys"]:
            out.append("\n  Foreign Keys:")
            for fk in details["foreign_keys"]:
                out.append(f"    * {fk['from_col']} -> {fk['to_table']}({fk['to_col']})")
                
    if views:
        out.append("\n" + "=" * 40)
        out.append("--- VIEWS ---")
        for view in views:
            out.append(f"\nView: {view['name']}")
            out.append("-" * (len(view['name']) + 6))
            out.append(view['sql'] or "No SQL definition available.")

    if triggers:
        out.append("\n" + "=" * 40)
        out.append("--- TRIGGERS ---")
        for trigger in triggers:
            out.append(f"\nTrigger: {trigger['name']} (on {trigger['table']})")
            out.append("-" * (len(trigger['name']) + 12))
            out.append(trigger['sql'] or "No SQL definition available.")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(
        description="SQLite Database Schema Visualizer."
    )
    parser.add_argument("db_path", help="Path to the SQLite database file.")
    parser.add_argument(
        "-f", "--format", 
        choices=["text", "mermaid"], 
        default="text",
        help="Output format: 'text' (default ASCII report) or 'mermaid' (Mermaid ER diagram)."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Path to save the output (prints to stdout if omitted)."
    )

    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database file '{args.db_path}' not found.", file=sys.stderr)
        return 1

    try:
        schema, triggers, views = get_db_schema(args.db_path)
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading database: {e}", file=sys.stderr)
        return 1

    if args.format == "mermaid":
        output_content = generate_mermaid_er(schema)
    else:
        output_content = generate_ascii_report(schema, triggers, views)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content + "\n")
            print(f"Schema successfully written to '{args.output}'.")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
