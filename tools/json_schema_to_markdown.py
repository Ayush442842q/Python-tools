#!/usr/bin/env python3
"""
JSON Schema to Markdown Generator

A standalone utility to parse a JSON Schema file (Draft-07 or newer) and
generate a clean, structured, and easy-to-read Markdown documentation file.

Usage:
    python tools/json_schema_to_markdown.py schema.json -o schema_docs.md
"""

import json
import sys
import argparse
from pathlib import Path

def parse_property(name, prop_def, required_list, depth=0):
    """Parse a single property definition and return its details as a dict."""
    is_required = name in required_list
    prop_type = prop_def.get("type", "any")
    description = prop_def.get("description", "")
    default_val = prop_def.get("default", "")
    
    # Collect constraints
    constraints = []
    if "minimum" in prop_def:
        constraints.append(f"min: {prop_def['minimum']}")
    if "maximum" in prop_def:
        constraints.append(f"max: {prop_def['maximum']}")
    if "minLength" in prop_def:
        constraints.append(f"min length: {prop_def['minLength']}")
    if "maxLength" in prop_def:
        constraints.append(f"max length: {prop_def['maxLength']}")
    if "pattern" in prop_def:
        constraints.append(f"pattern: `{prop_def['pattern']}`")
    if "enum" in prop_def:
        enum_vals = ", ".join([f"`{json.dumps(v)}`" for v in prop_def["enum"]])
        constraints.append(f"enum: [{enum_vals}]")
        
    constraint_str = "; ".join(constraints) if constraints else "-"
    
    # Handle array items type
    if prop_type == "array" and "items" in prop_def:
        items_def = prop_def["items"]
        if isinstance(items_def, dict):
            items_type = items_def.get("type", "any")
            prop_type = f"array of {items_type}"
            
    return {
        "name": name,
        "type": prop_type,
        "required": "Yes" if is_required else "No",
        "description": description,
        "default": json.dumps(default_val) if default_val != "" else "-",
        "constraints": constraint_str,
        "raw_def": prop_def,
        "depth": depth
    }

def process_schema(schema, title_override=None):
    """Convert JSON schema structure into a Markdown string."""
    title = title_override or schema.get("title", "JSON Schema Documentation")
    description = schema.get("description", "")
    schema_type = schema.get("type", "object")
    
    md_lines = []
    md_lines.append(f"# {title}")
    md_lines.append("")
    if description:
        md_lines.append(description)
        md_lines.append("")
        
    md_lines.append(f"**Root Schema Type**: `{schema_type}`")
    md_lines.append("")
    
    # Track nested objects to document them separately or in-line
    nested_objects = []
    
    def generate_properties_table(properties, required_list, depth=0, parent_name=""):
        table_lines = []
        table_lines.append("| Field | Type | Required | Default | Constraints | Description |")
        table_lines.append("| :--- | :--- | :---: | :--- | :--- | :--- |")
        
        for prop_name, prop_def in properties.items():
            full_name = f"{parent_name}.{prop_name}" if parent_name else prop_name
            parsed = parse_property(prop_name, prop_def, required_list, depth)
            
            # Print field name with indentation if nested
            indent = "&nbsp;&nbsp;" * depth
            display_name = f"{indent}`{prop_name}`"
            
            table_lines.append(
                f"| {display_name} | `{parsed['type']}` | {parsed['required']} | `{parsed['default']}` | {parsed['constraints']} | {parsed['description']} |"
            )
            
            # If the property is an object with its own properties, queue for nested display
            if isinstance(prop_def, dict):
                p_type = prop_def.get("type")
                p_props = prop_def.get("properties")
                if p_type == "object" and p_props:
                    nested_objects.append((full_name, p_props, prop_def.get("required", [])))
                elif p_type == "array" and "items" in prop_def:
                    items = prop_def["items"]
                    if isinstance(items, dict) and items.get("type") == "object" and "properties" in items:
                        nested_objects.append((f"{full_name}[]", items["properties"], items.get("required", [])))
                        
        return table_lines

    # Process main schema properties
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if properties:
        md_lines.append("## Properties")
        md_lines.append("")
        md_lines.extend(generate_properties_table(properties, required))
        md_lines.append("")
        
    # Process nested structures
    # We use a while loop because generating a nested table might discover more nested objects
    idx = 0
    while idx < len(nested_objects):
        obj_path, obj_props, obj_req = nested_objects[idx]
        md_lines.append(f"### Nested Object: `{obj_path}`")
        md_lines.append("")
        md_lines.extend(generate_properties_table(obj_props, obj_req, depth=0, parent_name=obj_path))
        md_lines.append("")
        idx += 1
        
    # Handle definitions/components if present
    definitions = schema.get("definitions", schema.get("$defs", {}))
    if definitions:
        md_lines.append("## Definitions / Referenced Models")
        md_lines.append("")
        for def_name, def_schema in definitions.items():
            md_lines.append(f"### Schema: `{def_name}`")
            def_desc = def_schema.get("description", "")
            if def_desc:
                md_lines.append(def_desc)
                md_lines.append("")
            def_props = def_schema.get("properties", {})
            def_req = def_schema.get("required", [])
            if def_props:
                md_lines.extend(generate_properties_table(def_props, def_req, parent_name=def_name))
                md_lines.append("")
                
    return "\n".join(md_lines)

def main():
    parser = argparse.ArgumentParser(description="Convert JSON Schema file to Markdown documentation")
    parser.add_argument("input", help="Path to input JSON Schema file")
    parser.add_argument("-o", "--output", help="Path to output Markdown file (prints to stdout if omitted)")
    parser.add_argument("-t", "--title", help="Override schema title in output markdown")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON syntax in schema file. {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1
        
    # Generate markdown
    markdown_content = process_schema(schema_data, title_override=args.title)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"✓ Documentation successfully generated and saved to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(markdown_content)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
