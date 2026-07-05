#!/usr/bin/env python3
"""
YAML Schema Validator & Structure Checker

Validates YAML configuration files against structural schema specifications, checking field
types, required fields, allowed values, regex patterns, and nested keys.
Supports zero external dependencies via lightweight internal parser, or uses PyYAML if installed.
"""

import os
import sys
import re
import json
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_yaml_file(filepath: str) -> Any:
    """Load YAML file using PyYAML if available, or lightweight json/custom fallback."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File '{filepath}' does not exist.")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        import yaml
        return yaml.safe_load(content)
    except ImportError:
        # Fallback: attempt json load if format is JSON-compatible YAML, or lightweight parser
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return _basic_yaml_parse(content)


def _basic_yaml_parse(content: str) -> Dict[str, Any]:
    """Basic fallback YAML line parser for simple key-value and dictionary structures."""
    result: Dict[str, Any] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            parts = line.split(':', 1)
            key = parts[0].strip()
            val = parts[1].strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            elif val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
            elif val.isdigit():
                val = int(val)
            result[key] = val
    return result


class ValidationError:
    def __init__(self, path: str, message: str, severity: str = "ERROR"):
        self.path = path
        self.message = message
        self.severity = severity

    def __str__(self):
        color = RED if self.severity == "ERROR" else YELLOW
        return f"{color}[{self.severity}] Path '{self.path}': {self.message}{RESET}"


class SchemaValidator:
    """Validates data structures against schema rules."""
    
    TYPE_MAP = {
        'string': str,
        'str': str,
        'int': int,
        'integer': int,
        'float': (int, float),
        'number': (int, float),
        'bool': bool,
        'boolean': bool,
        'list': list,
        'array': list,
        'dict': dict,
        'object': dict,
    }

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.errors: List[ValidationError] = []

    def validate(self, data: Any) -> List[ValidationError]:
        self.errors = []
        self._validate_node(data, self.schema, "$")
        return self.errors

    def _validate_node(self, data: Any, schema_node: Dict[str, Any], path: str):
        if not isinstance(schema_node, dict):
            return

        # Type checking
        expected_type_str = schema_node.get('type')
        if expected_type_str:
            target_type = self.TYPE_MAP.get(expected_type_str.lower())
            if target_type and not isinstance(data, target_type):
                self.errors.append(ValidationError(
                    path, f"Expected type '{expected_type_str}', got '{type(data).__name__}'"
                ))
                return

        # Enum check
        allowed_enum = schema_node.get('enum')
        if allowed_enum is not None and isinstance(allowed_enum, list):
            if data not in allowed_enum:
                self.errors.append(ValidationError(
                    path, f"Value '{data}' is not in allowed choices: {allowed_enum}"
                ))

        # String specific rules
        if isinstance(data, str):
            pattern = schema_node.get('pattern')
            if pattern and not re.search(pattern, data):
                self.errors.append(ValidationError(
                    path, f"Value '{data}' does not match regex pattern '{pattern}'"
                ))

            min_len = schema_node.get('min_length')
            if min_len is not None and len(data) < min_len:
                self.errors.append(ValidationError(
                    path, f"Length {len(data)} is shorter than minimum {min_len}"
                ))

            max_len = schema_node.get('max_length')
            if max_len is not None and len(data) > max_len:
                self.errors.append(ValidationError(
                    path, f"Length {len(data)} is longer than maximum {max_len}"
                ))

        # Numeric specific rules
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            minimum = schema_node.get('minimum')
            if minimum is not None and data < minimum:
                self.errors.append(ValidationError(
                    path, f"Value {data} is less than minimum threshold {minimum}"
                ))

            maximum = schema_node.get('maximum')
            if maximum is not None and data > maximum:
                self.errors.append(ValidationError(
                    path, f"Value {data} is greater than maximum threshold {maximum}"
                ))

        # Dictionary / Object rules
        if isinstance(data, dict):
            properties = schema_node.get('properties', {})
            required = schema_node.get('required', [])

            for req_key in required:
                if req_key not in data:
                    self.errors.append(ValidationError(
                        path, f"Missing required property '{req_key}'"
                    ))

            for key, val in data.items():
                child_path = f"{path}.{key}"
                if key in properties:
                    self._validate_node(val, properties[key], child_path)
                elif schema_node.get('additionalProperties') is False:
                    self.errors.append(ValidationError(
                        path, f"Additional property '{key}' is not allowed by schema"
                    ))

        # List / Array rules
        if isinstance(data, list):
            item_schema = schema_node.get('items')
            if item_schema:
                for idx, item in enumerate(data):
                    self._validate_node(item, item_schema, f"{path}[{idx}]")


def generate_sample_schema() -> Dict[str, Any]:
    """Returns an example validation schema."""
    return {
        "type": "object",
        "required": ["name", "version", "server"],
        "properties": {
            "name": {"type": "string", "min_length": 3},
            "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
            "debug": {"type": "boolean"},
            "server": {
                "type": "object",
                "required": ["host", "port"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "environment": {"type": "string", "enum": ["development", "staging", "production"]}
                }
            }
        }
    }


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Validate YAML or JSON configuration files against a structural schema.")
    parser.add_argument("yaml_file", nargs="?", help="Path to the YAML file to validate")
    parser.add_argument("-s", "--schema", help="Path to schema file (JSON or YAML format)")
    parser.add_argument("--generate-sample-schema", action="store_true", help="Print sample schema JSON and exit")

    args = parser.parse_args()

    if args.generate_sample_schema:
        print(json.dumps(generate_sample_schema(), indent=2))
        sys.exit(0)

    if not args.yaml_file:
        parser.error("the following arguments are required: yaml_file (unless --generate-sample-schema is used)")

    try:
        yaml_data = load_yaml_file(args.yaml_file)
    except Exception as e:
        print(f"{RED}Error loading target file '{args.yaml_file}': {e}{RESET}")
        sys.exit(1)

    if args.schema:
        try:
            schema_data = load_yaml_file(args.schema)
        except Exception as e:
            print(f"{RED}Error loading schema file '{args.schema}': {e}{RESET}")
            sys.exit(1)
    else:
        schema_data = generate_sample_schema()
        print(f"{CYAN}No schema file provided. Using built-in sample schema for validation.{RESET}\n")

    validator = SchemaValidator(schema_data)
    errors = validator.validate(yaml_data)

    if not errors:
        print(f"{GREEN}{BOLD}✓ Validation successful! '{args.yaml_file}' conforms to schema.{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}✗ Found {len(errors)} validation error(s) in '{args.yaml_file}':{RESET}\n")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)


if __name__ == '__main__':
    main()
