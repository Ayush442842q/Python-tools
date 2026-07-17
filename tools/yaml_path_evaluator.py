#!/usr/bin/env python3
"""
YAML Path Evaluator & Query Tool

A standalone utility to query and inspect YAML files natively in pure Python.
Translates YAML indentation structures into nested Python dictionaries and resolves
query paths (e.g. `stages.0`, `variables.PORT`, or wildcard paths `*.stage`)
to print matching keys and values.

Usage:
    python yaml_path_evaluator.py .gitlab-ci.yml "build_job.script.*"
"""

import sys
import os
import argparse
import json

def parse_basic_yaml(text):
    """
    Indent-based YAML parser that handles dict key-values, lists, and indentation.
    """
    lines = text.splitlines()
    root = {}
    stack = [(-1, root)]
    
    current_key = None
    
    for line_num, raw_line in enumerate(lines, 1):
        # Ignore comments and empty lines
        clean_line = raw_line.split('#', 1)[0]
        if not clean_line.strip():
            continue
            
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = clean_line.strip()
        
        # Pop stack until parent level is found
        while stack and stack[-1][0] >= indent:
            stack.pop()
            
        if not stack:
            stack = [(-1, root)]
            
        parent = stack[-1][1]
        
        # 1. List item "- item"
        if stripped.startswith('-'):
            val = stripped[1:].strip()
            # Unquote values
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            # Convert simple boolean / integer values
            if val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
            elif val.isdigit():
                val = int(val)
                
            if isinstance(parent, list):
                parent.append(val)
            elif isinstance(parent, dict):
                if current_key and current_key in parent:
                    if not isinstance(parent[current_key], list):
                        parent[current_key] = [parent[current_key]]
                    parent[current_key].append(val)
            continue

        # 2. Key-value pair "key: value" or block "key:"
        if ':' in stripped:
            key, val = stripped.split(':', 1)
            key = key.strip()
            val = val.strip()
            
            # Clean key/val quotes
            if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                key = key[1:-1]
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            current_key = key
            
            if val:
                # Convert boolean / integer values
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.isdigit():
                    val = int(val)
                parent[key] = val
            else:
                # Key maps to nested block
                is_list = False
                for next_line in lines[line_num:]:
                    next_strip = next_line.split('#', 1)[0].strip()
                    if next_strip:
                        if next_strip.startswith('-'):
                            is_list = True
                        break
                        
                container = [] if is_list else {}
                parent[key] = container
                stack.append((indent, container))
            continue
            
    return root

def evaluate_path(node, path_parts, current_path=""):
    """
    Recursively evaluates query path parts on the nested node structure.
    Returns list of tuples: (matched_path_string, matched_value)
    """
    if not path_parts:
        return [(current_path, node)]
        
    part = path_parts[0]
    remaining = path_parts[1:]
    results = []
    
    # Handle wildcard '*'
    if part == '*':
        if isinstance(node, dict):
            for k, val in node.items():
                p = f"{current_path}.{k}" if current_path else k
                results.extend(evaluate_path(val, remaining, p))
        elif isinstance(node, list):
            for idx, val in enumerate(node):
                p = f"{current_path}.{idx}" if current_path else str(idx)
                results.extend(evaluate_path(val, remaining, p))
                
    # Handle List Index lookup
    elif isinstance(node, list):
        if part.isdigit():
            idx = int(part)
            if 0 <= idx < len(node):
                p = f"{current_path}.{idx}" if current_path else str(idx)
                results.extend(evaluate_path(node[idx], remaining, p))
        else:
            # Querying a key directly on a list (e.g. list.*.key) -> evaluate on items
            # Auto-wrap wildcard logic
            for idx, val in enumerate(node):
                p = f"{current_path}.{idx}" if current_path else str(idx)
                results.extend(evaluate_path(val, path_parts, p))
                
    # Handle Dictionary key lookup
    elif isinstance(node, dict):
        if part in node:
            p = f"{current_path}.{part}" if current_path else part
            results.extend(evaluate_path(node[part], remaining, p))
            
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Query and inspect nested properties in YAML files natively.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("yaml_file", help="Path to the YAML configuration file.")
    parser.add_argument("query_path", help="Dot-separated query path (e.g. 'stages.0' or 'build_job.script.*').")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.yaml_file):
        print(f"Error: File '{args.yaml_file}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(args.yaml_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return 1
        
    # Parse YAML to dict
    config = parse_basic_yaml(content)
    
    # Split query path by dots
    path_parts = [p.strip() for p in args.query_path.split('.') if p.strip()]
    
    print(f"Querying: '{args.query_path}' in {args.yaml_file}")
    print("=" * 65)
    
    matches = evaluate_path(config, path_parts)
    
    if not matches:
        print("No matching nodes found for the specified path query.")
        return 0
        
    # Print matches
    for path, val in matches:
        # Format the value nicely (use json formatting for dicts/lists)
        if isinstance(val, (dict, list)):
            val_str = json.dumps(val, indent=2)
        else:
            val_str = str(val)
            
        print(f"Path : {path}")
        print(f"Value: {val_str}")
        print("-" * 65)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
