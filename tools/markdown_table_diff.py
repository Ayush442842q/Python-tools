#!/usr/bin/env python3
"""
Markdown Table Diff & Comparator
Compares two Markdown files (or raw GFM pipe tables) and highlights added, removed,
or modified rows and columns in side-by-side or unified table diff format.
"""

import argparse
import os
import re
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
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def parse_markdown_tables(content):
    lines = content.splitlines()
    tables = []
    current_table = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_table.append(stripped)
        else:
            if current_table:
                tables.append(current_table)
                current_table = []

    if current_table:
        tables.append(current_table)

    parsed_tables = []
    for table_lines in tables:
        if len(table_lines) < 2:
            continue
        
        # Parse headers
        headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
        
        # Check if line 1 is separator (e.g. |---|---|)
        sep_index = 1 if re.match(r"^\|?\s*:?-+:?\s*(\||\s*$)", table_lines[1]) else None
        data_start = 2 if sep_index else 1

        rows = []
        for line in table_lines[data_start:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            # Match cell count to headers count
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            rows.append(cells[:len(headers)])

        parsed_tables.append({
            "headers": headers,
            "rows": rows
        })

    return parsed_tables


def diff_tables(table_a, table_b, key_col=0):
    headers_a = table_a["headers"]
    headers_b = table_b["headers"]

    # Combine headers
    all_headers = list(headers_a)
    for h in headers_b:
        if h not in all_headers:
            all_headers.append(h)

    rows_a_map = {}
    for idx, r in enumerate(table_a["rows"]):
        key = r[key_col] if key_col < len(r) else str(idx)
        rows_a_map[key] = (idx, r)

    rows_b_map = {}
    for idx, r in enumerate(table_b["rows"]):
        key = r[key_col] if key_col < len(r) else str(idx)
        rows_b_map[key] = (idx, r)

    diff_result = []

    all_keys = list(rows_a_map.keys())
    for k in rows_b_map:
        if k not in all_keys:
            all_keys.append(k)

    for k in all_keys:
        in_a = k in rows_a_map
        in_b = k in rows_b_map

        if in_a and not in_b:
            diff_result.append({
                "status": "removed",
                "key": k,
                "row_a": rows_a_map[k][1],
                "row_b": None
            })
        elif not in_a and in_b:
            diff_result.append({
                "status": "added",
                "key": k,
                "row_a": None,
                "row_b": rows_b_map[k][1]
            })
        else:
            row_a = rows_a_map[k][1]
            row_b = rows_b_map[k][1]
            
            # Check cell modifications
            changed_cells = []
            for h_idx, h in enumerate(headers_a):
                val_a = row_a[h_idx] if h_idx < len(row_a) else ""
                val_b_idx = headers_b.index(h) if h in headers_b else -1
                val_b = row_b[val_b_idx] if val_b_idx != -1 and val_b_idx < len(row_b) else ""

                if val_a != val_b:
                    changed_cells.append((h, val_a, val_b))

            if changed_cells:
                diff_result.append({
                    "status": "modified",
                    "key": k,
                    "row_a": row_a,
                    "row_b": row_b,
                    "changes": changed_cells
                })
            else:
                diff_result.append({
                    "status": "unchanged",
                    "key": k,
                    "row_a": row_a,
                    "row_b": row_b
                })

    return all_headers, diff_result


def run_demo():
    tbl_a = """
| Tool Name | Category | Status | Version |
|---|---|---|---|
| backup_tool.py | File System | Active | 1.0.0 |
| log_parser.py | Data | Active | 1.2.0 |
| old_scanner.py | Security | Deprecated | 0.9.0 |
"""

    tbl_b = """
| Tool Name | Category | Status | Version |
|---|---|---|---|
| backup_tool.py | File System | Active | 1.1.0 |
| log_parser.py | Data | Active | 1.2.0 |
| new_fuzzer.py | Security | Active | 2.0.0 |
"""

    print(f"{BOLD}{CYAN}=== Markdown Table Diff Demo ==={RESET}\n")
    tables_a = parse_markdown_tables(tbl_a)
    tables_b = parse_markdown_tables(tbl_b)

    if not tables_a or not tables_b:
        print(f"{RED}Failed to parse demo tables.{RESET}")
        return

    headers, diffs = diff_tables(tables_a[0], tables_b[0], key_col=0)

    print(f"{BOLD}Headers:{RESET} {', '.join(headers)}\n")
    print(f"{BOLD}Diff Results:{RESET}\n")

    for item in diffs:
        status = item["status"]
        if status == "unchanged":
            print(f"  [UNCHANGED] {item['key']}")
        elif status == "added":
            print(f"  {GREEN}[+ ADDED]   {item['key']}: {item['row_b']}{RESET}")
        elif status == "removed":
            print(f"  {RED}[- REMOVED] {item['key']}: {item['row_a']}{RESET}")
        elif status == "modified":
            print(f"  {YELLOW}[* MODIFIED]{RESET} {item['key']}:")
            for h, old_v, new_v in item["changes"]:
                print(f"      - {h}: {RED}'{old_v}'{RESET} -> {GREEN}'{new_v}'{RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compare two Markdown tables and report row/column additions, removals, and modifications."
    )
    parser.add_argument("file_a", nargs="?", help="First Markdown file")
    parser.add_argument("file_b", nargs="?", help="Second Markdown file")
    parser.add_argument("--key-col", type=int, default=0, help="Column index to use as row key (default: 0)")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demo")

    args = parser.parse_args()

    if args.demo or not (args.file_a and args.file_b):
        if not (args.file_a and args.file_b) and not args.demo:
            print(f"{YELLOW}Two markdown files required. Running demo mode...{RESET}\n")
        run_demo()
        return

    for path in (args.file_a, args.file_b):
        if not os.path.isfile(path):
            print(f"{RED}Error: File '{path}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)

    try:
        with open(args.file_a, "r", encoding="utf-8") as f:
            t_a = parse_markdown_tables(f.read())
        with open(args.file_b, "r", encoding="utf-8") as f:
            t_b = parse_markdown_tables(f.read())

        if not t_a or not t_b:
            print(f"{RED}Error: Could not find Markdown pipe tables in one or both files.{RESET}")
            sys.exit(1)

        headers, diffs = diff_tables(t_a[0], t_b[0], key_col=args.key_col)

        print(f"\n{BOLD}{CYAN}=== Markdown Table Diff Report ==={RESET}\n")
        added_count = sum(1 for d in diffs if d["status"] == "added")
        removed_count = sum(1 for d in diffs if d["status"] == "removed")
        mod_count = sum(1 for d in diffs if d["status"] == "modified")

        for item in diffs:
            status = item["status"]
            if status == "added":
                print(f"  {GREEN}[+ ADDED]   {item['key']}: {item['row_b']}{RESET}")
            elif status == "removed":
                print(f"  {RED}[- REMOVED] {item['key']}: {item['row_a']}{RESET}")
            elif status == "modified":
                print(f"  {YELLOW}[* MODIFIED]{RESET} {item['key']}:")
                for h, old_v, new_v in item["changes"]:
                    print(f"      - {h}: {RED}'{old_v}'{RESET} -> {GREEN}'{new_v}'{RESET}")

        print(f"\n{BOLD}Summary:{RESET} {GREEN}+{added_count} added{RESET}, {RED}-{removed_count} removed{RESET}, {YELLOW}*{mod_count} modified{RESET}")

    except Exception as e:
        print(f"{RED}Error performing diff: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
