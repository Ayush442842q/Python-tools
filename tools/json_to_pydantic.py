#!/usr/bin/env python3
"""
JSON to Pydantic Model Generator
Generates clean, PEP-8 compliant Pydantic V2 models from JSON payloads or files.
Recursively handles nested dictionaries, arrays, lists of mixed types, and translates
invalid Python identifiers using Pydantic's Field(alias=...).
"""

import json
import sys
import re
import argparse
from typing import Any, Dict, List, Set, Tuple, Union

# Python keywords and built-in names to avoid as field names
PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "id", "type", "list", "dict", "set", "tuple", "str", "int", "float", "bool"
}

def clean_identifier(name: str) -> str:
    """Converts a JSON key into a valid Python identifier."""
    # Replace non-alphanumeric characters with underscores
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Strip leading digits
    cleaned = re.sub(r'^[0-9]+', '', cleaned)
    # Ensure it's not empty
    if not cleaned:
        cleaned = "field"
    # Append underscore if it conflicts with Python keywords
    if cleaned in PYTHON_KEYWORDS:
        cleaned = f"{cleaned}_"
    return cleaned

class SchemaNode:
    """Represents a type node in the inferred schema tree."""
    def __init__(self, name: str):
        self.name = name
        self.types: Set[str] = set()
        # For object types: key -> SchemaNode
        self.properties: Dict[str, 'SchemaNode'] = {}
        # For list types: SchemaNode representing items
        self.item_schema: Optional['SchemaNode'] = None
        # Flag if this field can be null/optional
        self.is_optional = False

    def merge_value(self, val: Any) -> None:
        """Updates the schema node by observing a value."""
        if val is None:
            self.is_optional = True
            return

        t = type(val)
        if t == dict:
            self.types.add("object")
            for k, v in val.items():
                if k not in self.properties:
                    self.properties[k] = SchemaNode(clean_identifier(k))
                self.properties[k].merge_value(v)
        elif t == list:
            self.types.add("array")
            if not self.item_schema:
                self.item_schema = SchemaNode(f"{self.name}Item")
            for item in val:
                self.item_schema.merge_value(item)
        elif t == bool:
            self.types.add("bool")
        elif t == int:
            self.types.add("int")
        elif t == float:
            self.types.add("float")
        elif t == str:
            self.types.add("str")
        else:
            self.types.add("Any")

    def merge_schema(self, other: 'SchemaNode') -> None:
        """Merges another schema node into this one."""
        self.types.update(other.types)
        self.is_optional = self.is_optional or other.is_optional
        
        # Merge properties
        for k, other_node in other.properties.items():
            if k not in self.properties:
                self.properties[k] = SchemaNode(clean_identifier(k))
            self.properties[k].merge_schema(other_node)
            
        # Merge list items
        if other.item_schema:
            if not self.item_schema:
                self.item_schema = SchemaNode(f"{self.name}Item")
            self.item_schema.merge_schema(other.item_schema)


