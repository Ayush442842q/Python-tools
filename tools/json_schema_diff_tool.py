#!/usr/bin/env python3
"""
JSON Schema Structural Diff & Compatibility Tool
------------------------------------------------
Compares two JSON Schemas to identify additions, removals, type changes,
and constraint modifications (such as required list updates, min/max bounds,
regex patterns, and enum choices).

Features:
- Structural comparison of object properties and array items.
- Identifies constraint shifts (minLength, maxLength, minimum, maximum, pattern, enum).
- Highlights changes to the 'required' properties array.
- Generates side-by-side CLI diffs, Markdown reports, or JSON output.
- Built-in --demo mode with example JSON schemas.

Usage:
    python json_schema_diff_tool.py --old schema_v1.json --new schema_v2.json
    python json_schema_diff_tool.py --demo
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Any, Optional, Tuple


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.MAGENTA = cls.CYAN = cls.BOLD = cls.RESET = ''


if not sys.stdout.isatty():
    Color.disable()



class JSONSchemaDiff:
    def __init__(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]):
        self.old_schema = old_schema
        self.new_schema = new_schema
        self.diffs: List[Dict[str, Any]] = []

    def compare(self) -> List[Dict[str, Any]]:
        self.diffs = []
        self._compare_nodes(self.old_schema, self.new_schema, path="$")
        return self.diffs

    def _add_diff(self, change_type: str, path: str, message: str, old_val: Any = None, new_val: Any = None):
        self.diffs.append({
            'type': change_type,
            'path': path,
            'message': message,
            'old_value': old_val,
            'new_value': new_val
        })

    def _compare_nodes(self, old_node: Dict[str, Any], new_node: Dict[str, Any], path: str):
        if not isinstance(old_node, dict) or not isinstance(new_node, dict):
            if old_node != new_node:
                self._add_diff('VALUE_CHANGED', path, f"Value changed from '{old_node}' to '{new_node}'", old_node, new_node)
            return

        # Type comparison
        old_type = old_node.get('type')
        new_type = new_node.get('type')
        if old_type != new_type:
            self._add_diff('TYPE_CHANGED', path, f"Type changed from '{old_type}' to '{new_type}'", old_type, new_type)

        # Required fields comparison
        old_req = set(old_node.get('required', []))
        new_req = set(new_node.get('required', []))

        added_req = new_req - old_req
        removed_req = old_req - new_req

        for req in added_req:
            self._add_diff('REQUIRED_ADDED', f"{path}.required", f"Property '{req}' added to required list", None, req)
        for req in removed_req:
            self._add_diff('REQUIRED_REMOVED', f"{path}.required", f"Property '{req}' removed from required list", req, None)

        # Properties comparison
        old_props = old_node.get('properties', {})
        new_props = new_node.get('properties', {})

        for prop, p_schema in old_props.items():
            prop_path = f"{path}.properties.{prop}"
            if prop not in new_props:
                self._add_diff('PROPERTY_REMOVED', prop_path, f"Property '{prop}' removed", p_schema, None)
            else:
                self._compare_nodes(p_schema, new_props[prop], prop_path)

        for prop, p_schema in new_props.items():
            prop_path = f"{path}.properties.{prop}"
            if prop not in old_props:
                self._add_diff('PROPERTY_ADDED', prop_path, f"Property '{prop}' added", None, p_schema)

        # Constraint attributes
        constraints = ['minimum', 'maximum', 'minLength', 'maxLength', 'pattern', 'enum', 'minItems', 'maxItems']
        for c in constraints:
            if c in old_node or c in new_node:
                ov = old_node.get(c)
                nv = new_node.get(c)
                if ov != nv:
                    self._add_diff('CONSTRAINT_CHANGED', f"{path}.{c}", f"Constraint '{c}' changed from {ov} to {nv}", ov, nv)


def get_demo_schemas() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    old_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "UserProfile",
        "type": "object",
        "required": ["id", "username", "email"],
        "properties": {
            "id": {"type": "integer", "minimum": 1},
            "username": {"type": "string", "minLength": 3, "maxLength": 20},
            "email": {"type": "string", "format": "email"},
            "age": {"type": "integer", "minimum": 18},
            "status": {"type": "string", "enum": ["active", "pending"]}
        }
    }

    new_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "UserProfile",
        "type": "object",
        "required": ["id", "username", "email", "phone"],  # Added 'phone' required
        "properties": {
            "id": {"type": "string"},  # Changed int -> string
            "username": {"type": "string", "minLength": 5, "maxLength": 20},  # minLength changed 3->5
            "email": {"type": "string", "format": "email"},
            # 'age' property removed
            "status": {"type": "string", "enum": ["active", "pending", "archived"]},  # Enum extended
            "phone": {"type": "string", "pattern": r"^\+?[1-9]\d{1,14}$"}  # Added property
        }
    }
    return old_schema, new_schema


def print_report(diffs: List[Dict[str, Any]], format_type: str = 'cli'):
    if format_type == 'json':
        print(json.dumps(diffs, indent=2))
        return

    if format_type == 'markdown':
        print("# JSON Schema Structural Diff Report\n")
        print(f"Total Structural Changes Identified: {len(diffs)}\n")
        print("| Change Type | JSON Path | Details |")
        print("|---|---|---|")
        for d in diffs:
            print(f"| `{d['type']}` | `{d['path']}` | {d['message']} |")
        return

    # CLI Output
    print(f"\n{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}          JSON SCHEMA STRUCTURAL DIFF REPORT       {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}\n")

    print(f"Total Differences Found: {Color.BOLD}{len(diffs)}{Color.RESET}\n")

    for d in diffs:
        t = d['type']
        if 'REMOVED' in t or 'TYPE_CHANGED' in t:
            color = Color.RED
            icon = "✖"
        elif 'ADDED' in t:
            color = Color.GREEN
            icon = "✔"
        else:
            color = Color.YELLOW
            icon = "✎"

        print(f"{color}{icon} [{t}] {d['path']}{Color.RESET}")
        print(f"  └─ {d['message']}")
        if d['old_value'] is not None or d['new_value'] is not None:
            print(f"     Old: {d['old_value']}  -->  New: {d['new_value']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="JSON Schema Structural Diff & Compatibility Tool")
    parser.add_argument("--old", help="Path to baseline/old JSON Schema file")
    parser.add_argument("--new", help="Path to target/new JSON Schema file")
    parser.add_argument("--demo", action="store_true", help="Run diff check on built-in demo JSON schemas")
    parser.add_argument("--format", choices=['cli', 'markdown', 'json'], default='cli', help="Output format")

    args = parser.parse_args()

    if args.demo or (not args.old and not args.new):
        if not args.demo:
            print(f"{Color.YELLOW}No input schema files specified. Running --demo mode...{Color.RESET}\n")
        old_s, new_s = get_demo_schemas()
    else:
        if not args.old or not args.new:
            print(f"{Color.RED}Error: Both --old and --new files are required.{Color.RESET}")
            sys.exit(1)

        try:
            with open(args.old, 'r', encoding='utf-8') as f:
                old_s = json.load(f)
            with open(args.new, 'r', encoding='utf-8') as f:
                new_s = json.load(f)
        except Exception as e:
            print(f"{Color.RED}Failed to read JSON Schema files: {e}{Color.RESET}")
            sys.exit(1)

    differ = JSONSchemaDiff(old_s, new_s)
    diffs = differ.compare()
    print_report(diffs, format_type=args.format)


if __name__ == "__main__":
    main()
