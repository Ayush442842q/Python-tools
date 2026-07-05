#!/usr/bin/env python3
"""JSON to .env Converter

Converts JSON configuration files or strings into standard .env environment variable files.
Supports flattening nested JSON structures, custom delimiters, array formatting, key casing choices,
and optional secret redacting/masking.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


def flatten_json(
    data: Any,
    prefix: str = "",
    separator: str = "_",
    uppercase: str = "true",
    array_mode: str = "comma",
) -> List[Tuple[str, str]]:
    """Recursively flattens a nested JSON dictionary into key-value tuples suitable for .env."""
    items: List[Tuple[str, str]] = []

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{prefix}{separator}{key}" if prefix else str(key)
            items.extend(flatten_json(value, new_key, separator, uppercase, array_mode))
    elif isinstance(data, list):
        if array_mode == "comma":
            formatted_val = ",".join(str(v) for v in data)
            items.append((prefix, formatted_val))
        elif array_mode == "json":
            items.append((prefix, json.dumps(data)))
        elif array_mode == "indexed":
            for idx, item in enumerate(data):
                new_key = f"{prefix}{separator}{idx}"
                items.extend(flatten_json(item, new_key, separator, uppercase, array_mode))
    else:
        if data is None:
            val_str = ""
        elif isinstance(data, bool):
            val_str = "true" if data else "false"
        else:
            val_str = str(data)
        items.append((prefix, val_str))

    return items


def format_env_key(key: str, uppercase: bool = True) -> str:
    """Formats the key string for .env compatibility."""
    clean_key = key.replace("-", "_").replace(".", "_")
    return clean_key.upper() if uppercase else clean_key


def format_env_value(value: str) -> str:
    """Formats the value for .env, quoting if it contains spaces or special characters."""
    if not value:
        return '""'
    if "\n" in value or " " in value or "#" in value or '"' in value or "'" in value:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def mask_sensitive_value(key: str, value: str) -> str:
    """Masks value if key contains sensitive keywords."""
    sensitive_words = ["SECRET", "PASSWORD", "PASS", "KEY", "TOKEN", "CREDENTIAL", "AUTH", "PRIVATE"]
    upper_key = key.upper()
    if any(word in upper_key for word in sensitive_words):
        if len(value) <= 4:
            return "****"
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    return value


def convert_json_to_env(
    json_data: Any,
    prefix_filter: str = "",
    separator: str = "_",
    uppercase: bool = True,
    array_mode: str = "comma",
    mask_secrets: bool = False,
    sort_keys: bool = True,
) -> str:
    """Main function to convert a JSON object into .env formatted string."""
    flat_items = flatten_json(
        json_data,
        prefix=prefix_filter,
        separator=separator,
        uppercase="true" if uppercase else "false",
        array_mode=array_mode,
    )

    env_pairs: List[Tuple[str, str]] = []
    for raw_key, raw_val in flat_items:
        formatted_key = format_env_key(raw_key, uppercase=uppercase)
        val = mask_sensitive_value(formatted_key, raw_val) if mask_secrets else raw_val
        formatted_val = format_env_value(val)
        env_pairs.append((formatted_key, formatted_val))

    if sort_keys:
        env_pairs.sort(key=lambda x: x[0])

    lines = [f"{k}={v}" for k, v in env_pairs]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert JSON configuration file or input into .env format."
    )
    parser.add_argument("input", nargs="?", help="Path to input JSON file. Reads stdin if omitted.")
    parser.add_argument("-o", "--output", help="Output path for generated .env file.")
    parser.add_argument(
        "--separator", default="_", help="Delimiter used to join nested keys (default: '_')."
    )
    parser.add_argument(
        "--prefix", default="", help="Prefix prepended to all generated environment variables."
    )
    parser.add_argument(
        "--no-uppercase", action="store_true", help="Preserve original key casing instead of forcing UPPERCASE."
    )
    parser.add_argument(
        "--array-mode",
        choices=["comma", "json", "indexed"],
        default="comma",
        help="How to format array values: 'comma' (val1,val2), 'json' (['val1']), or 'indexed' (KEY_0, KEY_1).",
    )
    parser.add_argument(
        "--mask-secrets", action="store_true", help="Mask sensitive values (e.g. passwords, tokens, keys)."
    )
    parser.add_argument(
        "--no-sort", action="store_true", help="Do not sort the output environment keys alphabetically."
    )

    args = parser.parse_args()

    # Read JSON content
    if args.input and args.input != "-":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"{COLOR_RED}Error: Input file '{args.input}' not found.{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"{COLOR_RED}Error parsing JSON file: {e}{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            data = json.load(sys.stdin)
        except Exception as e:
            print(f"{COLOR_RED}Error parsing JSON from stdin: {e}{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)

    env_output = convert_json_to_env(
        json_data=data,
        prefix_filter=args.prefix,
        separator=args.separator,
        uppercase=not args.no_uppercase,
        array_mode=args.array_mode,
        mask_secrets=args.mask_secrets,
        sort_keys=not args.no_sort,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(env_output + "\n")
        print(f"{COLOR_GREEN}Successfully wrote {len(env_output.splitlines())} variables to '{args.output}'.{COLOR_RESET}")
    else:
        print(env_output)


if __name__ == "__main__":
    main()
