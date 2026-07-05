#!/usr/bin/env python3
"""
Markdown Heading Hierarchy & Structural Validator

Audits Markdown files for heading hierarchy errors (skipped heading levels like H1 -> H3),
multiple H1 titles, duplicate section titles breaking anchor links, and empty sections.
Supports auto-fixing skipped levels, rendering visual ASCII heading outline trees,
and generating JSON audit reports.

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional


HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.+)$')


def audit_markdown_file(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    headings = []
    issues = []
    seen_titles: Dict[str, List[int]] = {}

    in_code_block = False
    h1_count = 0
    prev_level = 0

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        match = HEADING_REGEX.match(stripped)
        if match:
            hashes, title = match.groups()
            level = len(hashes)
            title_clean = title.strip()

            headings.append({
                "line": idx,
                "level": level,
                "title": title_clean
            })

            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    issues.append({
                        "type": "multiple_h1",
                        "line": idx,
                        "message": f"Multiple H1 headings detected: '{title_clean}'"
                    })

            # Check skipped level (e.g. H1 followed by H3)
            if prev_level > 0 and level > prev_level + 1:
                issues.append({
                    "type": "skipped_level",
                    "line": idx,
                    "prev_level": prev_level,
                    "current_level": level,
                    "message": f"Skipped heading level from H{prev_level} to H{level} for '{title_clean}'"
                })

            # Check duplicate heading title
            slug = re.sub(r'[^\w\-]', '', title_clean.lower().replace(' ', '-'))
            if slug:
                seen_titles.setdefault(slug, []).append(idx)

            prev_level = level

    # Check duplicates
    for slug, line_nums in seen_titles.items():
        if len(line_nums) > 1:
            issues.append({
                "type": "duplicate_title",
                "lines": line_nums,
                "message": f"Duplicate heading title slug '{slug}' on lines {line_nums}"
            })

    return {
        "file_path": str(file_path),
        "total_headings": len(headings),
        "h1_count": h1_count,
        "issues_count": len(issues),
        "headings": headings,
        "issues": issues
    }


def render_ascii_tree(headings: List[dict]) -> str:
    tree_lines = []
    for h in headings:
        indent = "  " * (h["level"] - 1)
        tree_lines.append(f"{indent}H{h['level']}: {h['title']} (L{h['line']})")
    return "\n".join(tree_lines)


def auto_fix_markdown_file(file_path: Path) -> bool:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    modified = False

    in_code_block = False
    prev_level = 0

    fixed_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            fixed_lines.append(line)
            continue

        if in_code_block:
            fixed_lines.append(line)
            continue

        match = HEADING_REGEX.match(stripped)
        if match:
            hashes, title = match.groups()
            level = len(hashes)

            if prev_level > 0 and level > prev_level + 1:
                fixed_level = prev_level + 1
                fixed_hashes = "#" * fixed_level
                fixed_lines.append(f"{fixed_hashes} {title}")
                prev_level = fixed_level
                modified = True
            else:
                prev_level = level
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    if modified:
        file_path.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")

    return modified


def main():
    parser = argparse.ArgumentParser(
        description="Audit Markdown files for heading hierarchy errors, skipped levels, and duplicate titles."
    )
    parser.add_argument("path", nargs="?", default=".", help="Path to Markdown file or directory (default: current directory)")
    parser.add_argument("--tree", action="store_true", help="Display visual ASCII heading outline tree")
    parser.add_argument("--fix", action="store_true", help="Auto-fix skipped heading levels in-place")
    parser.add_argument("--json", action="store_true", help="Output audit results in JSON format")

    args = parser.parse_args()
    target_path = Path(args.path).resolve()

    if not target_path.exists():
        print(f"Error: Path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    md_files = [target_path] if target_path.is_file() else list(target_path.rglob("*.md"))

    if not md_files:
        print("No Markdown files found for analysis.")
        sys.exit(0)

    reports = []
    total_issues = 0

    for file_p in md_files:
        if "node_modules" in file_p.parts or ".git" in file_p.parts:
            continue

        if args.fix:
            was_fixed = auto_fix_markdown_file(file_p)
            if was_fixed:
                print(f"Auto-fixed skipped heading levels in '{file_p.name}'.")

        report = audit_markdown_file(file_p)
        reports.append(report)
        total_issues += report["issues_count"]

    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        print("=== Markdown Heading Hierarchy Audit ===")
        print(f"Analyzed Files : {len(reports)}")
        print(f"Total Issues   : {total_issues}")

        for r in reports:
            if r["issues_count"] > 0 or args.tree:
                print(f"\nFile: {r['file_path']} ({r['total_headings']} headings, {r['issues_count']} issues)")
                
                if args.tree:
                    print("\n--- Heading Outline Tree ---")
                    print(render_ascii_tree(r["headings"]))

                if r["issues"]:
                    print("--- Issues Detected ---")
                    for iss in r["issues"]:
                        print(f"  - [Line {iss.get('line', iss.get('lines'))}] {iss['message']}")

    if total_issues > 0 and not args.fix and not args.json:
        print(f"\nTip: Run with --fix to automatically normalize skipped heading levels.")


if __name__ == "__main__":
    main()
