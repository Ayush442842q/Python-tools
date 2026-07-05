#!/usr/bin/env python3
"""
Java .properties Converter & Manager
------------------------------------
Parses Java .properties files (supporting unicode escape sequences, multi-line continuation,
comments, and key-value separators), converting bi-directionally between Java .properties,
JSON, YAML-like formats, and environment variable files (.env).
Supports key flattening/unflattening, variable interpolation, and duplicate key auditing.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import Dict, Any, List, Tuple, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def unescape_java_string(s: str) -> str:
    """Decodes Java unicode escape sequences \\uXXXX and standard escape characters."""
    def replace_unicode(match):
        return chr(int(match.group(1), 16))

    s = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, s)
    replacements = {
        '\\t': '\t',
        '\\n': '\n',
        '\\r': '\r',
        '\\f': '\f',
        '\\\\': '\\',
        '\\=': '=',
        '\\:': ':',
        '\\#': '#',
        '\\!': '!'
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s


def escape_java_key(k: str) -> str:
    """Escapes special characters in Java property keys."""
    return k.replace('\\', '\\\\').replace(' ', '\\ ').replace('=', '\\=').replace(':', '\\:')


def escape_java_value(v: str) -> str:
    """Escapes special characters in Java property values."""
    s = str(v).replace('\\', '\\\\').replace('\n', '\\n\n').replace('\r', '\\r').replace('\t', '\\t')
    return s


def parse_properties_content(content: str) -> Tuple[Dict[str, str], List[str], List[str]]:
    """
    Parses Java properties text content into:
    1. Dictionary of properties (key -> value)
    2. List of comments/structure lines
    3. List of warnings (e.g. duplicate keys)
    """
    properties = {}
    structure = []
    warnings = []

    lines = content.splitlines()
    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i].strip()

        # Blank lines or comments
        if not line or line.startswith('#') or line.startswith('!'):
            structure.append(lines[i])
            i += 1
            continue

        # Multi-line continuation check
        full_line = line
        while full_line.endswith('\\') and i + 1 < num_lines:
            full_line = full_line[:-1] + lines[i + 1].strip()
            i += 1

        # Key-Value separator: first unescaped '=' or ':' or whitespace
        match = re.search(r'(?<!\\)([:=\s])', full_line)
        if match:
            sep_idx = match.start()
            raw_key = full_line[:sep_idx].strip()
            raw_val = full_line[sep_idx + 1:].strip()
            if full_line[sep_idx] in (':', '='):
                pass
        else:
            raw_key = full_line.strip()
            raw_val = ""

        key = unescape_java_string(raw_key)
        val = unescape_java_string(raw_val)

        if key in properties:
            warnings.append(f"Duplicate key '{key}' found. Overwriting previous value '{properties[key]}' with '{val}'.")

        properties[key] = val
        structure.append(f"{escape_java_key(key)}={escape_java_value(val)}")
        i += 1

    return properties, structure, warnings


def interpolate_variables(props: Dict[str, str]) -> Dict[str, str]:
    """Resolves ${var.name} references inside property values."""
    resolved = dict(props)
    pattern = re.compile(r'\$\{([^}]+)\}')

    for _ in range(5):  # Max 5 passes for nested resolution
        changed = False
        for k, v in resolved.items():
            matches = pattern.findall(v)
            for ref in matches:
                if ref in resolved:
                    v = v.replace(f"${{{ref}}}", resolved[ref])
                    resolved[k] = v
                    changed = True
        if not changed:
            break

    return resolved


def unflatten_dict(props: Dict[str, str]) -> Dict[str, Any]:
    """Converts dot-notation properties ('db.conn.url') to nested dictionary objects."""
    nested = {}
    for key, val in props.items():
        parts = key.split('.')
        curr = nested
        for part in parts[:-1]:
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        curr[parts[-1]] = val
    return nested


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, str]:
    """Flattens a nested dictionary into dot-notation property keys."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v)))
    return dict(items)


def dict_to_env(props: Dict[str, str]) -> str:
    """Converts property dict to .env format (UPPERCASE_KEYS=value)."""
    env_lines = []
    for k, v in props.items():
        env_key = re.sub(r'[^A-Z0-9_]', '_', k.upper())
        if ' ' in v or '\n' in v or '"' in v:
            escaped_val = v.replace('"', '\\"')
            env_lines.append(f'{env_key}="{escaped_val}"')
        else:
            env_lines.append(f'{env_key}={v}')
    return '\n'.join(env_lines)


