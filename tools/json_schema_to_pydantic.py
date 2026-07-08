#!/usr/bin/env python3
"""
JSON Schema to Pydantic v2 Model Generator
A zero-dependency Python utility to compile standard JSON Schema definitions (draft-07 or newer)
into type-annotated, validated Python source code using Pydantic v2 BaseModel classes.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Set, Union


class SchemaCompiler:
    """Recursively compiles a JSON Schema structure into Pydantic models."""

    def __init__(self, root_name: str = "RootModel"):
        self.root_name = root_name
        self.models: List[str] = []
        self.compiled_classes: Set[str] = set()

    def clean_class_name(self, name: str) -> str:
        """Converts strings (e.g. kebab-case, snake_case) into PascalCase."""
        parts = name.replace("-", "_").split("_")
        return "".join(p.capitalize() for p in parts if p)

    def map_type(self, prop_schema: dict, prop_name: str) -> str:
        """
        Maps a property's JSON Schema type definition to a Python type annotation.
        Recursively compiles sub-objects and sub-arrays.
        """
        if not isinstance(prop_schema, dict):
            return "Any"

        js_type = prop_schema.get("type")
        
        # Support schema reference or title for sub-model naming
        sub_title = prop_schema.get("title") or prop_schema.get("description", prop_name)
        class_name = self.clean_class_name(sub_title)

        if js_type == "object" or "properties" in prop_schema:
            if not class_name or class_name in self.compiled_classes:
                class_name = f"{class_name}SubModel"
            self.compile_object(prop_schema, class_name)
            return class_name

        elif js_type == "array":
            items = prop_schema.get("items")
            if isinstance(items, dict):
                item_type = self.map_type(items, f"{prop_name}Item")
                return f"List[{item_type}]"
            elif isinstance(items, list):
                # Multiple types supported in array positional elements
                types = [self.map_type(t, f"{prop_name}Item") for t in items]
                union_types = ", ".join(types)
                return f"List[Union[{union_types}]]"
            return "List[Any]"

        # Handle basic mappings
        type_mapping = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "null": "None",
        }

        if isinstance(js_type, list):
            # Handle multiple types (e.g. ["string", "null"])
            mapped_types = []
            for t in js_type:
                if t in type_mapping:
                    mapped_types.append(type_mapping[t])
                else:
                    mapped_types.append("Any")
            # De-duplicate
            mapped_types = list(set(mapped_types))
            if len(mapped_types) == 1:
                return mapped_types[0]
            elif "None" in mapped_types:
                mapped_types.remove("None")
                non_none_type = f"Union[{', '.join(mapped_types)}]" if len(mapped_types) > 1 else mapped_types[0]
                return f"Optional[{non_none_type}]"
            return f"Union[{', '.join(mapped_types)}]"

        return type_mapping.get(js_type, "Any")

    def build_field_validator(self, prop_schema: dict) -> str:
        """
        Builds a Pydantic Field(...) validation block from JSON Schema validation keywords.
        """
        args = []
        
        # Mapping standard validation constraints
        if "default" in prop_schema:
            default = prop_schema["default"]
            if isinstance(default, str):
                args.append(f'default="{default}"')
            else:
                args.append(f"default={default}")
        
        if "description" in prop_schema:
            desc = prop_schema["description"].replace('"', '\\"')
            args.append(f'description="{desc}"')
            
        if "minimum" in prop_schema:
            args.append(f"ge={prop_schema['minimum']}")
            
        if "exclusiveMinimum" in prop_schema:
            args.append(f"gt={prop_schema['exclusiveMinimum']}")
            
        if "maximum" in prop_schema:
            args.append(f"le={prop_schema['maximum']}")
            
        if "exclusiveMaximum" in prop_schema:
            args.append(f"lt={prop_schema['exclusiveMaximum']}")
            
        if "minLength" in prop_schema:
            args.append(f"min_length={prop_schema['minLength']}")
            
        if "maxLength" in prop_schema:
            args.append(f"max_length={prop_schema['maxLength']}")
            
        if "pattern" in prop_schema:
            pat = prop_schema["pattern"].replace('"', '\\"')
            args.append(f'pattern=r"{pat}"')
            
        if "minItems" in prop_schema:
            args.append(f"min_length={prop_schema['minItems']}")
            
        if "maxItems" in prop_schema:
            args.append(f"max_length={prop_schema['maxItems']}")

        if args:
            return f"Field({', '.join(args)})"
        return ""

    def compile_object(self, schema: dict, class_name: str):
        """Compiles a single object schema definition to a BaseModel class string."""
        if class_name in self.compiled_classes:
            return
            
        self.compiled_classes.add(class_name)
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        description = schema.get("description", "")

        class_lines = []
        class_lines.append(f"class {class_name}(BaseModel):")
        
        if description:
            class_lines.append(f'    """{description}"""')
            
        if not properties:
            class_lines.append("    pass")
            class_lines.append("")
            self.models.append("\n".join(class_lines))
            return

        for prop_name, prop_schema in properties.items():
            py_type = self.map_type(prop_schema, prop_name)
            is_required = prop_name in required
            
            # Build Pydantic Field parameters
            field_def = self.build_field_validator(prop_schema)
            
            if is_required:
                if field_def:
                    # Required fields with constraints use Field(...) with no default or default=...
                    class_lines.append(f"    {prop_name}: {py_type} = {field_def}")
                else:
                    class_lines.append(f"    {prop_name}: {py_type}")
            else:
                # Optional fields
                if not py_type.startswith("Optional[") and py_type != "Any" and py_type != "None":
                    py_type = f"Optional[{py_type}]"
                
                # Check if default is already defined in Field
                if "default=" in field_def:
                    class_lines.append(f"    {prop_name}: {py_type} = {field_def}")
                else:
                    if field_def:
                        # Add default=None to field validator
                        if field_def.endswith("Field()"):
                            field_def = "Field(default=None)"
                        else:
                            field_def = field_def.replace("Field(", "Field(default=None, ")
                        class_lines.append(f"    {prop_name}: {py_type} = {field_def}")
                    else:
                        class_lines.append(f"    {prop_name}: {py_type} = None")

        class_lines.append("")
        self.models.append("\n".join(class_lines))

    def get_code(self) -> str:
        """Returns the compiled Python script containing Pydantic schemas."""
        header = [
            "# Generated code by json_schema_to_pydantic.py",
            "from typing import Any, Dict, List, Optional, Union",
            "from pydantic import BaseModel, Field",
            "",
            "",
        ]
        # We join models in insertion order. Sub-models were compiled and inserted first,
        # ensuring dependencies are declared before their parent classes.
        return "\n".join(header) + "\n".join(self.models)


def main():
    parser = argparse.ArgumentParser(
        description="JSON Schema to Pydantic v2 Class Compiler. "
                    "Converts JSON Schema files to Python code defining Pydantic BaseModel schemas."
    )
    parser.add_argument("schema_file", help="Path to input JSON Schema file")
    parser.add_argument("-o", "--output", help="Path to write compiled Python file (default: stdout)")
    parser.add_argument("-n", "--name", default="Model", help="Name of the root BaseModel class (default: Model)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.schema_file):
        print(f"[-] Error: File not found: {args.schema_file}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.schema_file, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[-] Error: Failed to parse input file as JSON: {e}", file=sys.stderr)
        sys.exit(1)
        
    compiler = SchemaCompiler(root_name=args.name)
    
    # Check if root is actually a valid schema object structure
    if not isinstance(schema_data, dict):
        print("[-] Error: Root of JSON Schema must be a JSON object.", file=sys.stderr)
        sys.exit(1)
        
    # Start recursive compilation from root
    root_class_name = compiler.clean_class_name(schema_data.get("title") or args.name)
    compiler.compile_object(schema_data, root_class_name)
    
    compiled_code = compiler.get_code()
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(compiled_code)
            print(f"[+] Successfully compiled schema to {args.output}")
        except Exception as e:
            print(f"[-] Failed to write output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(compiled_code)


if __name__ == "__main__":
    main()
