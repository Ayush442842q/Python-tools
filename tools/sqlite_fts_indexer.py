#!/usr/bin/env python3
"""
SQLite FTS Indexer
Creates a Full-Text Search (FTS5) index on an existing SQLite database table
and provides an interactive search interface with BM25 ranking.
"""

import os
import sys
import sqlite3
import argparse
from typing import List, Tuple

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
GRAY = "\033[90m"

def get_tables(conn: sqlite3.Connection) -> List[str]:
    """Retrieve all table names in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]

def get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """Retrieve all column names for a given table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table});")
    return [row[1] for row in cursor.fetchall()]

def setup_fts_index(
    db_path: str,
    source_table: str,
    key_col: str,
    index_cols: List[str],
    with_triggers: bool = True
):
    """Create the FTS5 virtual table and trigger sync mechanism."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    fts_table = f"{source_table}_fts"
    
    # 1. Drop existing FTS table if exists
    cursor.execute(f"DROP TABLE IF EXISTS {fts_table};")
    
    # 2. Create FTS5 virtual table
    # We include content=source_table and content_rowid=key_col to use external content FTS5 table.
    # This keeps database size smaller since text data isn't duplicated.
    cols_def = ", ".join(index_cols)
    create_fts_sql = (
        f"CREATE VIRTUAL TABLE {fts_table} USING fts5("
        f"  {cols_def},"
        f"  content='{source_table}',"
        f"  content_rowid='{key_col}'"
        f");"
    )
    
    print(f"{CYAN}Creating virtual table {fts_table}...{RESET}")
    cursor.execute(create_fts_sql)
    
    # 3. Populate FTS5 table with existing data
    cols_str = ", ".join(index_cols)
    populate_sql = (
        f"INSERT INTO {fts_table}(rowid, {cols_str}) "
        f"SELECT {key_col}, {cols_str} FROM {source_table};"
    )
    print(f"{CYAN}Indexing existing records...{RESET}")
    cursor.execute(populate_sql)
    
    # 4. Create Sync Triggers
    if with_triggers:
        print(f"{CYAN}Creating sync triggers (Insert, Update, Delete)...{RESET}")
        
        # Drop old triggers if they exist
        cursor.execute(f"DROP TRIGGER IF EXISTS {source_table}_ai;")
        cursor.execute(f"DROP TRIGGER IF EXISTS {source_table}_ad;")
        cursor.execute(f"DROP TRIGGER IF EXISTS {source_table}_au;")
        
        # Insert Trigger
        new_vals = ", ".join([f"new.{c}" for c in index_cols])
        insert_trigger = (
            f"CREATE TRIGGER {source_table}_ai AFTER INSERT ON {source_table} BEGIN "
            f"  INSERT INTO {fts_table}(rowid, {cols_str}) VALUES (new.{key_col}, {new_vals}); "
            f"END;"
        )
        cursor.execute(insert_trigger)
        
        # Delete Trigger
        old_vals = ", ".join([f"old.{c}" for c in index_cols])
        delete_trigger = (
            f"CREATE TRIGGER {source_table}_ad AFTER DELETE ON {source_table} BEGIN "
            f"  INSERT INTO {fts_table}({fts_table}, rowid, {cols_str}) VALUES('delete', old.{key_col}, {old_vals}); "
            f"END;"
        )
        cursor.execute(delete_trigger)
        
        # Update Trigger
        # For updates, we delete the old FTS entry and insert the new one
        update_trigger = (
            f"CREATE TRIGGER {source_table}_au AFTER UPDATE ON {source_table} BEGIN "
            f"  INSERT INTO {fts_table}({fts_table}, rowid, {cols_str}) VALUES('delete', old.{key_col}, {old_vals}); "
            f"  INSERT INTO {fts_table}(rowid, {cols_str}) VALUES(new.{key_col}, {new_vals}); "
            f"END;"
        )
        cursor.execute(update_trigger)
        
    conn.commit()
    conn.close()
    print(f"{BOLD}{GREEN}Successfully configured FTS5 index on '{source_table}'!{RESET}")

def search_fts_index(db_path: str, source_table: str, key_col: str, index_cols: List[str], query: str):
    """Search the FTS5 index and print results ranked by BM25 with text snippets."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    fts_table = f"{source_table}_fts"
    
    # We select rowid, matching details, and join back with source table for other metadata.
    # We use highlight() function of FTS5 to highlight matches.
    # highlight(fts_table, column_index, start_tag, end_tag)
    highlight_cols = []
    for idx, col in enumerate(index_cols):
        highlight_cols.append(f"highlight({fts_table}, {idx}, '\033[1m\033[32m', '\033[0m') AS hl_{col}")
        
    hl_str = ", ".join(highlight_cols)
    
    search_sql = (
        f"SELECT t.{key_col}, f.rank, {hl_str} "
        f"FROM {source_table} t "
        f"JOIN {fts_table} f ON t.{key_col} = f.rowid "
        f"WHERE {fts_table} MATCH ? "
        f"ORDER BY f.rank;"
    )
    
    try:
        cursor.execute(search_sql, (query,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"{RED}Search syntax error: {e}{RESET}\n"
              f"Tip: Try simple words. Avoid unclosed quotes or dangling operators.")
        conn.close()
        return

    if not rows:
        print(f"{YELLOW}No matches found for query: '{query}'{RESET}")
        conn.close()
        return
        
    print(f"\n{BOLD}{GREEN}Found {len(rows)} matching record(s):{RESET}")
    for row in rows:
        record_id = row[0]
        rank = row[1]
        print(f"\n{BOLD}{CYAN}Record ID: {record_id} (BM25 Rank Score: {rank:.4f}){RESET}")
        for i, col in enumerate(index_cols):
            val = row[2 + i]
            # Print if there is a match (contains ANSI highlight codes) or just print it if short
            if "\033[1m\033[32m" in str(val) or len(str(val)) < 200:
                print(f"  {BOLD}{col}:{RESET} {val}")
            else:
                # Print a simple truncated version
                print(f"  {BOLD}{col}:{RESET} {str(val)[:200]}...")
    conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="Configure and query Full-Text Search (FTS5) in a SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Configure FTS index on 'articles' table, indexing 'title' and 'body' using 'id' as key:
  python sqlite_fts_indexer.py -d blog.db -t articles -k id -c title body --setup

  # Search the index for 'python sqlite':
  python sqlite_fts_indexer.py -d blog.db -t articles -k id -c title body -q "python sqlite"

  # Search with query syntax (OR / NEAR):
  python sqlite_fts_indexer.py -d blog.db -t articles -k id -c title body -q "python NEAR database"
        """
    )
    parser.add_argument("-d", "--database", required=True, help="Path to SQLite database file")
    parser.add_argument("-t", "--table", required=True, help="Target table to index")
    parser.add_argument("-k", "--key", default="rowid", help="PrimaryKey/RowID column of table (default: rowid)")
    parser.add_argument("-c", "--columns", nargs="+", help="Columns to index for search")
    parser.add_argument("-q", "--query", help="Query string to search in the FTS index")
    parser.add_argument("--setup", action="store_true", help="Run database setup (creates virtual table and triggers)")
    parser.add_argument("--no-triggers", action="store_true", help="Do not create sync triggers during setup")

    args = parser.parse_args()

    db_path = args.database
    if not os.path.exists(db_path) and not args.setup:
        print(f"{RED}Error: Database file '{db_path}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = sqlite3.connect(db_path)
        tables = get_tables(conn)
        conn.close()
    except Exception as e:
        print(f"{RED}Error opening database: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.table not in tables:
        print(f"{RED}Error: Table '{args.table}' not found in database. Available tables: {', '.join(tables)}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Validate columns
    conn = sqlite3.connect(db_path)
    all_cols = get_columns(conn, args.table)
    conn.close()

    if args.key not in all_cols and args.key != "rowid":
        print(f"{RED}Error: Key column '{args.key}' not found in table '{args.table}'.{RESET}", file=sys.stderr)
        sys.exit(1)

    if not args.columns:
        # Default to all text/varchar columns (we can't easily detect types, so we ask users to specify or use all)
        print(f"{RED}Error: You must specify columns to index using -c/--columns.{RESET}\n"
              f"Available columns: {', '.join(all_cols)}")
        sys.exit(1)

    for col in args.columns:
        if col not in all_cols:
            print(f"{RED}Error: Column '{col}' not found in table '{args.table}'.{RESET}", file=sys.stderr)
            sys.exit(1)

    if args.setup:
        setup_fts_index(
            db_path=db_path,
            source_table=args.table,
            key_col=args.key,
            index_cols=args.columns,
            with_triggers=not args.no_triggers
        )
        
    if args.query:
        search_fts_index(
            db_path=db_path,
            source_table=args.table,
            key_col=args.key,
            index_cols=args.columns,
            query=args.query
        )

if __name__ == "__main__":
    main()
