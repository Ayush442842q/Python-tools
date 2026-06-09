#!/usr/bin/env python3
"""
JSON Schema Validator

Validates a JSON data file against a JSON schema file.
Supports standard types, required fields, and nested objects.

Usage:
    python tools/json_schema_validator.py data.json schema.json
"""

import argparse
import json
import os
import sys

def validate(data, schema, path=""):
    errors = []
    
    # 1. Type validation
    expected_type = schema.get("type")
    if expected_type:
        actual_type = type(data)
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }
        
        target_class = type_mapping.get(expected_type)
        if target_class:
            if not isinstance(data, target_class) or (expected_type == "integer" and isinstance(data, bool)):
                errors.append(f"Field '{path or 'root'}' type mismatch: Expected '{expected_type}', got '{actual_type.__name__}'")
                return errors

    # 2. Object validation (properties and required fields)
    if expected_type == "object" and isinstance(data, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for req in required:
            if req not in data:
                errors.append(f"Missing required field '{path + '.' + req if path else req}'")
        
        for key, value in data.items():
            if key in properties:
                sub_path = f"{path}.{key}" if path else key
                errors.extend(validate(value, properties[key], sub_path))

    # 3. Array validation (items)
    elif expected_type == "array" and isinstance(data, list):
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(data):
                sub_path = f"{path}[{idx}]"
                errors.extend(validate(item, items_schema, sub_path))
                
    return errors

def main():
    parser = argparse.ArgumentParser(description="JSON Schema Validator - Validate JSON files against a schema")
    parser.add_argument('data', help='Path to the JSON data file')
    parser.add_argument('schema', help='Path to the JSON schema file')
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"Error: Data file '{args.data}' not found.")
        return 1
    if not os.path.exists(args.schema):
        print(f"Error: Schema file '{args.schema}' not found.")
        return 1

    try:
        with open(args.data, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error parsing data JSON file: {e}")
        return 1

    try:
        with open(args.schema, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"Error parsing schema JSON file: {e}")
        return 1

    errors = validate(data, schema)
    
    if errors:
        print("[FAIL] Validation failed with the following errors:")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("[PASS] Validation successful! Data matches the schema.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
