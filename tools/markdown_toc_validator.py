#!/usr/bin/env python3
"""
Markdown Table of Contents (TOC) Validator & Auto-Fixer

Scans Markdown document(s), extracts heading hierarchies (#, ##, ###),
validates existing TOC blocks (or list items) against actual document headings,
detects missing/broken anchors/slugs and out-of-order items, and provides an
automatic repair option (`--fix`).

Usage:
    python markdown_toc_validator.py [file_or_dir] [options]
"""

import os
import sys
import re
import argparse
from typing import List, Tuple, Dict, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def slugify_heading(title: str) -> str:
    """Converts a heading title to standard GitHub Flavored Markdown slug format."""
    # Strip markdown links, code backticks, bold/italics
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", title)
    clean = re.sub(r"[`\*_~]", "", clean)
    clean = clean.lower().strip()
    # Replace non-alphanumeric (except hyphen and space) with empty
    clean = re.sub(r"[^\w\s-]", "", clean)
    # Replace whitespace with hyphens
    clean = re.sub(r"\s+", "-", clean)
    return clean


class Heading:
    def __init__(self, level: int, title: str, line_num: int):
        self.level = level
        self.title = title.strip()
        self.line_num = line_num
        self.slug = slugify_heading(self.title)


def parse_markdown_headings(lines: List[str]) -> List[Heading]:
    """Extracts headings while ignoring code blocks."""
    headings = []
    in_code_block = False

    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if not in_code_block and stripped.startswith("#"):
            match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                # Skip title of "Table of Contents" heading itself if present
                if title.lower() in ["table of contents", "toc"]:
                    continue
                headings.append(Heading(level, title, line_idx))

    return headings


def generate_toc_lines(headings: List[Heading], min_level: int = 1, max_level: int = 4) -> List[str]:
    """Generates formatted TOC lines for given headings."""
    toc_lines = []
    slug_counts: Dict[str, int] = {}

    for h in headings:
        if h.level < min_level or h.level > max_level:
            continue

        # Handle duplicate slugs (GitHub appends -1, -2, etc.)
        base_slug = h.slug
        if base_slug in slug_counts:
            slug_counts[base_slug] += 1
            final_slug = f"{base_slug}-{slug_counts[base_slug]}"
        else:
            slug_counts[base_slug] = 0
            final_slug = base_slug

        indent = "  " * (h.level - min_level)
        toc_lines.append(f"{indent}- [{h.title}](#{final_slug})")

    return toc_lines


def locate_toc_block(lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
    """Locates TOC start and end line indices (0-based) using markers or list heuristics."""
    start_idx, end_idx = None, None

    # Look for explicit comments first
    for idx, line in enumerate(lines):
        if "<!-- TOC -->" in line or "<!-- toc -->" in line:
            start_idx = idx
        elif "<!-- /TOC -->" in line or "<!-- /toc -->" in line:
            end_idx = idx
            break

    if start_idx is not None and end_idx is not None:
        return start_idx, end_idx

    # Heuristic: search for # Table of Contents
    for idx, line in enumerate(lines):
        if re.match(r"^#{1,3}\s+Table of Contents", line, re.IGNORECASE):
            start_idx = idx + 1
            # Scan forward for blank lines or next non-TOC header
            for j in range(start_idx, len(lines)):
                if lines[j].strip().startswith("#") and not re.match(r"^#{1,3}\s+Table of Contents", lines[j], re.IGNORECASE):
                    end_idx = j - 1
                    break
            if end_idx is None:
                end_idx = len(lines) - 1
            break

    return start_idx, end_idx


def validate_markdown_file(file_path: str, auto_fix: bool = False) -> Tuple[bool, List[str]]:
    """Validates and optionally fixes markdown file TOC."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    lines = content.splitlines()

    headings = parse_markdown_headings(lines)
    expected_toc = generate_toc_lines(headings)
    
    start_idx, end_idx = locate_toc_block(lines)
    issues = []
    is_valid = True

    if start_idx is None or end_idx is None:
        issues.append(f"{YELLOW}No TOC block or markers found in file.{RESET}")
        if auto_fix and headings:
            # Insert TOC at top (after any title/h1 or frontmatter)
            insert_pos = 0
            if lines and lines[0].startswith("---"):
                # Skip frontmatter
                for i in range(1, len(lines)):
                    if lines[i].startswith("---"):
                        insert_pos = i + 1
                        break
            elif lines and lines[0].startswith("# "):
                insert_pos = 1

            new_toc_block = [
                "",
                "## Table of Contents",
                "<!-- TOC -->",
                *expected_toc,
                "<!-- /TOC -->",
                ""
            ]
            lines[insert_pos:insert_pos] = new_toc_block
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            issues.append(f"{GREEN}Auto-inserted new TOC block at line {insert_pos+1}.{RESET}")
            return True, issues
        return False, issues

    existing_toc_lines = [l.strip() for l in lines[start_idx+1:end_idx] if l.strip() and not l.strip().startswith("<!--")]
    clean_expected = [l.strip() for l in expected_toc]

    if existing_toc_lines != clean_expected:
        is_valid = False
        issues.append(f"{RED}TOC block does not match current document headings.{RESET}")
        issues.append(f"  Existing TOC lines: {len(existing_toc_lines)}")
        issues.append(f"  Expected TOC lines: {len(clean_expected)}")

        if auto_fix:
            new_lines = lines[:start_idx] + ["<!-- TOC -->"] + expected_toc + ["<!-- /TOC -->"] + lines[end_idx+1:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            issues.append(f"{GREEN}Auto-updated TOC block in {file_path}.{RESET}")
            is_valid = True
    else:
        issues.append(f"{GREEN}TOC is up to date and valid.{RESET}")

    return is_valid, issues


def main():
    parser = argparse.ArgumentParser(description="Markdown Table of Contents (TOC) Validator & Auto-Fixer")
    parser.add_argument("target", nargs="?", default=".", help="Markdown file or directory to scan (default: current dir)")
    parser.add_argument("--fix", action="store_true", help="Automatically insert or update TOC blocks in files")
    parser.add_argument("--check", action="store_true", help="Return non-zero status code if invalid TOC is found")

    args = parser.parse_args()

    files_to_check = []
    if os.path.isfile(args.target):
        files_to_check.append(args.target)
    elif os.path.isdir(args.target):
        for root, _, files in os.walk(args.target):
            for file in files:
                if file.endswith(".md"):
                    files_to_check.append(os.path.join(root, file))

    if not files_to_check:
        print(f"{YELLOW}No Markdown files found to scan.{RESET}")
        sys.exit(0)

    print(f"\n{BOLD}{CYAN}=== Markdown TOC Validator ({len(files_to_check)} files) ==={RESET}\n")
    all_valid = True

    for file_path in files_to_check:
        rel_path = os.path.relpath(file_path)
        valid, issues = validate_markdown_file(file_path, auto_fix=args.fix)
        if not valid:
            all_valid = False

        status_icon = f"{GREEN}✓{RESET}" if valid else f"{RED}✗{RESET}"
        print(f"[{status_icon}] {BOLD}{rel_path}{RESET}")
        for issue in issues:
            print(f"    {issue}")
        print()

    if args.check and not all_valid:
        print(f"{RED}TOC validation failed for one or more files.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
