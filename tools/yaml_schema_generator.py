#!/usr/bin/env python3
"""
YAML Schema Generator

This tool automatically generates a structured JSON Schema (draft-07 validation schema)
from any YAML configuration file. It uses type inference to determine types, nested objects,
arrays, and list items. 

To maintain zero third-party dependencies, it imports standard 'yaml' if available,
and falls back to a custom, lightweight, indentation-based YAML parser if 'pyyaml'
is not installed.

Requirements:
    - Pure Python 3 (pyyaml optional)
"""

import sys
import os
import json
import re
import argparse

# ANSI Terminal Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

# Lightweight fallback YAML parser in pure Python
def parse_yaml_fallback(content):
    """
    Parses a basic YAML configuration into python objects (dicts/lists/primitives).
    Uses line indentation for nested mapping.
    """
    lines = content.splitlines()
    root = {}
    stack = [(-1, root)]  # list of (indent_level, container_obj)
    
    # Track list structures under indentation
    # stack elements can be: (-1, root_dict) or (indent, current_dict) or (indent, current_list)
    
    for idx, line in enumerate(lines, 1):
        # Ignore comments and blank lines
        clean_line = line.split('#')[0].rstrip()
        if not clean_line.strip():
            continue
            
        indent = len(clean_line) - len(clean_line.lstrip())
        stripped = clean_line.strip()
        
        # Pop stack until we find the parent of the current indentation level
        while stack and stack[-1][0] >= indent:
            stack.pop()
            
        if not stack:
            # Fallback safety
            stack = [(-1, root)]
            
        parent_indent, parent_container = stack[-1]
        
        # Check if it is a list item: starts with '- ' or '-'
        if stripped.startswith('-'):
            item_val = stripped[1:].strip()
            # If the parent isn't a list, we need to create one
            if not isinstance(parent_container, list):
                # This happens if we are matching under a key
                # We need to find the key we are adding to.
                # Since the stack tracks container, if the last was a dict, we convert the key value to list
                # But to keep it simple, we check if the parent is a dict and we are adding an array item
                # Better approach: when parsing dict key, if it has no inline value, we initialize it as None.
                # If the next line is a list item under it, we make it a list.
                pass
                
            # If parent is a list, we append to it
            if isinstance(parent_container, list):
                if not item_val:
                    # Nested object in list
                    new_obj = {}
                    parent_container.append(new_obj)
                    stack.append((indent, new_obj))
                else:
                    parent_container.append(infer_primitive(item_val))
            elif isinstance(parent_container, dict):
                # We have a list at this indent, but parent is dict.
                # This usually means a key mapping to a list.
                # To handle this, we look at the last key added to the dict.
                if parent_container:
                    last_key = list(parent_container.keys())[-1]
                    if parent_container[last_key] is None or parent_container[last_key] == "":
                        parent_container[last_key] = []
                    if isinstance(parent_container[last_key], list):
                        if not item_val:
                            new_obj = {}
                            parent_container[last_key].append(new_obj)
                            stack.append((indent, new_obj))
                        else:
                            parent_container[last_key].append(infer_primitive(item_val))
            continue
            
        # Check if it is a key-value mapping: key: value
        if ':' in stripped:
            parts = stripped.split(':', 1)
            key = parts[0].strip().strip('"\'')
            val = parts[1].strip()
            
            # Remove enclosing quotes if any
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
                
            if isinstance(parent_container, dict):
                if not val:
                    # Key with nested dict or list next
                    # We initialize as empty dict (will be overwritten to list if next line is '-')
                    parent_container[key] = {}
                    stack.append((indent, parent_container[key]))
                else:
                    parent_container[key] = infer_primitive(val)
            continue

    return root

def infer_primitive(val):
    """Converts string values into standard Python primitive types"""
    val_upper = val.upper()
    if val_upper in ("TRUE", "YES", "ON"):
        return True
    if val_upper in ("FALSE", "NO", "OFF"):
        return False
    if val_upper in ("NULL", "NONE", "~", ""):
        return None
        
    # Check integer
    if re.match(r'^[-+]?\d+$', val):
        return int(val)
        
    # Check float
    if re.match(r'^[-+]?\d*\.\d+$', val):
        return float(val)
        
    return val

