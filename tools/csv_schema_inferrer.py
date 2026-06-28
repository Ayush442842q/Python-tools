#!/usr/bin/env python3
"""
CSV Schema Inferrer & Profile Generator

A CLI utility that scans a CSV file, sniffs its formatting dialect, analyzes
each column to infer data types (Integer, Float, Boolean, DateTime, String),
records statistics (null counts, uniqueness, min/max values, lengths), and
generates a ready-to-run SQL CREATE TABLE DDL statement and a JSON Schema.

Usage:
    python tools/csv_schema_inferrer.py -i data.csv
    python tools/csv_schema_inferrer.py -i data.csv --dialect sqlite --table-name users
"""

import argparse
import csv
from datetime import datetime
import json
import os
import re
import sys
from typing import Dict, Any, List, Tuple, Optional, Set

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Simple patterns for type checking
BOOL_TRUE_VALS = {"true", "yes", "1", "t", "y", "on"}
BOOL_FALSE_VALS = {"false", "no", "0", "f", "n", "off"}
NULL_VALS = {"", "null", "none", "nil", "na", "n/a", "nan"}

DATE_FORMATS = [
    "%Y-%m-%d",          # 2026-06-28
    "%Y-%m-%d %H:%M:%S", # 2026-06-28 15:30:00
    "%d/%m/%Y",          # 28/06/2026
    "%m/%d/%Y",          # 06/28/2026
    "%d-%b-%Y",          # 28-Jun-2026
    "%Y-%m-%dT%H:%M:%SZ" # ISO
]

class CsvColumnProfile:
    def __init__(self, name: str):
        self.name = name
        self.total_rows = 0
        self.null_count = 0
        
        # Types counts
        self.type_counts = {
            "integer": 0,
            "float": 0,
            "boolean": 0,
            "datetime": 0,
            "string": 0
        }
        
        # Values collections for stats
        self.unique_values: Set[str] = set()
        self.min_val: Optional[Any] = None
        self.max_val: Optional[Any] = None
        self.min_len: Optional[int] = None
        self.max_len: Optional[int] = None

    def feed_value(self, val_str: str):
        self.total_rows += 1
        cleaned = val_str.strip()
        
        if cleaned.lower() in NULL_VALS:
            self.null_count += 1
            return

        self.unique_values.add(cleaned)
        
        # Inferred type check
        inferred = self._check_type(cleaned)
        self.type_counts[inferred] += 1

        # Collect stats
        val_len = len(cleaned)
        if self.min_len is None or val_len < self.min_len:
            self.min_len = val_len
        if self.max_len is None or val_len > self.max_len:
            self.max_len = val_len

        # Try to parse for min/max comparisons
        parsed = self._try_parse(cleaned, inferred)
        if parsed is not None:
            if self.min_val is None or parsed < self.min_val:
                self.min_val = parsed
            if self.max_val is None or parsed > self.max_val:
                self.max_val = parsed

    def _check_type(self, val: str) -> str:
        # Check Boolean
        if val.lower() in BOOL_TRUE_VALS or val.lower() in BOOL_FALSE_VALS:
            return "boolean"
        
        # Check Integer
        if re.match(r"^[-+]?\d+$", val):
            return "integer"
            
        # Check Float
        if re.match(r"^[-+]?\d*\.\d+$", val) or re.match(r"^[-+]?\d+\.\d*$", val):
            return "float"

        # Check DateTime
        for fmt in DATE_FORMATS:
            try:
                datetime.strptime(val, fmt)
                return "datetime"
            except ValueError:
                continue
                
        return "string"

    def _try_parse(self, val: str, type_str: str) -> Optional[Any]:
        if type_str == "integer":
            return int(val)
        if type_str == "float":
            return float(val)
        if type_str == "boolean":
            return val.lower() in BOOL_TRUE_VALS
        if type_str == "datetime":
            for fmt in DATE_FORMATS:
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue
        return val

    def get_final_type(self) -> str:
        """Determines final type by finding majority type, checking for fallback promotion."""
        non_null_rows = self.total_rows - self.null_count
        if non_null_rows == 0:
            return "string"  # Default fallback if all nulls

        # Find types that actually occurred
        active_types = {k: v for k, v in self.type_counts.items() if v > 0}
        
        # If any string exists, it propagates up to string
        if "string" in active_types:
            return "string"

        # Float forces integers/booleans to float
        if "float" in active_types:
            return "float"

        # Datetime remains datetime unless strings exist
        if "datetime" in active_types:
            if len(active_types) == 1:
                return "datetime"
            return "string"

        if "integer" in active_types:
            return "integer"

        if "boolean" in active_types:
            return "boolean"

        return "string"

