#!/usr/bin/env python3
"""
CSV to SQLite Converter
Imports CSV data into a SQLite database with automatic column type inference,
and supports running SQL queries on the imported tables.
"""

import argparse
import csv
import os
import sqlite3
import sys

def infer_type(val):
    """Infer SQLite data type for a string value."""
    val = val.strip()
    if not val:
        return 'NULL'
    # Try integer
    try:
        int(val)
        return 'INTEGER'
    except ValueError:
        pass
    # Try real/float
    try:
        float(val)
        return 'REAL'
    except ValueError:
        pass
    return 'TEXT'

def scan_csv_types(file_path, delimiter=',', encoding='utf-8', max_rows=100):
    """Scan first N rows of the CSV to infer best column data types."""
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(reader)
            except StopIteration:
                raise ValueError("CSV file is empty.")
                
            num_cols = len(headers)
            col_types = [set() for _ in range(num_cols)]
            
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                # Handle cases where row length doesn't match header length
                for j in range(min(num_cols, len(row))):
                    inferred = infer_type(row[j])
                    if inferred != 'NULL':
                        col_types[j].add(inferred)
                        
            # Resolve inferred type for each column
            inferred_schema = []
            for j, types in enumerate(col_types):
                clean_header = "".join([c if c.isalnum() else "_" for c in headers[j].strip()])
                if not clean_header:
                    clean_header = f"column_{j+1}"
                
                # Default type is TEXT
                final_type = 'TEXT'
                if 'TEXT' in types:
                    final_type = 'TEXT'
                elif 'REAL' in types:
                    final_type = 'REAL'
                elif 'INTEGER' in types:
                    final_type = 'INTEGER'
                    
                inferred_schema.append((clean_header, final_type))
                
            return inferred_schema
    except Exception as e:
        print(f"Error scanning CSV: {e}", file=sys.stderr)
        sys.exit(1)

def convert_csv_to_sqlite(csv_path, db_path, table_name, delimiter=',', encoding='utf-8'):
    # Step 1: Infer column types
    schema = scan_csv_types(csv_path, delimiter, encoding)
    
    # Step 2: Establish database connection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 3: Create table
        create_cols = ", ".join([f"[{name}] {dtype}" for name, dtype in schema])
        create_sql = f"CREATE TABLE IF NOT EXISTS [{table_name}] ({create_cols});"
        cursor.execute(create_sql)
        
        # Step 4: Insert CSV rows
        with open(csv_path, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=delimiter)
            # Skip header
            next(reader)
            
            placeholders = ", ".join(["?"] * len(schema))
            insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders});"
            
            # Batch inserts in transaction
            batch = []
            batch_size = 1000
            total_rows = 0
            
            for row in reader:
                # Pad/truncate row to match column count
                if len(row) < len(schema):
                    row = row + [''] * (len(schema) - len(row))
                elif len(row) > len(schema):
                    row = row[:len(schema)]
                
                # Convert empty strings to None (NULL in SQLite) if column isn't TEXT
                row_data = []
                for val, (_, dtype) in zip(row, schema):
                    val = val.strip()
                    if val == '' and dtype != 'TEXT':
                        row_data.append(None)
                    else:
                        row_data.append(val)
                
                batch.append(row_data)
                
                if len(batch) >= batch_size:
                    cursor.executemany(insert_sql, batch)
                    total_rows += len(batch)
                    batch = []
                    
            if batch:
                cursor.executemany(insert_sql, batch)
                total_rows += len(batch)
                
            conn.commit()
            return total_rows, schema
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def format_table(headers, rows):
    """Format and print query results nicely."""
    if not rows:
        return "No results."
        
    # Get max width of each column
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            col_widths[i] = max(col_widths[i], len(val_str))
            
    # Print header
    header_str = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    separator = "-+-".join("-" * w for w in col_widths)
    
    output = [header_str, separator]
    for row in rows:
        row_str = " | ".join(f"{str(val) if val is not None else 'NULL':<{w}}" for val, w in zip(row, col_widths))
        output.append(row_str)
        
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Convert CSV files to SQLite databases and query them.")
    parser.add_argument('csv_file', help="Path to CSV file")
    parser.add_argument('db_file', nargs='?', help="Path to SQLite output file (default: csv_filename.sqlite)")
    parser.add_argument('-t', '--table', help="SQLite table name (default: csv_filename)")
    parser.add_argument('-d', '--delimiter', default=',', help="CSV delimiter (default: ',')")
    parser.add_argument('-e', '--encoding', default='utf-8', help="File encoding (default: 'utf-8')")
    parser.add_argument('-q', '--query', help="Run a custom SQL query on the database after import and display results")

    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        print(f"Error: CSV file '{args.csv_file}' not found.", file=sys.stderr)
        sys.exit(1)

    # Resolve default paths
    csv_base = os.path.splitext(os.path.basename(args.csv_file))[0]
    db_file = args.db_file if args.db_file else f"{csv_base}.sqlite"
    table_name = args.table if args.table else csv_base
    
    # Normalize table name (replace spaces/dashes with underscores)
    table_name = "".join([c if c.isalnum() else "_" for c in table_name])

    print(f"Converting '{args.csv_file}' to SQLite table '{table_name}' in '{db_file}'...")
    
    try:
        rows_imported, schema = convert_csv_to_sqlite(
            args.csv_file, db_file, table_name, args.delimiter, args.encoding
        )
        print(f"Success! Imported {rows_imported} rows.")
        print("\nInferred Schema:")
        for name, dtype in schema:
            print(f"  - {name}: {dtype}")
            
    except Exception as e:
        print(f"Error during database conversion: {e}", file=sys.stderr)
        sys.exit(1)

    # Run query if requested
    if args.query:
        print(f"\nRunning query: {args.query}")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(args.query)
            headers = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            print("\n" + format_table(headers, rows))
            conn.close()
        except Exception as e:
            print(f"Error running query: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
