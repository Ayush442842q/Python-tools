#!/usr/bin/env python3
"""
SQL SELECT Query Mock Data Generator
Parses a SQL SELECT query and dynamically generates a mock dataset matching columns and WHERE conditions.
"""

import argparse
import csv
import json
import random
import re
import sys
from typing import List, Dict, Any, Tuple

# Sample data pools for realistic generation
NAMES = ["John Doe", "Jane Smith", "Alice Johnson", "Bob Brown", "Charlie Green", "David White", "Emma Black", "Frank Miller"]
EMAILS = ["john.doe@example.com", "jane.smith@example.net", "alice.j@test.org", "bob.b@mail.com", "charlie@company.com"]
STATUSES = ["active", "inactive", "pending", "suspended", "completed"]
CATEGORIES = ["Electronics", "Clothing", "Home & Kitchen", "Books", "Sports", "Beauty"]

def parse_sql_query(query: str) -> Tuple[List[str], Dict[str, Any], str]:
    """
    Statically parses basic features from a SQL query: columns, table, and WHERE conditions.
    """
    # Normalize spaces and casing
    query = " ".join(query.split()).strip()
    
    # 1. Extract columns
    select_match = re.match(r'^SELECT\s+(.*?)\s+FROM\s+(.*?)(?:\s+WHERE\s+(.*))?$', query, re.IGNORECASE)
    if not select_match:
        raise ValueError("Unsupported SQL format. Must be a standard SELECT query.")

    cols_raw = select_match.group(1).strip()
    table_name = select_match.group(2).strip().split()[0] # get table name, ignoring aliases
    where_raw = select_match.group(3)

    # Parse columns list, handling wildcards
    columns = []
    if cols_raw == "*":
        # Default columns if wildcard
        columns = ["id", "name", "email", "age", "status", "created_at"]
    else:
        for c in cols_raw.split(','):
            c = c.strip()
            # Handle aliases: e.g. "user_name AS name" or "user_name name"
            parts = re.split(r'\s+as\s+|\s+', c, flags=re.IGNORECASE)
            columns.append(parts[-1].strip('`"\'[]'))

    # 2. Parse WHERE conditions
    constraints: Dict[str, Any] = {}
    if where_raw:
        # Split by logical AND
        conditions = re.split(r'\s+AND\s+', where_raw, flags=re.IGNORECASE)
        for cond in conditions:
            cond = cond.strip()
            # Support equal (=)
            eq_match = re.match(r'^([\w\.]+)\s*=\s*(.*)$', cond)
            if eq_match:
                col = eq_match.group(1).strip().split('.')[-1]
                val = eq_match.group(2).strip().strip("'\"")
                constraints[col] = {"op": "=", "val": val}
                continue
            
            # Support inequality (> / <)
            ineq_match = re.match(r'^([\w\.]+)\s*(>|<|>=|<=)\s*(.*)$', cond)
            if ineq_match:
                col = ineq_match.group(1).strip().split('.')[-1]
                op = ineq_match.group(2)
                val_raw = ineq_match.group(3).strip().strip("'\"")
                try:
                    val = float(val_raw) if '.' in val_raw else int(val_raw)
                except ValueError:
                    val = val_raw
                constraints[col] = {"op": op, "val": val}
                continue

            # Support IN clause
            in_match = re.match(r'^([\w\.]+)\s+IN\s*\((.*?)\)$', cond, re.IGNORECASE)
            if in_match:
                col = in_match.group(1).strip().split('.')[-1]
                vals = [v.strip().strip("'\"") for v in in_match.group(2).split(',')]
                constraints[col] = {"op": "IN", "val": vals}

    return columns, constraints, table_name

