#!/usr/bin/env python3
"""
json_schema_compatibility_checker - JSON Schema Backward & Forward Compatibility Checker

Compares two JSON Schema definitions (Old Schema vs New Schema) to detect breaking API changes,
contract violations, type alterations, and backwards-incompatible schema evolution.

Usage:
    python tools/json_schema_compatibility_checker.py <old_schema.json> <new_schema.json> [options]

Examples:
    python tools/json_schema_compatibility_checker.py v1_schema.json v2_schema.json
    python tools/json_schema_compatibility_checker.py old.json new.json --strict --format json
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Any, Tuple


class SchemaDiffEngine:
    def __init__(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]):
        self.old = old_schema
        self.new = new_schema
        self.breaking_changes: List[Dict[str, Any]] = []
        self.non_breaking_changes: List[Dict[str, Any]] = []

    def compare(self):
        """Perform recursive comparison between old and new schema definitions."""
        self._compare_node("$", self.old, self.new)

    def _add_breaking(self, path: str, message: str, details: str = ""):
        self.breaking_changes.append({
            'path': path,
            'severity': 'BREAKING',
            'message': message,
            'details': details
        })

    def _add_non_breaking(self, path: str, message: str, details: str = ""):
        self.non_breaking_changes.append({
            'path': path,
            'severity': 'COMPATIBLE',
            'message': message,
            'details': details
        })

    def _compare_node(self, path: str, old_node: Dict[str, Any], new_node: Dict[str, Any]):
        if not isinstance(old_node, dict) or not isinstance(new_node, dict):
            return

        # 1. Type comparison
        old_type = old_node.get('type')
        new_type = new_node.get('type')

        if old_type and new_type and old_type != new_type:
            self._add_breaking(path, f"Data type changed from '{old_type}' to '{new_type}'.")

        # 2. Required properties comparison
        old_req = set(old_node.get('required', []))
        new_req = set(new_node.get('required', []))

        added_req = new_req - old_req
        removed_req = old_req - new_req

        if added_req:
            self._add_breaking(path, f"New required property/properties added: {sorted(list(added_req))}.")
        if removed_req:
            self._add_non_breaking(path, f"Property/properties no longer marked as required: {sorted(list(removed_req))}.")

        # 3. Object properties comparison
        old_props = old_node.get('properties', {})
        new_props = new_node.get('properties', {})

        removed_props = set(old_props.keys()) - set(new_props.keys())
        added_props = set(new_props.keys()) - set(old_props.keys())

        if removed_props:
            self._add_breaking(path, f"Property/properties removed from schema: {sorted(list(removed_props))}.")

        if added_props:
            self._add_non_breaking(path, f"New optional property/properties added: {sorted(list(added_props))}.")

        for prop_name in set(old_props.keys()).intersection(set(new_props.keys())):
            self._compare_node(f"{path}.{prop_name}", old_props[prop_name], new_props[prop_name])

        # 4. Enum comparison
        old_enum = old_node.get('enum')
        new_enum = new_node.get('enum')
        if old_enum is not None and new_enum is not None:
            old_enum_set, new_enum_set = set(old_enum), set(new_enum)
            removed_enums = old_enum_set - new_enum_set
            added_enums = new_enum_set - old_enum_set
            if removed_enums:
                self._add_breaking(path, f"Allowed enum values removed: {sorted(list(removed_enums))}.")
            if added_enums:
                self._add_non_breaking(path, f"New enum values added: {sorted(list(added_enums))}.")

        # 5. Array items comparison
        if 'items' in old_node and 'items' in new_node:
            self._compare_node(f"{path}[items]", old_node['items'], new_node['items'])


def load_json(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON schema from '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Compare two JSON Schema definitions for backward and forward breaking changes."
    )
    parser.add_argument("old_schema", help="Path to original JSON Schema file")
    parser.add_argument("new_schema", help="Path to updated JSON Schema file")
    parser.add_argument("-f", "--format", choices=['text', 'json'], default='text', help="Output format (default: text)")
    parser.add_argument("-o", "--output", help="Save compatibility report to output file")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any breaking change is detected")

    args = parser.parse_args()

    if not os.path.exists(args.old_schema):
        print(f"Error: File '{args.old_schema}' not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.new_schema):
        print(f"Error: File '{args.new_schema}' not found.", file=sys.stderr)
        sys.exit(1)

    old_json = load_json(args.old_schema)
    new_json = load_json(args.new_schema)

    diff_engine = SchemaDiffEngine(old_json, new_json)
    diff_engine.compare()

    is_compatible = len(diff_engine.breaking_changes) == 0

    report = {
        'old_schema': args.old_schema,
        'new_schema': args.new_schema,
        'is_backward_compatible': is_compatible,
        'breaking_changes_count': len(diff_engine.breaking_changes),
        'compatible_changes_count': len(diff_engine.non_breaking_changes),
        'breaking_changes': diff_engine.breaking_changes,
        'compatible_changes': diff_engine.non_breaking_changes
    }

    if args.format == 'json':
        output_str = json.dumps(report, indent=2)
    else:
        lines = []
        lines.append("=" * 70)
        lines.append("JSON SCHEMA COMPATIBILITY ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Original Schema: {args.old_schema}")
        lines.append(f"Updated Schema:  {args.new_schema}")
        lines.append(f"Status:          {'PASS (Backward Compatible)' if is_compatible else 'FAIL (Breaking Changes Detected)'}")
        lines.append("-" * 70)

        if diff_engine.breaking_changes:
            lines.append(f"\n[!] BREAKING CHANGES ({len(diff_engine.breaking_changes)}):")
            for item in diff_engine.breaking_changes:
                lines.append(f"  - Path: {item['path']}")
                lines.append(f"    Message: {item['message']}")

        if diff_engine.non_breaking_changes:
            lines.append(f"\n[+] COMPATIBLE / ADDITIVE CHANGES ({len(diff_engine.non_breaking_changes)}):")
            for item in diff_engine.non_breaking_changes:
                lines.append(f"  - Path: {item['path']}")
                lines.append(f"    Message: {item['message']}")

        if not diff_engine.breaking_changes and not diff_engine.non_breaking_changes:
            lines.append("\n[+] Both JSON schemas are structurally identical.")

        lines.append("=" * 70)
        output_str = "\n".join(lines)

    print(output_str)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"\n[+] Compatibility report saved to: {args.output}")

    if args.strict and not is_compatible:
        sys.exit(1)


if __name__ == "__main__":
    main()
