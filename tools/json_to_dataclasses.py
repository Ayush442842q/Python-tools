#!/usr/bin/env python3
"""
JSON to Python Dataclass & Pydantic Model Generator
Converts JSON structures into nested Python dataclasses or Pydantic models.
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Set, Tuple, Union

# Reserved Python keywords that shouldn't be used as attribute names directly
RESERVED_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"
}

def clean_identifier(name: str) -> str:
    """Convert a JSON key into a valid, safe Python identifier."""
    # Replace non-alphanumeric chars with underscore
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Remove leading numbers
    if re.match(r'^\d', clean):
        clean = f"_{clean}"
    # If reserved keyword, append underscore
    if clean in RESERVED_KEYWORDS:
        clean = f"{clean}_"
    return clean

def camel_case(name: str) -> str:
    """Convert a name into CamelCase for class names."""
    parts = re.split(r'[^a-zA-Z0-9]', name)
    return "".join(p.capitalize() for p in parts if p)

class TypeInferrer:
    def __init__(self, use_pydantic: bool = False):
        self.use_pydantic = use_pydantic
        self.classes: Dict[str, Dict[str, str]] = {}  # ClassName -> {fieldName: fieldType}
        self.raw_names: Dict[str, Dict[str, str]] = {}  # ClassName -> {fieldName: originalJsonKey}

    def infer_type(self, val: Any, key_hint: str) -> str:
        """Infer type of a JSON value, registering child classes as necessary."""
        if val is None:
            return "Optional[Any]"
        
        t = type(val)
        if t is bool:
            return "bool"
        elif t is int:
            return "int"
        elif t is float:
            return "float"
        elif t is str:
            return "str"
        elif t is dict:
            class_name = camel_case(key_hint)
            # Ensure class name is unique
            base_name = class_name
            counter = 1
            while class_name in self.classes and self.classes[class_name] != self._get_dict_schema(val):
                class_name = f"{base_name}{counter}"
                counter += 1
                
            self.classes[class_name] = self._get_dict_schema(val)
            self.raw_names[class_name] = {clean_identifier(k): k for k in val.keys()}
            return class_name
        elif t is list:
            if not val:
                return "List[Any]"
            
            # Infer types of all list items
            item_types = set()
            dict_items = []
            for item in val:
                if isinstance(item, dict):
                    dict_items.append(item)
                else:
                    item_types.add(self.infer_type(item, f"{key_hint}Item"))
                    
            if dict_items:
                # Merge dict schemas to create a unified subclass representation
                merged_dict = {}
                for d in dict_items:
                    for k, v in d.items():
                        if k not in merged_dict:
                            merged_dict[k] = v
                        else:
                            # Simple merge logic: if one is not None, prefer it
                            if merged_dict[k] is None:
                                merged_dict[k] = v
                class_name = self.infer_type(merged_dict, f"{key_hint}Item")
                item_types.add(class_name)
                
            if len(item_types) == 1:
                return f"List[{list(item_types)[0]}]"
            elif len(item_types) > 1:
                # Convert multiple items to Union
                union_types = ", ".join(sorted(list(item_types)))
                return f"List[Union[{union_types}]]"
            return "List[Any]"
            
        return "Any"

    def _get_dict_schema(self, d: Dict[str, Any]) -> Dict[str, str]:
        """Temporarily extract a dict's field type schema."""
        schema = {}
        for k, v in d.items():
            field_name = clean_identifier(k)
            # Use TypeInferrer without mutating state immediately, or do standard infer
            schema[field_name] = self.infer_type(v, k)
        return schema

    def analyze(self, data: Any, root_name: str = "Root") -> str:
        """Analyze data and returns the name of the root type."""
        return self.infer_type(data, root_name)

    def generate_code(self) -> str:
        """Produce the Python source code representing the classes."""
        lines = []
        if self.use_pydantic:
            lines.append("from typing import Any, List, Optional, Union")
            lines.append("from pydantic import BaseModel, Field")
            lines.append("")
        else:
            lines.append("from dataclasses import dataclass, field")
            lines.append("from typing import Any, List, Optional, Union")
            lines.append("")
            
        # Topologically sort classes so child classes are defined before parent classes
        dependencies = {}
        for cls_name, fields in self.classes.items():
            deps = set()
            for f_type in fields.values():
                # Extract class names from compound types like List[Item] or Union[A, B]
                found = re.findall(r'[a-zA-Z0-9_]+', f_type)
                for f in found:
                    if f in self.classes and f != cls_name:
                        deps.add(f)
            dependencies[cls_name] = deps
            
        sorted_classes = []
        visited = set()
        
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            for dep in dependencies.get(name, []):
                visit(dep)
            sorted_classes.append(name)
            
        for cls_name in self.classes:
            visit(cls_name)
            
        for cls_name in sorted_classes:
            fields = self.classes[cls_name]
            raw_keys = self.raw_names.get(cls_name, {})
            
            if self.use_pydantic:
                lines.append(f"class {cls_name}(BaseModel):")
                if not fields:
                    lines.append("    pass")
                for f_name, f_type in fields.items():
                    raw_key = raw_keys.get(f_name, f_name)
                    if raw_key != f_name:
                        lines.append(f"    {f_name}: {f_type} = Field(alias='{raw_key}')")
                    else:
                        lines.append(f"    {f_name}: {f_type}")
                lines.append("")
            else:
                lines.append("@dataclass")
                lines.append(f"class {cls_name}:")
                if not fields:
                    lines.append("    pass")
                for f_name, f_type in fields.items():
                    # Handle mutable default arguments for lists/dicts in standard dataclasses
                    if f_type.startswith("List["):
                        lines.append(f"    {f_name}: {f_type} = field(default_factory=list)")
                    elif f_type.startswith("Dict["):
                        lines.append(f"    {f_name}: {f_type} = field(default_factory=dict)")
                    elif "Optional[" in f_type or f_type == "Any":
                        lines.append(f"    {f_name}: {f_type} = None")
                    else:
                        lines.append(f"    {f_name}: {f_type}")
                lines.append("")
                
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="JSON to Python Dataclass & Pydantic Model Generator"
    )
    parser.add_argument(
        "file", nargs="?", help="Path to JSON file. If omitted, reads from standard input."
    )
    parser.add_argument(
        "--root", default="RootModel", help="Name of the root class to generate (default: RootModel)"
    )
    parser.add_argument(
        "--pydantic", action="store_true", help="Generate Pydantic v2 models instead of standard dataclasses"
    )
    args = parser.parse_args()

    # Load JSON source
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                raw_data = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            print("Enter JSON payload (Press Ctrl+D/Ctrl+Z to finalize):")
        raw_data = sys.stdin.read()

    if not raw_data.strip():
        print("Error: Empty input payload.", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON payload - {e}", file=sys.stderr)
        sys.exit(1)

    inferrer = TypeInferrer(use_pydantic=args.pydantic)
    root_type = inferrer.analyze(data, args.root)
    
    # If the root is a primitive list, output a message
    if root_type.startswith("List[") and not inferrer.classes:
        print(f"# Root JSON is a flat list of primitive elements.")
        print(f"# Unified Type representation: {root_type}")
        sys.exit(0)

    code = inferrer.generate_code()
    print(code)

if __name__ == "__main__":
    main()
