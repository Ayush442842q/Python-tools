#!/usr/bin/env python3
"""
API Response Schema Diff Tool

Compare two API responses or JSON Schemas to detect structural changes and breaking contracts
(e.g., deleted fields, changed types, changed nullability, or new required fields).

Usage:
    python tools/api_schema_diff.py [base_file_or_url] [target_file_or_url] [options]

Requirements:
    - Python 3.6+
    - Optional: requests (will fall back to urllib if not installed)
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Set, Tuple, Union, Optional

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"

def load_json_source(source: str) -> Any:
    """Load JSON from a local file path or HTTP/HTTPS URL."""
    if source.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(
                source, 
                headers={'User-Agent': 'api-schema-diff/1.0', 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Failed to fetch URL {source}: HTTP {e.code}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch URL {source}: {e}")
    else:
        path = os.path.abspath(source)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Local file not found: {source}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return json.load(f)

def infer_schema(data: Any) -> Dict[str, Any]:
    """Recursively infer a JSON Schema draft-07 from a raw JSON data structure."""
    if data is None:
        return {"type": "null"}
    elif isinstance(data, bool):
        return {"type": "boolean"}
    elif isinstance(data, int):
        return {"type": "integer"}
    elif isinstance(data, float):
        return {"type": "number"}
    elif isinstance(data, str):
        return {"type": "string"}
    elif isinstance(data, list):
        if not data:
            return {"type": "array", "items": {}}
        # Merge schemas of all items to represent the array elements
        item_schemas = [infer_schema(item) for item in data]
        merged_item = merge_schemas(item_schemas)
        return {"type": "array", "items": merged_item}
    elif isinstance(data, dict):
        properties = {}
        required = []
        for k, v in data.items():
            properties[k] = infer_schema(v)
            # By default in inference, assume keys present in raw JSON are required
            required.append(k)
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema
    return {}

def merge_schemas(schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Helper to merge multiple schemas (e.g. elements of a heterogeneous array) into one."""
    if not schemas:
        return {}
    if len(schemas) == 1:
        return schemas[0]
        
    types = set()
    for s in schemas:
        t = s.get("type")
        if t:
            if isinstance(t, list):
                types.update(t)
            else:
                types.add(t)
                
    if not types:
        return {}
        
    merged = {}
    if len(types) == 1:
        t = list(types)[0]
        merged["type"] = t
        if t == "object":
            # Merge properties recursively
            all_props: Dict[str, List[Dict[str, Any]]] = {}
            for s in schemas:
                props = s.get("properties", {})
                for k, v in props.items():
                    all_props.setdefault(k, []).append(v)
            merged_props = {}
            for k, val_schemas in all_props.items():
                merged_props[k] = merge_schemas(val_schemas)
            merged["properties"] = merged_props
        elif t == "array":
            item_schemas = [s.get("items", {}) for s in schemas if s.get("items")]
            merged["items"] = merge_schemas(item_schemas)
    else:
        # Multi-type schema
        merged["type"] = list(types)
        
    return merged

class DiffError:
    def __init__(self, path: str, error_type: str, description: str, is_breaking: bool):
        self.path = path # JSON path notation (e.g., "$.users[0].name")
        self.error_type = error_type # "MISSING_FIELD", "TYPE_MISMATCH", "NULLABILITY_CHANGE", etc.
        self.description = description
        self.is_breaking = is_breaking

    def __str__(self):
        impact = f"{COLOR_RED}[BREAKING]{COLOR_RESET}" if self.is_breaking else f"{COLOR_YELLOW}[WARNING]{COLOR_RESET}"
        return f"{impact} {self.path}: {self.description}"

