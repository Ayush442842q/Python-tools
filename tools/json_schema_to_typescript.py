#!/usr/bin/env python3
"""
JSON Schema to TypeScript Converter

A CLI utility that compiles JSON Schema files (.json) into clean, idiomatic
TypeScript interface and type definitions. It supports nested objects, arrays,
enums, optional/required fields, basic types, and extracts descriptions into JSDoc comments.

Usage:
    python tools/json_schema_to_typescript.py -i schema.json -o types.ts
    python tools/json_schema_to_typescript.py -i schema.json --root-name UserProfile
"""

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Set

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

class JsonSchemaToTypeScript:
    def __init__(self, root_name: str = "RootSchema"):
        self.root_name = root_name
        self.additional_types: Dict[str, str] = {}
        self.generated_types: Set[str] = set()

    def clean_name(self, name: str) -> str:
        """Converts a snake_case or kebab-case name to PascalCase."""
        name = name.replace('-', '_').replace(' ', '_')
        parts = name.split('_')
        return "".join(p.capitalize() for p in parts if p)

    def format_jsdoc(self, description: str, indent: str = "") -> str:
        """Formats a description string into JSDoc style comments."""
        if not description:
            return ""
        lines = description.strip().split('\n')
        if len(lines) == 1:
            return f"{indent}/** {lines[0]} */\n"
        
        jsdoc = f"{indent}/**\n"
        for line in lines:
            jsdoc += f"{indent} * {line}\n"
        jsdoc += f"{indent} */\n"
        return jsdoc

    def resolve_type(self, schema: Dict[str, Any], key_name: str, indent: str = "") -> str:
        """Recursively parses a schema node and returns its TypeScript type representation."""
        if not isinstance(schema, dict):
            return "any"

        # Handle $ref (basic support for local definitions)
        if "$ref" in schema:
            ref = schema["$ref"]
            if ref.startswith("#/definitions/"):
                ref_name = self.clean_name(ref.split("/")[-1])
                return ref_name
            elif ref.startswith("#/$defs/"):
                ref_name = self.clean_name(ref.split("/")[-1])
                return ref_name
            return "any"

        # Handle combinated schemas (oneOf, anyOf, allOf)
        if "oneOf" in schema:
            types = [self.resolve_type(sub, key_name, indent) for sub in schema["oneOf"]]
            return " | ".join(types)
        if "anyOf" in schema:
            types = [self.resolve_type(sub, key_name, indent) for sub in schema["anyOf"]]
            return " | ".join(types)
        if "allOf" in schema:
            types = [self.resolve_type(sub, key_name, indent) for sub in schema["allOf"]]
            return " & ".join(types)

        # Handle enum
        if "enum" in schema:
            enum_vals = schema["enum"]
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
            return " | ".join(formatted_vals)

        schema_type = schema.get("type", "object")

        if isinstance(schema_type, list):
            # Union of types
            types = []
            for t in schema_type:
                sub_schema = schema.copy()
                sub_schema["type"] = t
                types.append(self.resolve_type(sub_schema, key_name, indent))
            return " | ".join(types)

        if schema_type == "string":
            return "string"
        elif schema_type in ("number", "integer"):
            return "number"
        elif schema_type == "boolean":
            return "boolean"
        elif schema_type == "null":
            return "null"
        elif schema_type == "array":
            items = schema.get("items")
            if not items:
                return "any[]"
            item_type = self.resolve_type(items, key_name + "Item", indent)
            # Add parentheses if the item type contains union operators
            if "|" in item_type or "&" in item_type:
                return f"({item_type})[]"
            return f"{item_type}[]"

        elif schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            additional_properties = schema.get("additionalProperties", True)

            # Check if this is an inline nested object schema that we should extract
            if properties:
                next_indent = indent + "  "
                lines = ["{"]
                for prop_name, prop_schema in properties.items():
                    prop_desc = prop_schema.get("description", "")
                    lines.append(self.format_jsdoc(prop_desc, next_indent).rstrip('\n'))
                    
                    is_req = prop_name in required
                    opt_mark = "" if is_req else "?"
                    
                    # Resolve property type
                    prop_type = self.resolve_type(prop_schema, prop_name, next_indent)
                    lines.append(f"{next_indent}{prop_name}{opt_mark}: {prop_type};")
                
                # Handle dynamic properties
                if additional_properties is True:
                    lines.append(f"{next_indent}[key: string]: any;")
                elif isinstance(additional_properties, dict):
                    add_type = self.resolve_type(additional_properties, key_name + "Value", next_indent)
                    lines.append(f"{next_indent}[key: string]: {add_type};")

                lines.append(f"{indent}}")
                return "\n".join(lines)
            
            # Object without properties
            if isinstance(additional_properties, dict):
                add_type = self.resolve_type(additional_properties, key_name + "Value", indent)
                return f"{{ [key: string]: {add_type} }}"
            return "{ [key: string]: any }"

        return "any"

    def compile(self, schema: Dict[str, Any]) -> str:
        """Translates the top-level schema and all definitions into TypeScript."""
        output_parts = []
        
        # Process definitions/defs first
        definitions = schema.get("definitions", schema.get("$defs", {}))
        for def_name, def_schema in definitions.items():
            clean_def_name = self.clean_name(def_name)
            self.generated_types.add(clean_def_name)
            
            desc = def_schema.get("description", "")
            jsdoc = self.format_jsdoc(desc)
            
            # Resolve definition type
            def_type = self.resolve_type(def_schema, clean_def_name)
            
            if def_schema.get("type", "object") == "object" and def_schema.get("properties"):
                output_parts.append(f"{jsdoc}export interface {clean_def_name} {def_type}\n")
            else:
                output_parts.append(f"{jsdoc}export type {clean_def_name} = {def_type};\n")

        # Process main schema
        root_desc = schema.get("description", "")
        jsdoc = self.format_jsdoc(root_desc)
        root_type = self.resolve_type(schema, self.root_name)
        
        if schema.get("type", "object") == "object" and schema.get("properties"):
            output_parts.append(f"{jsdoc}export interface {self.root_name} {root_type}\n")
        else:
            output_parts.append(f"{jsdoc}export type {self.root_name} = {root_type};\n")

        return "\n".join(output_parts)

def main():
    parser = argparse.ArgumentParser(description="Convert JSON Schema to TypeScript Type Definitions")
    parser.add_argument("-i", "--input", help="Path to input JSON Schema file (reads from stdin if omitted)")
    parser.add_argument("-o", "--output", help="Path to output TypeScript file (writes to stdout if omitted)")
    parser.add_argument("-r", "--root-name", default="RootSchema", help="Name of the root TypeScript interface (default: RootSchema)")
    
    args = parser.parse_args()

    try:
        # Load schema
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                schema = json.load(f)
        else:
            if sys.stdin.isatty():
                parser.print_help()
                sys.exit(1)
            schema = json.loads(sys.stdin.read())
    except Exception as e:
        print(color_text(f"Error parsing JSON schema: {e}", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    converter = JsonSchemaToTypeScript(root_name=args.root_name)
    typescript_code = converter.compile(schema)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(typescript_code)
            print(color_text(f"Successfully generated TypeScript definitions to {args.output}", COLOR_GREEN))
        except Exception as e:
            print(color_text(f"Error writing output file: {e}", COLOR_RED), file=sys.stderr)
            sys.exit(1)
    else:
        print(typescript_code)

if __name__ == "__main__":
    main()
