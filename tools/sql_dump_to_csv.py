#!/usr/bin/env python3
"""
SQL Dump to CSV Converter

A standalone data utility that parses SQL database dump files (.sql) and 
extracts table data from INSERT INTO statements, writing them into standard CSV files.

This is highly useful for extracting data from SQL dumps without needing to 
install or run a database server.

Usage:
    python tools/sql_dump_to_csv.py [options] <sql_file>

Examples:
    python tools/sql_dump_to_csv.py database_dump.sql
    python tools/sql_dump_to_csv.py --list-tables database_dump.sql
    python tools/sql_dump_to_csv.py --table users --output-dir ./extracted/ database_dump.sql
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

def parse_sql_values(values_str):
    """
    Parse the content of a VALUES clause, taking into account quotes, 
    escaped characters, and multiple tuple elements.
    Example input: "('1', 'John O\\'Connor', 'active', NULL), ('2', 'Jane \"Doe\"', 'pending', 3.14)"
    Returns a list of lists of values.
    """
    tuples = []
    current_tuple = []
    
    # State flags
    in_string = False
    string_char = None
    escaped = False
    buffer = []
    
    # Clean whitespace but preserve it inside strings
    idx = 0
    length = len(values_str)
    
    while idx < length:
        char = values_str[idx]
        
        if escaped:
            buffer.append(char)
            escaped = False
            idx += 1
            continue
            
        if char == '\\':
            escaped = True
            idx += 1
            continue
            
        if in_string:
            if char == string_char:
                # Check for double quote escaping in SQL (e.g. '' or "")
                if idx + 1 < length and values_str[idx + 1] == string_char:
                    buffer.append(string_char)
                    idx += 2
                    continue
                else:
                    in_string = False
                    string_char = None
            else:
                buffer.append(char)
            idx += 1
            continue
            
        # Outside string
        if char in ("'", '"', "`"):
            in_string = True
            string_char = char
            idx += 1
            continue
            
        if char == '(':
            current_tuple = []
            buffer = []
            idx += 1
            continue
            
        if char == ')':
            # End of a row tuple
            val = "".join(buffer).strip()
            # Handle NULL/numbers/empty
            if val.upper() == 'NULL':
                current_tuple.append(None)
            else:
                current_tuple.append(val)
            tuples.append(current_tuple)
            current_tuple = []
            buffer = []
            idx += 1
            continue
            
        if char == ',':
            val = "".join(buffer).strip()
            # If we are inside a tuple (between parens)
            if len(current_tuple) >= 0:
                if val.upper() == 'NULL':
                    current_tuple.append(None)
                else:
                    current_tuple.append(val)
                buffer = []
            idx += 1
            continue
            
        # Ignore top-level whitespace, commas, etc., outside tuples
        if char.isspace():
            idx += 1
            continue
            
        # Accumulate chars
        buffer.append(char)
        idx += 1
        
    return tuples

def extract_insert_data(sql_line_stream, target_table=None):
    """
    Process the stream of lines, merging multi-line INSERT statements
    and yields (table_name, columns, rows) tuples.
    """
    # Regex to capture INSERT INTO table_name [(cols)] VALUES (vals)
    # Supports backticks, double quotes or unquoted table names
    insert_pattern = re.compile(
        r"INSERT\s+INTO\s+[`\"']?([a-zA-Z0-9_\-]+)[`\"']?\s*(?:\(([^)]+)\))?\s+VALUES\s*(.*)",
        re.IGNORECASE
    )
    
    current_statement = []
    in_insert = False
    table_name = None
    columns = None
    
    for line in sql_line_stream:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('--') or line_stripped.startswith('/*'):
            continue
            
        if not in_insert:
            match = insert_pattern.search(line_stripped)
            if match:
                table_name = match.group(1)
                
                # Check target table filter
                if target_table and table_name.lower() != target_table.lower():
                    continue
                    
                cols_str = match.group(2)
                if cols_str:
                    columns = [c.strip(' `"\n\r\t') for c in cols_str.split(',')]
                else:
                    columns = []
                    
                vals_start = match.group(3)
                current_statement = [vals_start]
                in_insert = True
                
                # Check if it ends on same line
                if line_stripped.endswith(';'):
                    in_insert = False
                    full_vals = " ".join(current_statement)[:-1] # strip semicolon
                    rows = parse_sql_values(full_vals)
                    yield table_name, columns, rows
        else:
            # Check target table filter (skip collecting if not matching)
            if target_table and table_name.lower() != target_table.lower():
                if line_stripped.endswith(';'):
                    in_insert = False
                continue
                
            current_statement.append(line_stripped)
            if line_stripped.endswith(';'):
                in_insert = False
                full_vals = " ".join(current_statement)[:-1] # strip semicolon
                rows = parse_sql_values(full_vals)
                yield table_name, columns, rows

def main():
    parser = argparse.ArgumentParser(
        description="Convert standard SQL dump INSERT statements into CSV files."
    )
    parser.add_argument(
        'sql_file',
        help='Path to the SQL dump file (.sql)'
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='.',
        help='Directory to output the CSV files (default: current directory)'
    )
    parser.add_argument(
        '-t', '--table',
        help='Only extract data for this specific table (case-insensitive)'
    )
    parser.add_argument(
        '-l', '--list-tables',
        action='store_true',
        help='Only scan and list tables with INSERT data, do not write CSV files'
    )
    
    args = parser.parse_args()
    
    sql_path = Path(args.sql_file)
    if not sql_path.exists():
        print(f"Error: SQL dump file '{args.sql_file}' does not exist.", file=sys.stderr)
        return 1
        
    out_dir = Path(args.output_dir)
    if not args.list_tables and not out_dir.exists():
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating output directory '{args.output_dir}': {e}", file=sys.stderr)
            return 1
            
    # Track statistics
    tables_found = {}
    
    print(f"Reading SQL file: {sql_path.name}...")
    try:
        with open(sql_path, 'r', encoding='utf-8', errors='ignore') as f:
            for table, cols, rows in extract_insert_data(f, target_table=args.table):
                if table not in tables_found:
                    tables_found[table] = {
                        'rows_count': 0,
                        'cols_count': len(cols),
                        'columns': cols
                    }
                tables_found[table]['rows_count'] += len(rows)
                
                # If we are listing tables, we don't write
                if args.list_tables:
                    continue
                    
                csv_path = out_dir / f"{table}.csv"
                write_header = not csv_path.exists()
                
                try:
                    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        
                        # Write headers if it's a new file
                        if write_header:
                            if cols:
                                writer.writerow(cols)
                            else:
                                # Fallback dummy headers if cols are empty (INSERT INTO values without explicit columns)
                                dummy_cols = [f"column_{i+1}" for i in range(len(rows[0]))] if rows else []
                                writer.writerow(dummy_cols)
                                tables_found[table]['columns'] = dummy_cols
                                tables_found[table]['cols_count'] = len(dummy_cols)
                                
                        writer.writerows(rows)
                except Exception as e:
                    print(f"Error writing to {csv_path}: {e}", file=sys.stderr)
                    return 1
    except Exception as e:
        print(f"Error reading SQL file: {e}", file=sys.stderr)
        return 1
        
    print("\nParsing Summary:")
    print("=" * 40)
    if not tables_found:
        print("No INSERT INTO statements found in the SQL file.")
    else:
        for t_name, info in tables_found.items():
            col_preview = ", ".join(info['columns'][:4])
            if info['cols_count'] > 4:
                col_preview += ", ..."
            print(f"Table: {t_name}")
            print(f"  Rows Extracted: {info['rows_count']}")
            print(f"  Columns ({info['cols_count']}): [{col_preview}]")
            if not args.list_tables:
                print(f"  Saved to: {(out_dir / f'{t_name}.csv').name}")
            print("-" * 40)
            
    return 0

if __name__ == '__main__':
    sys.exit(main())
