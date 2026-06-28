#!/usr/bin/env python3
"""
Structured Data to SQL Insert Generator - Convert CSV, JSON, or JSONL files into SQL INSERT statements

This tool infers column data types, escapes strings, handles NULL/None values,
and formats values into dialect-specific SQL INSERT statements (SQLite, MySQL, PostgreSQL, MSSQL).
It supports multi-row insert batching for high performance.

Usage:
    python tools/data_to_sql_insert.py [INPUT_FILE] [--table TABLE_NAME] [--dialect DIALECT] [--batch-size N]

Example:
    python tools/data_to_sql_insert.py data.csv --table users --dialect postgresql --batch-size 500
"""

import argparse
import csv
import json
import os
import sys
from typing import List, Dict, Any, Tuple, Generator

def escape_sql_string(val: str, dialect: str) -> str:
    """Escapes string values for safe SQL insertion depending on dialect."""
    # Standard single quote escape
    escaped = val.replace("'", "''")
    if dialect == 'mysql':
        # MySQL can escape with backslash or standard single quotes, standard is safer if NO_BACKSLASH_ESCAPE is off
        escaped = val.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"

def infer_and_format_value(val: Any, dialect: str) -> str:
    """Infers the value's type and formats it appropriately for the SQL dialect."""
    if val is None:
        return "NULL"
    
    # If it's a string, check if it represents common types or if it's just a raw string
    if isinstance(val, str):
        val_lower = val.strip().lower()
        if val_lower == '' or val_lower == 'null' or val_lower == 'none':
            return "NULL"
        
        # Check if boolean representation
        if val_lower in ('true', 'yes', 'on'):
            return "1" if dialect in ('sqlite', 'mssql') else "TRUE"
        if val_lower in ('false', 'no', 'off'):
            return "0" if dialect in ('sqlite', 'mssql') else "FALSE"
        
        # Check if integer
        try:
            int(val)
            return val.strip()
        except ValueError:
            pass
        
        # Check if float
        try:
            float(val)
            return val.strip()
        except ValueError:
            pass
            
        return escape_sql_string(val, dialect)
    
    if isinstance(val, bool):
        if val:
            return "1" if dialect in ('sqlite', 'mssql') else "TRUE"
        return "0" if dialect in ('sqlite', 'mssql') else "FALSE"
        
    if isinstance(val, (int, float)):
        return str(val)
        
    # Fallback to string representation
    return escape_sql_string(str(val), dialect)

def load_data(file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Loads dataset from CSV, JSON list, or JSONL files and returns columns and row dicts."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")
        
    rows: List[Dict[str, Any]] = []
    columns: List[str] = []
    
    if ext == '.csv':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                columns = [c.strip() for c in reader.fieldnames if c.strip()]
            for row in reader:
                # Clean keys and values
                cleaned_row = {k.strip(): v for k, v in row.items() if k and k.strip()}
                rows.append(cleaned_row)
                
    elif ext == '.json':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            # If it's a single object, wrap it
            rows = [data]
        else:
            raise ValueError("JSON file must contain an array of objects or a single object.")
            
        # Extract unique keys
        col_set = {}
        for r in rows:
            for k in r.keys():
                col_set[k] = True
        columns = list(col_set.keys())
        
    elif ext in ('.jsonl', '.ndjson'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rows.append(row)
                except json.JSONDecodeError as e:
                    print(f"Skipping line {line_no} due to invalid JSON: {e}", file=sys.stderr)
                    
        col_set = {}
        for r in rows:
            for k in r.keys():
                col_set[k] = True
        columns = list(col_set.keys())
        
    else:
        raise ValueError("Unsupported file format. Please provide a .csv, .json, or .jsonl file.")
        
    return columns, rows

def generate_inserts(table: str, columns: List[str], rows: List[Dict[str, Any]], 
                     dialect: str, batch_size: int) -> Generator[str, None, None]:
    """Generates SQL INSERT statements in batches for the target dialect."""
    quote_char = '`' if dialect == 'mysql' else '"' if dialect in ('postgresql', 'sqlite', 'mssql') else ''
    
    # Format column names
    escaped_cols = [f"{quote_char}{col}{quote_char}" for col in columns]
    cols_str = ", ".join(escaped_cols)
    
    # Process rows in chunks
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        # Build values string
        values_list = []
        for row in batch:
            row_vals = []
            for col in columns:
                val = row.get(col, None)
                row_vals.append(infer_and_format_value(val, dialect))
            values_list.append(f"({', '.join(row_vals)})")
            
        if dialect == 'mssql':
            # MSSQL does not support standard bulk insert with more than 1000 rows in one statement
            # and might need slightly different syntax or multiple single inserts if older versions.
            # But standard multi-row VALUES is fine up to 1000.
            stmt = f"INSERT INTO {table} ({cols_str}) VALUES\n" + ",\n".join(values_list) + ";"
            yield stmt
        elif dialect in ('sqlite', 'postgresql', 'mysql'):
            # Standard multi-row insert syntax
            stmt = f"INSERT INTO {table} ({cols_str}) VALUES\n" + ",\n".join(values_list) + ";"
            yield stmt
        else:
            # Fallback to single inserts if batch_size is 1
            for row_vals_str in values_list:
                yield f"INSERT INTO {table} ({cols_str}) VALUES {row_vals_str};"

def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV, JSON, or JSONL files into SQL INSERT statements."
    )
    parser.add_argument('input_file', help='Path to the input file (.csv, .json, or .jsonl)')
    parser.add_argument('--table', help='Name of the target SQL table (defaults to input file base name)')
    parser.add_argument('--dialect', choices=['sqlite', 'mysql', 'postgresql', 'mssql'], default='sqlite',
                        help='Target SQL dialect (default: sqlite)')
    parser.add_argument('--batch-size', type=int, default=1000,
                        help='Number of rows to batch per SQL statement (default: 1000)')
    parser.add_argument('--output', help='Path to write the SQL output file (prints to stdout if omitted)')
    
    args = parser.parse_args()
    
    if args.batch_size <= 0:
        print("Error: Batch size must be a positive integer.", file=sys.stderr)
        return 1
        
    table_name = args.table or os.path.splitext(os.path.basename(args.input_file))[0]
    # Clean table name to be SQL safe
    table_name = "".join(c for c in table_name if c.isalnum() or c == '_')
    
    try:
        print(f"Loading data from {args.input_file}...", file=sys.stderr)
        columns, rows = load_data(args.input_file)
        
        if not rows:
            print("Error: No data found in the input file.", file=sys.stderr)
            return 1
            
        print(f"Loaded {len(rows)} records and {len(columns)} columns.", file=sys.stderr)
        print(f"Generating INSERT statements for {args.dialect} (batch size: {args.batch_size})...", file=sys.stderr)
        
        out_stream = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout
        
        try:
            # Write a small header comment
            out_stream.write(f"-- SQL INSERT statements generated from {os.path.basename(args.input_file)}\n")
            out_stream.write(f"-- Target table: {table_name} | Dialect: {args.dialect}\n\n")
            
            for statement in generate_inserts(table_name, columns, rows, args.dialect, args.batch_size):
                out_stream.write(statement + "\n\n")
                
            if args.output:
                print(f"SQL statements successfully saved to {args.output}", file=sys.stderr)
                
        finally:
            if args.output:
                out_stream.close()
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
