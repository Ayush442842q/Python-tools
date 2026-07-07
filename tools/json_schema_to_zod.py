#!/usr/bin/env python3
"""
JSON Schema to TypeScript Zod Schema Converter

Parses a standard JSON Schema file (.json) and generates its equivalent Zod schema
in TypeScript. Useful for translating shared API schemas into frontend runtime validations.

Supported JSON Schema features:
- Types: string, number, integer, boolean, null, array, object
- Validations: minLength, maxLength, pattern, format (email, uuid, uri, ipv4, ipv6, datetime),
               minimum, maximum, minItems, maxItems
- Object properties: required vs optional, additionalProperties (strict vs passthrough)
- Combinators: anyOf, oneOf (mapped to z.union), allOf (mapped to z.intersection)

Usage:
    python tools/json_schema_to_zod.py schema.json -o schema.ts
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Any, Optional

def convert_type(schema: Dict[str, Any], indent_level: int = 0) -> str:
    """Recursively converts a JSON Schema fragment to a Zod string expression."""
    schema_type = schema.get("type")
    
    # Check for combinators first
    if "anyOf" in schema or "oneOf" in schema:
        sub_schemas = schema.get("anyOf") or schema.get("oneOf", [])
        sub_zods = [convert_type(s, indent_level) for s in sub_schemas]
        return f"z.union([{', '.join(sub_zods)}])"

    if "allOf" in schema:
        sub_schemas = schema.get("allOf", [])
        if not sub_schemas:
            return "z.any()"
        sub_zods = [convert_type(s, indent_level) for s in sub_schemas]
        # Chain intersections
        current = sub_zods[0]
        for sub in sub_zods[1:]:
            current = f"{current}.and({sub})"
        return current

    # Handle enum
    if "enum" in schema:
        enum_vals = schema["enum"]
        # Format values properly for TS (strings quoted, others literal)
        formatted_vals = []
        for val in enum_vals:
            if isinstance(val, str):
                formatted_vals.append(f'"{val}"')
            elif isinstance(val, bool):
                formatted_vals.append("true" if val else "false")
            elif val is None:
                formatted_vals.append("null")
            else:
                formatted_vals.append(str(val))
        
        if len(formatted_vals) == 1:
            return f"z.literal({formatted_vals[0]})"
        return f"z.union([{', '.join(f'z.literal({v})' for v in formatted_vals)}])"

    if not schema_type:
        # Default fallback if no type is declared but properties exist
        if "properties" in schema:
            schema_type = "object"
        else:
            return "z.any()"

    # If type is an array of types, e.g., ["string", "null"]
    if isinstance(schema_type, list):
        if len(schema_type) == 2 and "null" in schema_type:
            other_type = [t for t in schema_type if t != "null"][0]
            sub_schema = schema.copy()
            sub_schema["type"] = other_type
            return f"{convert_type(sub_schema, indent_level)}.nullable()"
        else:
            # Map multiple types to a union
            sub_zods = []
            for t in schema_type:
                sub_schema = schema.copy()
                sub_schema["type"] = t
                sub_zods.append(convert_type(sub_schema, indent_level))
            return f"z.union([{', '.join(sub_zods)}])"

    # Base types
    if schema_type == "string":
        zod_parts = ["z.string()"]
        
        # Validations
        if "minLength" in schema:
            zod_parts.append(f"min({schema['minLength']})")
        if "maxLength" in schema:
            zod_parts.append(f"max({schema['maxLength']})")
        if "pattern" in schema:
            # Escape backslashes for JS regex
            pattern = schema["pattern"].replace("\\", "\\\\")
            zod_parts.append(f"regex(/{pattern}/)")
        
        # Formats
        fmt = schema.get("format")
        if fmt == "email":
            zod_parts.append("email()")
        elif fmt == "uuid":
            zod_parts.append("uuid()")
        elif fmt == "uri":
            zod_parts.append("url()")
        elif fmt in ("ipv4", "ip"):
            zod_parts.append("ip({ version: 'v4' })")
        elif fmt == "ipv6":
            zod_parts.append("ip({ version: 'v6' })")
        elif fmt in ("date-time", "datetime"):
            zod_parts.append("datetime()")

        return ".".join(zod_parts)

    elif schema_type in ("number", "integer"):
        zod_parts = ["z.number()"] if schema_type == "number" else ["z.number().int()"]
        
        if "minimum" in schema:
            zod_parts.append(f"min({schema['minimum']})")
        if "maximum" in schema:
            zod_parts.append(f"max({schema['maximum']})")
        if "multipleOf" in schema:
            zod_parts.append(f"multipleOf({schema['multipleOf']})")
            
        return ".".join(zod_parts)

    elif schema_type == "boolean":
        return "z.boolean()"

    elif schema_type == "null":
        return "z.null()"

    elif schema_type == "array":
        items = schema.get("items")
        if not items:
            return "z.array(z.any())"
        
        inner_zod = convert_type(items, indent_level)
        zod_parts = [f"z.array({inner_zod})"]
        
        if "minItems" in schema:
            zod_parts.append(f"min({schema['minItems']})")
        if "maxItems" in schema:
            zod_parts.append(f"max({schema['maxItems']})")
            
        return ".".join(zod_parts)

    elif schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        if not properties:
            return "z.object({})"

        indent = "  " * indent_level
        inner_indent = "  " * (indent_level + 1)
        
        lines = ["z.object({"]
        for prop_name, prop_schema in properties.items():
            # Check if property is required
            is_req = prop_name in required
            prop_zod = convert_type(prop_schema, indent_level + 1)
            
            # Format property name (quote if it contains special characters)
            safe_prop_name = prop_name
            if not re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', prop_name):
                safe_prop_name = f'"{prop_name}"'

            if is_req:
                lines.append(f"{inner_indent}{safe_prop_name}: {prop_zod},")
            else:
                lines.append(f"{inner_indent}{safe_prop_name}: {prop_zod}.optional(),")
        
        # Handle additionalProperties
        add_props = schema.get("additionalProperties", True)
        suffix = ""
        if add_props is False:
            suffix = ".strict()"
        elif isinstance(add_props, dict):
            # If additionalProperties is a schema, Zod doesn't have a direct equivalent
            # but we can map it to .catchall()
            catchall_zod = convert_type(add_props, indent_level)
            suffix = f".catchall({catchall_zod})"
        else:
            suffix = ".passthrough()"

        lines.append(f"{indent}}}){suffix}")
        return "\n".join(lines)

    return "z.any()"

def generate_typescript_code(schema_dict: Dict[str, Any], schema_name: str) -> str:
    """Formats the generated Zod string into a complete TypeScript module."""
    zod_schema = convert_type(schema_dict, 0)
    
    title = schema_dict.get("title", schema_name)
    # Sanitize title to form a valid TS variable name
    var_name = re.sub(r'[^a-zA-Z0-9_$]', '', title)
    # Ensure it starts with lowercase or matches typical naming
    if var_name:
        var_name = var_name[0].lower() + var_name[1:] + "Schema"
    else:
        var_name = "defaultSchema"

    description = schema_dict.get("description", "")
    doc_comment = ""
    if description:
        doc_comment = f"/**\n * {description}\n */\n"

    ts_code = (
        "import { z } from 'zod';\n\n"
        f"{doc_comment}"
        f"export const {var_name} = {zod_schema};\n\n"
        f"export type {title} = z.infer<typeof {var_name}>;\n"
    )
    return ts_code

def main():
    parser = argparse.ArgumentParser(description="Convert JSON Schema to TypeScript Zod schemas.")
    parser.add_argument("schema_file", help="Path to the JSON Schema file.")
    parser.add_argument("-o", "--output", help="Path to write the generated TypeScript file. Outputs to stdout if omitted.")
    parser.add_argument("-n", "--name", default="apiSchema", help="Fallback name for the exported schema variable.")

    args = parser.parse_args()

    if not os.path.isfile(args.schema_file):
        print(f"Error: Schema file '{args.schema_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.schema_file, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
    except Exception as e:
        print(f"Error: Failed to parse JSON: {e}", file=sys.stderr)
        sys.exit(1)

    ts_output = generate_typescript_code(schema_data, args.name)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(ts_output)
            print(f"Successfully converted and saved Zod schema to {args.output}")
        except Exception as e:
            print(f"Error: Failed to write output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(ts_output)

if __name__ == "__main__":
    main()
