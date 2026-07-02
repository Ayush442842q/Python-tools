#!/usr/bin/env python3
"""
SQLite Database Merger
A CLI tool to perform a schema-aware merge of a source SQLite database into a target
SQLite database. It manages integer primary key conflicts on auto-increment tables
and automatically updates corresponding foreign key references across tables.

Usage:
    python tools/sqlite_db_merger.py <source_db> <target_db> [options]
"""

import argparse
import os
import sqlite3
import sys

# ANSI colors for styling
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_tables(conn):
    """Returns list of user tables in the SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn, table):
    """Returns columns information as a list of dicts: name, type, notnull, pk."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table});")
    return [{
        "name": row[1],
        "type": row[2].upper(),
        "notnull": bool(row[3]),
        "pk": bool(row[5])
    } for row in cursor.fetchall()]


def get_foreign_keys(conn, table):
    """Returns list of foreign keys for a table: table, from_col, to_col."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA foreign_key_list({table});")
    return [{
        "table": row[2],
        "from": row[3],
        "to": row[4]
    } for row in cursor.fetchall()]


def topological_sort(tables, dependencies):
    """Topologically sorts tables based on foreign key dependencies to ensure parent tables merge first."""
    visited = set()
    temp_stack = set()
    order = []

    def visit(t):
        if t in temp_stack:
            # Cycle detected (e.g. self-referencing or circular). We will try our best.
            return
        if t not in visited:
            temp_stack.add(t)
            # Visit dependencies (tables referenced by t)
            for dep in dependencies.get(t, []):
                if dep in tables: # Only check dependencies within our tables list
                    visit(dep)
            temp_stack.remove(t)
            visited.add(t)
            order.append(t)

    for table in tables:
        visit(table)

    return order


def merge_databases(source_path, target_path, on_conflict="abort", ignore_missing=False, dry_run=False):
    """Merges source SQLite database into the target database."""
    if not os.path.exists(source_path):
        print(f"{RED}Error: Source database '{source_path}' does not exist.{RESET}", file=sys.stderr)
        return 1
    if not os.path.exists(target_path):
        print(f"{RED}Error: Target database '{target_path}' does not exist.{RESET}", file=sys.stderr)
        return 1

    src_conn = sqlite3.connect(source_path)
    tgt_conn = sqlite3.connect(target_path)
    
    # Enable foreign keys on target connection
    tgt_conn.execute("PRAGMA foreign_keys = ON;")

    src_tables = get_tables(src_conn)
    tgt_tables = get_tables(tgt_conn)

    print(f"{BOLD}Source database: {source_path} ({len(src_tables)} table(s)){RESET}")
    print(f"{BOLD}Target database: {target_path} ({len(tgt_tables)} table(s)){RESET}\n")

    # Map tables and their dependencies
    dependencies = {}
    for table in src_tables:
        fkeys = get_foreign_keys(src_conn, table)
        dependencies[table] = [fk["table"] for fk in fkeys if fk["table"] != table]

    # Topologically sort tables so parent tables (no foreign keys) are merged first
    sorted_tables = topological_sort(src_tables, dependencies)

    # Primary key remapping dictionaries: table_name -> {old_pk: new_pk}
    pk_mappings = {}

    # Track overall progress
    total_inserted = 0
    total_skipped = 0

    try:
        for table in sorted_tables:
            if table not in tgt_tables:
                if ignore_missing:
                    print(f"{YELLOW}Skipping missing table '{table}' in target database.{RESET}")
                    continue
                else:
                    raise ValueError(f"Table '{table}' does not exist in target database. Create it first or use --ignore-missing.")

            # Validate schema
            src_schema = {c["name"]: c["type"] for c in get_table_schema(src_conn, table)}
            tgt_schema = {c["name"]: c["type"] for c in get_table_schema(tgt_conn, table)}
            
            if src_schema != tgt_schema:
                # Basic warning, checking if common columns match
                mismatched = set(src_schema.keys()) ^ set(tgt_schema.keys())
                if mismatched:
                    raise ValueError(f"Schema mismatch for table '{table}': Column sets differ by {mismatched}")

            # Identify primary key and foreign keys
            columns_info = get_table_schema(src_conn, table)
            pk_cols = [c["name"] for c in columns_info if c["pk"]]
            fkeys = get_foreign_keys(src_conn, table)

            # Check if primary key can be remapped (single integer primary key)
            can_remap_pk = False
            pk_col = None
            if len(pk_cols) == 1:
                pk_col = pk_cols[0]
                pk_type = src_schema[pk_col]
                if "INT" in pk_type:
                    can_remap_pk = True

            print(f"Merging table {BOLD}{table}{RESET}...")
            
            # Fetch all rows from source
            src_cursor = src_conn.cursor()
            src_cursor.execute(f"SELECT * FROM [{table}];")
            columns = [d[0] for d in src_cursor.description]
            rows = src_cursor.fetchall()

            if not rows:
                print(f"  No records found in source table. Skipped.")
                continue

            tgt_cursor = tgt_conn.cursor()
            pk_mappings[table] = {}

            table_inserted = 0
            table_skipped = 0

            for row_tuple in rows:
                row = dict(zip(columns, row_tuple))
                old_pk_val = row.get(pk_col) if pk_col else None

                # 1. Update foreign key references in this row based on previous remappings
                for fk in fkeys:
                    parent_table = fk["table"]
                    from_col = fk["from"]
                    to_col = fk["to"]
                    
                    old_fk_val = row.get(from_col)
                    if old_fk_val is not None and parent_table in pk_mappings:
                        # Remap to new parent PK
                        new_fk_val = pk_mappings[parent_table].get(old_fk_val)
                        if new_fk_val is not None:
                            row[from_col] = new_fk_val

                # 2. Insert row
                # If we can remap primary key, we remove it from the row to let SQLite autogenerate it,
                # then record the mappings.
                if can_remap_pk:
                    row_data = {k: v for k, v in row.items() if k != pk_col}
                    cols_str = ", ".join(f"[{k}]" for k in row_data.keys())
                    vals_placeholder = ", ".join("?" for _ in row_data)
                    insert_sql = f"INSERT INTO [{table}] ({cols_str}) VALUES ({vals_placeholder});"
                    
                    if not dry_run:
                        try:
                            tgt_cursor.execute(insert_sql, list(row_data.values()))
                            new_pk_val = tgt_cursor.lastrowid
                            if old_pk_val is not None:
                                pk_mappings[table][old_pk_val] = new_pk_val
                            table_inserted += 1
                        except sqlite3.IntegrityError as e:
                            if on_conflict == "ignore":
                                table_skipped += 1
                            elif on_conflict == "replace":
                                # If we replace, we have to insert manually with old PK if it exists,
                                # or handle manually. Since autoincrement PK is dropped, this is rare.
                                raise e
                            else:
                                raise e
                    else:
                        table_inserted += 1

                else:
                    # Insert with original PK (no remapping)
                    cols_str = ", ".join(f"[{k}]" for k in row.keys())
                    vals_placeholder = ", ".join("?" for _ in row)
                    
                    conflict_clause = ""
                    if on_conflict == "ignore":
                        conflict_clause = "OR IGNORE"
                    elif on_conflict == "replace":
                        conflict_clause = "OR REPLACE"

                    insert_sql = f"INSERT {conflict_clause} INTO [{table}] ({cols_str}) VALUES ({vals_placeholder});"
                    
                    if not dry_run:
                        try:
                            tgt_cursor.execute(insert_sql, list(row.values()))
                            if tgt_cursor.rowcount > 0:
                                table_inserted += 1
                            else:
                                table_skipped += 1
                        except sqlite3.IntegrityError as e:
                            if on_conflict == "abort":
                                raise e
                            else:
                                table_skipped += 1
                    else:
                        table_inserted += 1

            print(f"  Inserted: {table_inserted} row(s), Skipped/Conflicts: {table_skipped} row(s)")
            total_inserted += table_inserted
            total_skipped += table_skipped

        if not dry_run:
            tgt_conn.commit()
            print(f"\n{GREEN}Merge completed successfully!{RESET}")
        else:
            print(f"\n{YELLOW}Dry-run completed. No changes written.{RESET}")

        print(f"Total inserted rows: {total_inserted}")
        print(f"Total skipped rows: {total_skipped}")

    except Exception as e:
        tgt_conn.rollback()
        print(f"\n{RED}Error occurred during merge. Transactions rolled back.{RESET}", file=sys.stderr)
        print(f"{RED}Error details: {e}{RESET}", file=sys.stderr)
        return 1
    finally:
        src_conn.close()
        tgt_conn.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="SQLite Database Merger - Performs a schema-aware merge of two SQLite databases with primary/foreign key remapping."
    )
    parser.add_argument("source_db", help="Path to the source SQLite database file")
    parser.add_argument("target_db", help="Path to the target SQLite database file")
    parser.add_argument("--on-conflict", choices=["abort", "ignore", "replace"], default="abort",
                        help="Action when unique/primary key conflict occurs on non-remapped rows (default: abort)")
    parser.add_argument("--ignore-missing", action="store_true", 
                        help="Skip source tables that do not exist in the target database instead of aborting")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse schemas, trace dependencies, and simulate merge without writing changes")

    args = parser.parse_args()

    return merge_databases(
        args.source_db,
        args.target_db,
        on_conflict=args.on_conflict,
        ignore_missing=args.ignore_missing,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Merge operation cancelled by user.{RESET}")
        sys.exit(1)
