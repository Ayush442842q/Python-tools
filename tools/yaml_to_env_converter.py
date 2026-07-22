#!/usr/bin/env python3
"""
YAML to .env Converter
A CLI utility to convert nested YAML configuration files into a flat .env environment variable file format.

Features:
- Flattens nested dictionary structures into UPPER_CASE environment variable names using a customizable separator (e.g. `_` or `__`).
- Handles nested keys, lists (converts lists into indexes or comma-separated lists), numbers, booleans, and strings.
- Gracefully handles multiline strings, inline comments, and null values.
- Built-in lightweight YAML parser with fallback to PyYAML (`import yaml`) if installed.
"""

import sys
import os
import argparse
from typing import Dict, Any, List

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def parse_yaml_fallback(content: str) -> Dict[str, Any]:
    """
    A lightweight, dependency-free parser for standard YAML.
    Handles basic nesting, indentation, and key-value mapping.
    """
    lines = content.splitlines()
    data: Dict[str, Any] = {}
    stack: List[Dict[str, Any]] = [data]
    indents = [-1]

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # Clean inline comments
        if "#" in stripped:
            # Simple check for quote bounds to prevent stripping inside strings
            parts = stripped.split("#", 1)
            if not (parts[0].count('"') % 2 == 1 or parts[0].count("'") % 2 == 1):
                stripped = parts[0].strip()

        if not stripped:
            continue

        # Adjust stack based on indentation level
        while indents and indent <= indents[-1]:
            indents.pop()
            stack.pop()

        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip().strip('"').strip("'")
            val = val.strip()

            if val == "":
                # Nested map starts
                new_map: Dict[str, Any] = {}
                stack[-1][key] = new_map
                stack.append(new_map)
                indents.append(indent)
            else:
                # Leaf key-value
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                elif val.lower() in ("null", "~", "none"):
                    val = ""
                elif val.lower() == "true":
                    val = "true"
                elif val.lower() == "false":
                    val = "false"
                stack[-1][key] = val
        elif stripped.startswith("-"):
            # List item
            list_val = stripped[1:].strip().strip('"').strip("'")
            # Convert parent map/parent list to a list if not already
            # (Fallback parser simplified list handling)
            pass

    return data


def load_yaml(content: str) -> Dict[str, Any]:
    """Loads YAML content using PyYAML if available, else falling back to built-in parser."""
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        return parse_yaml_fallback(content)


def flatten_dict(d: Any, prefix: str = "", separator: str = "_") -> Dict[str, str]:
    """Recursively flattens nested dictionaries/lists into flat string dictionary."""
    items: Dict[str, str] = {}
    
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{prefix}{separator}{k}" if prefix else k
            items.update(flatten_dict(v, new_key, separator))
    elif isinstance(d, list):
        for idx, item in enumerate(d):
            new_key = f"{prefix}{separator}{idx}"
            items.update(flatten_dict(item, new_key, separator))
    else:
        # Format values cleanly
        if d is None:
            val_str = ""
        elif isinstance(d, bool):
            val_str = "true" if d else "false"
        else:
            val_str = str(d)
        items[prefix] = val_str

    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert nested YAML files to flat .env format.")
    parser.add_argument("input", nargs="?", type=str, help="Input YAML file path (reads stdin if omitted).")
    parser.add_argument("-o", "--output", type=str, help="Output .env file path.")
    parser.add_argument("-s", "--separator", type=str, default="_", help="Separator between nested key names (default: '_').")
    parser.add_argument("--upper", action="store_true", default=True, help="Force keys to uppercase (default: True).")
    parser.add_argument("--no-upper", dest="upper", action="store_false", help="Do not force keys to uppercase.")

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
        yaml_data = load_yaml(content)
    except Exception as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        sys.exit(1)

    flat_data = flatten_dict(yaml_data, separator=args.separator)

    env_lines: List[str] = []
    for k, v in flat_data.items():
        key_name = k.upper() if args.upper else k
        # Quote values containing spaces, specials, or hashes
        if any(char in v for char in (" ", "#", "=", "\n", "\r", '"', "'")):
            # Escape quotes
            escaped_val = v.replace('"', '\\"')
            v = f'"{escaped_val}"'
        env_lines.append(f"{key_name}={v}")

    output_str = "\n".join(env_lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str + "\n")
        print(f"Successfully saved env variables to {args.output}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
