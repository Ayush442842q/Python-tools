#!/usr/bin/env python3
"""
JSON Key Rename & Transformation Utility

Batch renames keys in JSON documents using case presets, mappings, regex rules, or affixes.

Features:
- Casing conversions: snake_case, camelCase, PascalCase, kebab-case, UPPERCASE, lowercase
- Key mapping via JSON file or inline pairs (old=new)
- Prefix and suffix attachment
- Regular expression substitution on key names
- Recursive application through nested objects and arrays
- Dry-run mode displaying diff of modified keys
- Output format customization and validation

Usage:
    python json_key_rename_utility.py data.json --casing camelCase
    python json_key_rename_utility.py data.json --prefix "app_" --out output.json
    python json_key_rename_utility.py data.json --map old_key=new_key --dry-run
"""

import os
import sys
import json
import re
import argparse
from typing import Any, Dict, List, Tuple, Optional, Callable

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"


def to_snake_case(name: str) -> str:
    """Converts key string to snake_case."""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    s3 = re.sub(r'[-\s]+', '_', s2)
    return s3.lower()


def to_camel_case(name: str) -> str:
    """Converts key string to camelCase."""
    snake = to_snake_case(name)
    components = snake.split('_')
    if not components:
        return name
    return components[0] + ''.join(x.title() for x in components[1:])


def to_pascal_case(name: str) -> str:
    """Converts key string to PascalCase."""
    snake = to_snake_case(name)
    return ''.join(x.title() for x in snake.split('_'))


def to_kebab_case(name: str) -> str:
    """Converts key string to kebab-case."""
    snake = to_snake_case(name)
    return snake.replace('_', '-')


def transform_key_string(
    key: str,
    casing: Optional[str] = None,
    prefix: str = "",
    suffix: str = "",
    mapping: Optional[Dict[str, str]] = None,
    regex_pattern: Optional[re.Pattern] = None,
    regex_replace: str = ""
) -> str:
    """Applies case conversions, mappings, regexes, and affixes to a key string."""
    new_key = key

    # 1. Exact mapping check
    if mapping and new_key in mapping:
        new_key = mapping[new_key]

    # 2. Casing transformation
    if casing:
        c = casing.lower()
        if c == "snake_case":
            new_key = to_snake_case(new_key)
        elif c == "camelcase":
            new_key = to_camel_case(new_key)
        elif c == "pascalcase":
            new_key = to_pascal_case(new_key)
        elif c == "kebab-case":
            new_key = to_kebab_case(new_key)
        elif c == "uppercase":
            new_key = new_key.upper()
        elif c == "lowercase":
            new_key = new_key.lower()

    # 3. Regex substitution
    if regex_pattern:
        new_key = regex_pattern.sub(regex_replace, new_key)

    # 4. Prefix & Suffix
    if prefix:
        new_key = f"{prefix}{new_key}"
    if suffix:
        new_key = f"{new_key}{suffix}"

    return new_key


def process_json_structure(
    obj: Any,
    transform_func: Callable[[str], str],
    changes: List[Tuple[str, str, str]],
    path: str = "$"
) -> Any:
    """Recursively processes JSON structures and tracks key modifications."""
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_k = transform_func(k)
            curr_path = f"{path}.{k}"
            if k != new_k:
                changes.append((curr_path, k, new_k))
            new_dict[new_k] = process_json_structure(v, transform_func, changes, f"{path}.{new_k}")
        return new_dict
    elif isinstance(obj, list):
        return [
            process_json_structure(item, transform_func, changes, f"{path}[{idx}]")
            for idx, item in enumerate(obj)
        ]
    return obj


def main():
    parser = argparse.ArgumentParser(
        description="JSON Key Rename & Transformation Utility"
    )
    parser.add_argument("target", help="Path to JSON file or raw JSON string")
    parser.add_argument(
        "--casing",
        choices=["snake_case", "camelCase", "PascalCase", "kebab-case", "UPPERCASE", "lowercase"],
        help="Convert keys to target casing standard"
    )
    parser.add_argument("--prefix", default="", help="Add prefix to all key names")
    parser.add_argument("--suffix", default="", help="Add suffix to all key names")
    parser.add_argument(
        "--map", nargs="+", metavar="OLD=NEW",
        help="Specify key rename pairs (e.g. --map id=user_id name=full_name)"
    )
    parser.add_argument("--map-file", help="Path to JSON file containing key mapping dictionary")
    parser.add_argument("--regex-pattern", help="Regex pattern to search in key names")
    parser.add_argument("--regex-replace", default="", help="Replacement string for regex pattern")
    parser.add_argument("--out", "-o", help="Save transformed JSON to output file")
    parser.add_argument("--indent", type=int, default=2, help="JSON output indentation (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview key changes without saving output")

    args = parser.parse_args()

    # Load input JSON
    try:
        if os.path.exists(args.target):
            with open(args.target, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(args.target)
    except Exception as e:
        print(f"{RED}Error parsing input JSON: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Build mapping dict
    mapping_dict = {}
    if args.map_file:
        try:
            with open(args.map_file, "r", encoding="utf-8") as f:
                mapping_dict.update(json.load(f))
        except Exception as e:
            print(f"{RED}Error reading mapping file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)

    if args.map:
        for pair in args.map:
            if "=" in pair:
                old_k, new_k = pair.split("=", 1)
                mapping_dict[old_k.strip()] = new_k.strip()

    # Compile regex pattern
    compiled_regex = None
    if args.regex_pattern:
        try:
            compiled_regex = re.compile(args.regex_pattern)
        except re.error as e:
            print(f"{RED}Invalid regex pattern: {e}{RESET}", file=sys.stderr)
            sys.exit(1)

    # Define key transform lambda
    def key_transform(k: str) -> str:
        return transform_key_string(
            key=k,
            casing=args.casing,
            prefix=args.prefix,
            suffix=args.suffix,
            mapping=mapping_dict,
            regex_pattern=compiled_regex,
            regex_replace=args.regex_replace
        )

    changes: List[Tuple[str, str, str]] = []
    transformed_data = process_json_structure(data, key_transform, changes)

    print(f"\n{BOLD}{CYAN}=== JSON Key Rename Summary ==={RESET}")
    print(f"Total keys modified: {BOLD}{len(changes)}{RESET}\n")

    if changes:
        print(f"{BOLD}Key Modifications:{RESET}")
        for path, old_k, new_k in changes[:50]:  # Cap display at 50 for readability
            print(f" - {path}: {YELLOW}'{old_k}'{RESET} -> {GREEN}'{new_k}'{RESET}")
        if len(changes) > 50:
            print(f" ... and {len(changes) - 50} more changes.")
        print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN MODE] No changes written to disk.{RESET}")
        sys.exit(0)

    # Output result
    json_output = json.dumps(transformed_data, indent=args.indent, ensure_ascii=False)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(json_output + "\n")
            print(f"{GREEN}Transformed JSON successfully written to: {args.out}{RESET}")
        except Exception as e:
            print(f"{RED}Failed to write output file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        if not changes:
            print(f"{CYAN}No keys were changed.{RESET}")
        else:
            print(f"{BOLD}Transformed Output:{RESET}")
            print(json_output)


if __name__ == "__main__":
    main()
