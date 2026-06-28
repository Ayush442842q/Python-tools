#!/usr/bin/env python3
"""
JSON Key Sorter - Recursively sorts the keys of JSON files.
Supports sorting alphabetically, reverse sorting, sorting with priority/bottom keys,
check-only mode, safe backups, and in-place sorting.
"""

import os
import sys
import json
import argparse
from collections import OrderedDict

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_color(text, color):
    print(f"{color}{text}{RESET}")

def sort_json_data(data, reverse=False, priority_keys=None, bottom_keys=None):
    """
    Recursively sorts dictionary keys. Priority keys are placed first,
    bottom keys are placed last, and others are sorted alphabetically.
    """
    if isinstance(data, dict):
        priority = priority_keys or []
        bottom = bottom_keys or []

        def sort_key(k):
            # We want to return a tuple representing the sort order:
            # 1. Priority keys (using their index in the priority list)
            # 2. Sorted standard keys
            # 3. Bottom keys (using their index in the bottom list)
            if k in priority:
                return (0, priority.index(k), k)
            elif k in bottom:
                return (2, bottom.index(k), k)
            else:
                # Reverse alphabetical if requested
                return (1, k if not reverse else [-ord(c) for c in k], k)

        sorted_keys = sorted(data.keys(), key=sort_key)
        
        ordered_dict = OrderedDict()
        for k in sorted_keys:
            ordered_dict[k] = sort_json_data(data[k], reverse, priority, bottom)
        return ordered_dict

    elif isinstance(data, list):
        return [sort_json_data(item, reverse, priority_keys, bottom_keys) for item in data]
    else:
        return data

def process_file(filepath, args):
    if not os.path.exists(filepath):
        print_color(f"Error: File '{filepath}' does not exist.", RED)
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print_color(f"Error: '{filepath}' is not a valid JSON file. {e}", RED)
        return False
    except Exception as e:
        print_color(f"Error reading '{filepath}': {e}", RED)
        return False

    # Perform recursive sort
    sorted_data = sort_json_data(
        data, 
        reverse=args.reverse, 
        priority_keys=args.priority, 
        bottom_keys=args.bottom
    )

    # Format sorted data
    sorted_content = json.dumps(sorted_data, indent=args.indent, ensure_ascii=False)
    # Add trailing newline standard
    sorted_content += "\n"

    # Normalize whitespace for direct comparison
    # We can parse raw content back and dump to check if it's already structured/sorted identically
    normalized_raw = json.dumps(data, indent=args.indent, ensure_ascii=False) + "\n"
    is_sorted = normalized_raw == sorted_content

    if args.check:
        if is_sorted:
            print(f"File '{filepath}': {GREEN}Already Sorted{RESET}")
            return True
        else:
            print(f"File '{filepath}': {RED}Not Sorted{RESET}")
            return False

    if is_sorted:
        print(f"File '{filepath}': Already sorted. No changes made.")
        return True

    # Backup if requested
    if args.backup and not args.dry_run:
        backup_path = filepath + ".bak"
        try:
            with open(backup_path, 'w', encoding='utf-8') as bf:
                bf.write(raw_content)
            print(f"Backup created: '{backup_path}'")
        except Exception as e:
            print_color(f"Error creating backup for '{filepath}': {e}", RED)
            return False

    # Output changes
    if args.dry_run:
        print_color(f"[DRY-RUN] File '{filepath}' would be sorted.", YELLOW)
        if args.verbose:
            print("--- Sorted Output Preview ---")
            print(sorted_content[:500] + ("\n..." if len(sorted_content) > 500 else ""))
    else:
        if args.in_place:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(sorted_content)
                print_color(f"Successfully sorted '{filepath}' in-place.", GREEN)
            except Exception as e:
                print_color(f"Error writing sorted JSON to '{filepath}': {e}", RED)
                return False
        else:
            sys.stdout.write(sorted_content)

    return True

def main():
    parser = argparse.ArgumentParser(
        description="JSON Key Sorter - Recursively sorts keys of JSON structures."
    )
    parser.add_argument("files", nargs="+", help="JSON files to process")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify files in-place instead of printing to stdout")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sort keys in reverse order")
    parser.add_argument("-c", "--check", action="store_true", help="Only check if files are sorted. Exit with 0 if sorted, 1 otherwise")
    parser.add_argument("-b", "--backup", action="store_true", help="Create a .bak backup file before modifying")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Perform a dry run without modifying files")
    parser.add_argument("--indent", type=int, default=4, help="Indentation level for output (default: 4)")
    parser.add_argument("--verbose", action="store_true", help="Show more detail/previews")
    
    # Priority key ordering options
    parser.add_argument(
        "-p", "--priority",
        help="Comma-separated list of keys to place at the top of object keys (e.g. 'id,name,type')"
    )
    parser.add_argument(
        "--bottom",
        help="Comma-separated list of keys to place at the bottom of object keys (e.g. 'created_at,updated_at')"
    )

    args = parser.parse_args()

    # Parse priority and bottom keys
    args.priority = [k.strip() for k in args.priority.split(",")] if args.priority else []
    args.bottom = [k.strip() for k in args.bottom.split(",")] if args.bottom else []

    # Windows ANSI support
    if sys.platform == "win32":
        os.system("")

    all_success = True
    for filepath in args.files:
        success = process_file(filepath, args)
        if not success:
            all_success = False

    if args.check:
        sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    main()
