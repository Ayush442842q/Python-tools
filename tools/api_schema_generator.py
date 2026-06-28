#!/usr/bin/env python3
"""
API Response Schema Generator - Generate JSON Schema from API responses.

Fetches data from API endpoints and automatically generates JSON Schema
definitions based on the response structure.

Usage:
    python api_schema_generator.py https://api.example.com/users
    python api_schema_generator.py --output schema.json https://api.example.com/data
    python api_schema_generator.py --infer-types --required-fields https://api.example.com/users
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime


def fetch_url(url, headers=None):
    """Fetch content from a URL."""
    if headers is None:
        headers = {
            'User-Agent': 'APISchemaGenerator/1.0',
            'Accept': 'application/json'
        }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8'), response.status
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        sys.exit(1)


def infer_type(value):
    """Infer JSON Schema type from a Python value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        # Check for common date/time formats
        if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            return "string (date)"
        elif re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
            return "string (date-time)"
        elif re.match(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$', value):
            return "string (uuid)"
        elif re.match(r'^https?://', value):
            return "string (uri)"
        elif re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value):
            return "string (email)"
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    return "string"


def generate_schema(data, path="root", infer_types=False, require_fields=False):
    """Generate JSON Schema from data structure."""
    schema = {}
    
    if isinstance(data, dict):
        schema["type"] = "object"
        schema["properties"] = {}
        schema["title"] = path.replace('.', ' ').title()
        
        if require_fields:
            schema["required"] = list(data.keys())
        
        for key, value in data.items():
            if isinstance(value, dict):
                schema["properties"][key] = generate_schema(
                    value, f"{path}.{key}", infer_types, require_fields
                )
            elif isinstance(value, list) and value:
                # Analyze array items
                sample_item = value[0] if value else {}
                item_schema = generate_schema(
                    sample_item, f"{path}.{key}[]", infer_types, require_fields
                )
                schema["properties"][key] = {
                    "type": "array",
                    "items": item_schema,
                    "title": key.replace('_', ' ').title()
                }
                if len(value) > 1:
                    schema["properties"][key]["minItems"] = 1
            else:
                if infer_types and value is not None:
                    inferred = infer_type(value)
                    if " (" in inferred:
                        schema["properties"][key] = {
                            "type": inferred.split(" (")[0],
                            "format": inferred.split(" (")[1].rstrip(")"),
                            "title": key.replace('_', ' ').title()
                        }
                    else:
                        schema["properties"][key] = {
                            "type": inferred,
                            "title": key.replace('_', ' ').title()
                        }
                else:
                    schema["properties"][key] = {
                        "type": "string",
                        "title": key.replace('_', ' ').title(),
                        "description": f"Auto-generated from API response"
                    }
    
    elif isinstance(data, list):
        schema["type"] = "array"
        if data:
            schema["items"] = generate_schema(
                data[0], f"{path}[]", infer_types, require_fields
            )
        schema["title"] = path.replace('.', ' ').title()
    
    else:
        schema["type"] = infer_type(data) if infer_types else "string"
        schema["title"] = path.replace('.', ' ').title()
    
    return schema


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON Schema from API response data"
    )
    parser.add_argument('url', help='API endpoint URL')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--infer-types', action='store_true', 
                        help='Try to infer specific types (dates, emails, etc.)')
    parser.add_argument('--required-fields', action='store_true',
                        help='Mark all fields as required')
    parser.add_argument('--header', '-H', action='append',
                        help='Custom HTTP header (format: Header-Name: value)')
    parser.add_argument('--draft', choices=['draft-07', 'draft-2019-09', 'draft-2020-12'],
                        default='draft-07', help='JSON Schema draft version')
    
    args = parser.parse_args()
    
    # Parse custom headers
    headers = {}
    if args.header:
        for h in args.header:
            if ':' in h:
                name, value = h.split(':', 1)
                headers[name.strip()] = value.strip()
    
    print(f"Fetching: {args.url}")
    content, status = fetch_url(args.url, headers if headers else None)
    print(f"Status: {status}")
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)
    
    # Generate schema
    schema = {
        "$schema": f"http://json-schema.org/{args.draft}/schema#",
        "$id": args.url,
        "title": f"API Response Schema",
        "description": f"Auto-generated from {args.url}",
        "generatedAt": datetime.utcnow().isoformat() + "Z"
    }
    
    # Merge generated schema
    generated = generate_schema(data, "response", args.infer_types, args.required_fields)
    schema.update(generated)
    
    # Output
    output = json.dumps(schema, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Schema written to: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()