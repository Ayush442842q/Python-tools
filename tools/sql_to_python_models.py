#!/usr/bin/env python3
"""
SQL-to-Python Models Generator
A standalone utility that parses SQL DDL schemas (CREATE TABLE statements)
and generates Python model code for SQLAlchemy, Django, Pydantic (v2), or Dataclasses.
"""

import argparse
import re
import sys

# SQL type mapping to Python types and package-specific field classes
TYPE_MAPPING = {
    # Text types
    "varchar": {"py": "str", "sqla": "String", "django": "CharField", "needs_len": True},
    "char": {"py": "str", "sqla": "String", "django": "CharField", "needs_len": True},
    "text": {"py": "str", "sqla": "Text", "django": "TextField"},
    "ntext": {"py": "str", "sqla": "Text", "django": "TextField"},
    "json": {"py": "dict", "sqla": "JSON", "django": "JSONField"},
    "jsonb": {"py": "dict", "sqla": "JSON", "django": "JSONField"},
    
    # Integer types
    "int": {"py": "int", "sqla": "Integer", "django": "IntegerField"},
    "integer": {"py": "int", "sqla": "Integer", "django": "IntegerField"},
    "smallint": {"py": "int", "sqla": "SmallInteger", "django": "SmallIntegerField"},
    "bigint": {"py": "int", "sqla": "BigInteger", "django": "BigIntegerField"},
    "serial": {"py": "int", "sqla": "Integer", "django": "AutoField"},
    "bigserial": {"py": "int", "sqla": "BigInteger", "django": "BigAutoField"},
    
    # Numeric/Float types
    "numeric": {"py": "Decimal", "sqla": "Numeric", "django": "DecimalField", "needs_prec": True},
    "decimal": {"py": "Decimal", "sqla": "Numeric", "django": "DecimalField", "needs_prec": True},
    "float": {"py": "float", "sqla": "Float", "django": "FloatField"},
    "double": {"py": "float", "sqla": "Float", "django": "FloatField"},
    "real": {"py": "float", "sqla": "Float", "django": "FloatField"},
    
    # Date/Time types
    "date": {"py": "date", "sqla": "Date", "django": "DateField"},
    "time": {"py": "time", "sqla": "Time", "django": "TimeField"},
    "timestamp": {"py": "datetime", "sqla": "DateTime", "django": "DateTimeField"},
    "datetime": {"py": "datetime", "sqla": "DateTime", "django": "DateTimeField"},
    "datetime2": {"py": "datetime", "sqla": "DateTime", "django": "DateTimeField"},
    
    # Boolean
    "bool": {"py": "bool", "sqla": "Boolean", "django": "BooleanField"},
    "boolean": {"py": "bool", "sqla": "Boolean", "django": "BooleanField"},
    "tinyint": {"py": "int", "sqla": "Integer", "django": "IntegerField"}, # often used as bool
    
    # Binary
    "blob": {"py": "bytes", "sqla": "LargeBinary", "django": "BinaryField"},
    "bytea": {"py": "bytes", "sqla": "LargeBinary", "django": "BinaryField"},
    "binary": {"py": "bytes", "sqla": "LargeBinary", "django": "BinaryField"},
    "varbinary": {"py": "bytes", "sqla": "LargeBinary", "django": "BinaryField"},
}


def clean_sql(sql):
    """Remove comments and format lines."""
    # Remove single line comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    # Remove multiline comments
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # Compact spaces
    sql = re.sub(r'\s+', ' ', sql)
    return sql


