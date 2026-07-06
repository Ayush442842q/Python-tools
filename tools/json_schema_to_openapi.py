#!/usr/bin/env python3
"""
JSON Schema to OpenAPI 3.0/3.1 Converter
-----------------------------------------
Converts JSON Schema documents (draft-04, draft-07, 2020-12) into valid OpenAPI 3.0/3.1
components and path object definitions, handling references ($ref), data types, required
fields, enums, and default values. Generates structured JSON or YAML output specs.

Author: Antigravity
License: MIT
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, List, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def convert_schema_to_openapi(json_schema: Dict[str, Any], is_v31: bool = False) -> Dict[str, Any]:
    """Recursively transform JSON Schema keywords into OpenAPI Schema Objects."""
    if not isinstance(json_schema, dict):
        return json_schema

    openapi_schema: Dict[str, Any] = {}

    for key, val in json_schema.items():
        if key in ("$schema", "id", "$id"):
            # Omit JSON Schema meta-schemas in OpenAPI 3.0
            if is_v31 and key == "$schema":
                openapi_schema["$schema"] = val
            continue
        elif key == "definitions":
            # JSON Schema definitions -> OpenAPI $ref target (handled at root level)
            continue
        elif key == "$ref":
            # Fix reference paths: #/definitions/Foo -> #/components/schemas/Foo
            ref_str = str(val)
            ref_str = ref_str.replace("#/definitions/", "#/components/schemas/")
            openapi_schema["$ref"] = ref_str
        elif key == "type":
            # OpenAPI 3.0 does not support array types like ["string", "null"]
            if isinstance(val, list):
                if "null" in val:
                    non_null = [t for t in val if t != "null"]
                    openapi_schema["type"] = non_null[0] if non_null else "string"
                    if not is_v31:
                        openapi_schema["nullable"] = True
                else:
                    openapi_schema["type"] = val[0]
            else:
                openapi_schema["type"] = val
        elif key == "properties" and isinstance(val, dict):
            openapi_schema["properties"] = {
                prop_k: convert_schema_to_openapi(prop_v, is_v31)
                for prop_k, prop_v in val.items()
            }
        elif key in ("items", "additionalProperties") and isinstance(val, dict):
            openapi_schema[key] = convert_schema_to_openapi(val, is_v31)
        elif key in ("oneOf", "anyOf", "allOf") and isinstance(val, list):
            openapi_schema[key] = [convert_schema_to_openapi(item, is_v31) for item in val]
        else:
            openapi_schema[key] = val

    return openapi_schema


def dump_simple_yaml(data: Any, indent_level: int = 0) -> str:
    """Zero-dependency lightweight YAML dumper for OpenAPI objects."""
    indent = "  " * indent_level
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{indent}{k}:")
                lines.append(dump_simple_yaml(v, indent_level + 1))
            else:
                val_str = json.dumps(v) if isinstance(v, str) and (":" in v or "\n" in v) else str(v)
                lines.append(f"{indent}{k}: {val_str}")
        return "\n".join(lines)
    elif isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.append(dump_simple_yaml(item, indent_level + 1))
            else:
                lines.append(f"{indent}- {item}")
        return "\n".join(lines)
    else:
        return f"{indent}{data}"


def build_openapi_spec(
    json_schema: Dict[str, Any],
    title: str,
    version: str,
    endpoint: str,
    openapi_version: str
) -> Dict[str, Any]:
    """Wrap converted JSON schema into full OpenAPI 3.0/3.1 document."""
    is_v31 = openapi_version.startswith("3.1")
    schema_name = json_schema.get("title", "GeneratedModel").replace(" ", "")
    
    converted_main = convert_schema_to_openapi(json_schema, is_v31)
    
    # Handle definitions -> components/schemas
    component_schemas: Dict[str, Any] = {
        schema_name: converted_main
    }
    
    defs = json_schema.get("definitions") or json_schema.get("$defs")
    if isinstance(defs, dict):
        for def_name, def_body in defs.items():
            component_schemas[def_name] = convert_schema_to_openapi(def_body, is_v31)

    endpoint_path = f"/{endpoint.strip('/')}"
    
    spec = {
        "openapi": openapi_version,
        "info": {
            "title": title,
            "version": version,
            "description": f"Auto-generated OpenAPI spec from JSON Schema: {schema_name}"
        },
        "paths": {
            endpoint_path: {
                "get": {
                    "summary": f"Retrieve {schema_name} resource",
                    "operationId": f"get{schema_name}",
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": f"#/components/schemas/{schema_name}"
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": f"Create new {schema_name}",
                    "operationId": f"create{schema_name}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": f"#/components/schemas/{schema_name}"
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created Successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": f"#/components/schemas/{schema_name}"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": component_schemas
        }
    }
    
    return spec


DEMO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "UserProfile",
    "type": "object",
    "required": ["id", "username", "email"],
    "properties": {
        "id": {
            "type": "integer",
            "description": "Unique identifier"
        },
        "username": {
            "type": "string",
            "minLength": 3
        },
        "email": {
            "type": "string",
            "format": "email"
        },
        "role": {
            "type": "string",
            "enum": ["admin", "user", "guest"],
            "default": "user"
        },
        "address": {
            "$ref": "#/definitions/Address"
        }
    },
    "definitions": {
        "Address": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "zipcode": {"type": "string"}
            }
        }
    }
}


def main():
    parser = argparse.ArgumentParser(description="JSON Schema to OpenAPI 3.0/3.1 Converter")
    parser.add_argument("schema_file", nargs="?", help="JSON Schema file to convert (or stdin)")
    parser.add_argument("--title", default="API Documentation", help="API Title for OpenAPI spec")
    parser.add_argument("--version", default="1.0.0", help="API Version string")
    parser.add_argument("--openapi-version", choices=["3.0.3", "3.1.0"], default="3.0.3", help="OpenAPI version target")
    parser.add_argument("--endpoint", default="users", help="Base route endpoint path")
    parser.add_argument("--format", choices=["json", "yaml"], default="yaml", help="Output format")
    parser.add_argument("--output", help="Write output spec to file")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample JSON Schema input")

    args = parser.parse_args()

    if args.demo:
        print(f"{BOLD}{CYAN}=== Running JSON Schema to OpenAPI Converter Demo ==={RESET}\n")
        schema_data = DEMO_SCHEMA
    elif args.schema_file:
        if not os.path.exists(args.schema_file):
            print(f"{RED}Error: Schema file '{args.schema_file}' not found.{RESET}")
            sys.exit(1)
        with open(args.schema_file, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    else:
        if not sys.stdin.isatty():
            schema_data = json.load(sys.stdin)
        else:
            parser.print_help()
            sys.exit(0)

    spec = build_openapi_spec(
        schema_data,
        args.title,
        args.version,
        args.endpoint,
        args.openapi_version
    )

    if args.format == "yaml":
        output_str = dump_simple_yaml(spec)
    else:
        output_str = json.dumps(spec, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"{GREEN}OpenAPI Spec saved to {args.output}{RESET}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
