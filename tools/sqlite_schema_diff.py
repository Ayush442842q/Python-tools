#!/usr/bin/env python3
"""
SQLite Schema Diff Tool - Compare SQLite database schemas and generate migrations

This tool compares the schemas of two SQLite databases (source and target) and
identifies discrepancies in tables, columns, indexes, views, and triggers.
It outputs a structural report of the differences and generates the SQL
migration script to transition the source database schema to the target.

Usage:
    python tools/sqlite_schema_diff.py source.db target.db [-o migration.sql]
"""

import argparse
import os
import re
import sqlite3
import sys
from typing import Dict, List, Set, Tuple, Any, Optional


def get_db_schema_objects(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Retrieves all schema objects (tables, indexes, views, triggers) from sqlite_master."""
    cursor = conn.cursor()
    cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%';")
    
    objects = {}
    for obj_type, name, tbl_name, sql in cursor.fetchall():
        objects[name] = {
            'type': obj_type,
            'tbl_name': tbl_name,
            # Normalize whitespace for comparison
            'sql': re.sub(r'\s+', ' ', sql).strip(),
            'raw_sql': sql
        }
    return objects


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> Dict[str, Dict[str, Any]]:
    """Gets column details for a table using PRAGMA table_info."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = {}
        for _, name, col_type, notnull, dflt_value, pk in cursor.fetchall():
            columns[name] = {
                'type': col_type.upper(),
                'notnull': bool(notnull),
                'dflt_value': dflt_value,
                'pk': bool(pk)
            }
        return columns
    except sqlite3.OperationalError:
        return {}


def format_column_definition(col_name: str, col_info: Dict[str, Any]) -> str:
    """Formats column definition for ALTER TABLE ... ADD COLUMN."""
    parts = [col_name, col_info['type']]
    if col_info['notnull']:
        parts.append("NOT NULL")
    if col_info['dflt_value'] is not None:
        parts.append(f"DEFAULT {col_info['dflt_value']}")
    if col_info['pk']:
        parts.append("PRIMARY KEY")
    return " ".join(parts)


def compare_schemas(source_path: str, target_path: str) -> Tuple[List[str], List[str]]:
    """
    Compares the schema of source_db and target_db.
    Returns (report_lines, migration_sql_statements).
    """
    report = []
    migration = []

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source database path not found: {source_path}")
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Target database path not found: {target_path}")

    src_conn = sqlite3.connect(source_path)
    tgt_conn = sqlite3.connect(target_path)

    try:
        src_objs = get_db_schema_objects(src_conn)
        tgt_objs = get_db_schema_objects(tgt_conn)

        src_tables = {name: info for name, info in src_objs.items() if info['type'] == 'table'}
        tgt_tables = {name: info for name, info in tgt_objs.items() if info['type'] == 'table'}

        # 1. Compare Tables
        all_tables = set(src_tables.keys()).union(tgt_tables.keys())
        
        for table in sorted(all_tables):
            if table not in src_tables:
                report.append(f"[+] Missing Table in Source: {table}")
                migration.append(f"-- Create Table: {table}")
                migration.append(tgt_objs[table]['raw_sql'] + ";")
                
            elif table not in tgt_tables:
                report.append(f"[-] Extra Table in Source: {table}")
                migration.append(f"-- Drop Table (Warning: Data loss!): {table}")
                migration.append(f"-- DROP TABLE {table};")
                
            else:
                # Compare columns of tables existing in both
                src_cols = get_table_columns(src_conn, table)
                tgt_cols = get_table_columns(tgt_conn, table)

                # Find column differences
                all_cols = set(src_cols.keys()).union(tgt_cols.keys())
                col_migration_lines = []
                
                for col in sorted(all_cols):
                    if col not in src_cols:
                        report.append(f"[*] Table '{table}': Missing Column: {col} ({tgt_cols[col]['type']})")
                        col_def = format_column_definition(col, tgt_cols[col])
                        col_migration_lines.append(f"ALTER TABLE {table} ADD COLUMN {col_def};")
                    elif col not in tgt_cols:
                        report.append(f"[*] Table '{table}': Extra Column: {col}")
                        col_migration_lines.append(f"-- ALTER TABLE {table} DROP COLUMN {col}; -- (Note: DROP COLUMN requires SQLite 3.35.0+)")
                    else:
                        # Compare definition
                        src_c = src_cols[col]
                        tgt_c = tgt_cols[col]
                        
                        if src_c != tgt_c:
                            report.append(f"[*] Table '{table}': Column '{col}' Definition Mismatch (Source: {src_c['type']}, Target: {tgt_c['type']})")
                            col_migration_lines.append(f"-- Warning: Column type change for {table}.{col} requires table rebuild in SQLite.")

                if col_migration_lines:
                    migration.append(f"-- Schema migrations for table: {table}")
                    migration.extend(col_migration_lines)

        # 2. Compare Views, Indexes, Triggers
        # Filter non-table objects
        src_other = {name: info for name, info in src_objs.items() if info['type'] != 'table'}
        tgt_other = {name: info for name, info in tgt_objs.items() if info['type'] != 'table'}
        
        all_other = set(src_other.keys()).union(tgt_other.keys())

        for name in sorted(all_other):
            obj_type = tgt_other[name]['type'] if name in tgt_other else src_other[name]['type']
            
            if name not in src_other:
                report.append(f"[+] Missing {obj_type.capitalize()} in Source: {name}")
                migration.append(f"-- Create {obj_type.capitalize()}: {name}")
                migration.append(tgt_other[name]['raw_sql'] + ";")
                
            elif name not in tgt_other:
                report.append(f"[-] Extra {obj_type.capitalize()} in Source: {name}")
                drop_keyword = "VIEW" if obj_type == "view" else "TRIGGER" if obj_type == "trigger" else "INDEX"
                migration.append(f"-- Drop {obj_type.capitalize()}: {name}")
                migration.append(f"DROP {drop_keyword} {name};")
                
            else:
                # Exists in both, compare sql structure
                if src_other[name]['sql'] != tgt_other[name]['sql']:
                    report.append(f"[*] {obj_type.capitalize()} Definition Mismatch: {name}")
                    drop_keyword = "VIEW" if obj_type == "view" else "TRIGGER" if obj_type == "trigger" else "INDEX"
                    migration.append(f"-- Recreate {obj_type.capitalize()}: {name}")
                    migration.append(f"DROP {drop_keyword} {name};")
                    migration.append(tgt_other[name]['raw_sql'] + ";")

    finally:
        src_conn.close()
        tgt_conn.close()

    return report, migration


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SQLite Schema Diff Tool - Compare schemas of two SQLite databases and generate SQL migrations."
    )
    parser.add_argument("source_db", help="Path to the source SQLite database (to be migrated)")
    parser.add_argument("target_db", help="Path to the target SQLite database (schema template)")
    parser.add_argument("-o", "--output", help="Write generated migration SQL statements to this file")
    parser.add_argument("-q", "--quiet", action="store_true", help="Print only migration SQL queries to stdout")

    args = parser.parse_args()

    try:
        report, migration = compare_schemas(args.source_db, args.target_db)
        
        # 1. Output Report
        if not args.quiet:
            print("=" * 60)
            print("SQLite Schema Comparison Report")
            print("=" * 60)
            if not report:
                print("Schemas are identical!")
            else:
                for line in report:
                    print(line)
            print("-" * 60)

        # 2. Compile Migration SQL
        migration_content = []
        if migration:
            migration_content.append("-- Generated by SQLite Schema Diff Tool")
            migration_content.append("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n")
            migration_content.extend(migration)
            migration_content.append("\nCOMMIT;\nPRAGMA foreign_keys=ON;")
            
            mig_sql = "\n".join(migration_content)
        else:
            mig_sql = "-- No schema migration required. Databases are identical."

        # 3. Write/Print Migration
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(mig_sql)
                if not args.quiet:
                    print(f"Migration script written successfully to: {args.output}")
            except IOError as e:
                print(f"Error writing migration script: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            if args.quiet:
                print(mig_sql)
            else:
                print("Migration SQL script preview:")
                print("=" * 60)
                print(mig_sql)
                print("=" * 60)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
