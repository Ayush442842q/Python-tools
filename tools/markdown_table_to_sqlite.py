#!/usr/bin/env python3
"""
Markdown Table to SQLite Database Converter

Scans markdown files, detects Markdown tables, parses their headers and rows,
dynamically infers SQLite column types (INTEGER, REAL, TEXT), and imports them
into a local SQLite database for easy SQL querying and sample data loading.
"""

import os
import sys
import re
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def clean_cell_value(val: str) -> str:
    """Cleans a markdown cell value by stripping extra whitespace and basic markdown formatting."""
    cleaned = val.strip()
    
    # Strip bold/italic wrappers
    cleaned = re.sub(r'^\*+\s*(.*?)\s*\*+$', r'\1', cleaned)
    cleaned = re.sub(r'^_+\s*(.*?)\s*_+$', r'\1', cleaned)
    
    # Strip backticks for code blocks
    cleaned = re.sub(r'^`\s*(.*?)\s*`$', r'\1', cleaned)
    
    # Remove simple markdown links: e.g. [text](url) -> text
    cleaned = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', cleaned)
    
    return cleaned.strip()

def parse_markdown_tables(file_path: Path) -> List[Tuple[str, List[str], List[List[str]]]]:
    """
    Parses a markdown file to locate and extract tables.
    Returns a list of tuples: (table_title, headers, rows)
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(color_text(f"Error reading file '{file_path}': {e}", COLOR_RED))
        return []

    tables = []
    lines = content.splitlines()
    
    i = 0
    last_header_text = ""
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Keep track of the most recent markdown header (to name the tables)
        if line.startswith("#"):
            last_header_text = line.lstrip("#").strip()
            i += 1
            continue
            
        # A markdown table row starts and ends with '|' or contains multiple '|'
        if line.startswith("|") and i + 1 < len(lines):
            next_line = lines[i+1].strip()
            
            # Check for separator row: | --- | :---: | ---: |
            # A valid separator row has dashes, colons, pipes, and spaces only
            if next_line.startswith("|") and re.match(r'^\|[\s\-:|]+$', next_line):
                # Parse headers
                headers = [clean_cell_value(col) for col in line.split("|")[1:-1]]
                
                rows = []
                j = i + 2
                while j < len(lines):
                    data_line = lines[j].strip()
                    if not data_line.startswith("|"):
                        break
                    
                    row = [clean_cell_value(col) for col in data_line.split("|")[1:-1]]
                    
                    # Pad row if columns don't match header count
                    if len(row) < len(headers):
                        row += [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                        
                    rows.append(row)
                    j += 1
                
                # Derive table name from last header or fallback to generic
                table_title = last_header_text if last_header_text else "table"
                # Keep alphanumeric and underscores only
                table_title = re.sub(r'[^a-zA-Z0-9_]', '_', table_title.lower()).strip("_")
                if not table_title:
                    table_title = "table"
                    
                tables.append((table_title, headers, rows))
                
                # Advance pointer past table block
                i = j
                continue
        i += 1
        
    return tables

def infer_column_type(values: List[str]) -> str:
    """Infers the SQLite column type (INTEGER, REAL, TEXT) based on list values."""
    is_int = True
    is_real = True
    
    non_empty_count = 0
    for v in values:
        if not v:
            continue
        non_empty_count += 1
        
        # Check integer
        if is_int:
            try:
                int(v)
            except ValueError:
                is_int = False
                
        # Check float
        if is_real:
            try:
                float(v)
            except ValueError:
                is_real = False
                
    if non_empty_count == 0:
        return "TEXT"
    if is_int:
        return "INTEGER"
    if is_real:
        return "REAL"
    return "TEXT"

def make_sql_column_name(name: str) -> str:
    """Sanitizes header name to make it a valid SQLite column name."""
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower()).strip("_")
    return clean if clean else "column"

def import_tables_to_sqlite(db_path: Path, tables: List[Tuple[str, List[str], List[List[str]]]], overwrite: bool) -> None:
    """Creates database tables and inserts markdown rows."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except Exception as e:
        print(color_text(f"Database connection error: {e}", COLOR_RED))
        return

    table_counts = {}
    
    for title, headers, rows in tables:
        # Avoid naming collisions
        base_title = title
        suffix_idx = 1
        while title in table_counts or table_exists(cursor, title):
            if overwrite:
                cursor.execute(f"DROP TABLE IF EXISTS {title}")
                break
            title = f"{base_title}_{suffix_idx}"
            suffix_idx += 1
            
        table_counts[title] = len(rows)
        
        # Clean headers and infer types
        clean_headers = []
        col_types = []
        for idx, h in enumerate(headers):
            col_name = make_sql_column_name(h)
            
            # Avoid duplicate column names in the same table
            base_col = col_name
            col_suffix = 1
            while col_name in clean_headers:
                col_name = f"{base_col}_{col_suffix}"
                col_suffix += 1
                
            clean_headers.append(col_name)
            
            # Collect all values in this column for type inference
            col_values = [row[idx] for row in rows if idx < len(row)]
            col_types.append(infer_column_type(col_values))
            
        # Create table SQL
        col_defs = [f"{name} {t}" for name, t in zip(clean_headers, col_types)]
        create_sql = f"CREATE TABLE {title} ({', '.join(col_defs)});"
        
        try:
            cursor.execute(create_sql)
        except sqlite3.OperationalError as e:
            print(color_text(f"SQL Creation Error for table '{title}': {e}", COLOR_RED))
            continue
            
        # Insert rows
        insert_placeholders = ", ".join(["?"] * len(clean_headers))
        insert_sql = f"INSERT INTO {title} ({', '.join(clean_headers)}) VALUES ({insert_placeholders});"
        
        # Normalize row lengths and insert
        formatted_rows = []
        for r in rows:
            formatted_row = []
            for idx, cell in enumerate(r):
                # Try to convert cell value based on inferred column type
                col_t = col_types[idx]
                if not cell:
                    formatted_row.append(None)
                elif col_t == "INTEGER":
                    formatted_row.append(int(cell))
                elif col_t == "REAL":
                    formatted_row.append(float(cell))
                else:
                    formatted_row.append(cell)
            formatted_rows.append(formatted_row)
            
        try:
            cursor.executemany(insert_sql, formatted_rows)
            conn.commit()
            print(f" {color_text('✓', COLOR_GREEN)} Imported table '{color_text(title, COLOR_BOLD + COLOR_CYAN)}' ({len(rows)} rows) with columns:")
            for name, t in zip(clean_headers, col_types):
                print(f"    - {name}: {t}")
        except Exception as e:
            conn.rollback()
            print(color_text(f"Failed to insert rows into table '{title}': {e}", COLOR_RED))
            
    conn.close()

