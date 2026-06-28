#!/usr/bin/env python3
"""
YAML Validator
Validate YAML syntax, structure, and schema compliance.

Usage:
    python yaml_validator.py file1.yaml file2.yaml ... [--schema schema.yaml] [--strict]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Installing PyYAML...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyYAML", "-q"])
    import yaml


def validate_yaml_syntax(content: str) -> Tuple[bool, Optional[str], Optional[Any]]:
    """
    Validate YAML syntax.
    
    Returns:
        Tuple of (is_valid, error_message, parsed_data)
    """
    try:
        data = yaml.safe_load(content)
        return True, None, data
    except yaml.YAMLError as e:
        error_msg = str(e)
        # Try to extract line/column info
        if hasattr(e, 'problem_mark') and e.problem_mark:
            mark = e.problem_mark
            error_msg = f"Line {mark.line + 1}, Column {mark.column + 1}: {e.problem}"
        return False, error_msg, None


def validate_yaml_structure(data: Any, strict: bool = False) -> List[str]:
    """
    Validate YAML structure and common issues.
    
    Args:
        data: Parsed YAML data
        strict: Enable strict validation mode
    
    Returns:
        List of warning/error messages
    """
    issues = []
    
    if data is None:
        issues.append("⚠️  Empty YAML document")
        return issues
    
    if isinstance(data, dict):
        # Check for duplicate keys (yaml.safe_load already handles this)
        # Check for common issues
        
        # Warn about empty top-level
        if not data:
            issues.append("⚠️  Empty mapping at root level")
        
        # Check for nested empty collections
        def check_nested(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, dict) and not value:
                        issues.append(f"⚠️  Empty mapping at '{current_path}'")
                    elif isinstance(value, list) and not value:
                        issues.append(f"⚠️  Empty sequence at '{current_path}'")
                    else:
                        check_nested(value, current_path)
        
        check_nested(data)
        
        # In strict mode, check for additional issues
        if strict:
            # Check for non-string keys
            def check_keys(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if not isinstance(key, str):
                            current_path = f"{path}.{key}" if path else str(key)
                            issues.append(f"⚠️  Non-string key at '{current_path}': {type(key).__name__}")
                        check_keys(value, f"{path}.{key}" if path else str(key))
            
            check_keys(data)
    
    elif isinstance(data, list):
        if not data:
            issues.append("⚠️  Empty sequence at root level")
        
        if strict:
            # Check for mixed types in lists
            if len(data) > 1:
                types = set(type(item).__name__ for item in data if item is not None)
                if len(types) > 1:
                    issues.append(f"⚠️  Mixed types in root sequence: {', '.join(types)}")
    
    return issues


def load_schema(schema_path: str) -> Optional[Dict]:
    """Load and parse a YAML schema file."""
    try:
        with open(schema_path, 'r') as f:
            schema = yaml.safe_load(f)
        return schema
    except Exception as e:
        return {"error": f"Failed to load schema: {e}"}


def validate_against_schema(data: Any, schema: Dict, path: str = "") -> List[str]:
    """
    Validate data against a simple schema.
    
    Schema format (simplified):
    ```yaml
    type: object  # or array, string, number, boolean
    required:
      - field1
      - field2
    properties:
      field1:
        type: string
        min_length: 1
      field2:
        type: integer
        minimum: 0
        maximum: 100
      field3:
        type: array
        items:
          type: string
    ```
    """
    issues = []
    
    if not schema or "error" in schema:
        return [f"⚠️  Schema error: {schema.get('error', 'Unknown')}"]
    
    def validate_type(value: Any, expected_type: str, current_path: str) -> bool:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }
        
        python_type = type_map.get(expected_type)
        if python_type is None:
            return True  # Unknown type, skip validation
        
        # Special case: in YAML, integers are also valid numbers
        if expected_type == "number" and isinstance(value, bool):
            return False
        if expected_type == "integer" and isinstance(value, bool):
            return False
        
        return isinstance(value, python_type)
    
    def validate_value(value: Any, field_schema: Dict, current_path: str):
        expected_type = field_schema.get("type")
        
        # Type validation
        if expected_type and not validate_type(value, expected_type, current_path):
            issues.append(f"❌ Type mismatch at '{current_path}': expected {expected_type}, got {type(value).__name__}")
            return
        
        # String constraints
        if isinstance(value, str):
            min_length = field_schema.get("min_length")
            max_length = field_schema.get("max_length")
            pattern = field_schema.get("pattern")
            
            if min_length is not None and len(value) < min_length:
                issues.append(f"❌ String at '{current_path}' is too short (min: {min_length})")
            
            if max_length is not None and len(value) > max_length:
                issues.append(f"❌ String at '{current_path}' is too long (max: {max_length})")
            
            if pattern:
                import re
                if not re.match(pattern, value):
                    issues.append(f"❌ String at '{current_path}' doesn't match pattern: {pattern}")
        
        # Number constraints
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = field_schema.get("minimum")
            maximum = field_schema.get("maximum")
            
            if minimum is not None and value < minimum:
                issues.append(f"❌ Number at '{current_path}' is below minimum: {minimum}")
            
            if maximum is not None and value > maximum:
                issues.append(f"❌ Number at '{current_path}' is above maximum: {maximum}")
        
        # Array validation
        if isinstance(value, list):
            min_items = field_schema.get("min_items")
            max_items = field_schema.get("max_items")
            items_schema = field_schema.get("items")
            
            if min_items is not None and len(value) < min_items:
                issues.append(f"❌ Array at '{current_path}' has too few items (min: {min_items})")
            
            if max_items is not None and len(value) > max_items:
                issues.append(f"❌ Array at '{current_path}' has too many items (max: {max_items})")
            
            if items_schema:
                for i, item in enumerate(value):
                    validate_value(item, items_schema, f"{current_path}[{i}]")
        
        # Object validation
        if isinstance(value, dict):
            required_fields = field_schema.get("required", [])
            properties = field_schema.get("properties", {})
            
            for req_field in required_fields:
                if req_field not in value:
                    issues.append(f"❌ Missing required field '{req_field}' at '{current_path}'")
            
            for key, val in value.items():
                field_path = f"{current_path}.{key}" if current_path else key
                if key in properties:
                    validate_value(val, properties[key], field_path)
    
    # Start validation
    schema_type = schema.get("type")
    if schema_type:
        if not validate_type(data, schema_type, path):
            issues.append(f"❌ Root type mismatch: expected {schema_type}, got {type(data).__name__}")
            return issues
    
    validate_value(data, schema, path)
    
    return issues


def format_output(results: List[Dict], json_format: bool = False) -> str:
    """Format validation results for output."""
    if json_format:
        return json.dumps(results, indent=2)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("YAML VALIDATOR")
    output_lines.append("=" * 80)
    
    valid_count = 0
    
    for result in results:
        file_path = result["file"]
        
        if result.get("schema_error"):
            output_lines.append(f"\n📄 {file_path}")
            output_lines.append(f"  Schema validation: {result['schema_error']}")
        elif not result["syntax_valid"]:
            valid_count += 0
            output_lines.append(f"\n❌ {file_path}")
            output_lines.append(f"  Syntax error: {result['syntax_error']}")
        else:
            valid_count += 1
            output_lines.append(f"\n✅ {file_path}")
            output_lines.append(f"  Syntax: Valid")
            
            if result.get("structure_issues"):
                for issue in result["structure_issues"]:
                    output_lines.append(f"  {issue}")
            
            if result.get("schema_issues"):
                for issue in result["schema_issues"]:
                    output_lines.append(f"  {issue}")
            
            if result.get("data_stats"):
                stats = result["data_stats"]
                output_lines.append(f"  Stats: {stats.get('type', 'N/A')}, "
                                  f"{stats.get('keys', stats.get('items', 0))} "
                                  f"{stats.get('type', 'items')}")
    
    output_lines.append("\n" + "=" * 80)
    output_lines.append(f"Summary: {valid_count}/{len(results)} files valid")
    output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate YAML syntax, structure, and schema compliance."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="YAML files to validate"
    )
    parser.add_argument(
        "--schema", "-s",
        type=str,
        help="Schema file for validation (YAML format)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation mode"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show detailed statistics about YAML structure"
    )
    
    args = parser.parse_args()
    
    if not args.files:
        parser.print_help()
        print("\nError: No YAML files provided.")
        sys.exit(1)
    
    # Load schema if provided
    schema = None
    if args.schema:
        schema = load_schema(args.schema)
        if schema and "error" in schema:
            print(f"Schema error: {schema['error']}")
            sys.exit(1)
    
    results = []
    
    for file_path in args.files:
        result = {
            "file": file_path,
            "syntax_valid": False,
            "syntax_error": None,
            "structure_issues": [],
            "schema_issues": [],
            "data_stats": None,
            "schema_error": None
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Syntax validation
            syntax_valid, syntax_error, data = validate_yaml_syntax(content)
            result["syntax_valid"] = syntax_valid
            result["syntax_error"] = syntax_error
            
            if syntax_valid:
                # Structure validation
                structure_issues = validate_yaml_structure(data, strict=args.strict)
                result["structure_issues"] = structure_issues
                
                # Schema validation
                if schema:
                    schema_issues = validate_against_schema(data, schema)
                    result["schema_issues"] = schema_issues
                
                # Statistics
                if args.stats and data is not None:
                    if isinstance(data, dict):
                        result["data_stats"] = {
                            "type": "object",
                            "keys": len(data)
                        }
                    elif isinstance(data, list):
                        result["data_stats"] = {
                            "type": "array",
                            "items": len(data)
                        }
                    else:
                        result["data_stats"] = {
                            "type": type(data).__name__
                        }
        
        except FileNotFoundError:
            result["syntax_error"] = f"File not found: {file_path}"
        except Exception as e:
            result["syntax_error"] = f"Error reading file: {e}"
        
        results.append(result)
    
    output = format_output(results, json_format=args.json)
    print(output)
    
    # Exit with error if any invalid files
    invalid_count = sum(1 for r in results if not r["syntax_valid"])
    if invalid_count > 0:
        sys.exit(1)
    
    # Exit with error if schema validation failed
    if schema and any(r.get("schema_issues") for r in results):
        sys.exit(2)


if __name__ == "__main__":
    main()