def dict_to_properties(props: Dict[str, str]) -> str:
    """Converts property dict to Java .properties format."""
    lines = [
        "# Generated by Java .properties Converter",
        "#"
    ]
    for k in sorted(props.keys()):
        lines.append(f"{escape_java_key(k)}={escape_java_value(props[k])}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Java .properties Converter & Manager")
    parser.add_argument("input_file", nargs="?", help="Path to input file (.properties, .json, .env)")
    parser.add_argument("--format", "-f", choices=["json", "properties", "env", "yaml"], default="json", help="Output target format")
    parser.add_argument("--out", "-o", help="Write output to specified file")
    parser.add_argument("--unflatten", "-u", action="store_true", help="Unflatten dot-notation keys into nested objects (for JSON/YAML output)")
    parser.add_argument("--interpolate", "-i", action="store_true", help="Resolve ${var} placeholders in values")
    parser.add_argument("--audit", "-a", action="store_true", help="Audit file for duplicates, missing variables, and formatting issues")

    args = parser.parse_args()

    if not args.input_file:
        print(f"{YELLOW}No input file specified. Running demonstration with sample properties:{RESET}\n")
        sample_props = (
            "# Database Settings\n"
            "db.host=localhost\n"
            "db.port=5432\n"
            "db.name=myapp_db\n"
            "db.url=jdbc:postgresql://${db.host}:${db.port}/${db.name}\n"
            "\n"
            "# App Config\n"
            "app.title=My App \\u2605\n"
            "app.max_connections=50\n"
            "app.description=Line 1\\nLine 2\n"
        )
        print(f"{CYAN}{BOLD}Sample Input Java .properties:{RESET}")
        print(sample_props)

        props, _, warnings = parse_properties_content(sample_props)
        if args.interpolate:
            props = interpolate_variables(props)

        print(f"\n{GREEN}{BOLD}Converted Output (JSON):{RESET}")
        print(json.dumps(unflatten_dict(props), indent=2, ensure_ascii=False))
        return

    if not os.path.exists(args.input_file):
        print(f"{RED}Error: File '{args.input_file}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    ext = os.path.splitext(args.input_file)[1].lower()

    if ext == ".json":
        data = json.loads(content)
        props = flatten_dict(data) if isinstance(data, dict) else {}
        warnings = []
    else:
        props, _, warnings = parse_properties_content(content)

    if args.interpolate:
        props = interpolate_variables(props)

    if args.audit:
        print(f"\n{BOLD}{BLUE}=== Java .properties Audit Report: {args.input_file} ==={RESET}\n")
        print(f"Total keys found: {BOLD}{len(props)}{RESET}")
        if warnings:
            print(f"\n{YELLOW}{BOLD}Warnings ({len(warnings)}):{RESET}")
            for w in warnings:
                print(f"  {YELLOW}⚠ {w}{RESET}")
        else:
            print(f"{GREEN}✔ No duplicate keys or structural defects found.{RESET}")

        unresolved = []
        for k, v in props.items():
            if "${" in v:
                unresolved.append((k, v))

        if unresolved:
            print(f"\n{YELLOW}{BOLD}Unresolved Variable Referencing ({len(unresolved)}):{RESET}")
            for k, v in unresolved:
                print(f"  - {k} -> {v}")
        return

    output_str = ""
    if args.format == "json":
        final_data = unflatten_dict(props) if args.unflatten else props
        output_str = json.dumps(final_data, indent=2, ensure_ascii=False)
    elif args.format == "env":
        output_str = dict_to_env(props)
    elif args.format == "properties":
        output_str = dict_to_properties(props)
    elif args.format == "yaml":
        final_data = unflatten_dict(props) if args.unflatten else props
        # Simple YAML serialization
        def to_yaml(obj, indent=0):
            lines = []
            pad = ' ' * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        lines.append(f"{pad}{k}:")
                        lines.append(to_yaml(v, indent + 2))
                    else:
                        lines.append(f"{pad}{k}: \"{v}\"")
            return '\n'.join(lines)
        output_str = to_yaml(final_data)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"{GREEN}✔ Successfully wrote output to {args.out}{RESET}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