def compare_schemas(base: Dict[str, Any], target: Dict[str, Any], path: str = "$") -> List[DiffError]:
    """Recursively compare two JSON Schemas and return a list of differences."""
    diffs: List[DiffError] = []
    
    # Extract types
    base_type = base.get("type")
    target_type = target.get("type")
    
    # Handle nullable differences (Union of type + "null" vs. raw type)
    base_types = [base_type] if isinstance(base_type, str) else (base_type or [])
    target_types = [target_type] if isinstance(target_type, str) else (target_type or [])
    
    # If types are entirely different
    if set(base_types) != set(target_types):
        # Check if it's just a nullability change (e.g. integer vs [integer, null])
        base_nullable = "null" in base_types
        target_nullable = "null" in target_types
        
        base_clean_types = {t for t in base_types if t != "null"}
        target_clean_types = {t for t in target_types if t != "null"}
        
        if base_clean_types == target_clean_types:
            # Only nullability changed
            if base_nullable and not target_nullable:
                # Target is stricter (no longer accepts nulls). Breaking if client sends null.
                diffs.append(DiffError(
                    path, "NULLABILITY_STRICTER", 
                    f"Nullability removed. Schema now strictly expects non-null value (was nullable).", 
                    is_breaking=True
                ))
            elif not base_nullable and target_nullable:
                # Target is more relaxed (now accepts nulls). Typically non-breaking for readers.
                diffs.append(DiffError(
                    path, "NULLABILITY_RELAXED", 
                    f"Value is now nullable (was non-nullable).", 
                    is_breaking=False
                ))
        else:
            diffs.append(DiffError(
                path, "TYPE_MISMATCH", 
                f"Type changed from '{base_type}' to '{target_type}'.", 
                is_breaking=True
            ))
            return diffs # Return early for this node as structures diverge
            
    # If both are objects, compare properties
    if "object" in base_types and "object" in target_types:
        base_props = base.get("properties", {})
        target_props = target.get("properties", {})
        
        base_req = base.get("required", [])
        target_req = target.get("required", [])
        
        # Check for missing properties in target (API removed a field)
        for prop_name in base_props:
            if prop_name not in target_props:
                # Removed field is breaking if it was required or if consumer expects it
                is_req = prop_name in base_req
                diffs.append(DiffError(
                    f"{path}.{prop_name}", "MISSING_FIELD",
                    f"Field was removed from the response schema (was {'required' if is_req else 'optional'}).",
                    is_breaking=True
                ))
                
        # Check for new properties in target (API added a field)
        for prop_name in target_props:
            if prop_name not in base_props:
                is_req = prop_name in target_req
                # Adding a field is generally non-breaking for forward-compatible readers,
                # but might be breaking if it is required by the writer.
                diffs.append(DiffError(
                    f"{path}.{prop_name}", "NEW_FIELD",
                    f"New field added to the schema ({'required' if is_req else 'optional'}).",
                    is_breaking=False
                ))
                
        # Compare overlapping properties
        for prop_name in base_props:
            if prop_name in target_props:
                prop_diffs = compare_schemas(
                    base_props[prop_name], 
                    target_props[prop_name], 
                    f"{path}.{prop_name}"
                )
                diffs.extend(prop_diffs)
                
    # If both are arrays, compare items
    elif "array" in base_types and "array" in target_types:
        base_items = base.get("items")
        target_items = target.get("items")
        
        if base_items and target_items:
            # If items is a list of schemas (tuple validation)
            if isinstance(base_items, list) and isinstance(target_items, list):
                min_len = min(len(base_items), len(target_items))
                for i in range(min_len):
                    diffs.extend(compare_schemas(base_items[i], target_items[i], f"{path}[{i}]"))
                if len(base_items) > len(target_items):
                    diffs.append(DiffError(
                        path, "ARRAY_TUPLE_SHRINK", 
                        f"Array tuple length decreased from {len(base_items)} to {len(target_items)} schemas.",
                        is_breaking=True
                    ))
                elif len(target_items) > len(base_items):
                    diffs.append(DiffError(
                        path, "ARRAY_TUPLE_GROWTH", 
                        f"Array tuple length increased from {len(base_items)} to {len(target_items)} schemas.",
                        is_breaking=False
                    ))
            elif isinstance(base_items, dict) and isinstance(target_items, dict):
                # Normal array validation (all items share same schema)
                diffs.extend(compare_schemas(base_items, target_items, f"{path}[*]"))
            else:
                diffs.append(DiffError(
                    path, "ARRAY_ITEMS_STRUCTURE_MISMATCH",
                    f"Array items definition mismatch (tuple vs single schema validation).",
                    is_breaking=True
                ))
                
    return diffs

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare API response structures or JSON Schemas to identify breaking contract changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "base",
        help="Base JSON file path, API URL, or JSON Schema"
    )
    parser.add_argument(
        "target",
        help="Target JSON file path, API URL, or JSON Schema"
    )
    parser.add_argument(
        "--is-schema", "-s",
        action="store_true",
        help="Treat inputs as JSON Schemas rather than raw API JSON payloads"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color highlights in terminal output"
    )
    
    args = parser.parse_args()
    
    # Enable color formatting
    global COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_BOLD, COLOR_RESET
    if args.no_color or not sys.stdout.isatty():
        COLOR_RED = ""
        COLOR_GREEN = ""
        COLOR_YELLOW = ""
        COLOR_CYAN = ""
        COLOR_BOLD = ""
        COLOR_RESET = ""
        
    try:
        base_data = load_json_source(args.base)
        target_data = load_json_source(args.target)
    except Exception as e:
        print(f"Error loading inputs: {e}", file=sys.stderr)
        return 1
        
    # Generate schemas if input is raw JSON response
    if args.is_schema:
        base_schema = base_data
        target_schema = target_data
    else:
        print("Inferring JSON Schema from base response payload...")
        base_schema = infer_schema(base_data)
        print("Inferring JSON Schema from target response payload...")
        target_schema = infer_schema(target_data)
        
    print("Performing deep schema comparison...")
    diffs = compare_schemas(base_schema, target_schema)
    
    breaking_diffs = [d for d in diffs if d.is_breaking]
    warning_diffs = [d for d in diffs if not d.is_breaking]
    
    print("\n" + "="*80)
    print("API SCHEMA COMPARISON RESULTS")
    print("="*80)
    print(f"Base:   {args.base}")
    print(f"Target: {args.target}")
    print(f"Total differences found: {len(diffs)}")
    print(f"Breaking changes:        {COLOR_RED if breaking_diffs else COLOR_GREEN}{len(breaking_diffs)}{COLOR_RESET}")
    print(f"Non-breaking warnings:   {COLOR_YELLOW if warning_diffs else COLOR_GREEN}{len(warning_diffs)}{COLOR_RESET}")
    print("="*80)
    
    if diffs:
        print("\nDIFFERENCES LIST:")
        for d in diffs:
            print(d)
    else:
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}Success: No schema changes detected. API contract is perfectly compatible!{COLOR_RESET}")
        
    print()
    return 1 if breaking_diffs else 0

if __name__ == "__main__":
    sys.exit(main())