class PydanticGenerator:
    def __init__(self, root_name: str = "RootModel", use_optional: bool = True):
        self.root_name = root_name
        self.use_optional = use_optional
        # Map of ClassName -> Python class definition text
        self.classes: Dict[str, str] = {}
        # Used class names to avoid collision
        self.generated_class_names: Set[str] = set()

    def get_unique_classname(self, base_name: str) -> str:
        """Generates a unique, PascalCase class name."""
        # Convert snake_case/kebab-case or spaced name to PascalCase
        camel = "".join(w.capitalize() for w in re.split(r'[-_\s]+', base_name))
        # Remove non-alphanumeric chars
        camel = re.sub(r'[^a-zA-Z0-9]', '', camel)
        if not camel:
            camel = "Model"
        
        candidate = camel
        counter = 1
        while candidate in self.generated_class_names:
            candidate = f"{camel}{counter}"
            counter += 1
        
        self.generated_class_names.add(candidate)
        return candidate

    def determine_type_str(self, node: SchemaNode) -> Tuple[str, List[str]]:
        """
        Determines the type annotation for a schema node.
        Returns the type string and any nested model classes that need to be defined.
        """
        if not node.types:
            return "Any", []

        # If multiple types, union them
        type_parts = []
        deps = []

        if "object" in node.types:
            # We must generate a class for this object
            class_name = self.get_unique_classname(node.name)
            deps.append((class_name, node))
            type_parts.append(class_name)
        
        if "array" in node.types and node.item_schema:
            item_type, item_deps = self.determine_type_str(node.item_schema)
            deps.extend(item_deps)
            type_parts.append(f"List[{item_type}]")
            
        # Primitive types
        for t in ["str", "int", "float", "bool", "Any"]:
            if t in node.types:
                # If both int and float are present, float usually suffices, but we can list both
                if t == "int" and "float" in node.types:
                    continue
                type_parts.append(t)

        # Build union if multiple types
        if len(type_parts) > 1:
            type_str = f"Union[{', '.join(type_parts)}]"
        elif type_parts:
            type_str = type_parts[0]
        else:
            type_str = "Any"

        if node.is_optional and self.use_optional:
            type_str = f"Optional[{type_str}]"

        return type_str, deps

    def generate_class_definition(self, class_name: str, node: SchemaNode) -> str:
        """Generates the code for a single Pydantic class."""
        lines = [f"class {class_name}(BaseModel):"]
        if not node.properties:
            lines.append("    pass")
            lines.append("")
            return "\n".join(lines)

        pending_classes = []
        for orig_key, prop_node in node.properties.items():
            py_field_name = clean_identifier(orig_key)
            type_str, field_deps = self.determine_type_str(prop_node)
            pending_classes.extend(field_deps)

            # Determine field metadata (aliases, etc.)
            field_args = []
            if py_field_name != orig_key:
                field_args.append(f'alias="{orig_key}"')
            
            if prop_node.is_optional and self.use_optional:
                field_args.append("default=None")

            if field_args:
                field_def = f" = Field({', '.join(field_args)})"
            else:
                field_def = ""

            lines.append(f"    {py_field_name}: {type_str}{field_def}")
        
        lines.append("")
        
        # Recursively generate dependees first (so they are declared before use)
        for dep_class_name, dep_node in pending_classes:
            if dep_class_name not in self.classes:
                # Place-hold to prevent infinite recursion in cyclic refs
                self.classes[dep_class_name] = "" 
                self.classes[dep_class_name] = self.generate_class_definition(dep_class_name, dep_node)

        return "\n".join(lines)

    def generate(self, root_node: SchemaNode) -> str:
        """Generates the complete Python file contents containing the Pydantic models."""
        self.classes.clear()
        self.generated_class_names.clear()

        # Generate root and all sub-classes
        root_class_name = self.get_unique_classname(self.root_name)
        root_class_def = self.generate_class_definition(root_class_name, root_node)
        self.classes[root_class_name] = root_class_def

        # Assemble imports and class definitions
        output = [
            "from pydantic import BaseModel, Field",
            "from typing import Any, Dict, List, Optional, Union",
            "",
            ""
        ]

        # Add all generated class definitions in reverse order of creation
        # (inner classes are defined first, root is last)
        for class_name in list(self.generated_class_names):
            class_def = self.classes.get(class_name)
            if class_def:
                output.append(class_def)

        return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Pydantic V2 models from JSON payloads or schema definitions."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Path to JSON file. Reads from standard input if omitted."
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Path to output python file. Prints to stdout if omitted."
    )
    parser.add_argument(
        "-r", "--root-name",
        default="RootModel",
        help="Name of the root Pydantic model (default: RootModel)."
    )
    parser.add_argument(
        "--no-optional",
        action="store_true",
        help="Do not wrap nullable or missing fields in Optional[] (default: False)."
    )

    args = parser.parse_args()

    # Read and parse JSON input
    try:
        raw_content = args.input.read().strip()
        if not raw_content:
            print("Error: Empty input.", file=sys.stderr)
            sys.exit(1)
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    # Infer schema
    root_node = SchemaNode(args.root_name)
    if isinstance(data, list):
        # Merge all list elements to get a robust root schema
        root_node.types.add("array")
        item_node = SchemaNode(f"{args.root_name}Item")
        for item in data:
            item_node.merge_value(item)
        root_node.item_schema = item_node
    else:
        root_node.merge_value(data)

    # Generate Pydantic models code
    generator = PydanticGenerator(
        root_name=args.root_name,
        use_optional=not args.no_optional
    )
    code = generator.generate(root_node)

    # Output code
    args.output.write(code)
    if args.output != sys.stdout:
        print(f"Successfully generated Pydantic models and saved to {args.output.name}")


if __name__ == "__main__":
    main()