def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Checks if a table already exists in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Markdown Table to SQLite Database Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Path to markdown file or folder containing markdown files.")
    parser.add_argument("-o", "--output", default="markdown_tables.db", help="Path to output SQLite database (default: markdown_tables.db)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing database tables if they clash.")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    db_path = Path(args.output)
    
    # Collect markdown files
    markdown_files = []
    if input_path.is_file():
        if input_path.suffix.lower() in ('.md', '.markdown'):
            markdown_files.append(input_path)
    elif input_path.is_dir():
        for root, _, files in os.walk(input_path):
            for f in files:
                file_path = Path(root) / f
                if file_path.suffix.lower() in ('.md', '.markdown'):
                    markdown_files.append(file_path)
                    
    if not markdown_files:
        print(color_text("Error: No markdown (.md/.markdown) files found matching input criteria.", COLOR_RED), file=sys.stderr)
        return 1
        
    print(f"Scanning {len(markdown_files)} markdown file(s) for tables...")
    print(f"Destination SQLite database: {db_path.resolve()}")
    print("-" * 80)
    
    all_extracted_tables = []
    for f in markdown_files:
        tables = parse_markdown_tables(f)
        if tables:
            print(f"Found {len(tables)} table(s) in: {f.name}")
            all_extracted_tables.extend(tables)
            
    if not all_extracted_tables:
        print("No valid markdown tables found.")
        return 0
        
    print("-" * 80)
    print("Writing tables to SQLite database...")
    import_tables_to_sqlite(db_path, all_extracted_tables, args.overwrite)
    print("-" * 80)
    print(color_text("Import complete!", COLOR_BOLD + COLOR_GREEN))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
