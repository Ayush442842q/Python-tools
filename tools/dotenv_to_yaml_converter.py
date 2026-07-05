#!/usr/bin/env python3
"""
Dotenv to YAML / JSON Converter
-------------------------------
Converts flat .env environment files into structured, nested YAML or JSON configurations.
Supports automatic type inference (booleans, numbers, arrays, JSON strings), secret masking,
and custom namespace delimiter parsing.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import Dict, Any, Union, List

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_dotenv_content(content: str) -> Dict[str, str]:
    """Parses .env file content into key-value string dictionary."""
    env_dict = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Remove export keyword if present
        if line.startswith("export "):
            line = line[7:].strip()

        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Strip enclosing single/double quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            env_dict[key] = val
    return env_dict


def infer_value_type(val_str: str) -> Any:
    """Infers integer, float, boolean, null, JSON object/array from string values."""
    if val_str.lower() in ("true", "yes", "on"):
        return True
    if val_str.lower() in ("false", "no", "off"):
        return False
    if val_str.lower() in ("null", "none", "nil"):
        return None

    # Check integer
    if re.match(r'^-?\d+$', val_str):
        try:
            return int(val_str)
        except ValueError:
            pass

    # Check float
    if re.match(r'^-?\d+\.\d+$', val_str):
        try:
            return float(val_str)
        except ValueError:
            pass

    # Check JSON
    if (val_str.startswith("{") and val_str.endswith("}")) or (
        val_str.startswith("[") and val_str.endswith("]")
    ):
        try:
            return json.loads(val_str)
        except Exception:
            pass

    # Check comma-separated values for arrays if non-empty
    if "," in val_str and not val_str.startswith("http"):
        parts = [p.strip() for p in val_str.split(",")]
        return [infer_value_type(p) for p in parts]

    return val_str


def convert_to_nested_dict(
    env_dict: Dict[str, str],
    delimiter: str = "_",
    infer_types: bool = True,
    mask_secrets: bool = False,
) -> Dict[str, Any]:
    """Converts flat key-value pairs into nested hierarchy dictionary."""
    nested = {}
    secret_patterns = ["password", "secret", "token", "key", "credential", "auth", "private"]

    for flat_key, raw_val in env_dict.items():
        val = infer_value_type(raw_val) if infer_types else raw_val

        if mask_secrets and any(sp in flat_key.lower() for sp in secret_patterns):
            val = "********"

        parts = [p.lower() for p in flat_key.split(delimiter) if p]
        current = nested
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = val
            else:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

    return nested


def dict_to_yaml(data: Any, indent_level: int = 0) -> str:
    """Simple lightweight fallback YAML serializer."""
    indent = "  " * indent_level
    yaml_lines = []

    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, (dict, list)):
                yaml_lines.append(f"{indent}{key}:")
                yaml_lines.append(dict_to_yaml(val, indent_level + 1))
            else:
                formatted_val = json.dumps(val) if isinstance(val, str) and (":" in val or "#" in val) else val
                yaml_lines.append(f"{indent}{key}: {formatted_val}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                yaml_lines.append(f"{indent}-")
                yaml_lines.append(dict_to_yaml(item, indent_level + 1))
            else:
                yaml_lines.append(f"{indent}- {item}")

    return "\n".join(yaml_lines)


def run_demo():
    """Run interactive demonstration."""
    sample_dotenv = """# Environment configuration
APP_NAME="Antigravity System"
APP_PORT=8080
APP_DEBUG=true
DATABASE_HOST="127.0.0.1"
DATABASE_PORT=5432
DATABASE_USER="postgres"
DATABASE_PASSWORD="SuperSecretPassword123!"
REDIS_ENABLED=true
REDIS_NODES=redis-01:6379,redis-02:6379
FEATURE_FLAGS='{"beta_ui": true, "max_threads": 8}'
"""
    print(f"{BOLD}{CYAN}=== Dotenv to YAML / JSON Converter Demo ==={RESET}\n")
    print(f"{BOLD}Input .env File Content:{RESET}\n")
    print(sample_dotenv)

    env_dict = parse_dotenv_content(sample_dotenv)
    nested_data = convert_to_nested_dict(env_dict, delimiter="_", infer_types=True, mask_secrets=True)

    print(f"{BOLD}{YELLOW}--- Converted Structured YAML (Secrets Masked) ---{RESET}\n")
    print(dict_to_yaml(nested_data))

    print(f"\n{BOLD}{YELLOW}--- Converted Structured JSON ---{RESET}\n")
    print(json.dumps(nested_data, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Convert flat .env configuration files into nested YAML or JSON structures."
    )
    parser.add_argument("input_file", nargs="?", help="Path to input .env file (reads stdin if omitted)")
    parser.add_argument("-o", "--output", help="Output file path (prints to stdout if omitted)")
    parser.add_argument(
        "-f", "--format", choices=["yaml", "json"], default="yaml", help="Output format (default: yaml)"
    )
    parser.add_argument(
        "-d", "--delimiter", default="_", help="Key hierarchy namespace delimiter (default: '_')"
    )
    parser.add_argument(
        "--mask-secrets", action="store_true", help="Mask sensitive variable values (passwords, tokens, keys)"
    )
    parser.add_argument(
        "--no-type-infer", action="store_false", dest="infer_types", help="Keep all values as raw strings"
    )
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    args = parser.parse_args()

    if args.demo or (not args.input_file and sys.stdin.isatty()):
        run_demo()
        return

    if args.input_file:
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file '{args.input_file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content = sys.stdin.read()

    env_dict = parse_dotenv_content(content)
    nested_data = convert_to_nested_dict(
        env_dict, delimiter=args.delimiter, infer_types=args.infer_types, mask_secrets=args.mask_secrets
    )

    if args.format.lower() == "json":
        result = json.dumps(nested_data, indent=2)
    else:
        result = dict_to_yaml(nested_data)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"Successfully exported configuration to '{args.output}'.")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(result)


if __name__ == "__main__":
    main()
