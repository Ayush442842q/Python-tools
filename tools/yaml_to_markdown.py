#!/usr/bin/env python3
"""
YAML Configuration Documenter (YAML to Markdown)
-----------------------------------------------
Parses nested YAML configuration files (such as Docker Compose files, Kubernetes manifests,
or custom app configurations) and compiles them into a structured Markdown document.
Includes nested sections, type inference, parameter description tables, default values,
and extracts documentation comments directly from the YAML code.

Dependencies:
    - python 3.6+
    - pyyaml (optional, standard library fallback included)

Usage:
    python tools/yaml_to_markdown.py config.yaml -o README_CONFIG.md
"""

import os
import sys
import re
import argparse
from typing import Dict, Any, List, Tuple, Optional

# Attempt to load pyyaml, fall back to custom line parser if not present
HAS_PYYAML = False
try:
    import yaml
    HAS_PYYAML = True
except ImportError:
    pass

class YamlCommentParser:
    """
    Parses a YAML file line-by-line to associate comments with configuration parameters.
    This works as a fallback parser and also extracts description comments.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.comments: Dict[str, str] = {}  # Maps dotted path to comment text
        self.hierarchy: List[str] = []
        self.indent_stack: List[int] = [-1]
        
    def parse(self) -> Dict[str, Any]:
        """Parse YAML file and extract structured keys, values, and comments."""
        data = {}
        current_comments = []
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                stripped = line.strip()
                
                # Check for comments
                if stripped.startswith('#'):
                    comment_content = stripped.lstrip('#').strip()
                    if comment_content:
                        current_comments.append(comment_content)
                    continue
                
                if not stripped:
                    # Empty line resets accumulated comments
                    current_comments = []
                    continue
                    
                # Handle inline comment if present
                inline_comment = ""
                if '#' in line:
                    # Simple split, avoiding split inside string quotes (rough approximation)
                    parts = line.split('#', 1)
                    line_content = parts[0]
                    inline_comment = parts[1].strip()
                else:
                    line_content = line
                    
                # Match key-value: "key: value"
                match = re.match(r'^(\s*)([a-zA-Z0-9_\-\.]+)\s*:\s*(.*)$', line_content)
                if match:
                    indent_str, key, value_str = match.groups()
                    indent = len(indent_str)
                    value_str = value_str.strip()
                    
                    # Manage hierarchy based on indentation
                    while self.indent_stack and indent <= self.indent_stack[-1]:
                        self.indent_stack.pop()
                        if self.hierarchy:
                            self.hierarchy.pop()
                            
                    self.hierarchy.append(key)
                    self.indent_stack.append(indent)
                    
                    # Form dotted path key
                    path = ".".join(self.hierarchy)
                    
                    # Assemble description comment
                    desc = " ".join(current_comments)
                    if inline_comment:
                        desc = f"{desc} {inline_comment}".strip()
                    if desc:
                        self.comments[path] = desc
                        
                    # Store raw value for type evaluation
                    val = None
                    if value_str:
                        # Clean quotes
                        if (value_str.startswith('"') and value_str.endswith('"')) or \
                           (value_str.startswith("'") and value_str.endswith("'")):
                            val = value_str[1:-1]
                        elif value_str.lower() in ('true', 'yes', 'on'):
                            val = True
                        elif value_str.lower() in ('false', 'no', 'off'):
                            val = False
                        elif value_str.isdigit():
                            val = int(value_str)
                        else:
                            try:
                                val = float(value_str)
                            except ValueError:
                                val = value_str
                                
                    # If this is a parent dictionary (value_str is empty and next lines are indented),
                    # we will keep it as dict.
                    # We write values to a flat dictionary first
                    data[path] = {
                        "key": key,
                        "value": val,
                        "description": desc or "No description provided.",
                        "type": type(val).__name__ if val is not None else "object"
                    }
                    
                    # Clear comments for next parameter
                    current_comments = []
                else:
                    # Reset comments if line doesn't match key
                    current_comments = []
                    
        return data

def build_markdown(data: Dict[str, Dict[str, Any]], filename: str) -> str:
    """Generate Markdown text structure from the parsed data."""
    md = []
    md.append(f"# Configuration Documentation: `{filename}`")
    md.append("\nThis document details the configuration parameters, their expected types, default values, and functional descriptions.\n")
    md.append("## Configuration Reference Table\n")
    md.append("| Parameter Path | Type | Default Value | Description |")
    md.append("|---|---|---|---|")
    
    # Sort paths alphabetically
    for path in sorted(data.keys()):
        info = data[path]
        val = info["value"]
        
        # Format default value string
        if val is None:
            default_str = "*None*"
        elif isinstance(val, bool):
            default_str = "`true`" if val else "`false`"
        elif isinstance(val, str):
            default_str = f'"{val}"'
        else:
            default_str = f"`{val}`"
            
        # Format type representation
        t_name = info["type"]
        if t_name == "str":
            t_name = "String"
        elif t_name == "int":
            t_name = "Integer"
        elif t_name == "float":
            t_name = "Float"
        elif t_name == "bool":
            t_name = "Boolean"
            
        md.append(f"| **{path}** | `{t_name}` | {default_str} | {info['description']} |")
        
    # Group parameters by top-level section for detailed breakdown
    sections: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for path, info in data.items():
        parts = path.split('.')
        top_level = parts[0]
        if top_level not in sections:
            sections[top_level] = []
        sections[top_level].append((path, info))
        
    md.append("\n## Detailed Parameter Descriptions\n")
    
    for section_name in sorted(sections.keys()):
        md.append(f"### Section: `{section_name}`\n")
        
        for path, info in sorted(sections[section_name], key=lambda x: x[0]):
            md.append(f"#### `{path}`")
            md.append(f"- **Type:** `{info['type']}`")
            default_val = info["value"]
            if default_val is not None:
                md.append(f"- **Default Value:** `{default_val}`")
            md.append(f"- **Description:** {info['description']}\n")
            
    return "\n".join(md)

def load_with_pyyaml(filepath: str) -> Dict[str, Any]:
    """Helper load using PyYAML framework."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flattens nested dictionaries into dotted path keys."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def main():
    parser = argparse.ArgumentParser(
        description="YAML Configuration Documenter: Converts nested YAML configurations into styled Markdown docs."
    )
    parser.add_argument("yaml_file", help="Path to the input YAML file")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.yaml_file):
        print(f"Error: YAML file '{args.yaml_file}' not found.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Parsing YAML file: {args.yaml_file}")
    
    # 1. Use the custom parser to extract comments alongside keys
    comment_parser = YamlCommentParser(args.yaml_file)
    extracted_data = comment_parser.parse()
    
    # 2. If pyyaml is available, we double-check structural values & types
    if HAS_PYYAML:
        try:
            yaml_struct = load_with_pyyaml(args.yaml_file)
            if isinstance(yaml_struct, dict):
                flat_struct = flatten_dict(yaml_struct)
                
                # Enrich extracted comments data with actual parsed types/values from PyYAML
                for path, val in flat_struct.items():
                    if path in extracted_data:
                        extracted_data[path]["value"] = val
                        extracted_data[path]["type"] = type(val).__name__
                    else:
                        extracted_data[path] = {
                            "key": path.split('.')[-1],
                            "value": val,
                            "description": "No description provided.",
                            "type": type(val).__name__
                        }
        except Exception as e:
            print(f"Warning: Standard PyYAML parser encountered error: {e}. Using fallback parser.", file=sys.stderr)
            
    # Remove nodes that are empty parent objects (have child fields documented)
    keys_to_delete = []
    all_keys = list(extracted_data.keys())
    for k in all_keys:
        # Check if it acts as a parent prefix to another documented key
        is_parent = any(other.startswith(k + ".") for other in all_keys)
        if is_parent and extracted_data[k]["type"] == "object":
            keys_to_delete.append(k)
            
    for k in keys_to_delete:
        del extracted_data[k]
        
    if not extracted_data:
        print("Warning: No config parameters parsed from the file.")
        sys.exit(0)
        
    # Generate Markdown content
    md_content = build_markdown(extracted_data, os.path.basename(args.yaml_file))
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(md_content)
            print(f"Successfully generated documentation: '{args.output}'")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n--- GENERATED DOCUMENTATION ---")
        print(md_content)

if __name__ == "__main__":
    main()