def parse_create_tables(sql_content):
    """
    Parses CREATE TABLE statements from SQL.
    Returns a list of table definitions.
    """
    cleaned = clean_sql(sql_content)
    
    # Find all CREATE TABLE statements (case-insensitive)
    # Match: CREATE TABLE [IF NOT EXISTS] name ( body )
    table_matches = re.finditer(
        r'create\s+table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z0-9_\"`\.]+)\s*\((.*?)\)(?=\s*(?:;|$|create\s+table))',
        cleaned,
        re.IGNORECASE
    )

    tables = []

    for match in table_matches:
        raw_name = match.group(1)
        # Strip quotes and schema qualifiers
        table_name = raw_name.strip('"` ').split('.')[-1]
        body = match.group(2).strip()

        # Split columns by comma, but ignore commas within parentheses e.g. VARCHAR(255, 2) or DECIMAL(10, 2)
        columns_raw = []
        current_col = []
        paren_depth = 0

        for char in body:
            if char == '(':
                paren_depth += 1
                current_col.append(char)
            elif char == ')':
                paren_depth -= 1
                current_col.append(char)
            elif char == ',' and paren_depth == 0:
                columns_raw.append("".join(current_col).strip())
                current_col = []
            else:
                current_col.append(char)
        if current_col:
            columns_raw.append("".join(current_col).strip())

        parsed_columns = []
        table_constraints = []

        for col_str in columns_raw:
            if not col_str:
                continue

            # Check if this is a table constraint rather than a column (e.g. PRIMARY KEY (col), CONSTRAINT, UNIQUE, FOREIGN KEY)
            col_upper = col_str.upper()
            if col_upper.startswith("PRIMARY KEY") or col_upper.startswith("CONSTRAINT") or col_upper.startswith("FOREIGN KEY") or col_upper.startswith("UNIQUE") or col_upper.startswith("KEY"):
                table_constraints.append(col_str)
                continue

            # Parse column definition: Name Type [Constraints]
            # Match word, then type (optionally with parentheses), then trailing options
            col_match = re.match(r'^([a-zA-Z0-9_\"`]+)\s+([a-zA-Z0-9_]+(?:\s*\([^)]+\))?)(.*)$', col_str, re.IGNORECASE)
            if not col_match:
                continue

            c_name = col_match.group(1).strip('"` ')
            c_type_raw = col_match.group(2).strip().lower()
            c_opts = col_match.group(3).strip().upper()

            # Separate type name and length/precision params
            type_name_match = re.match(r'^([a-zA-Z0-9_]+)(?:\s*\(([^)]+)\))?', c_type_raw)
            type_name = type_name_match.group(1)
            type_args = type_name_match.group(2) if type_name_match.group(2) else ""

            # Check constraints
            is_pk = "PRIMARY KEY" in c_opts
            is_nullable = "NOT NULL" not in c_opts
            default_val = None
            default_match = re.search(r'DEFAULT\s+([^ ]+)', c_opts)
            if default_match:
                default_val = default_match.group(1).strip("'\" ")

            parsed_columns.append({
                "name": c_name,
                "type_name": type_name,
                "type_args": type_args,
                "is_primary": is_pk,
                "is_nullable": is_nullable,
                "default": default_val
            })

        # Retrofit primary keys from table constraints if found
        for const in table_constraints:
            const_upper = const.upper()
            if "PRIMARY KEY" in const_upper:
                # Extract columns in parens
                pk_cols_match = re.search(r'\(([^)]+)\)', const)
                if pk_cols_match:
                    pk_cols = [c.strip('"` ') for c in pk_cols_match.group(1).split(',')]
                    for col_info in parsed_columns:
                        if col_info["name"] in pk_cols:
                            col_info["is_primary"] = True

        tables.append({
            "name": table_name,
            "columns": parsed_columns
        })

    return tables


def to_camel_case(text):
    """Converts snake_case/table_name to CamelCase for class names."""
    return "".join(word.capitalize() for word in text.split('_'))


def generate_sqlalchemy(table):
    """Generate SQLAlchemy Model code."""
    class_name = to_camel_case(table["name"])
    lines = [
        f"class {class_name}(Base):",
        f"    __tablename__ = '{table['name']}'",
        ""
    ]
    for col in table["columns"]:
        t_info = TYPE_MAPPING.get(col["type_name"], {"py": "str", "sqla": "String"})
        sqla_type = t_info["sqla"]
        
        # Format types with params
        if t_info.get("needs_len") and col["type_args"]:
            sqla_type = f"{sqla_type}({col['type_args']})"
        elif t_info.get("needs_prec") and col["type_args"]:
            sqla_type = f"{sqla_type}({col['type_args']})"

        args = [sqla_type]
        if col["is_primary"]:
            args.append("primary_key=True")
        if not col["is_nullable"]:
            args.append("nullable=False")
        if col["default"]:
            args.append(f"default={col['default']}")

        lines.append(f"    {col['name']} = Column({', '.join(args)})")
    
    return "\n".join(lines)


