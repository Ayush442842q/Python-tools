#!/usr/bin/env python3
"""
SQLite to PostgreSQL Converter

A command-line tool that inspects a SQLite database file and generates a
PostgreSQL-compatible SQL dump file, converting table schemas, constraints,
indexes, and records with proper data-type mapping and SQL dialect adaptations.

Usage:
    python tools/sqlite_to_postgresql_converter.py -i input.db -o output.sql [options]

Options:
    -i, --input PATH      Path to the source SQLite database file
    -o, --output PATH     Path to save the generated PostgreSQL SQL dump
    --schema-only         Only dump the database schema (no INSERT statements)
    --data-only           Only dump data/records (no CREATE TABLE statements)
    --clean               Prepend DROP TABLE IF EXISTS statements
    --no-indexes          Skip exporting indexes
    --no-fkeys            Skip exporting foreign keys
"""

import argparse
import os
import sqlite3
import sys
from typing import List, Dict, Tuple, Any

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def supports_color() -> bool:
    """Returns True if the terminal supports ANSI colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty


def color_text(text: str, color_code: str) -> str:
    """Colors text for terminal output if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text


def map_type(sqlite_type: str, is_autoincrement: bool = False) -> str:
    """Maps a SQLite data type to its PostgreSQL equivalent."""
    t = sqlite_type.upper().strip()
    
    if is_autoincrement:
        if "BIGINT" in t or "INT8" in t:
            return "BIGSERIAL"
        return "SERIAL"

    if not t:
        return "TEXT"

    # Numeric mappings
    if "INT" in t:
        if "BIGINT" in t or "INT8" in t:
            return "BIGINT"
        if "SMALLINT" in t or "INT2" in t:
            return "SMALLINT"
        return "INTEGER"
    if "CHAR" in t or "TEXT" in t or "CLOB" in t:
        if "(" in t:  # e.g., VARCHAR(255)
            return t
        return "TEXT"
    if "BLOB" in t or "BINARY" in t:
        return "BYTEA"
    if "REAL" in t or "FLOA" in t or "DOUBLE" in t:
        return "DOUBLE PRECISION"
    if "NUMERIC" in t or "DEC" in t:
        return t
    if "BOOL" in t:
        return "BOOLEAN"
    if "DATE" in t or "TIME" in t:
        if "DATETIME" in t or "TIMESTAMP" in t:
            return "TIMESTAMP WITH TIME ZONE"
        return t

    return "TEXT"


def escape_name(name: str) -> str:
    """Escapes table or column names for PostgreSQL SQL syntax."""
    # Postgres names are case-sensitive if double-quoted.
    # To keep it simple and clean, wrap in double quotes.
    return f'"{name}"'


def escape_value(val: Any, pg_type: str) -> str:
    """Escapes values for PostgreSQL INSERT statements based on PostgreSQL data type."""
    if val is None:
        return "NULL"

    if pg_type == "BOOLEAN":
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if str(val).strip() in ('1', 'true', 'TRUE', 't', 'T'):
            return "TRUE"
        return "FALSE"

    if pg_type == "BYTEA":
        # SQLite returns blobs as bytes. We format them as hex E'\\x...'
        if isinstance(val, bytes):
            return f"E'\\\\x{val.hex()}'"
        # If SQLite stored it as a string, check if it's hex or encode it
        val_str = str(val)
        if val_str.startswith("x'") or val_str.startswith("X'"):
            hex_val = val_str[2:-1]
            return f"E'\\\\x{hex_val}'"
        return f"E'\\\\x{val_str.encode('utf-8').hex()}'"

    # String, Text, Datetime types
    if isinstance(val, (str, bytes)):
        if isinstance(val, bytes):
            val_str = val.decode('utf-8', errors='replace')
        else:
            val_str = val
        # Escape single quotes by doubling them
        escaped = val_str.replace("'", "''")
        return f"'{escaped}'"

    return str(val)