class CsvSchemaInferrer:
    def __init__(self, table_name: str = "imported_table"):
        self.table_name = table_name
        self.columns: List[CsvColumnProfile] = []

    def analyze_file(self, file_path: str) -> bool:
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                # Sniff dialect
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    # Fallback to standard comma
                    dialect = csv.excel
                
                reader = csv.reader(f, dialect)
                headers = next(reader, None)
                if not headers:
                    return False

                # Clean headers and instantiate profiles
                clean_headers = []
                for i, h in enumerate(headers):
                    name = h.strip()
                    if not name:
                        name = f"column_{i}"
                    # Remove SQL-unfriendly characters
                    name = re.sub(r"[^\w]", "_", name).lower()
                    clean_headers.append(name)

                self.columns = [CsvColumnProfile(h) for h in clean_headers]

                # Feed rows
                for row in reader:
                    if not row:
                        continue
                    for col_idx, val in enumerate(row):
                        if col_idx < len(self.columns):
                            self.columns[col_idx].feed_value(val)
            return True
        except Exception as e:
            print(color_text(f"Error reading CSV file: {e}", COLOR_RED), file=sys.stderr)
            return False

    def generate_sql_ddl(self, dialect: str = "sqlite") -> str:
        dialect = dialect.lower()
        sql = [f"CREATE TABLE {self.table_name} ("]
        col_definitions = []

        for col in self.columns:
            final_type = col.get_final_type()
            
            # Map type to SQL dialect types
            sql_type = "TEXT"
            if final_type == "integer":
                sql_type = "INTEGER" if dialect in ("sqlite", "postgresql") else "INT"
            elif final_type == "float":
                sql_type = "REAL" if dialect == "sqlite" else ("DOUBLE PRECISION" if dialect == "postgresql" else "DOUBLE")
            elif final_type == "boolean":
                sql_type = "INTEGER" if dialect == "sqlite" else ("BOOLEAN" if dialect == "postgresql" else "TINYINT(1)")
            elif final_type == "datetime":
                sql_type = "TEXT" if dialect == "sqlite" else "TIMESTAMP"

            nullability = "" if col.null_count > 0 else " NOT NULL"
            
            # If unique (excluding nulls) and has enough values
            uniqueness = ""
            non_nulls = col.total_rows - col.null_count
            if non_nulls > 0 and len(col.unique_values) == non_nulls and len(col.unique_values) > 1:
                uniqueness = " UNIQUE"

            col_definitions.append(f"    {col.name} {sql_type}{nullability}{uniqueness}")

        sql.append(",\n".join(col_definitions))
        sql.append(");")
        return "\n".join(sql)

    def generate_json_schema(self) -> str:
        properties = {}
        required = []

        for col in self.columns:
            final_type = col.get_final_type()
            
            # Map type to JSON Schema types
            json_type = "string"
            if final_type == "integer":
                json_type = "integer"
            elif final_type == "float":
                json_type = "number"
            elif final_type == "boolean":
                json_type = "boolean"
            elif final_type == "datetime":
                json_type = "string"

            col_schema = {"type": json_type}
            if final_type == "datetime":
                col_schema["format"] = "date-time"

            if col.null_count > 0:
                col_schema["type"] = [json_type, "null"]
            else:
                required.append(col.name)

            properties[col.name] = col_schema

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": self.table_name,
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required

        return json.dumps(schema, indent=2)

def main():
    parser = argparse.ArgumentParser(description="CSV Schema Inferrer & Profile Generator")
    parser.add_argument("-i", "--input", required=True, help="Path to input CSV file")
    parser.add_argument("-t", "--table-name", default="csv_data", help="Table name for SQL/JSON output [default: csv_data]")
    parser.add_argument("-d", "--dialect", choices=["sqlite", "postgresql", "mysql"], default="sqlite", help="SQL dialect target [default: sqlite]")
    
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(color_text(f"Error: File '{args.input}' does not exist.", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    inferrer = CsvSchemaInferrer(table_name=args.table_name)
    if not inferrer.analyze_file(args.input):
        sys.exit(1)

    # Print Summary Table
    print(color_text(f"\n{COLOR_BOLD}=== CSV Profile & Analysis Summary ==={COLOR_RESET}", COLOR_CYAN))
    
    header = f"{'Column Name':<20} | {'Inferred Type':<13} | {'Nulls (%)':<10} | {'Unique Count':<12} | {'Min/MinLen':<12} | {'Max/MaxLen':<12}"
    print(header)
    print("-" * len(header))

    for col in inferrer.columns:
        final_type = col.get_final_type()
        
        null_pct = (col.null_count / col.total_rows * 100) if col.total_rows > 0 else 0.0
        nulls_str = f"{col.null_count} ({null_pct:.1f}%)"
        
        min_repr = str(col.min_val) if col.min_val is not None else ""
        max_repr = str(col.max_val) if col.max_val is not None else ""
        
        # If it's a string, display min/max length instead of values
        if final_type == "string":
            min_repr = f"len={col.min_len}" if col.min_len is not None else ""
            max_repr = f"len={col.max_len}" if col.max_len is not None else ""
        elif isinstance(col.min_val, datetime):
            min_repr = col.min_val.strftime("%Y-%m-%d")
            max_repr = col.max_val.strftime("%Y-%m-%d")

        print(f"{col.name:<20} | {final_type:<13} | {nulls_str:<10} | {len(col.unique_values):<12} | {min_repr:<12} | {max_repr:<12}")

    print(color_text(f"\n{COLOR_BOLD}=== Autogenerated SQL DDL ({args.dialect}) ==={COLOR_RESET}", COLOR_CYAN))
    print(inferrer.generate_sql_ddl(dialect=args.dialect))

    print(color_text(f"\n{COLOR_BOLD}=== Autogenerated JSON Schema ==={COLOR_RESET}", COLOR_CYAN))
    print(inferrer.generate_json_schema())
    print()

if __name__ == "__main__":
    main()
