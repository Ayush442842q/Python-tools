#!/usr/bin/env python3
"""
TOML to JSON / YAML Converter
A CLI utility to convert TOML configuration files into JSON or YAML format with key filtering and formatting options.

Features:
- Supports Python standard library `tomllib` (Python 3.11+) with fallback for older Python versions.
- Convert TOML files to formatted JSON or simple YAML.
- Key path filtering (extract sub-dictionaries via dot notation e.g., --key tool.poetry).
- Read from file or standard input.
"""

import sys
import os
import json
import argparse
from typing import Any, Dict

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def load_toml(content: str) -> Dict[str, Any]:
    """Loads TOML string content using tomllib or fallback."""
    try:
        import tomllib
        return tomllib.loads(content)
    except ImportError:
        try:
            import tomli
            return tomli.loads(content)
        except ImportError:
            # Simple fallback parser for basic key-value TOML
            data: Dict[str, Any] = {}
            current_section = data
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    sec_name = line[1:-1].strip()
                    keys = sec_name.split(".")
                    curr = data
                    for k in keys:
                        curr = curr.setdefault(k, {})
                    current_section = curr
                elif "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip().strip('"').strip("'")
                    v = v.strip()
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    elif v.lower() == "true":
                        v = True
                    elif v.lower() == "false":
                        v = False
                    elif v.isdigit():
                        v = int(v)
                    current_section[k] = v
            return data


def get_nested_key(data: Dict[str, Any], key_path: str) -> Any:
    """Extracts nested value using dot notation key path (e.g. 'tool.poetry')."""
    parts = key_path.split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            raise KeyError(f"Key path '{key_path}' not found at segment '{part}'.")
    return curr


def dict_to_simple_yaml(data: Any, indent: int = 0) -> str:
    """Simple recursive YAML formatter without external PyYAML dependency."""
    spacing = " " * indent
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{spacing}{k}:")
                lines.append(dict_to_simple_yaml(v, indent + 2))
            else:
                lines.append(f"{spacing}{k}: {json.dumps(v)}")
        return "\n".join(lines)
    elif isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{spacing}-")
                lines.append(dict_to_simple_yaml(item, indent + 2))
            else:
                lines.append(f"{spacing}- {json.dumps(item)}")
        return "\n".join(lines)
    else:
        return f"{spacing}{json.dumps(data)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert TOML configuration files to JSON or YAML.")
    parser.add_argument("input", nargs="?", type=str, help="Path to input TOML file (reads stdin if omitted).")
    parser.add_argument("-o", "--output", type=str, help="Output file path.")
    parser.add_argument("-f", "--format", choices=["json", "yaml"], default="json", help="Output format (default: json).")
    parser.add_argument("-k", "--key", type=str, help="Extract specific key path using dot notation (e.g. tool.poetry.dependencies).")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level (default: 2).")

    args = parser.parse_args()

    if args.input and os.path.exists(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        content = sys.stdin.read()

    try:
        data = load_toml(content)
    except Exception as e:
        print(f"Error parsing TOML content: {e}", file=sys.stderr)
        sys.exit(1)

    if args.key:
        try:
            data = get_nested_key(data, args.key)
        except KeyError as ke:
            print(f"Error: {ke}", file=sys.stderr)
            sys.exit(1)

    if args.format == "json":
        output_str = json.dumps(data, indent=args.indent, ensure_ascii=False)
    else:
        output_str = dict_to_simple_yaml(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str + "\n")
        print(f"Successfully saved {args.format.upper()} output to {args.output}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