def generate_django(table):
    """Generate Django Model code."""
    class_name = to_camel_case(table["name"])
    lines = [
        f"class {class_name}(models.Model):",
    ]
    for col in table["columns"]:
        t_info = TYPE_MAPPING.get(col["type_name"], {"py": "str", "django": "TextField"})
        dj_field = t_info["django"]

        args = []
        if col["is_primary"]:
            args.append("primary_key=True")
        
        # CharField needs max_length
        if dj_field == "CharField":
            max_len = col["type_args"] if col["type_args"] else "255"
            args.append(f"max_length={max_len}")
        
        # DecimalField needs max_digits and decimal_places
        if dj_field == "DecimalField":
            if col["type_args"] and "," in col["type_args"]:
                parts = col["type_args"].split(",")
                args.append(f"max_digits={parts[0].strip()}")
                args.append(f"decimal_places={parts[1].strip()}")
            else:
                args.append("max_digits=10")
                args.append("decimal_places=2")

        if col["is_nullable"]:
            args.append("null=True")
            args.append("blank=True")
        if col["default"]:
            # handle quotes
            val = col["default"]
            if t_info["py"] == "str" and not val.startswith("'"):
                val = f"'{val}'"
            args.append(f"default={val}")

        lines.append(f"    {col['name']} = models.{dj_field}({', '.join(args)})")

    lines.extend([
        "",
        "    class Meta:",
        f"        db_table = '{table['name']}'"
    ])
    return "\n".join(lines)


def generate_pydantic(table):
    """Generate Pydantic v2 Schema code."""
    class_name = to_camel_case(table["name"])
    lines = [
        f"class {class_name}(BaseModel):"
    ]
    
    # Imports tracking
    needs_datetime = False
    needs_decimal = False
    needs_date = False
    needs_time = False

    for col in table["columns"]:
        t_info = TYPE_MAPPING.get(col["type_name"], {"py": "str"})
        py_type = t_info["py"]
        
        if py_type == "datetime":
            py_type = "datetime"
            needs_datetime = True
        elif py_type == "Decimal":
            py_type = "Decimal"
            needs_decimal = True
        elif py_type == "date":
            py_type = "date"
            needs_date = True
        elif py_type == "time":
            py_type = "time"
            needs_time = True

        # Handle nullability
        if col["is_nullable"]:
            py_type = f"Optional[{py_type}]"
            default_expr = " = None"
        else:
            default_expr = ""

        if col["default"]:
            val = col["default"]
            if t_info["py"] == "str" and not (val.startswith("'") or val.startswith('"')):
                val = f"'{val}'"
            default_expr = f" = {val}"

        lines.append(f"    {col['name']}: {py_type}{default_expr}")

    # Build header metadata to show what to import
    imports = []
    if needs_datetime or needs_date or needs_time:
        imp_parts = []
        if needs_datetime: imp_parts.append("datetime")
        if needs_date: imp_parts.append("date")
        if needs_time: imp_parts.append("time")
        imports.append(f"from datetime import {', '.join(imp_parts)}")
    if needs_decimal:
        imports.append("from decimal import Decimal")
    
    return {"imports": imports, "code": "\n".join(lines)}


