#!/usr/bin/env python3
"""
JSON Structure & Schema Tree Visualizer
Parses complex nested JSON or JSONL files and renders visual ASCII/Unicode structural trees,
displaying data types, element counts, key statistics, and schema summaries.
"""

import argparse
import json
import os
import sys

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_type_name(value):
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    return type(value).__name__


def format_sample(value, max_len=20):
    if value is None:
        return "null"
    if isinstance(value, str):
        s = repr(value)
        return s[:max_len] + "..." if len(s) > max_len else s
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def build_tree_lines(data, prefix="", is_last=True, depth=0, max_depth=10, show_samples=True):
    lines = []
    if depth > max_depth:
        lines.append(f"{prefix}{'└── ' if is_last else '├── '}{YELLOW}... (depth limit reached){RESET}")
        return lines

    val_type = get_type_name(data)
    type_color = {
        "object": CYAN,
        "array": MAGENTA,
        "string": GREEN,
        "integer": BLUE,
        "float": BLUE,
        "boolean": YELLOW,
        "null": RED
    }.get(val_type, RESET)

    connector = "└── " if is_last else "├── "

    if isinstance(data, dict):
        lines.append(f"{prefix}{connector}{type_color}{BOLD}{val_type}{RESET} ({len(data)} keys)")
        new_prefix = prefix + ("    " if is_last else "│   ")
        keys = list(data.keys())
        for idx, key in enumerate(keys):
            last_key = idx == len(keys) - 1
            key_conn = "└── " if last_key else "├── "
            child_val = data[key]
            child_type = get_type_name(child_val)
            child_color = type_color = {
                "object": CYAN,
                "array": MAGENTA,
                "string": GREEN,
                "integer": BLUE,
                "float": BLUE,
                "boolean": YELLOW,
                "null": RED
            }.get(child_type, RESET)

            if isinstance(child_val, (dict, list)):
                lines.append(f"{new_prefix}{key_conn}{BOLD}{key}{RESET}: {child_color}{child_type}{RESET}")
                lines.extend(build_tree_lines(child_val, new_prefix + ("    " if last_key else "│   "), True, depth + 1, max_depth, show_samples))
            else:
                sample_str = f" = {format_sample(child_val)}" if show_samples else ""
                lines.append(f"{new_prefix}{key_conn}{BOLD}{key}{RESET}: {child_color}{child_type}{RESET}{sample_str}")

    elif isinstance(data, list):
        lines.append(f"{prefix}{connector}{type_color}{BOLD}{val_type}{RESET} [{len(data)} items]")
        new_prefix = prefix + ("    " if is_last else "│   ")
        if data:
            # Check homogeneous or sample elements
            types_in_list = set(get_type_name(x) for x in data)
            if len(data) > 0 and (isinstance(data[0], (dict, list)) or len(types_in_list) > 1):
                sample_count = min(len(data), 3)
                for idx in range(sample_count):
                    last_item = idx == sample_count - 1 and len(data) == sample_count
                    item_conn = "└── " if last_item else "├── "
                    lines.append(f"{new_prefix}{item_conn}[{idx}]:")
                    lines.extend(build_tree_lines(data[idx], new_prefix + ("    " if last_item else "│   "), True, depth + 1, max_depth, show_samples))
                if len(data) > sample_count:
                    lines.append(f"{new_prefix}└── ... (+{len(data) - sample_count} more items of types: {', '.join(types_in_list)})")
            else:
                sample_str = f" e.g. {format_sample(data[0])}" if show_samples and data else ""
                lines.append(f"{new_prefix}└── items type: {GREEN}{list(types_in_list)[0] if types_in_list else 'empty'}{RESET}{sample_str}")
    else:
        sample_str = f" = {format_sample(data)}" if show_samples else ""
        lines.append(f"{prefix}{connector}{type_color}{val_type}{RESET}{sample_str}")

    return lines


def compute_schema_stats(data):
    stats = {"total_keys": 0, "max_depth": 0, "type_counts": {}}

    def _traverse(val, current_depth):
        stats["max_depth"] = max(stats["max_depth"], current_depth)
        t_name = get_type_name(val)
        stats["type_counts"][t_name] = stats["type_counts"].get(t_name, 0) + 1

        if isinstance(val, dict):
            stats["total_keys"] += len(val)
            for k, v in val.items():
                _traverse(v, current_depth + 1)
        elif isinstance(val, list):
            for item in val:
                _traverse(item, current_depth + 1)

    _traverse(data, 1)
    return stats


def run_demo():
    sample_json = {
        "app_name": "Antigravity Workspace Manager",
        "version": "2.4.0",
        "active": True,
        "port": 8080,
        "database": {
            "host": "localhost",
            "max_connections": 50,
            "ssl_enabled": False,
            "credentials": None
        },
        "modules": [
            {
                "id": "mod_auth",
                "enabled": True,
                "routes": ["/login", "/logout", "/token"]
            },
            {
                "id": "mod_analytics",
                "enabled": False,
                "routes": ["/metrics", "/health"]
            }
        ],
        "tags": ["python", "cli", "tools", "utility"]
    }

    print(f"{BOLD}{CYAN}=== JSON Structure Visualizer Demo ==={RESET}\n")
    print(f"{BOLD}Visualizing Nested JSON Tree Structure:{RESET}\n")

    lines = build_tree_lines(sample_json, max_depth=10, show_samples=True)
    print("\n".join(lines))

    stats = compute_schema_stats(sample_json)
    print(f"\n{BOLD}{YELLOW}Schema Statistics:{RESET}")
    print(f"  • Total Keys : {stats['total_keys']}")
    print(f"  • Max Depth  : {stats['max_depth']}")
    print(f"  • Type Breakdown:")
    for t_name, count in sorted(stats['type_counts'].items()):
        print(f"    - {t_name.capitalize():<10}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize JSON / JSONL structure as an ASCII tree with schema insights."
    )
    parser.add_argument("file", nargs="?", help="JSON file path to inspect")
    parser.add_argument("--max-depth", type=int, default=10, help="Maximum tree depth to display (default: 10)")
    parser.add_argument("--no-samples", action="store_true", help="Hide sample values in tree nodes")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demo")

    args = parser.parse_args()

    if args.demo or not args.file:
        if not args.file and not args.demo:
            print(f"{YELLOW}No JSON file specified. Running demo mode...{RESET}\n")
        run_demo()
        return

    if not os.path.isfile(args.file):
        print(f"{RED}Error: File '{args.file}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content.startswith("{") or content.startswith("["):
                data = json.loads(content)
            else:
                # Try parsing as JSONL
                data = [json.loads(line) for line in content.splitlines() if line.strip()]

        print(f"\n{BOLD}{CYAN}=== JSON Structure Tree for: {args.file} ==={RESET}\n")
        lines = build_tree_lines(data, max_depth=args.max_depth, show_samples=not args.no_samples)
        print("\n".join(lines))

        stats = compute_schema_stats(data)
        print(f"\n{BOLD}{YELLOW}Schema Summary:{RESET}")
        print(f"  • Total Keys : {stats['total_keys']}")
        print(f"  • Max Depth  : {stats['max_depth']}")
        print(f"  • Data Types : {', '.join(f'{k}({v})' for k,v in stats['type_counts'].items())}\n")

    except Exception as e:
        print(f"{RED}Error parsing JSON file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
