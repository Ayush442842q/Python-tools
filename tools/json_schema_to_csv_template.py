#!/usr/bin/env python3
"""
JSON Schema to CSV Template Generator
Parses a JSON Schema file and generates a flat CSV template file where the columns
represent flattened JSON paths. Also generates a Markdown documentation file detailing
validation constraints, required fields, and descriptions for each column.
"""

import sys
import os
import json
import csv
import argparse

class SchemaParser:
    def __init__(self, root_schema):
        self.root_schema = root_schema
        self.columns = []

    def resolve_ref(self, ref_path):
        """Resolves internal JSON Schema references like '#/$defs/name'."""
        if not ref_path.startswith("#/"):
            raise ValueError(f"Only internal schema references (starting with '#/') are supported. Got: {ref_path}")
            
        parts = ref_path.split("/")[1:]
        current = self.root_schema
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    raise ValueError(f"Could not resolve ref index '{part}' in reference path: {ref_path}")
            else:
                raise ValueError(f"Could not resolve key '{part}' in reference path: {ref_path}")
        return current

    def parse(self, schema, current_path="", required_in_parent=False):
        """Recursively parses schema nodes and flattens properties into columns."""
        # Resolve references
        if "$ref" in schema:
            try:
                resolved = self.resolve_ref(schema["$ref"])
                self.parse(resolved, current_path, required_in_parent)
                return
            except ValueError as e:
                print(f"Warning: {e}")
                return

        # Handle composite schemas (allOf, anyOf, oneOf) by merging properties
        if "allOf" in schema:
            merged_properties = {}
            merged_required = []
            for sub in schema["allOf"]:
                if "$ref" in sub:
                    sub = self.resolve_ref(sub["$ref"])
                if "properties" in sub:
                    merged_properties.update(sub["properties"])
                if "required" in sub:
                    merged_required.extend(sub["required"])
            
            # Create a synthetic schema merging all properties
            schema = schema.copy()
            schema["type"] = "object"
            schema["properties"] = merged_properties
            if "required" in schema:
                schema["required"] = list(set(schema["required"] + merged_required))
            else:
                schema["required"] = merged_required

        schema_type = schema.get("type")
        
        # If type is not explicitly defined but 'properties' exists, treat as object
        if not schema_type and "properties" in schema:
            schema_type = "object"

        if schema_type == "object":
            properties = schema.get("properties", {})
            required_list = schema.get("required", [])
            for prop_name, prop_schema in properties.items():
                new_path = f"{current_path}.{prop_name}" if current_path else prop_name
                is_required = prop_name in required_list
                self.parse(prop_schema, new_path, is_required)
                
        elif schema_type == "array":
            items = schema.get("items", {})
            # Pre-populate index [0] to represent array items in flat CSV
            new_path = f"{current_path}[0]"
            self.parse(items, new_path, required_in_parent)
            
        else:
            # Leaf primitive node (string, number, integer, boolean) or null/untyped
            col_info = {
                "path": current_path,
                "type": schema_type or "any",
                "required": required_in_parent,
                "description": schema.get("description", ""),
                "enum": schema.get("enum"),
                "default": schema.get("default"),
                "minimum": schema.get("minimum"),
                "maximum": schema.get("maximum"),
                "pattern": schema.get("pattern"),
            }
            self.columns.append(col_info)

def generate_csv_template(columns, output_file, include_guidance_row=False):
    """Generates the CSV template file with headers."""
    headers = [col["path"] for col in columns]
    
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            if include_guidance_row:
                # Add a row displaying data type and whether it's required
                guidance = []
                for col in columns:
                    req_str = "REQUIRED" if col["required"] else "OPTIONAL"
                    type_str = col["type"].upper()
                    guidance.append(f"<{type_str} | {req_str}>")
                writer.writerow(guidance)
                
        print(f"Successfully generated CSV Template: {output_file}")
        return True
    except Exception as e:
        print(f"Error writing CSV template: {e}")
        return False

def generate_markdown_doc(columns, output_file, schema_name=""):
    """Generates a markdown documentation explaining each CSV column constraint."""
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# CSV Template Documentation: {schema_name}\n\n")
            f.write("This document explains the columns, types, and constraints for the generated CSV template.\n\n")
            f.write("| Column Path (CSV Header) | Type | Required? | Constraints | Description |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            
            for col in columns:
                # Format constraints
                constraints = []
                if col["enum"]:
                    constraints.append(f"Enum: {list(col['enum'])}")
                if col["default"] is not None:
                    constraints.append(f"Default: {col['default']}")
                if col["minimum"] is not None:
                    constraints.append(f"Min: {col['minimum']}")
                if col["maximum"] is not None:
                    constraints.append(f"Max: {col['maximum']}")
                if col["pattern"]:
                    constraints.append(f"Regex: `{col['pattern']}`")
                
                constraint_str = ", ".join(constraints) if constraints else "None"
                req_str = "**Yes**" if col["required"] else "No"
                desc = col["description"].replace("\n", " ") if col["description"] else "N/A"
                
                f.write(f"| `{col['path']}` | `{col['type']}` | {req_str} | {constraint_str} | {desc} |\n")
                
        print(f"Successfully generated Markdown Documentation: {output_file}")
        return True
    except Exception as e:
        print(f"Error writing markdown documentation: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="JSON Schema to Flat CSV Template & Documentation Generator")
    parser.add_argument("-s", "--schema", required=True, help="Path to input JSON Schema file")
    parser.add_argument("-c", "--csv", required=True, help="Path to output CSV template file")
    parser.add_argument("-d", "--doc", required=True, help="Path to output Markdown documentation file")
    parser.add_argument("-g", "--guidance-row", action="store_true", help="Include a type/required guidance row in the CSV template")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.schema):
        print(f"Error: JSON Schema file '{args.schema}' not found.")
        sys.exit(1)
        
    try:
        with open(args.schema, "r", encoding="utf-8") as f:
            root_schema = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON Schema: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
        
    schema_name = root_schema.get("title") or root_schema.get("$id") or os.path.basename(args.schema)
    
    parser = SchemaParser(root_schema)
    parser.parse(root_schema)
    
    if not parser.columns:
        print("Error: No primitive properties found in schema. Cannot create CSV headers.")
        sys.exit(1)
        
    # Generate files
    csv_ok = generate_csv_template(parser.columns, args.csv, args.guidance_row)
    doc_ok = generate_markdown_doc(parser.columns, args.doc, schema_name)
    
    if not (csv_ok and doc_ok):
        sys.exit(1)

if __name__ == "__main__":
    main()
