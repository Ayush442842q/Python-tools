#!/usr/bin/env python3
"""
JSON Diff Tool - Semantically compare two JSON files.

This tool recursively compares two JSON structures, identifying added, removed,
and modified keys, ignoring differences in key ordering or whitespace.

Usage:
    python tools/json_diff.py file1.json file2.json [options]
"""

import json
import sys
import argparse
from typing import Any, Dict, List, Tuple, Union

# ANSI escape codes for colorized output
COLOR_ADD = "\033[92m"      # Green
COLOR_REMOVE = "\033[91m"   # Red
COLOR_MODIFY = "\033[93m"   # Yellow
COLOR_RESET = "\033[0m"
COLOR_PATH = "\033[96m"     # Cyan


def parse_args():
    parser = argparse.ArgumentParser(
        description="JSON Diff - Compare two JSON files semantically."
    )
    parser.add_argument("file1", help="First JSON file (original)")
    parser.add_argument("file2", help="Second JSON file (modified)")
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colorized output"
    )
    parser.add_argument(
        "--brief", "-b", action="store_true", help="Only show summary, not full details"
    )
    return parser.parse_args()


def load_json(filepath: str) -> Any:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: '{filepath}' is not valid JSON. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def compare_json(
    val1: Any, val2: Any, path: str = "root", diffs: Dict[str, List[Tuple[str, Any]]] = None
) -> Dict[str, List[Tuple[str, Any]]]:
    if diffs is None:
        diffs = {"added": [], "removed": [], "modified": []}

    if type(val1) != type(val2):
        diffs["modified"].append((path, (val1, val2)))
        return diffs

    if isinstance(val1, dict):
        keys1 = set(val1.keys())
        keys2 = set(val2.keys())

        # Removed keys
        for k in keys1 - keys2:
            diffs["removed"].append((f"{path}.{k}", val1[k]))

        # Added keys
        for k in keys2 - keys1:
            diffs["added"].append((f"{path}.{k}", val2[k]))

        # Keys in both
        for k in keys1 & keys2:
            compare_json(val1[k], val2[k], f"{path}.{k}", diffs)

    elif isinstance(val1, list):
        len1 = len(val1)
        len2 = len(val2)
        min_len = min(len1, len2)

        for i in range(min_len):
            compare_json(val1[i], val2[i], f"{path}[{i}]", diffs)

        if len1 > len2:
            for i in range(min_len, len1):
                diffs["removed"].append((f"{path}[{i}]", val1[i]))
        elif len2 > len1:
            for i in range(min_len, len2):
                diffs["added"].append((f"{path}[{i}]", val2[i]))

    else:
        if val1 != val2:
            diffs["modified"].append((path, (val1, val2)))

    return diffs


def format_value(val: Any) -> str:
    if isinstance(val, (dict, list)):
        return json.dumps(val, indent=2)
    return str(val)


def print_diffs(diffs: Dict[str, List[Any]], use_color: bool, brief: bool):
    green = COLOR_ADD if use_color else ""
    red = COLOR_REMOVE if use_color else ""
    yellow = COLOR_MODIFY if use_color else ""
    cyan = COLOR_PATH if use_color else ""
    reset = COLOR_RESET if use_color else ""

    added = diffs["added"]
    removed = diffs["removed"]
    modified = diffs["modified"]

    total_diffs = len(added) + len(removed) + len(modified)

    print(f"=== JSON Diff Summary ===")
    print(f"Added keys/elements:      {green}{len(added)}{reset}")
    print(f"Removed keys/elements:    {red}{len(removed)}{reset}")
    print(f"Modified keys/elements:   {yellow}{len(modified)}{reset}")
    print(f"Total Differences:        {total_diffs}")
    print("=========================\n")

    if brief or total_diffs == 0:
        return

    if removed:
        print(f"{red}--- REMOVED ELEMENTS ---{reset}")
        for path, val in removed:
            print(f"{cyan}{path}{reset}")
            val_str = format_value(val)
            for line in val_str.splitlines():
                print(f"{red}- {line}{reset}")
        print()

    if added:
        print(f"{green}+++ ADDED ELEMENTS +++{reset}")
        for path, val in added:
            print(f"{cyan}{path}{reset}")
            val_str = format_value(val)
            for line in val_str.splitlines():
                print(f"{green}+ {line}{reset}")
        print()

    if modified:
        print(f"{yellow}~~~ MODIFIED ELEMENTS ~~~{reset}")
        for path, (val1, val2) in modified:
            print(f"{cyan}{path}{reset}")
            val1_str = format_value(val1)
            val2_str = format_value(val2)
            # Simple layout: before and after
            if '\n' in val1_str or '\n' in val2_str:
                print(f"{red}- (Original):{reset}")
                for line in val1_str.splitlines():
                    print(f"{red}-   {line}{reset}")
                print(f"{green}+ (Modified):{reset}")
                for line in val2_str.splitlines():
                    print(f"{green}+   {line}{reset}")
            else:
                print(f"{red}- {val1_str}{reset} -> {green}+ {val2_str}{reset}")
        print()


def main():
    args = parse_args()
    use_color = not args.no_color and sys.stdout.isatty()

    val1 = load_json(args.file1)
    val2 = load_json(args.file2)

    diffs = compare_json(val1, val2)
    print_diffs(diffs, use_color, args.brief)

    # Return 1 if there are differences, 0 otherwise
    has_diffs = any(diffs.values())
    return 1 if has_diffs else 0


if __name__ == "__main__":
    sys.exit(main())