def generate_mock_row(columns: List[str], constraints: Dict[str, Any], row_id: int) -> Dict[str, Any]:
    row = {}
    for col in columns:
        col_lower = col.lower()
        
        # Check if column has a direct '=' constraint in WHERE clause
        if col in constraints and constraints[col]["op"] == "=":
            row[col] = constraints[col]["val"]
            continue

        # Check if column has an 'IN' constraint
        if col in constraints and constraints[col]["op"] == "IN":
            row[col] = random.choice(constraints[col]["val"])
            continue

        # Check for inequalities to bound values
        min_val = None
        max_val = None
        if col in constraints:
            c = constraints[col]
            if c["op"] == ">":
                min_val = c["val"] + 1
            elif c["op"] == ">=":
                min_val = c["val"]
            elif c["op"] == "<":
                max_val = c["val"] - 1
            elif c["op"] == "<=":
                max_val = c["val"]

        # Generate realistic data based on name heuristics
        if "id" in col_lower:
            row[col] = row_id
        elif "email" in col_lower:
            row[col] = f"user_{row_id}@" + random.choice(["example.com", "test.net", "company.com"])
        elif "name" in col_lower:
            row[col] = random.choice(NAMES)
        elif "age" in col_lower:
            start = int(min_val) if min_val is not None else 18
            end = int(max_val) if max_val is not None else 80
            row[col] = random.randint(max(0, start), max(start, end))
        elif "status" in col_lower:
            row[col] = random.choice(STATUSES)
        elif "category" in col_lower:
            row[col] = random.choice(CATEGORIES)
        elif "price" in col_lower or "amount" in col_lower or "total" in col_lower:
            start = float(min_val) if min_val is not None else 5.0
            end = float(max_val) if max_val is not None else 1000.0
            row[col] = round(random.uniform(start, end), 2)
        elif "date" in col_lower or "created_at" in col_lower or "updated_at" in col_lower:
            year = random.randint(2024, 2026)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            row[col] = f"{year}-{month:02d}-{day:02d}"
        else:
            # Fallback values
            if min_val is not None or max_val is not None:
                start = int(min_val) if min_val is not None else 1
                end = int(max_val) if max_val is not None else 100
                row[col] = random.randint(start, end)
            else:
                row[col] = f"val_{row_id}"

    return row

def format_sql_inserts(table: str, columns: List[str], rows: List[Dict[str, Any]]) -> str:
    statements = []
    col_str = ", ".join(columns)
    for r in rows:
        vals = []
        for col in columns:
            v = r[col]
            if isinstance(v, (int, float)):
                vals.append(str(v))
            elif v is None:
                vals.append("NULL")
            else:
                # Escape single quotes
                escaped = str(v).replace("'", "''")
                vals.append(f"'{escaped}'")
        val_str = ", ".join(vals)
        statements.append(f"INSERT INTO {table} ({col_str}) VALUES ({val_str});")
    return "\n".join(statements)

def main():
    parser = argparse.ArgumentParser(
        description="SQL SELECT Query Mock Data Generator - Generates mock dataset from SQL queries."
    )
    parser.add_argument("query", help="SQL SELECT query to generate mock data for")
    parser.add_argument("-r", "--rows", type=int, default=5, help="Number of rows to generate (default: 5)")
    parser.add_argument("-f", "--format", choices=["json", "csv", "sql"], default="json",
                        help="Output format (default: json)")
    parser.add_argument("-o", "--output", help="Path to write the output data")

    args = parser.parse_args()

    try:
        columns, constraints, table = parse_sql_query(args.query)
        
        # Generate rows
        mock_rows = []
        for idx in range(1, args.rows + 1):
            mock_rows.append(generate_mock_row(columns, constraints, idx))

        # Format output
        output_str = ""
        if args.format == "json":
            output_str = json.dumps(mock_rows, indent=2)
        elif args.format == "sql":
            output_str = format_sql_inserts(table, columns, mock_rows)
        elif args.format == "csv":
            # Write to temporary string IO
            import io
            f_out = io.StringIO()
            writer = csv.DictWriter(f_out, fieldnames=columns)
            writer.writeheader()
            writer.writerows(mock_rows)
            output_str = f_out.getvalue()

        # Write or display
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str + "\n")
            print(f"Mock data successfully written to: {args.output}")
        else:
            print(output_str)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
