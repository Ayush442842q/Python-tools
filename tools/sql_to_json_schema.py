#!/usr/bin/env python3
"""
SQL Schema to JSON Schema & Pydantic Converter
Parses SQL 'CREATE TABLE' statements and translates them into:
1. JSON Schema (Draft 7 / 2020-12 compatible)
2. Pydantic V2 class models
Supports SQLite, PostgreSQL, and MySQL data types, mapping constraints
like NOT NULL, DEFAULT, PRIMARY KEY, and FOREIGN KEY.
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Tuple

# Type mapping dictionary: SQL type keyword -> (JSON Schema type, Python type)
TYPE_MAPPING = {
    # Integers
    "INT": ("integer", "int"),
    "INTEGER": ("integer", "int"),
    "BIGINT": ("integer", "int"),
    "SMALLINT": ("integer", "int"),
    "TINYINT": ("integer", "int"),
    "SERIAL": ("integer", "int"),
    "BIGSERIAL": ("integer", "int"),
    
    # Decimals/Reals
    "REAL": ("number", "float"),
    "FLOAT": ("number", "float"),
    "DOUBLE": ("number", "float"),
    "DOUBLE PRECISION": ("number", "float"),
    "DECIMAL": ("number", "float"),
    "NUMERIC": ("number", "float"),
    
    # Strings
    "VARCHAR": ("string", "str"),
    "CHAR": ("string", "str"),
    "CHARACTER": ("string", "str"),
    "TEXT": ("string", "str"),
    "UUID": ("string", "str"),
    "CLOB": ("string", "str"),
    
    # Boolean
    "BOOL": ("boolean", "bool"),
    "BOOLEAN": ("boolean", "bool"),
    
    # Dates/Times
    "DATE": ("string", "str"),        # Can map to date format
    "DATETIME": ("string", "str"),    # Can map to date-time format
    "TIMESTAMP": ("string", "str"),   # Can map to date-time format
    
    # Binary
    "BLOB": ("string", "bytes"),
    "BINARY": ("string", "bytes"),
    "VARBINARY": ("string", "bytes"),
    "BYTEA": ("string", "bytes"),
}

class SQLColumn:
    def __init__(self, name: str, sql_type: str):
        self.name = name.strip('"`[] ')
        self.sql_type = sql_type.upper().strip()
        self.is_nullable = True
        self.is_primary_key = False
        self.default_value = None
        
        # Determine base types
        self.js_type, self.py_type = self._resolve_types()

    def _resolve_types(self) -> Tuple[str, str]:
        """Resolves SQL type to JSON Schema and Python types."""
        # Clean type (remove sizes e.g. VARCHAR(255) -> VARCHAR)
        base_type = re.sub(r'\(.*?\)', '', self.sql_type).strip()
        
        # Check direct mapping
        if base_type in TYPE_MAPPING:
            return TYPE_MAPPING[base_type]
            
        # Partial matching for types like TIMESTAMP WITH TIME ZONE
        for k, v in TYPE_MAPPING.items():
            if base_type.startswith(k):
                return v
                
        # Default fallback
        return "string", "str"

class SQLTableParser:
    def __init__(self, sql: str):
        self.sql = sql
        self.table_name = "Model"
        self.columns: List[SQLColumn] = []

    def parse(self) -> None:
        """Parses the CREATE TABLE statement using regular expressions."""
        # Clean SQL: remove comments and normalize spaces
        cleaned = re.sub(r'--.*$', '', self.sql, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Match Table Name
        table_match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_`"\[\]\.]+)', cleaned, re.IGNORECASE)
        if not table_match:
            raise ValueError("Could not find a valid 'CREATE TABLE' statement in input.")
        
        self.table_name = table_match.group(1).strip('"`[] ').split('.')[-1]
        
        # Extract body inside first '(' and last ')'
        body_match = re.search(r'\((.*)\)', cleaned)
        if not body_match:
            raise ValueError(f"Could not parse body of table '{self.table_name}'. Make sure it contains parenthesized column list.")
            
        body = body_match.group(1)
        
        # Parse items separated by commas, taking parentheses nesting into account
        items = []
        depth = 0
        current_item = []
        
        for char in body:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            
            if char == ',' and depth == 0:
                items.append("".join(current_item).strip())
                current_item = []
            else:
                current_item.append(char)
        if current_item:
            items.append("".join(current_item).strip())

        # Process each parsed column or constraint
        for item in items:
            # Skip table-level constraints for simple column-level matching (e.g. PRIMARY KEY (col1, col2))
            if re.match(r'^(?:CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|KEY|INDEX)\b', item, re.IGNORECASE):
                continue
                
            # Column pattern: name type [constraints]
            col_match = re.match(r'^([a-zA-Z0-9_`"\[\]]+)\s+([a-zA-Z0-9_]+(?:\s*\(.*?\))?)(.*)$', item, re.IGNORECASE)
            if not col_match:
                continue
                
            name, col_type, constraints_str = col_match.groups()
            column = SQLColumn(name, col_type)
            
            # Analyze constraints
            if re.search(r'\bNOT\s+NULL\b', constraints_str, re.IGNORECASE):
                column.is_nullable = False
            if re.search(r'\bPRIMARY\s+KEY\b', constraints_str, re.IGNORECASE):
                column.is_primary_key = True
                column.is_nullable = False  # Primary keys are inherently not null
                
            # Match default value
            def_match = re.search(r'\bDEFAULT\s+([^ ]+)', constraints_str, re.IGNORECASE)
            if def_match:
                val = def_match.group(1).strip("'\" ")
                if val.lower() != 'null':
                    column.default_value = val

            self.columns.append(column)

    def to_json_schema(self) -> Dict[str, Any]:
        """Generates JSON Schema definition."""
        properties = {}
        required = []
        
        for col in self.columns:
            prop = {"type": col.js_type}
            
            # Add description / details
            prop["description"] = f"SQL Type: {col.sql_type}"
            
            if col.default_value is not None:
                prop["default"] = col.default_value
                
            properties[col.name] = prop
            
            if not col.is_nullable:
                required.append(col.name)
                
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": self.table_name,
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required
            
        return schema

    def to_pydantic_code(self) -> str:
        """Generates Pydantic V2 Python class code."""
        # Convert table name to PascalCase
        class_name = "".join(w.capitalize() for w in re.split(r'[-_\s]+', self.table_name))
        
        lines = [
            "from pydantic import BaseModel, Field",
            "from typing import Optional",
            "",
            f"class {class_name}(BaseModel):",
        ]
        
        if not self.columns:
            lines.append("    pass")
            return "\n".join(lines)
            
        for col in self.columns:
            # Map type annotation
            type_annot = col.py_type
            if col.is_nullable:
                type_annot = f"Optional[{type_annot}]"
                
            # Define Field arguments
            field_args = []
            if col.default_value is not None:
                # Basic parsing of default values
                if col.py_type == "int":
                    field_args.append(f"default={int(col.default_value)}")
                elif col.py_type == "float":
                    field_args.append(f"default={float(col.default_value)}")
                elif col.py_type == "bool":
                    field_args.append(f"default={col.default_value.lower() == 'true'}")
                else:
                    field_args.append(f"default='{col.default_value}'")
            elif col.is_nullable:
                field_args.append("default=None")
                
            field_str = f" = Field({', '.join(field_args)})" if field_args else ""
            lines.append(f"    {col.name}: {type_annot}{field_str}")
            
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert SQL 'CREATE TABLE' statements to JSON Schema or Pydantic V2 models."
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Path to SQL file. Reads from standard input if omitted."
    )
    parser.add_argument(
        "-t", "--target",
        choices=["schema", "pydantic"],
        default="schema",
        help="Output target format: 'schema' for JSON Schema or 'pydantic' for Python Pydantic V2 code (default: schema)."
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Path to output file. Prints to stdout if omitted."
    )

    args = parser.parse_args()

    # Read SQL script
    try:
        sql = args.file.read().strip()
        if not sql:
            print("Error: Empty input SQL.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse SQL schema
    try:
        parser_inst = SQLTableParser(sql)
        parser_inst.parse()
    except ValueError as e:
        print(f"Parsing Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate output format
    if args.target == "schema":
        schema_dict = parser_inst.to_json_schema()
        output_str = json.dumps(schema_dict, indent=2, ensure_ascii=False)
    else:
        output_str = parser_inst.to_pydantic_code()

    # Output results
    args.output.write(output_str)
    if args.output != sys.stdout:
        print(f"Successfully generated {args.target} and saved to {args.output.name}")


if __name__ == "__main__":
    main()
