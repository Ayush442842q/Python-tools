#!/usr/bin/env python3
"""
Interactive SQL REPL & SQLite Playground
A terminal-based REPL to inspect and query SQLite databases.
Supports multi-line inputs, query history, timing, schema inspection,
and exporting query results to CSV or JSON formats.
"""

import sys
import os
import time
import sqlite3
import csv
import json
import argparse

# Try to import readline for query history and line-editing features
try:
    import readline
except ImportError:
    readline = None

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"

def supports_color():
    """Returns True if the terminal supports colored output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_MAGENTA = ""
    COLOR_CYAN = ""

class SQLitePlayground:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.last_headers = None
        self.last_rows = None
        self.history_file = os.path.expanduser("~/.sqlite_playground_history")
        
    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            
            # Setup readline history
            if readline:
                try:
                    if os.path.exists(self.history_file):
                        readline.read_history_file(self.history_file)
                    readline.set_history_length(1000)
                except Exception:
                    pass
            return True
        except sqlite3.Error as e:
            print(f"{COLOR_RED}Error connecting to database: {e}{COLOR_RESET}")
            return False
            
    def close(self):
        if self.conn:
            self.conn.close()
        if readline:
            try:
                readline.write_history_file(self.history_file)
            except Exception:
                pass

    def format_table(self, headers, rows):
        """Format rows into a well-aligned ASCII text table."""
        if not headers:
            return "No columns returned."
        if not rows:
            return "No rows returned."
            
        # Convert all fields to strings and measure widths
        str_rows = [[str(cell) for cell in row] for row in rows]
        widths = [len(h) for h in headers]
        
        for row in str_rows:
            for idx, cell in enumerate(row):
                if idx < len(widths):
                    widths[idx] = max(widths[idx], len(cell))
                else:
                    widths.append(len(cell))
                    
        # Separator line
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        header_line = "|" + "|".join(f" {COLOR_BOLD}{COLOR_CYAN}{h:<{widths[i]}}{COLOR_RESET} " for i, h in enumerate(headers)) + "|"
        
        lines = [sep, header_line, sep]
        for row in str_rows:
            row_line = "|" + "|".join(f" {cell:<{widths[i]}} " for i, cell in enumerate(row)) + "|"
            lines.append(row_line)
        lines.append(sep)
        
        return "\n".join(lines)

    def execute_sql(self, query):
        """Executes a SQL query, prints the result, and tracks execution time."""
        if not query.strip():
            return
            
        start_time = time.perf_counter()
        try:
            self.cursor.execute(query)
            
            # Check if this query returns data (like SELECT) or updates database
            if self.cursor.description:
                self.last_headers = [desc[0] for desc in self.cursor.description]
                self.last_rows = self.cursor.fetchall()
                elapsed = (time.perf_counter() - start_time) * 1000
                
                print(self.format_table(self.last_headers, self.last_rows))
                print(f"{COLOR_GREEN}{len(self.last_rows)} rows in set ({elapsed:.2f} ms){COLOR_RESET}\n")
            else:
                self.conn.commit()
                elapsed = (time.perf_counter() - start_time) * 1000
                self.last_headers = None
                self.last_rows = None
                print(f"{COLOR_GREEN}Query OK, {self.cursor.rowcount} row(s) affected ({elapsed:.2f} ms){COLOR_RESET}\n")
        except sqlite3.Error as e:
            print(f"{COLOR_RED}SQL Error: {e}{COLOR_RESET}\n")

    def show_tables(self):
        """Dot command: Show list of tables."""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        tables = self.cursor.fetchall()
        if not tables:
            print("No tables found in database.")
        else:
            print(f"{COLOR_BOLD}Tables:{COLOR_RESET}")
            for t in tables:
                print(f"  {t[0]}")
        print()

    def show_schema(self, table_name):
        """Dot command: Show table schema (CREATE TABLE)."""
        if not table_name:
            print(f"{COLOR_RED}Usage: .schema <table_name>{COLOR_RESET}\n")
            return
            
        self.cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
        res = self.cursor.fetchone()
        if not res:
            print(f"{COLOR_RED}Table '{table_name}' not found.{COLOR_RESET}\n")
        else:
            print(f"{COLOR_BOLD}Schema for {table_name}:{COLOR_RESET}")
            print(res[0])
            print()

    def show_databases(self):
        """Dot command: Show attached databases."""
        self.cursor.execute("PRAGMA database_list;")
        db_list = self.cursor.fetchall()
        print(f"{COLOR_BOLD}Attached Databases:{COLOR_RESET}")
        for db in db_list:
            seq, name, file_path = db
            print(f"  {seq}: {name} -> {file_path if file_path else ':memory:'}")
        print()

    def export_results(self, export_format, filepath):
        """Dot command: Export last query results to CSV or JSON."""
        if not self.last_rows or not self.last_headers:
            print(f"{COLOR_RED}Error: No query results available to export. Run a SELECT query first.{COLOR_RESET}\n")
            return
            
        if not filepath:
            print(f"{COLOR_RED}Usage: .export {export_format} <file_path>{COLOR_RESET}\n")
            return
            
        try:
            if export_format == "csv":
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.last_headers)
                    writer.writerows(self.last_rows)
                print(f"{COLOR_GREEN}Exported {len(self.last_rows)} rows to CSV: '{filepath}'{COLOR_RESET}\n")
            elif export_format == "json":
                # Convert rows to dicts
                dict_list = [dict(zip(self.last_headers, row)) for row in self.last_rows]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(dict_list, f, indent=2)
                print(f"{COLOR_GREEN}Exported {len(self.last_rows)} rows to JSON: '{filepath}'{COLOR_RESET}\n")
        except Exception as e:
            print(f"{COLOR_RED}Export failed: {e}{COLOR_RESET}\n")

    def show_help(self):
        """Prints the list of commands and usage details."""
        print(f"""{COLOR_BOLD}SQLite Playground REPL Help:{COLOR_RESET}
  Enter any standard SQL query ending with a semicolon (;) to execute it.
  Queries can span multiple lines.

  {COLOR_BOLD}Special Dot Commands:{COLOR_RESET}
    .help                 Show this help manual
    .tables               List all user-created tables in the database
    .schema <table_name>  Show the CREATE SQL statement for the table
    .databases            List all attached database files
    .export csv <path>    Export the results of the last SELECT query to a CSV file
    .export json <path>   Export the results of the last SELECT query to a JSON file
    .exit or .quit        Exit the playground
