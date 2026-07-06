#!/usr/bin/env python3
"""
Jinja2 Template Variable Extractor & JSON Schema Generator
Statically analyzes Jinja2 template files and generates a JSON Schema representing the required input context.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, Any, List, Set, Tuple

def clean_var_name(name: str) -> str:
    """Removes Jinja filters, spaces, and brackets."""
    # Handle filters like: var | default('foo')
    name = name.split('|')[0].strip()
    # Remove array access or dict keys: var['key'] or var[0]
    name = re.sub(r'\[.*?\]', '', name)
    return name.strip()

def infer_schema_from_template(content: str) -> Dict[str, Any]:
    # Regex definitions for Jinja tags
    var_pattern = re.compile(r'\{\{\s*(.*?)\s*\}\}')
    for_pattern = re.compile(r'\{%\s*for\s+(.*?)\s+in\s+(.*?)\s*%\}')
    if_pattern = re.compile(r'\{%\s*(?:if|elif)\s+(.*?)\s*%\}')
    endfor_pattern = re.compile(r'\{%\s*endfor\s*%\}')

    # Keep track of active loop variables and loop contexts
    # loop_stack stores tuples of (loop_variable, array_variable_name)
    loop_stack: List[Tuple[str, str]] = []
    
    # Store schema types
    # schema_tree will store schema definitions for fields.
    properties: Dict[str, Any] = {}
    
    # We will process line by line to support tracking loop blocks
    lines = content.splitlines()
    
    for line in lines:
        # 1. Check for end of loop
        if endfor_pattern.search(line):
            if loop_stack:
                loop_stack.pop()

        # 2. Check for start of loop: {% for item in items %}
        for_match = for_pattern.search(line)
        if for_match:
            item_var = for_match.group(1).strip()
            items_raw = for_match.group(2).strip()
            
            # Resolve if items_raw is a property of another object
            items_clean = clean_var_name(items_raw)
            loop_stack.append((item_var, items_clean))
            
            # Set items_clean as array type in properties
            # If the variable is inside parent loop, we'll nest it later
            _set_property_type(properties, items_clean, "array", loop_stack[:-1])
            continue

        # 3. Check for conditional expressions: {% if user.is_logged_in %}
        if_matches = if_pattern.findall(line)
        for cond in if_matches:
            # We simplify by splitting on comparison operators and logical operators
            tokens = re.split(r'\s+(?:and|or|==|!=|<|>|<=|>=|in|not)\s+', cond)
            for token in tokens:
                token = token.strip()
                # Skip numeric constants, strings, and boolean values
                if (token.startswith('"') and token.endswith('"')) or \
                   (token.startswith("'") and token.endswith("'")) or \
                   token.isdigit() or token in ("True", "False", "none", "None"):
                    continue
                
                var_name = clean_var_name(token)
                if var_name and not var_name.startswith('loop.'):
                    # Conditionals usually imply a boolean or presence check
                    _set_property_type(properties, var_name, "boolean", loop_stack)

        # 4. Check for variable output: {{ user.name }}
        var_matches = var_pattern.findall(line)
        for var_expr in var_matches:
            var_name = clean_var_name(var_expr)
            if var_name and not var_name.startswith('loop.'):
                # Standard variable output defaults to string
                _set_property_type(properties, var_name, "string", loop_stack)

    # Wrap in root JSON Schema object
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "JinjaTemplateContext",
        "description": "Auto-generated JSON Schema for Jinja2 template context validation",
        "type": "object",
        "properties": properties,
        "required": list(properties.keys())
    }
    return schema

def _set_property_type(properties: Dict[str, Any], path: str, inferred_type: str, loop_stack: List[Tuple[str, str]]):
    """
    Sets the property type at the specified dot-separated path, handling nesting and loop scopes.
    """
    parts = path.split('.')
    root_part = parts[0]
    
    # Resolve loop variables
    # If root_part matches a loop variable in stack, we need to map it into the array's items schema.
    for loop_var, array_var in reversed(loop_stack):
        if root_part == loop_var:
            # We are modifying elements inside an array
            # We need to find or create the array schema at array_var
            array_schema = _get_or_create_array_schema(properties, array_var)
            
            # If there are subparts (e.g. item.name), resolve the nested path on the array items object
            if len(parts) > 1:
                sub_path = ".".join(parts[1:])
                _set_property_type(array_schema["items"]["properties"], sub_path, inferred_type, [])
            else:
                # Direct loop variable usage: e.g. {{ item }}
                # Change item type from object to primitive string
                array_schema["items"] = {"type": inferred_type}
            return

    # Standard non-loop nested variable resolution
    current = properties
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # Last part: set the type
            if part not in current:
                if inferred_type == "array":
                    current[part] = {"type": "array", "items": {"type": "object", "properties": {}}}
                else:
                    current[part] = {"type": inferred_type}
            else:
                # Upgrade type if current type is primitive but we found object/array subparts
                if inferred_type == "array" and current[part].get("type") != "array":
                    current[part] = {"type": "array", "items": {"type": "object", "properties": {}}}
        else:
            # Intermediate path parts: must be an object
            if part not in current:
                current[part] = {"type": "object", "properties": {}}
            elif current[part].get("type") != "object":
                current[part] = {"type": "object", "properties": {}}
            current = current[part]["properties"]

def _get_or_create_array_schema(properties: Dict[str, Any], path: str) -> Dict[str, Any]:
    parts = path.split('.')
    current = properties
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            if part not in current or current[part].get("type") != "array":
                current[part] = {"type": "array", "items": {"type": "object", "properties": {}}}
            return current[part]
        else:
            if part not in current or current[part].get("type") != "object":
                current[part] = {"type": "object", "properties": {}}
            current = current[part]["properties"]
    return {}

def main():
    parser = argparse.ArgumentParser(
        description="Jinja2 Template Variable Extractor & JSON Schema Generator - Statically infers template inputs schema."
    )
    parser.add_argument("template", help="Path to the Jinja2 template file")
    parser.add_argument("-o", "--output", help="Output file path to save JSON Schema (default: stdout)")
    args = parser.parse_args()

    if not os.path.exists(args.template):
        print(f"Error: Template file not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.template, "r", encoding="utf-8") as f:
            content = f.read()
        
        schema = infer_schema_from_template(content)
        schema_str = json.dumps(schema, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(schema_str + "\n")
            print(f"JSON Schema written successfully to: {args.output}")
        else:
            print(schema_str)

    except Exception as e:
        print(f"Failed to analyze template: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
