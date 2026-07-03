#!/usr/bin/env python3
"""
Converts standard JSON or JSON Lines (JSONL/NDJSON) data files into a SQLite database 
with automatic table creation, type inference, nested object serialization, and indexing.
"""

import sys
import os
import json
import sqlite3
import argparse

def infer_sql_type(val):
    """Infers the SQLite column type for a given python value."""
    if val is None:
        return "TEXT"  # Default fallback
    elif isinstance(val, bool):
        return "INTEGER"
    elif isinstance(val, int):
        return "INTEGER"
    elif isinstance(val, float):
        return "REAL"
    elif isinstance(val, (dict, list)):
        return "TEXT"  # Will be serialized as JSON string
    else:
        return "TEXT"

def parse_json_lines(filepath):
    """Parses JSON Lines (JSONL/NDJSON) file."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping line {idx} due to decode error: {e}", file=sys.stderr)
    return records

def parse_json_file(filepath):
    """Parses standard JSON file and returns a list of dictionaries."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # If dict, check if there's a list under any key (common layout)
        lists_under_keys = {k: v for k, v in data.items() if isinstance(v, list)}
        if len(lists_under_keys) == 1:
            key = list(lists_under_keys.keys())[0]
            print(f"Detected list of records under dictionary key: '{key}'", file=sys.stderr)
            return lists_under_keys[key]
        elif len(lists_under_keys) > 1:
            # Let user choose or default to first one
            key = list(lists_under_keys.keys())[0]
            print(f"Warning: Multiple lists found. Defaulting to: '{key}'", file=sys.stderr)
            return lists_under_keys[key]
        else:
            # Just treat the dict as a single record
            return [data]
    else:
        raise ValueError("JSON file root structure must be an array or an object.")

def build_schema(records):
    """Analyzes records to infer column names and types."""
    schema = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for key, val in rec.items():
            if val is None and key in schema:
                continue
            sql_type = infer_sql_type(val)
            # Upgrade type if already in schema (e.g., INTEGER -> REAL)
            if key in schema:
                curr_type = schema[key]
                if curr_type == "INTEGER" and sql_type == "REAL":
                    schema[key] = "REAL"
            else:
                schema[key] = sql_type
                
    return schema

def convert_records_to_sqlite(records, db_path, table_name, index_columns=None):
    """Creates SQLite table and inserts the list of dictionary records."""
    if not records:
        print("Error: No records found to process.", file=sys.stderr)
        return False

    schema = build_schema(records)
    if not schema:
        print("Error: Inferred schema is empty.", file=sys.stderr)
        return False
        
    # Connect to SQLite
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database {db_path}: {e}", file=sys.stderr)
        return False

    # Construct CREATE TABLE DDL
    columns_ddl = []
    for col_name, col_type in schema.items():
        # Sanitize column names by wrapping in double quotes to allow reserved words
        columns_ddl.append(f'"{col_name}" {col_type}')
        
    ddl = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  {",\n  ".join(columns_ddl)}\n);'
    
    try:
        cursor.execute(ddl)
    except Exception as e:
        print(f"Error creating table: {e}", file=sys.stderr)
        conn.close()
        return False
        
    # Prepare Insert Statement
    col_names = list(schema.keys())
    quoted_cols = [f'"{c}"' for c in col_names]
    placeholders = [":" + c for c in col_names]
    
    insert_sql = f'INSERT INTO "{table_name}" ({", ".join(quoted_cols)}) VALUES ({", ".join(placeholders)})'
    
    # Process and sanitize records for insertion
    processed_rows = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row_dict = {}
        for col in col_names:
            val = rec.get(col, None)
            # Serialize lists and dicts to string
            if isinstance(val, (dict, list)):
                row_dict[col] = json.dumps(val, ensure_ascii=False)
            else:
                row_dict[col] = val
        processed_rows.append(row_dict)

    # Insert in batch transaction
    try:
        cursor.executemany(insert_sql, processed_rows)
        conn.commit()
        print(f"Successfully inserted {len(processed_rows)} rows into table '{table_name}'.", file=sys.stderr)
    except Exception as e:
        print(f"Error executing batch insert: {e}", file=sys.stderr)
        conn.rollback()
        conn.close()
        return False

    # Create Indexes
    if index_columns:
        for idx_col in index_columns:
            if idx_col in schema:
                idx_name = f"idx_{table_name}_{idx_col}".replace("-", "_").replace(" ", "_")
                create_idx_sql = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" ("{idx_col}");'
                try:
                    cursor.execute(create_idx_sql)
                    print(f"Created index on column '{idx_col}'.", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Failed to create index on '{idx_col}': {e}", file=sys.stderr)
        conn.commit()
        
    conn.close()
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Convert standard JSON or JSON Lines (JSONL/NDJSON) data files into a SQLite database."
    )
    parser.add_argument("input", help="Path to input JSON or JSONL file.")
    parser.add_argument("db", help="Path to output SQLite database file.")
    
    parser.add_argument(
        "-t", "--table", 
        help="Target database table name. If omitted, uses the base input filename."
    )
    parser.add_argument(
        "-i", "--index", 
        action="append", 
        help="Column(s) to create SQLite index on (can specify multiple times)."
    )
    parser.add_argument(
        "--jsonl", 
        action="store_true", 
        help="Force input parsing as JSON Lines (JSONL) format."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Auto-detect format or force JSONL
    is_jsonl = args.jsonl or args.input.endswith((".jsonl", ".ndjson"))
    
    print(f"Parsing input file '{args.input}'...", file=sys.stderr)
    try:
        if is_jsonl:
            records = parse_json_lines(args.input)
        else:
            records = parse_json_file(args.input)
    except Exception as e:
        print(f"Error parsing input data: {e}", file=sys.stderr)
        sys.exit(1)

    # Inferred table name
    table_name = args.table or os.path.splitext(os.path.basename(args.input))[0]
    # Replace non-alphanumeric chars with underscores for table name safety
    table_name = "".join(c if c.isalnum() else "_" for c in table_name)
    if table_name.startswith(("_", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
        table_name = "t_" + table_name

    print(f"Writing to SQLite database '{args.db}'...", file=sys.stderr)
    success = convert_records_to_sqlite(
        records=records,
        db_path=args.db,
        table_name=table_name,
        index_columns=args.index
    )
    
    if success:
        print("\nData conversion completed successfully!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
