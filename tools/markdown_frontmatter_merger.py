#!/usr/bin/env python3
"""
Markdown Frontmatter Merger & Metadata Manager

Merges, updates, and manages YAML frontmatter metadata in Markdown files without breaking content body.

Features:
- Parse existing frontmatter blocks (delimited by '---')
- Add or overwrite metadata fields using CLI key=value pairs or JSON files
- Remove specified frontmatter fields
- Sort frontmatter keys deterministically
- Batch operation across entire directories of Markdown files
- Dry-run mode for previewing metadata diffs before writing

Usage:
    python markdown_frontmatter_merger.py document.md --set author="Jane Doe" status="published"
    python markdown_frontmatter_merger.py ./posts --set tags="['python','cli']" --sort-keys
    python markdown_frontmatter_merger.py document.md --remove draft review_date --dry-run
"""

import os
import sys
import json
import re
import argparse
from typing import Dict, Any, Tuple, List, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"


def parse_simple_yaml_frontmatter(raw_yaml: str) -> Dict[str, Any]:
    """Simple lightweight YAML parser for frontmatter key-value pairs."""
    data = {}
    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            # Attempt primitive parsing
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            elif val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.isdigit():
                val = int(val)
            elif (val.startswith("[") and val.endswith("]")) or (val.startswith("{") and val.endswith("}")):
                try:
                    val = json.loads(val.replace("'", '"'))
                except Exception:
                    pass
            data[key] = val
    return data


def dump_simple_yaml_frontmatter(data: Dict[str, Any], sort_keys: bool = False) -> str:
    """Formats Python dictionary into clean YAML frontmatter block."""
    keys = sorted(data.keys()) if sort_keys else list(data.keys())
    lines = ["---"]
    for k in keys:
        v = data[k]
        if isinstance(v, (list, dict)):
            v_str = json.dumps(v, ensure_ascii=False)
            lines.append(f"{k}: {v_str}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, str) and (":" in v or " " in v or "#" in v):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def extract_frontmatter_and_body(content: str) -> Tuple[Dict[str, Any], str]:
    """Splits Markdown content into frontmatter dictionary and body text."""
    pattern = r"^\s*---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)$"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        raw_yaml = match.group(1)
        body = match.group(2)
        return parse_simple_yaml_frontmatter(raw_yaml), body
    return {}, content.lstrip()


def merge_frontmatter(
    content: str,
    update_data: Dict[str, Any],
    remove_keys: Optional[List[str]] = None,
    sort_keys: bool = False
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Merges new metadata into content's frontmatter and returns updated content."""
    original_data, body = extract_frontmatter_and_body(content)
    updated_data = dict(original_data)

    # Apply updates
    updated_data.update(update_data)

    # Apply removals
    if remove_keys:
        for k in remove_keys:
            updated_data.pop(k, None)

    new_fm = dump_simple_yaml_frontmatter(updated_data, sort_keys=sort_keys)
    new_content = f"{new_fm}\n\n{body}" if body else f"{new_fm}\n"

    return new_content, original_data, updated_data


def main():
    parser = argparse.ArgumentParser(
        description="Markdown Frontmatter Merger & Metadata Manager"
    )
    parser.add_argument("target", help="Path to Markdown file (.md) or directory")
    parser.add_argument(
        "--set", nargs="+", metavar="KEY=VALUE",
        help="Set frontmatter key-value pairs (e.g. --set author='Alice' tags=['a','b'])"
    )
    parser.add_argument("--json-file", help="JSON file containing metadata fields to merge")
    parser.add_argument("--remove", nargs="+", metavar="KEY", help="Remove frontmatter keys")
    parser.add_argument("--sort-keys", action="store_true", help="Alphabetically sort frontmatter keys")
    parser.add_argument("--dry-run", action="store_true", help="Preview metadata changes without updating files")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Target path does not exist: {args.target}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Build update dataset
    update_dict = {}
    if args.json_file:
        try:
            with open(args.json_file, "r", encoding="utf-8") as f:
                update_dict.update(json.load(f))
        except Exception as e:
            print(f"{RED}Error loading JSON file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)

    if args.set:
        for item in args.set:
            if "=" in item:
                k, v = item.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Parse value if typed string
                if (v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}")):
                    try:
                        v = json.loads(v.replace("'", '"'))
                    except Exception:
                        pass
                elif v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                elif v.isdigit():
                    v = int(v)
                update_dict[k] = v

    targets = []
    if os.path.isfile(args.target):
        targets.append(args.target)
    else:
        for root, _, files in os.walk(args.target):
            for file in files:
                if file.endswith(".md"):
                    targets.append(os.path.join(root, file))

    print(f"\n{BOLD}{CYAN}=== Markdown Frontmatter Merger ==={RESET}")
    print(f"Target files: {len(targets)}")
    if args.dry_run:
        print(f"{YELLOW}[DRY RUN MODE ENABLED]{RESET}")
    print()

    updated_count = 0
    for filepath in targets:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                original_text = f.read()

            new_text, orig_data, new_data = merge_frontmatter(
                content=original_text,
                update_data=update_dict,
                remove_keys=args.remove,
                sort_keys=args.sort_keys
            )

            if original_text != new_text:
                updated_count += 1
                rel_p = os.path.basename(filepath)
                print(f"File: {BOLD}{rel_p}{RESET}")
                print(f" Original keys: {list(orig_data.keys())}")
                print(f" Updated keys : {list(new_data.keys())}\n")

                if not args.dry_run:
                    with open(filepath, "w", encoding="utf-8") as f_out:
                        f_out.write(new_text)

        except Exception as e:
            print(f"{RED}Failed processing {filepath}: {e}{RESET}")

    status_msg = "Would update" if args.dry_run else "Successfully updated"
    print(f"{GREEN}{status_msg} {updated_count} file(s).{RESET}")


if __name__ == "__main__":
    main()