class SchemaGenerator:
    def __init__(self, make_required=True):
        self.make_required = make_required

    def generate(self, obj):
        """Recursively generates JSON Schema properties from a python object representation"""
        if isinstance(obj, dict):
            schema = {
                "type": "object",
                "properties": {}
            }
            required_keys = []
            
            for k, v in obj.items():
                schema["properties"][k] = self.generate(v)
                if self.make_required and v is not None:
                    required_keys.append(k)
                    
            if required_keys:
                schema["required"] = required_keys
            return schema
            
        elif isinstance(obj, list):
            schema = {
                "type": "array"
            }
            if not obj:
                schema["items"] = {"type": "string"}  # Default fallback for empty list
            else:
                # Infer item type based on the first item or union type if mixed
                # For simplicity, we scan all items and build schema
                item_schemas = [self.generate(item) for item in obj]
                # If they are all same type, merge them
                first_type = item_schemas[0]["type"]
                all_same = all(s["type"] == first_type for s in item_schemas)
                
                if all_same:
                    if first_type == "object":
                        # Merge object structures
                        merged_properties = {}
                        for s in item_schemas:
                            for prop, prop_schema in s.get("properties", {}).items():
                                if prop not in merged_properties:
                                    merged_properties[prop] = prop_schema
                        schema["items"] = {
                            "type": "object",
                            "properties": merged_properties
                        }
                    else:
                        schema["items"] = item_schemas[0]
                else:
                    # Mixed types, use anyOf
                    # Deduplicate schemas by type
                    unique_schemas = []
                    seen_types = set()
                    for s in item_schemas:
                        if s["type"] not in seen_types:
                            seen_types.add(s["type"])
                            unique_schemas.append(s)
                    schema["items"] = {"anyOf": unique_schemas}
            return schema
            
        elif isinstance(obj, bool):
            return {"type": "boolean"}
        elif isinstance(obj, int):
            return {"type": "integer"}
        elif isinstance(obj, float):
            return {"type": "number"}
        elif obj is None:
            return {"type": "null"}
        else:
            return {"type": "string"}

def main():
    parser = argparse.ArgumentParser(description="Generate JSON Schema from a YAML configuration file.")
    parser.add_argument("yaml_file", help="Path to the YAML file")
    parser.add_argument("-o", "--output", help="Path to output the generated JSON Schema file")
    parser.add_argument("--no-required", action="store_true", help="Do not mark keys as required in the schema")
    
    args = parser.parse_args()

    if not os.path.exists(args.yaml_file):
        print(colorize(f"Error: File not found: {args.yaml_file}", 'red'), file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.yaml_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(colorize(f"Error reading file: {e}", 'red'), file=sys.stderr)
        sys.exit(1)

    # Attempt to parse using PyYAML first
    data = None
    parse_method = "Custom Fallback Parser"
    
    try:
        import yaml
        try:
            data = yaml.safe_load(content)
            parse_method = "PyYAML Engine"
        except yaml.YAMLError as ye:
            print(colorize(f"YAML Parse Error: {ye}", 'red'), file=sys.stderr)
            sys.exit(1)
    except ImportError:
        # Fallback to custom parser
        try:
            data = parse_yaml_fallback(content)
        except Exception as e:
            print(colorize(f"Fallback YAML parsing error: {e}", 'red'), file=sys.stderr)
            print("Please install PyYAML for full spec compliance: `pip install pyyaml`", file=sys.stderr)
            sys.exit(1)

    if data is None:
        data = {}

    # Generate schema
    generator = SchemaGenerator(make_required=not args.no_required)
    schema = generator.generate(data)
    
    # Add root schema standard metadata
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": f"Schema for {os.path.basename(args.yaml_file)}",
        "description": "Auto-generated JSON Schema from YAML file structure",
        **schema
    }

    schema_json = json.dumps(schema, indent=2)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(schema_json)
            print(colorize(f"Schema successfully saved to: {args.output}", 'green'))
        except Exception as e:
            print(colorize(f"Error writing schema to file: {e}", 'red'), file=sys.stderr)
            sys.exit(1)
    else:
        # Print to stdout
        print(colorize(f"=== Generated JSON Schema (parsed via {parse_method}) ===", 'bold'))
        print(schema_json)

if __name__ == "__main__":
    main()
