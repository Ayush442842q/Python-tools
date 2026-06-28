#!/usr/bin/env python3
"""
JSON Schema to SQL DDL Generator
Converts JSON Schema definitions (or raw JSON files by inferring schema) into SQL DDL commands
for SQLite, PostgreSQL, and MySQL. Supports automatic table extraction for nested objects/arrays.
"""

import os
import sys
import json
import argparse
import re

# Dialect configurations
DIALECTS = {
    "sqlite": {
        "primary_key": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "types": {
            "string": "TEXT",
            "integer": "INTEGER",
            "number": "REAL",
            "boolean": "INTEGER",  # SQLite uses 0/1 for booleans
            "object": "TEXT",     # Fallback to JSON text
            "array": "TEXT",      # Fallback to JSON text
            "any": "TEXT"
        },
        "quote": '"{}"'
    },
    "postgres": {
        "primary_key": "SERIAL PRIMARY KEY",
        "types": {
            "string": "VARCHAR(255)",
            "integer": "INTEGER",
            "number": "DOUBLE PRECISION",
            "boolean": "BOOLEAN",
            "object": "JSONB",
            "array": "JSONB",
            "any": "TEXT"
        },
        "quote": '"{}"'
    },
    "mysql": {
        "primary_key": "INT AUTO_INCREMENT PRIMARY KEY",
        "types": {
            "string": "VARCHAR(255)",
            "integer": "INT",
            "number": "DOUBLE",
            "boolean": "TINYINT(1)",
            "object": "JSON",
            "array": "JSON",
            "any": "TEXT"
        },
        "quote": "`{}`"
    }
}

