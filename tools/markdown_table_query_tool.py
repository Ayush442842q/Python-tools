#!/usr/bin/env python3
"""
Markdown Table SQL Query Tool

Parses all Markdown tables in a markdown file, converts them into temporary
SQLite database tables, and allows running SQL queries directly on them.

Usage:
    python tools/markdown_table_query_tool.py <markdown_file> [options]
"""

import sys
import os
import re
import sqlite3
import argparse

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
      📊  MARKDOWN TABLE SQL QUERY TOOL  📊
========================================================={RESET}
"""
    print(banner)

class MarkdownTableParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.tables = []  # List of dicts containing: name, headers, rows

    def parse(self):
        """Parses the markdown file and extracts all tables."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        with open(self.filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_heading = "table"
        heading_counter = {}
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Track the latest heading to name tables contextually
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Clean up heading to be a valid SQL table name
                raw_heading = heading_match.group(2).strip()
                current_heading = re.sub(r"[^a-zA-Z0-9_]", "_", raw_heading).lower()
                current_heading = re.sub(r"_+", "_", current_heading).strip("_")
                if not current_heading:
                    current_heading = "table"
            
            # Look for a potential table header row
            if "|" in line:
                # Check if next line is a separator row (e.g., |---|:---:|)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # A separator line should only contain |, -, :, and spaces
                    if "|" in next_line and re.match(r"^[|:\s\-]+$", next_line):
                        # Parse table
                        headers = self._parse_row(line)
                        separator = self._parse_row(next_line)
                        
                        rows = []
                        j = i + 2
                        while j < len(lines):
                            data_line = lines[j].strip()
                            if "|" not in data_line:
                                break
                            
                            # Parse data row
                            row_cells = self._parse_row(data_line)
                            # Align column counts by truncating or padding
                            if len(row_cells) < len(headers):
                                row_cells.extend([""] * (len(headers) - len(row_cells)))
                            elif len(row_cells) > len(headers):
                                row_cells = row_cells[:len(headers)]
                            
                            rows.append(row_cells)
                            j += 1
                        
                        # Generate unique table name
                        table_base_name = current_heading if current_heading != "table" else "table"
                        heading_counter[table_base_name] = heading_counter.get(table_base_name, 0) + 1
                        table_name = f"{table_base_name}_{heading_counter[table_base_name]}"
                        
                        self.tables.append({
                            "name": table_name,
                            "headers": headers,
                            "rows": rows
                        })
                        
                        # Advance outer pointer
                        i = j - 1
            i += 1

    def _parse_row(self, line):
        """Splits a markdown table row line into cells, handling boundaries."""
        # Strip leading/trailing pipes
        trimmed = line.strip()
        if trimmed.startswith("|"):
            trimmed = trimmed[1:]
        if trimmed.endswith("|"):
            trimmed = trimmed[:-1]
            
        cells = trimmed.split("|")
        return [cell.strip() for cell in cells]


