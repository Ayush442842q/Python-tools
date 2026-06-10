#!/usr/bin/env python3
"""
JSON Schema Generator

A standalone developer utility to recursively analyze a JSON dataset or document
and automatically generate a draft-07 compliant JSON Schema with inferred types
and constraint rules.

Usage:
    python tools/json_schema_generator.py [options] [json_file]

Examples:
    python tools/json_schema_generator.py sample.json
    python tools/json_schema_generator.py --strict --indent 4 sample.json > schema.json
    cat sample.json | python tools/json_schema_generator.py
"""

import argparse
import json
import sys
from collections import OrderedDict

def infer_schema(data, strict=False, infer_constraints=True):
    """Recursively analyze data and build its corresponding JSON schema."""
    schema = OrderedDict()
    
    if data is None:
        schema['type'] = 'null'
        
    elif isinstance(data, bool):
        schema['type'] = 'boolean'
        
    elif isinstance(data, int):
        schema['type'] = 'integer'
        if infer_constraints:
            schema['minimum'] = data
            schema['maximum'] = data
            
    elif isinstance(data, float):
        schema['type'] = 'number'
        if infer_constraints:
            schema['minimum'] = data
            schema['maximum'] = data
            
    elif isinstance(data, str):
        schema['type'] = 'string'
        if infer_constraints:
            schema['minLength'] = len(data)
            schema['maxLength'] = len(data)
            # Basic checks for format
            if data.startswith(('http://', 'https://')):
                schema['format'] = 'uri'
            elif '@' in data and '.' in data:
                schema['format'] = 'email'
            elif len(data) == 19 and data[4] == '-' and data[7] == '-' and data[10] == 'T':
                schema['format'] = 'date-time'
                
    elif isinstance(data, list):
        schema['type'] = 'array'
        if infer_constraints:
            schema['minItems'] = len(data)
            schema['maxItems'] = len(data)
            
        if not data:
            schema['items'] = {}
        else:
            # Analyze all items in the array
            item_schemas = []
            for item in data:
                item_schemas.append(infer_schema(item, strict, infer_constraints))
                
            # Deduplicate items schemas
            unique_schemas = []
            for item_s in item_schemas:
                if item_s not in unique_schemas:
                    unique_schemas.append(item_s)
                    
            if len(unique_schemas) == 1:
                schema['items'] = unique_schemas[0]
                # If constraints were inferred, we merge them into min/max ranges
                if infer_constraints and unique_schemas[0].get('type') in ('integer', 'number'):
                    vals = [x for x in data if isinstance(x, (int, float))]
                    if vals:
                        schema['items']['minimum'] = min(vals)
                        schema['items']['maximum'] = max(vals)
                elif infer_constraints and unique_schemas[0].get('type') == 'string':
                    lens = [len(x) for x in data if isinstance(x, str)]
                    if lens:
                        schema['items']['minLength'] = min(lens)
                        schema['items']['maxLength'] = max(lens)
            else:
                schema['items'] = {'anyOf': unique_schemas}
                
    elif isinstance(data, dict):
        schema['type'] = 'object'
        properties = OrderedDict()
        required = []
        
        # Process in sorted or original order
        for key, value in data.items():
            properties[key] = infer_schema(value, strict, infer_constraints)
            required.append(key)
            
        schema['properties'] = properties
        if required:
            schema['required'] = required
            
        if strict:
            schema['additionalProperties'] = False
            
    return schema

def main():
    parser = argparse.ArgumentParser(
        description="Generate a draft-07 JSON Schema from a sample JSON file or standard input."
    )
    parser.add_argument(
        'json_file',
        nargs='?',
        help='Path to the sample JSON file. If omitted, reads from standard input.'
    )
    parser.add_argument(
        '-s', '--strict',
        action='store_true',
        help='Enable strict schema mode (sets additionalProperties to false for objects)'
    )
    parser.add_argument(
        '--no-constraints',
        action='store_true',
        help='Disable smart constraint inference (like minimum/maximum, minLength/maxLength, formats)'
    )
    parser.add_argument(
        '-i', '--indent',
        type=int,
        default=2,
        help='Spacing indentation for the output JSON (default: 2)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Write the generated schema to a file instead of stdout'
    )
    
    args = parser.parse_args()
    
    # Read input data
    input_str = ""
    if args.json_file:
        try:
            with open(args.json_file, 'r', encoding='utf-8') as f:
                input_str = f.read()
        except Exception as e:
            print(f"Error reading file '{args.json_file}': {e}", file=sys.stderr)
            return 1
    else:
        # Check if stdin is a TTY (user did not pipe anything)
        if sys.stdin.isatty():
            print("Error: No input JSON file provided, and standard input is empty.", file=sys.stderr)
            parser.print_help()
            return 1
        input_str = sys.stdin.read()
        
    try:
        data = json.loads(input_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing input as valid JSON: {e}", file=sys.stderr)
        return 1
        
    # Generate schema root
    schema_root = OrderedDict()
    schema_root['$schema'] = 'http://json-schema.org/draft-07/schema#'
    schema_root['title'] = 'Generated Schema'
    schema_root['description'] = 'Auto-generated schema from sample dataset'
    
    # Infer inner schema
    inferred = infer_schema(data, strict=args.strict, infer_constraints=not args.no_constraints)
    schema_root.update(inferred)
    
    # Render JSON schema
    out_schema = json.dumps(schema_root, indent=args.indent)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(out_schema + '\n')
            print(f"Schema successfully written to {args.output}")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(out_schema)
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