""")

    def start_repl(self):
        db_label = "in-memory" if self.db_path == ":memory:" else self.db_path
        print(f"=== {COLOR_BOLD}{COLOR_MAGENTA}SQLite Playground REPL{COLOR_RESET} ===")
        print(f"Connected to database: {COLOR_BLUE}{db_label}{COLOR_RESET}")
        print("Type '.help' for help. Enter queries ending with ';'")
        print("=" * 50 + "\n")
        
        query_buffer = []
        
        while True:
            try:
                # Prompt changes if entering a multi-line query
                prompt = "sqlite> " if not query_buffer else "   ... "
                line = input(prompt)
                
                stripped = line.strip()
                if not stripped:
                    continue
                    
                # Handle Dot Commands
                if stripped.startswith("."):
                    parts = stripped.split(None, 2)
                    cmd = parts[0].lower()
                    
                    if cmd in (".exit", ".quit"):
                        print("Goodbye!")
                        break
                    elif cmd == ".help":
                        self.show_help()
                    elif cmd == ".tables":
                        self.show_tables()
                    elif cmd == ".databases":
                        self.show_databases()
                    elif cmd == ".schema":
                        table_name = parts[1] if len(parts) > 1 else None
                        self.show_schema(table_name)
                    elif cmd == ".export":
                        export_format = parts[1].lower() if len(parts) > 1 else None
                        filepath = parts[2] if len(parts) > 2 else None
                        if export_format not in ("csv", "json"):
                            print(f"{COLOR_RED}Error: Export format must be 'csv' or 'json'.{COLOR_RESET}\n")
                        else:
                            self.export_results(export_format, filepath)
                    else:
                        print(f"{COLOR_RED}Unknown dot command: {cmd}. Type '.help' for available commands.{COLOR_RESET}\n")
                    continue
                
                # Add line to buffer
                query_buffer.append(line)
                
                # If query ends with a semicolon, execute it
                if stripped.endswith(";"):
                    full_query = " ".join(query_buffer)
                    self.execute_sql(full_query)
                    query_buffer = []
                    
            except KeyboardInterrupt:
                # Clear line buffer on Ctrl+C
                print("\nKeyboardInterrupt (Query cancelled)")
                query_buffer = []
            except EOFError:
                # Exit on Ctrl+D
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"{COLOR_RED}Unexpected Error: {e}{COLOR_RESET}\n")
                query_buffer = []

def main():
    parser = argparse.ArgumentParser(
        description="SQLite Playground REPL - Interactive console tool to query SQLite databases.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("database", nargs="?", default=":memory:", help="Path to SQLite database file (default: :memory:)")
    
    args = parser.parse_args()
    
    playground = SQLitePlayground(args.database)
    if playground.connect():
        try:
            playground.start_repl()
        finally:
            playground.close()
            
if __name__ == "__main__":
    main()