class SQLSchemaGenerator:
    def __init__(self, dialect="sqlite", default_varchar_len=255, nested_strategy="relational"):
        self.dialect_name = dialect.lower()
        if self.dialect_name not in DIALECTS:
            self.dialect_name = "sqlite"
        self.config = DIALECTS[self.dialect_name]
        self.default_varchar_len = default_varchar_len
        self.nested_strategy = nested_strategy  # "relational" or "json"
        self.tables = {}  # table_name -> {columns, foreign_keys}

    def quote_identifier(self, identifier):
        return self.config["quote"].format(identifier)

    def sanitize_name(self, name):
        """Sanitize identifiers to be SQL compatible."""
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Avoid leading digits or double underscores
        if name and name[0].isdigit():
            name = f"col_{name}"
        return name.lower()

    def get_sql_type(self, schema_prop, name=""):
        """Map JSON schema type to SQL type."""
        js_type = schema_prop.get("type", "any")
        
        # Handle list of types (e.g. ["string", "null"])
        if isinstance(js_type, list):
            # Extract first non-null type, or fallback
            non_null_types = [t for t in js_type if t != "null"]
            js_type = non_null_types[0] if non_null_types else "any"

        # Specialized formats
        if js_type == "string":
            fmt = schema_prop.get("format", "")
            if fmt == "date-time":
                if self.dialect_name == "sqlite":
                    return "TEXT"
                elif self.dialect_name == "postgres":
                    return "TIMESTAMP WITH TIME ZONE"
                else:
                    return "DATETIME"
            elif fmt == "date":
                return "DATE"
            elif fmt == "uuid":
                if self.dialect_name == "postgres":
                    return "UUID"
                return "VARCHAR(36)"
            
            # String length limits
            max_len = schema_prop.get("maxLength")
            if max_len:
                return f"VARCHAR({max_len})"
            return f"VARCHAR({self.default_varchar_len})" if self.dialect_name != "sqlite" else "TEXT"

        return self.config["types"].get(js_type, self.config["types"]["any"])

    def process_schema(self, schema, table_name="main", parent_table=None, parent_pk=None):
        """Recursively traverse schema and generate table definitions."""
        table_name = self.sanitize_name(table_name)
        
        # Check if we already processed this table to avoid cycles
        if table_name in self.tables:
            return

        columns = {}
        foreign_keys = []
        
        # Add primary key
        pk_name = "id"
        columns[pk_name] = self.config["primary_key"]
        
        # Add parent foreign key if creating a sub-table relationally
        if parent_table and parent_pk:
            fk_col_name = f"{parent_table}_{parent_pk}"
            fk_col_name = self.sanitize_name(fk_col_name)
            
            # Sub-table foreign key has same type as parent PK (typically integer)
            columns[fk_col_name] = self.config["types"]["integer"]
            foreign_keys.append({
                "column": fk_col_name,
                "ref_table": parent_table,
                "ref_column": parent_pk
            })

        # Process properties
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            col_name = self.sanitize_name(prop_name)
            
            # Check nested types
            prop_type = prop_schema.get("type")
            if isinstance(prop_type, list):
                non_null_types = [t for t in prop_type if t != "null"]
                prop_type = non_null_types[0] if non_null_types else "any"

            # Object or array properties
            if prop_type == "object" and self.nested_strategy == "relational":
                # Create a 1-to-1 or 1-to-many relationship table
                sub_table_name = f"{table_name}_{col_name}"
                self.process_schema(prop_schema, table_name=sub_table_name, parent_table=table_name, parent_pk=pk_name)
                # Keep reference columns in this table optional or drop direct columns
                continue
            elif prop_type == "array" and self.nested_strategy == "relational":
                items_schema = prop_schema.get("items", {})
                items_type = items_schema.get("type")
                
                # If array contains objects, spin off a table
                if items_type == "object":
                    sub_table_name = f"{table_name}_{col_name}"
                    self.process_schema(items_schema, table_name=sub_table_name, parent_table=table_name, parent_pk=pk_name)
                else:
                    # Array of primitive values: make a simple value table
                    sub_table_name = f"{table_name}_{col_name}"
                    scalar_schema = {
                        "properties": {
                            "value": items_schema
                        },
                        "required": ["value"]
                    }
                    self.process_schema(scalar_schema, table_name=sub_table_name, parent_table=table_name, parent_pk=pk_name)
                continue

            # Standard column mapping
            sql_type = self.get_sql_type(prop_schema, name=col_name)
            constraints = []
            
            # NULL / NOT NULL constraints
            if prop_name in required:
                constraints.append("NOT NULL")
            else:
                # SQLite doesn't strictly need NULL, others allow it
                if self.dialect_name != "sqlite":
                    constraints.append("NULL")

            # Default values
            default_val = prop_schema.get("default")
            if default_val is not None:
                if isinstance(default_val, bool):
                    default_val_str = "1" if default_val else "0" if self.dialect_name == "sqlite" else str(default_val).upper()
                elif isinstance(default_val, (int, float)):
                    default_val_str = str(default_val)
                else:
                    default_val_str = f"'{default_val}'"
                constraints.append(f"DEFAULT {default_val_str}")

            columns[col_name] = f"{sql_type} {' '.join(constraints)}".strip()

        self.tables[table_name] = {
            "columns": columns,
            "foreign_keys": foreign_keys
        }

    def generate_ddl(self):
        """Construct SQL string for all tables."""
        ddl_output = []
        ddl_output.append(f"-- SQL Schema generated for {self.dialect_name.upper()}")
        ddl_output.append(f"-- Nested structure strategy: {self.nested_strategy.upper()}")
        ddl_output.append("")

        # Order tables: parents first, then children to handle foreign keys cleanly
        # We can do this by tracking foreign key dependencies
        resolved = []
        pending = list(self.tables.keys())
        
        while pending:
            progress = False
            for table_name in list(pending):
                deps = [fk["ref_table"] for fk in self.tables[table_name]["foreign_keys"]]
                # If all dependencies are already resolved, we can create this table
                if all(dep in resolved for dep in deps):
                    resolved.append(table_name)
                    pending.remove(table_name)
                    progress = True
            
            # If no progress and pending list is not empty, there is a cycle. Break it.
            if not progress and pending:
                resolved.extend(pending)
                break

        for table_name in resolved:
            table_info = self.tables[table_name]
            quoted_table = self.quote_identifier(table_name)
            
            table_ddl = []
            table_ddl.append(f"CREATE TABLE {quoted_table} (")
            
            # List columns
            col_lines = []
            for col_name, col_def in table_info["columns"].items():
                quoted_col = self.quote_identifier(col_name)
                col_lines.append(f"    {quoted_col} {col_def}")
                
            # List foreign keys
            for fk in table_info["foreign_keys"]:
                quoted_col = self.quote_identifier(fk["column"])
                quoted_ref_table = self.quote_identifier(fk["ref_table"])
                quoted_ref_col = self.quote_identifier(fk["ref_column"])
                
                # SQLite supports inline foreign keys. Others support constraints.
                if self.dialect_name == "mysql":
                    col_lines.append(f"    FOREIGN KEY ({quoted_col}) REFERENCES {quoted_ref_table}({quoted_ref_col}) ON DELETE CASCADE")
                else:
                    col_lines.append(f"    CONSTRAINT fk_{table_name}_{fk['column']} FOREIGN KEY ({quoted_col}) REFERENCES {quoted_ref_table}({quoted_ref_col}) ON DELETE CASCADE")

            table_ddl.append(",\n".join(col_lines))
            table_ddl.append(");")
            table_ddl.append("")
            
            # Create indexes on foreign keys
            for fk in table_info["foreign_keys"]:
                index_name = f"idx_{table_name}_{fk['column']}"
                quoted_idx = self.quote_identifier(index_name)
                quoted_col = self.quote_identifier(fk["column"])
                table_ddl.append(f"CREATE INDEX {quoted_idx} ON {quoted_table} ({quoted_col});")
            
            if table_info["foreign_keys"]:
                table_ddl.append("")

            ddl_output.append("\n".join(table_ddl))

        return "\n".join(ddl_output)