def generate_dataclass(table):
    """Generate Python standard dataclass code."""
    class_name = to_camel_case(table["name"])
    lines = [
        "@dataclass",
        f"class {class_name}:"
    ]
    
    needs_datetime = False
    needs_decimal = False
    needs_date = False
    needs_time = False

    for col in table["columns"]:
        t_info = TYPE_MAPPING.get(col["type_name"], {"py": "str"})
        py_type = t_info["py"]

        if py_type == "datetime":
            needs_datetime = True
        elif py_type == "Decimal":
            needs_decimal = True
        elif py_type == "date":
            needs_date = True
        elif py_type == "time":
            needs_time = True

        if col["is_nullable"]:
            py_type = f"Optional[{py_type}]"
            default_expr = " = None"
        else:
            default_expr = ""

        if col["default"]:
            val = col["default"]
            if t_info["py"] == "str" and not (val.startswith("'") or val.startswith('"')):
                val = f"'{val}'"
            default_expr = f" = {val}"

        lines.append(f"    {col['name']}: {py_type}{default_expr}")

    imports = []
    if needs_datetime or needs_date or needs_time:
        imp_parts = []
        if needs_datetime: imp_parts.append("datetime")
        if needs_date: imp_parts.append("date")
        if needs_time: imp_parts.append("time")
        imports.append(f"from datetime import {', '.join(imp_parts)}")
    if needs_decimal:
        imports.append("from decimal import Decimal")

    return {"imports": imports, "code": "\n".join(lines)}


def main():
    parser = argparse.ArgumentParser(
        description="Convert SQL CREATE TABLE DDL commands into Python ORM models and dataclasses."
    )
    parser.add_argument("sql_file", nargs="?", help="Path to SQL DDL file. If omitted, reads from stdin.")
    parser.add_argument(
        "-t", "--target",
        choices=["sqlalchemy", "django", "pydantic", "dataclass"],
        default="sqlalchemy",
        help="Target Python model framework format. Default: sqlalchemy"
    )
    parser.add_argument("-o", "--output", help="Output file path. Defaults to stdout.")

    args = parser.parse_args()

    # Read SQL content
    if args.sql_file:
        try:
            with open(args.sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
        except Exception as e:
            print(f"Error reading SQL file: {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("No input SQL file specified. Paste SQL CREATE TABLE statements below, then press Ctrl+D (or Ctrl+Z on Windows) to convert:")
        sql_content = sys.stdin.read()

    if not sql_content.strip():
        print("Error: Input SQL content is empty.", file=sys.stderr)
        return 1

    tables = parse_create_tables(sql_content)

    if not tables:
        print("No CREATE TABLE statements parsed. Check your SQL syntax.", file=sys.stderr)
        return 1

    output_lines = []

    # Print target-specific imports
    if args.target == "sqlalchemy":
        output_lines.extend([
            "from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Time, Numeric, Float, JSON, LargeBinary",
            "from sqlalchemy.orm import declarative_base",
            "",
            "Base = declarative_base()",
            ""
        ])
        for t in tables:
            output_lines.append(generate_sqlalchemy(t))
            output_lines.append("\n")

    elif args.target == "django":
        output_lines.extend([
            "from django.db import models",
            ""
        ])
        for t in tables:
            output_lines.append(generate_django(t))
            output_lines.append("\n")

    elif args.target == "pydantic":
        # We need to collect imports across all tables
        all_imports = {"from pydantic import BaseModel", "from typing import Optional"}
        codes = []
        for t in tables:
            res = generate_pydantic(t)
            all_imports.update(res["imports"])
            codes.append(res["code"])

        output_lines.extend(sorted(list(all_imports)))
        output_lines.append("")
        for code in codes:
            output_lines.append(code)
            output_lines.append("\n")

    elif args.target == "dataclass":
        all_imports = {"from dataclasses import dataclass", "from typing import Optional"}
        codes = []
        for t in tables:
            res = generate_dataclass(t)
            all_imports.update(res["imports"])
            codes.append(res["code"])

        output_lines.extend(sorted(list(all_imports)))
        output_lines.append("")
        for code in codes:
            output_lines.append(code)
            output_lines.append("\n")

    output_str = "\n".join(output_lines)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"Generated Python models saved to: {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print("\nGenerated Models:")
        print("=" * 40)
        print(output_str)
        print("=" * 40)

    return 0


if __name__ == "__main__":
    sys.exit(main())
