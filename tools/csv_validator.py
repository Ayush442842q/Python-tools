#!/usr/bin/env python3
"""
CSV Validator - A standalone tool to validate CSV file structure and data integrity.

Supports verifying column counts, checking data types (int, float, date, email, url, bool),
and identifying malformed rows.
"""

import sys
import csv
import re
import argparse
from datetime import datetime
from pathlib import Path

# Common regular expressions for validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
URL_REGEX = re.compile(r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?$')
DATE_FORMATS = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d']

def is_email(val):
    return bool(EMAIL_REGEX.match(val))

def is_url(val):
    return bool(URL_REGEX.match(val))

def is_int(val):
    try:
        int(val)
        return True
    except ValueError:
        return False

def is_float(val):
    try:
        float(val)
        return True
    except ValueError:
        return False

def is_bool(val):
    return val.lower() in ('true', 'false', '1', '0', 'yes', 'no', 'y', 'n')

def is_date(val):
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(val, fmt)
            return True
        except ValueError:
            pass
    return False

# Mapping from string schema definitions to validator functions
VALIDATORS = {
    'int': (is_int, "Integer"),
    'float': (is_float, "Float/Decimal"),
    'email': (is_email, "Email Address"),
    'url': (is_url, "URL"),
    'date': (is_date, "Date (e.g. YYYY-MM-DD)"),
    'bool': (is_bool, "Boolean (true/false/1/0)"),
    'str': (lambda x: True, "String/Any")
}

def parse_schema(schema_str):
    """
    Parses a schema string like "id:int,name:str,email:email,signup_date:date"
    Returns a dictionary of {column_name: type_key}
    """
    if not schema_str:
        return None
    
    schema = {}
    parts = schema_str.split(',')
    for part in parts:
        if ':' not in part:
            print(f"Warning: Invalid schema format for section '{part}'. Expected 'column_name:type'")
            continue
        col_name, col_type = part.split(':', 1)
        col_name = col_name.strip()
        col_type = col_type.strip().lower()
        if col_type not in VALIDATORS:
            print(f"Warning: Unknown validation type '{col_type}'. Falling back to 'str'.")
            col_type = 'str'
        schema[col_name] = col_type
    return schema

def validate_csv(filepath, schema=None, delimiter=',', quotechar='"', strict=False):
    errors = []
    row_count = 0
    valid_count = 0
    header = None
    column_count = 0
    
    try:
        with open(filepath, 'r', newline='', encoding='utf-8', errors='replace') as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
            
            # Read header
            try:
                header = next(reader)
                row_count += 1
                column_count = len(header)
                if not header:
                    errors.append((1, "Empty CSV file or invalid header row"))
                    return errors, row_count, valid_count, column_count
            except StopIteration:
                errors.append((0, "File is completely empty"))
                return errors, row_count, valid_count, column_count
            
            # Match schema columns to indices
            schema_indices = {}
            if schema:
                for col_name, col_type in schema.items():
                    if col_name in header:
                        schema_indices[header.index(col_name)] = (col_name, col_type)
                    else:
                        print(f"Warning: Schema column '{col_name}' not found in CSV headers.")
            
            # Read data rows
            for line_no, row in enumerate(reader, start=2):
                row_count += 1
                row_errors = []
                
                # 1. Check column count
                if len(row) != column_count:
                    msg = f"Column count mismatch. Expected {column_count} fields, got {len(row)}"
                    row_errors.append(msg)
                    if strict:
                        errors.append((line_no, msg))
                        continue
                
                # 2. Check data types against schema
                if schema:
                    for idx, val in enumerate(row):
                        if idx in schema_indices:
                            col_name, col_type = schema_indices[idx]
                            val_stripped = val.strip()
                            if val_stripped == "":
                                # Skip empty values (optional: could add required/nullable support)
                                continue
                            
                            validator, type_desc = VALIDATORS[col_type]
                            if not validator(val_stripped):
                                row_errors.append(
                                    f"Value '{val}' in column '{col_name}' is not a valid {type_desc}"
                                )
                
                if row_errors:
                    for err in row_errors:
                        errors.append((line_no, err))
                else:
                    valid_count += 1
                    
    except Exception as e:
        errors.append((0, f"Critical reader failure: {str(e)}"))
        
    return errors, row_count - 1, valid_count, column_count

def main():
    parser = argparse.ArgumentParser(
        description="CSV Validator - Check structure and validation rules for CSV files."
    )
    parser.add_argument("file", help="Path to the CSV file to validate")
    parser.add_argument(
        "-d", "--delimiter", default=",",
        help="Delimiter character (default: ',')"
    )
    parser.add_argument(
        "-q", "--quotechar", default='"',
        help="Quote character (default: '\"')"
    )
    parser.add_argument(
        "-s", "--schema", default=None,
        help="Schema validation definition. Format: 'column:type,column2:type' (Supported types: int, float, date, email, url, bool, str)"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Strict mode: Stop processing row values on column count mismatch"
    )
    parser.add_argument(
        "--max-errors", type=int, default=50,
        help="Maximum errors to display (default: 50)"
    )
    
    args = parser.parse_args()
    
    csv_path = Path(args.file)
    if not csv_path.is_file():
        print(f"Error: File '{args.file}' does not exist.")
        sys.exit(1)
        
    schema = parse_schema(args.schema)
    
    print(f"Analyzing: {csv_path.name}")
    print(f"Delimiter: '{args.delimiter}' | Quotechar: '{args.quotechar}'")
    if schema:
        print("Schema loaded:")
        for col, type_key in schema.items():
            print(f"  - {col}: {VALIDATORS[type_key][1]}")
    print("=" * 60)
    
    errors, total_rows, valid_rows, cols = validate_csv(
        csv_path, schema=schema, delimiter=args.delimiter, quotechar=args.quotechar, strict=args.strict
    )
    
    # Report results
    if not errors:
        print("\033[92m[OK] Validation Passed Successfully!\033[0m")
        print(f"Total Columns: {cols}")
        print(f"Total Data Rows: {total_rows}")
        print(f"Valid Rows: {valid_rows}")
    else:
        print(f"\033[91m[FAIL] Validation Failed with {len(errors)} error(s).\033[0m")
        print(f"Total Columns: {cols}")
        print(f"Total Data Rows: {total_rows}")
        print(f"Valid Rows: {valid_rows} | Invalid Rows: {total_rows - valid_rows}")
        print("\nError Log:")
        print(f"{'Line':<8} | {'Details':<50}")
        print("-" * 60)
        for line_no, detail in errors[:args.max_errors]:
            line_str = f"Row {line_no}" if line_no > 0 else "System"
            print(f"{line_str:<8} | {detail}")
            
        if len(errors) > args.max_errors:
            print(f"\n... and {len(errors) - args.max_errors} more errors omitted.")
            
        sys.exit(1)

if __name__ == "__main__":
    main()