class SqliteToPostgresConverter:
    def __init__(self, db_path: str, schema_only: bool = False, data_only: bool = False,
                 clean: bool = False, no_indexes: bool = False, no_fkeys: bool = False):
        self.db_path = db_path
        self.schema_only = schema_only
        self.data_only = data_only
        self.clean = clean
        self.no_indexes = no_indexes
        self.no_fkeys = no_fkeys
        self.conn = None

    def connect(self):
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"SQLite file not found at: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def get_tables(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        return [row['name'] for row in cursor.fetchall()]

    def get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        # Fetch indexes except automatic ones created for primary key/unique constraints
        cursor.execute(f"PRAGMA index_list({escape_name(table_name)});")
        indexes = []
        for idx in cursor.fetchall():
            if idx['origin'] == 'c':  # 'c' means created by CREATE INDEX
                # Get columns in index
                cursor.execute(f"PRAGMA index_info({escape_name(idx['name'])});")
                cols = [col['name'] for col in cursor.fetchall()]
                indexes.append({
                    'name': idx['name'],
                    'unique': bool(idx['unique']),
                    'columns': cols
                })
        return indexes

    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({escape_name(table_name)});")
        fkeys = []
        for row in cursor.fetchall():
            fkeys.append({
                'from': row['from'],
                'table': row['table'],
                'to': row['to'],
                'on_update': row['on_update'],
                'on_delete': row['on_delete']
            })
        return fkeys

    def get_table_schema(self, table_name: str) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
        """Returns column definitions, primary keys, and auto-increment status."""
        cursor = self.conn.cursor()
        
        # Get raw table creation SQL to check for AUTOINCREMENT keyword
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        create_sql = cursor.fetchone()
        is_autoincrement = False
        if create_sql and create_sql['sql'] and "AUTOINCREMENT" in create_sql['sql'].upper():
            is_autoincrement = True

        cursor.execute(f"PRAGMA table_info({escape_name(table_name)});")
        columns = []
        pkeys = []
        
        for col in cursor.fetchall():
            is_pk = bool(col['pk'])
            columns.append({
                'name': col['name'],
                'type': col['type'],
                'notnull': bool(col['notnull']),
                'dflt_value': col['dflt_value'],
                'is_pk': is_pk,
                'is_auto': is_autoincrement if is_pk else False
            })
            if is_pk:
                pkeys.append(col['name'])

        return columns, pkeys, is_autoincrement

    def generate_postgres_sql(self) -> str:
        self.connect()
        tables = self.get_tables()
        lines = []

        lines.append("-- -------------------------------------------------------------")
        lines.append(f"-- PostgreSQL Dump migrated from SQLite database: {os.path.basename(self.db_path)}")
        lines.append(f"-- Generated using sqlite_to_postgresql_converter.py")
        lines.append("-- -------------------------------------------------------------\n")
        
        # Set settings for transaction safety and encoding
        lines.append("SET statement_timeout = 0;")
        lines.append("SET lock_timeout = 0;")
        lines.append("SET client_encoding = 'UTF8';")
        lines.append("SET standard_conforming_strings = on;")
        lines.append("SET check_function_bodies = false;")
        lines.append("SET client_min_messages = warning;")
        lines.append("SET row_security = off;\n")

        # Convert schemas table by table
        for table in tables:
            columns, pkeys, is_auto = self.get_table_schema(table)
            
            # 1. DROP TABLE IF EXISTS
            if self.clean and not self.data_only:
                lines.append(f"DROP TABLE IF EXISTS {escape_name(table)} CASCADE;")

            # 2. CREATE TABLE
            if not self.data_only:
                lines.append(f"CREATE TABLE {escape_name(table)} (")
                col_defs = []
                
                for col in columns:
                    pg_type = map_type(col['type'], col['is_auto'])
                    col_line = f"    {escape_name(col['name'])} {pg_type}"
                    
                    if col['notnull']:
                        col_line += " NOT NULL"
                    
                    if col['dflt_value'] is not None:
                        # Translate default values like CURRENT_TIMESTAMP or auto numbers
                        dflt = col['dflt_value'].strip()
                        if dflt.upper() in ("CURRENT_TIMESTAMP", "'NOW'"):
                            col_line += " DEFAULT CURRENT_TIMESTAMP"
                        else:
                            col_line += f" DEFAULT {dflt}"
                            
                    col_defs.append(col_line)

                # Add Primary Key constraint
                if pkeys:
                    pkeys_escaped = ", ".join(escape_name(pk) for pk in pkeys)
                    col_defs.append(f"    CONSTRAINT {escape_name(table + '_pkey')} PRIMARY KEY ({pkeys_escaped})")

                # Add Foreign Key constraints
                if not self.no_fkeys:
                    fkeys = self.get_foreign_keys(table)
                    for i, fk in enumerate(fkeys):
                        fk_name = escape_name(f"{table}_{fk['from']}_fkey")
                        from_col = escape_name(fk['from'])
                        to_table = escape_name(fk['table'])
                        to_col = escape_name(fk['to'])
                        
                        fk_line = f"    CONSTRAINT {fk_name} FOREIGN KEY ({from_col}) REFERENCES {to_table}({to_col})"
                        
                        if fk['on_delete'] and fk['on_delete'].upper() != 'NO ACTION':
                            fk_line += f" ON DELETE {fk['on_delete']}"
                        if fk['on_update'] and fk['on_update'].upper() != 'NO ACTION':
                            fk_line += f" ON UPDATE {fk['on_update']}"
                            
                        col_defs.append(fk_line)

                lines.append(",\n".join(col_defs))
                lines.append(");\n")

            # 3. INSERT STATEMENTS (DATA DUMP)
            if not self.schema_only:
                cursor = self.conn.cursor()
                # Sort columns to ensure consistent value mapping
                col_names = [col['name'] for col in columns]
                col_types_mapped = {col['name']: map_type(col['type']) for col in columns}
                
                escaped_cols = ", ".join(escape_name(c) for c in col_names)
                cursor.execute(f"SELECT * FROM {escape_name(table)};")
                
                rows = cursor.fetchall()
                if rows:
                    lines.append(f"-- Data dump for table: {table}")
                    
                    # Dump rows in chunks to prevent massive SQL strings or support batch inserts
                    for row in rows:
                        values = []
                        for col in col_names:
                            val = row[col]
                            pg_type = col_types_mapped[col]
                            values.append(escape_value(val, pg_type))
                        
                        val_str = ", ".join(values)
                        lines.append(f"INSERT INTO {escape_name(table)} ({escaped_cols}) VALUES ({val_str});")
                    lines.append("")

            # 4. CREATE INDEXES
            if not self.no_indexes and not self.data_only:
                indexes = self.get_indexes(table)
                for idx in indexes:
                    unique_str = "UNIQUE " if idx['unique'] else ""
                    idx_name_escaped = escape_name(idx['name'])
                    table_escaped = escape_name(table)
                    cols_escaped = ", ".join(escape_name(c) for c in idx['columns'])
                    
                    lines.append(f"CREATE {unique_str}INDEX {idx_name_escaped} ON {table_escaped} ({cols_escaped});")
                if indexes:
                    lines.append("")

        self.close()
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SQLite databases to PostgreSQL-compatible SQL dump files."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input SQLite database file (.db, .sqlite)")
    parser.add_argument("-o", "--output", help="Path to save the generated PostgreSQL SQL dump (default: stdout)")
    parser.add_argument("--schema-only", action="store_true", help="Dump schema only, no records")
    parser.add_argument("--data-only", action="store_true", help="Dump data only, no create tables")
    parser.add_argument("--clean", action="store_true", help="Prepend DROP TABLE IF EXISTS statements")
    parser.add_argument("--no-indexes", action="store_true", help="Skip exporting indexes")
    parser.add_argument("--no-fkeys", action="store_true", help="Skip exporting foreign keys")

    args = parser.parse_args()

    # Verify input exists
    if not os.path.exists(args.input):
        print(color_text(f"Error: Input SQLite file does not exist at '{args.input}'", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    print(color_text("Starting SQLite to PostgreSQL Conversion...", COLOR_CYAN), file=sys.stderr)
    print(color_text(f"  Source Database : {args.input}", COLOR_BOLD), file=sys.stderr)
    
    try:
        converter = SqliteToPostgresConverter(
            db_path=args.input,
            schema_only=args.schema_only,
            data_only=args.data_only,
            clean=args.clean,
            no_indexes=args.no_indexes,
            no_fkeys=args.no_fkeys
        )
        
        sql_content = converter.generate_postgres_sql()
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(sql_content)
            print(color_text(f"Conversion complete! Output saved to: {args.output}", COLOR_GREEN), file=sys.stderr)
        else:
            print(sql_content)
            
    except Exception as e:
        print(color_text(f"Migration Failed: {str(e)}", COLOR_RED), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