class TableDB:
    def __init__(self, parsed_tables):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.table_names = []
        self._load_tables(parsed_tables)

    def _clean_column_name(self, col_name, idx):
        """Cleans column names to be valid SQLite identifiers."""
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", col_name).strip("_")
        if not cleaned or cleaned[0].isdigit():
            cleaned = f"col_{idx}"
        return cleaned.lower()

    def _load_tables(self, parsed_tables):
        cursor = self.conn.cursor()
        for t in parsed_tables:
            original_headers = t["headers"]
            cleaned_headers = []
            seen = set()
            
            for idx, h in enumerate(original_headers):
                cleaned = self._clean_column_name(h, idx)
                # Avoid column name collisions
                while cleaned in seen:
                    cleaned = f"{cleaned}_{idx}"
                seen.add(cleaned)
                cleaned_headers.append(cleaned)

            # Create table
            columns_def = ", ".join([f"[{col}] TEXT" for col in cleaned_headers])
            create_sql = f"CREATE TABLE [{t['name']}] ({columns_def});"
            cursor.execute(create_sql)

            # Insert rows
            if t["rows"]:
                placeholders = ", ".join(["?"] * len(cleaned_headers))
                insert_sql = f"INSERT INTO [{t['name']}] VALUES ({placeholders});"
                cursor.executemany(insert_sql, t["rows"])
                
            self.table_names.append((t["name"], original_headers, cleaned_headers))
        self.conn.commit()

    def query(self, sql_query):
        """Executes a SQL query and returns column names and rows."""
        cursor = self.conn.cursor()
        cursor.execute(sql_query)
        columns = [desc[0] for desc in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return columns, rows

    def show_schemas(self):
        """Prints the schema of loaded tables."""
        print(f"\n{BOLD}{YELLOW}--- Detected Database Tables ---{RESET}")
        for tbl, orig_h, clean_h in self.table_names:
            print(f"\n{GREEN}Table: {BOLD}{tbl}{RESET}")
            print(f"  Columns (Original -> SQL Column):")
            for o, c in zip(orig_h, clean_h):
                print(f"    - {o} -> {c}")


def print_result_table(headers, rows):
    """Prints output in a beautiful CLI ASCII Table."""
    if not headers:
        return
        
    # Determine column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            str_val = str(val) if val is not None else "NULL"
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(str_val))
                
    # Build borders
    border_top = "┌─" + "─┬─".join("─" * w for w in col_widths) + "─┐"
    border_mid = "├─" + "─┼─".join("─" * w for w in col_widths) + "─┤"
    border_bot = "└─" + "─┴─".join("─" * w for w in col_widths) + "─┘"
    
    # Print header
    print(border_top)
    header_str = "│ " + " │ ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " │"
    print(f"{BOLD}{header_str}{RESET}")
    print(border_mid)
    
    # Print rows
    if not rows:
        empty_str = "No rows returned."
        total_w = sum(col_widths) + (3 * (len(col_widths) - 1))
        print("│ " + f"{empty_str:<{total_w}}" + " │")
    else:
        for row in rows:
            row_str = "│ " + " │ ".join(f"{str(val) if val is not None else 'NULL':<{w}}" for val, w in zip(row, col_widths)) + " │"
            print(row_str)
            
    print(border_bot)


def interactive_repl(db):
    """Enters an interactive SQL prompt."""
    print(f"\nEntering SQL REPL. Type {BOLD}help{RESET} or {BOLD}schema{RESET} for database structure, and {BOLD}exit{RESET} to quit.")
    while True:
        try:
            query_str = input(f"\n{BLUE}SQL>{RESET} ").strip()
            if not query_str:
                continue
            if query_str.lower() in ("exit", "quit", "q"):
                break
            if query_str.lower() == "help":
                print("Commands:")
                print("  schema - Show table structures and column mappings")
                print("  exit   - Quit the REPL")
                print("Enter any standard SQLite SELECT statement to query tables.")
                continue
            if query_str.lower() == "schema":
                db.show_schemas()
                continue
                
            # Execute query
            headers, rows = db.query(query_str)
            print_result_table(headers, rows)
            print(f"({len(rows)} rows returned)")
        except sqlite3.Error as e:
            print(f"{RED}SQLite Error: {e}{RESET}")
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")


def main():
    print_banner()
    parser = argparse.ArgumentParser(
        description="Extract and query Markdown tables with SQL",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the Markdown file containing tables")
    parser.add_argument("-q", "--query", help="SQL query to execute directly")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start interactive SQL REPL")
    parser.add_argument("-s", "--schemas", action="store_true", help="Print table schemas and column mappings")
    
    args = parser.parse_args()
    
    try:
        # Parse Markdown File
        m_parser = MarkdownTableParser(args.file)
        m_parser.parse()
        
        if not m_parser.tables:
            print(f"{YELLOW}No Markdown tables found in: {args.file}{RESET}")
            return 0
            
        print(f"Loaded {len(m_parser.tables)} table(s) from Markdown file.")
        
        # Load into SQLite
        db = TableDB(m_parser.tables)
        
        # Action routing
        if args.schemas:
            db.show_schemas()
            
        if args.query:
            print(f"\nExecuting query: {BOLD}{args.query}{RESET}\n")
            headers, rows = db.query(args.query)
            print_result_table(headers, rows)
            print(f"({len(rows)} rows returned)")
            
        if args.interactive or (not args.query and not args.schemas):
            interactive_repl(db)
            
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