def infer_schema_from_json(data):
    """Dynamically infer a JSON Schema from a sample JSON data payload."""
    if isinstance(data, dict):
        properties = {}
        required = []
        for k, v in data.items():
            properties[k] = infer_schema_from_json(v)
            # Treat everything present in sample as required by default
            required.append(k)
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    elif isinstance(data, list):
        if not data:
            return {
                "type": "array",
                "items": {"type": "any"}
            }
        # Infer items schema from first element or merge
        return {
            "type": "array",
            "items": infer_schema_from_json(data[0])
        }
    elif isinstance(data, bool):
        return {"type": "boolean"}
    elif isinstance(data, int):
        return {"type": "integer"}
    elif isinstance(data, float):
        return {"type": "number"}
    elif data is None:
        return {"type": "any"}
    else:
        # Check string formats
        val_str = str(data)
        schema = {"type": "string"}
        if len(val_str) == 36 and val_str.count("-") == 4:
            schema["format"] = "uuid"
        elif re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', val_str):
            schema["format"] = "date-time"
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', val_str):
            schema["format"] = "date"
        return schema

def main():
    parser = argparse.ArgumentParser(
        description="JSON Schema to SQL DDL Generator - Generate database tables from JSON schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", help="Path to input JSON Schema file or raw JSON file (or '-' for stdin)")
    parser.add_argument("-d", "--dialect", choices=["sqlite", "postgres", "mysql"], default="sqlite",
                        help="Target SQL dialect (default: sqlite)")
    parser.add_argument("-s", "--strategy", choices=["relational", "json"], default="relational",
                        help="Handling of nested objects/arrays. 'relational' spins off tables, 'json' uses JSON fields (default: relational)")
    parser.add_argument("-t", "--table", default="main",
                        help="Name of the root table (default: main)")
    parser.add_argument("-o", "--output", help="Path to save the generated DDL output (prints to stdout if omitted)")
    parser.add_argument("-i", "--infer", action="store_true",
                        help="Treat input as a raw sample JSON file instead of a JSON Schema, and infer schema dynamically")

    args = parser.parse_args()

    # Load input data
    try:
        if args.input == "-":
            input_content = sys.stdin.read()
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                input_content = f.read()
        
        json_data = json.loads(input_content)
    except Exception as e:
        print(f"Error loading input JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve schema
    if args.infer:
        print("-- Informational: Inferring JSON Schema from sample JSON payload...", file=sys.stderr)
        schema = infer_schema_from_json(json_data)
    else:
        schema = json_data

    # Generate DDL
    generator = SQLSchemaGenerator(dialect=args.dialect, nested_strategy=args.strategy)
    generator.process_schema(schema, table_name=args.table)
    ddl = generator.generate_ddl()

    # Output results
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(ddl)
            print(f"SQL DDL successfully written to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(ddl)

if __name__ == "__main__":
    main()
