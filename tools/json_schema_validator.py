#!/usr/bin/env python3
"""
JSON Schema Validator
Validates a JSON data file against a JSON Schema file (Draft-07 subset).
Uses only standard Python libraries.
"""
import argparse
import json
import re
import sys
import math

class JsonSchemaValidator:
    def __init__(self):
        self.errors = []

    def validate(self, data, schema):
        self.errors = []
        self._validate_value(data, schema, "root")
        return len(self.errors) == 0, self.errors

    def _add_error(self, path, message):
        self.errors.append(f"[{path}] {message}")

    def _validate_value(self, value, schema, path):
        if not isinstance(schema, dict):
            # If schema is boolean (True/False as in Draft-07 additionalProperties)
            if schema is False:
                self._add_error(path, "Value is not allowed here (additionalProperties is False)")
            return

        # 1. Type validation
        expected_type = schema.get("type")
        if expected_type:
            types = expected_type if isinstance(expected_type, list) else [expected_type]
            type_matched = False
            for t in types:
                if t == "null" and value is None:
                    type_matched = True
                elif t == "boolean" and isinstance(value, bool):
                    type_matched = True
                elif t == "integer" and isinstance(value, int) and not isinstance(value, bool):
                    type_matched = True
                elif t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                    type_matched = True
                elif t == "string" and isinstance(value, str):
                    type_matched = True
                elif t == "object" and isinstance(value, dict):
                    type_matched = True
                elif t == "array" and isinstance(value, list):
                    type_matched = True
            
            if not type_matched:
                self._add_error(path, f"Expected type '{expected_type}', but got '{type(value).__name__}'")
                return

        # 2. Enum & Const
        if "enum" in schema:
            if value not in schema["enum"]:
                self._add_error(path, f"Value '{value}' is not in enum {schema['enum']}")
        
        if "const" in schema:
            if value != schema["const"]:
                self._add_error(path, f"Value '{value}' does not match constant '{schema['const']}'")

        # 3. Object-specific validations
        if isinstance(value, dict):
            # Required properties
            required = schema.get("required", [])
            for req_prop in required:
                if req_prop not in value:
                    self._add_error(path, f"Missing required property '{req_prop}'")

            # Properties validation
            properties = schema.get("properties", {})
            for prop_name, prop_val in value.items():
                if prop_name in properties:
                    self._validate_value(prop_val, properties[prop_name], f"{path}.{prop_name}")
                else:
                    # Check patternProperties if no matching standard property
                    pattern_matched = False
                    pattern_properties = schema.get("patternProperties", {})
                    for pattern, pattern_schema in pattern_properties.items():
                        if re.search(pattern, prop_name):
                            self._validate_value(prop_val, pattern_schema, f"{path}.{prop_name}")
                            pattern_matched = True
                    
                    # Check additionalProperties if not matched by properties or patternProperties
                    if not pattern_matched and "additionalProperties" in schema:
                        add_props = schema["additionalProperties"]
                        if add_props is False:
                            self._add_error(path, f"Property '{prop_name}' is not allowed (additionalProperties is False)")
                        elif isinstance(add_props, dict):
                            self._validate_value(prop_val, add_props, f"{path}.{prop_name}")

            # Min/Max properties
            if "minProperties" in schema and len(value) < schema["minProperties"]:
                self._add_error(path, f"Object has {len(value)} properties, minimum is {schema['minProperties']}")
            if "maxProperties" in schema and len(value) > schema["maxProperties"]:
                self._add_error(path, f"Object has {len(value)} properties, maximum is {schema['maxProperties']}")

        # 4. Array-specific validations
        elif isinstance(value, list):
            items_schema = schema.get("items")
            if items_schema:
                if isinstance(items_schema, dict):
                    # Single schema for all items
                    for idx, val in enumerate(value):
                        self._validate_value(val, items_schema, f"{path}[{idx}]")
                elif isinstance(items_schema, list):
                    # Tuple validation (list of schemas matching positions)
                    for idx, val in enumerate(value):
                        if idx < len(items_schema):
                            self._validate_value(val, items_schema[idx], f"{path}[{idx}]")
                        else:
                            # Handle additionalItems
                            add_items = schema.get("additionalItems", True)
                            if add_items is False:
                                self._add_error(path, f"Array item at index {idx} is not allowed (additionalItems is False)")
                            elif isinstance(add_items, dict):
                                self._validate_value(val, add_items, f"{path}[{idx}]")

            # Unique items
            if schema.get("uniqueItems", False):
                # Try to serialize items to check for uniqueness
                serialized_items = []
                for item in value:
                    try:
                        serialized_items.append(json.dumps(item, sort_keys=True))
                    except TypeError:
                        serialized_items.append(str(item))
                if len(serialized_items) != len(set(serialized_items)):
                    self._add_error(path, "Array items must be unique")

            # Min/Max items
            if "minItems" in schema and len(value) < schema["minItems"]:
                self._add_error(path, f"Array has {len(value)} items, minimum is {schema['minItems']}")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                self._add_error(path, f"Array has {len(value)} items, maximum is {schema['maxItems']}")

        # 5. String-specific validations
        elif isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                self._add_error(path, f"String length is {len(value)}, minimum is {schema['minLength']}")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                self._add_error(path, f"String length is {len(value)}, maximum is {schema['maxLength']}")
            if "pattern" in schema:
                pattern = schema["pattern"]
                if not re.search(pattern, value):
                    self._add_error(path, f"String '{value}' does not match pattern '{pattern}'")

        # 6. Number/Integer validations
        elif isinstance(value, (int, float)):
            # Minimum
            if "minimum" in schema and value < schema["minimum"]:
                self._add_error(path, f"Value {value} is less than minimum {schema['minimum']}")
            if "exclusiveMinimum" in schema:
                ex_min = schema["exclusiveMinimum"]
                if isinstance(ex_min, bool):
                    if ex_min and "minimum" in schema and value <= schema["minimum"]:
                        self._add_error(path, f"Value {value} is less than or equal to exclusive minimum {schema['minimum']}")
                else:
                    if value <= ex_min:
                        self._add_error(path, f"Value {value} is less than or equal to exclusive minimum {ex_min}")

            # Maximum
            if "maximum" in schema and value > schema["maximum"]:
                self._add_error(path, f"Value {value} is greater than maximum {schema['maximum']}")
            if "exclusiveMaximum" in schema:
                ex_max = schema["exclusiveMaximum"]
                if isinstance(ex_max, bool):
                    if ex_max and "maximum" in schema and value >= schema["maximum"]:
                        self._add_error(path, f"Value {value} is greater than or equal to exclusive maximum {schema['maximum']}")
                else:
                    if value >= ex_max:
                        self._add_error(path, f"Value {value} is greater than or equal to exclusive maximum {ex_max}")

            # MultipleOf
            if "multipleOf" in schema:
                mult = schema["multipleOf"]
                # Avoid float division precision issues
                if (value / mult) % 1 != 0 and not math.isclose((value / mult) % 1, 0, abs_tol=1e-9) and not math.isclose((value / mult) % 1, 1, abs_tol=1e-9):
                    self._add_error(path, f"Value {value} is not a multiple of {mult}")

def main():
    parser = argparse.ArgumentParser(description="Validate a JSON file against a JSON Schema (Draft-07 subset).")
    parser.add_argument("data_file", help="Path to JSON data file")
    parser.add_argument("schema_file", help="Path to JSON Schema file")
    
    args = parser.parse_args()
    
    # Load files
    try:
        with open(args.data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data file '{args.data_file}': {e}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"Error loading schema file '{args.schema_file}': {e}", file=sys.stderr)
        sys.exit(1)
        
    validator = JsonSchemaValidator()
    is_valid, errors = validator.validate(data, schema)
    
    if is_valid:
        print("✓ JSON data is VALID against the schema.")
        sys.exit(0)
    else:
        print("✗ JSON data is INVALID. Found validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
