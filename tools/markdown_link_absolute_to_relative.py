#!/usr/bin/env python3
"""
Markdown Link Doctor

Scans Markdown documents in a project directory to audit links. It:
1. Automatically converts absolute local paths (within the project folder) into correct relative links.
2. Checks relative file paths locally and warns if they point to non-existent files.
3. Performs a dry-run check or fixes the files in-place.

Usage:
    python tools/markdown_link_absolute_to_relative.py /path/to/project --dry-run
    python tools/markdown_link_absolute_to_relative.py /path/to/project --fix
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text: str, color: str):
    """Print to stderr in color if a tty."""
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def make_relative(base_file_path: Path, target_absolute_path: Path) -> str:
    """Calculates relative path from base_file_path's parent folder to target_absolute_path."""
    try:
        relative = os.path.relpath(target_absolute_path, base_file_path.parent)
        # Standardize on forward slashes for URL path compatibility
        return relative.replace('\\', '/')
    except Exception:
        return str(target_absolute_path)

def audit_file(filepath: Path, root_path: Path, fix: bool) -> Tuple[int, int]:
    """Audits links in a single Markdown file. Returns (fixed_count, broken_count)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print_colored(f"[-] Error reading '{filepath}': {e}", RED)
        return 0, 0

    # Pattern to match Markdown links: [text](link)
    # We want to extract links that are NOT http/https and NOT anchors (#something)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    modified = False
    new_content = content
    fixed_count = 0
    broken_count = 0

    # Find matches
    matches = list(link_pattern.finditer(content))
    if not matches:
        return 0, 0

    # Sort matches in reverse to replace correctly without offset shift problems
    for match in reversed(matches):
        link_text = match.group(1)
        link_target = match.group(2).strip()

        # Skip remote URLs, mailto, and plain anchor jumps
        if link_target.startswith(("http://", "https://", "mailto:", "#")):
            continue
            
        # Strip query params or hash anchors from file target to validate file presence
        target_path_part = link_target.split("?")[0].split("#")[0]
        if not target_path_part:
            continue

        # 1. Resolve absolute path Conversion
        # Check if absolute windows or unix path (e.g. H:\... or /home/...)
        is_abs = os.path.isabs(target_path_part) or (len(target_path_part) > 1 and target_path_part[1] == ':')
        
        target_path = Path(target_path_part)
        
        # If absolute, verify if it points within our project folder root
        if is_abs:
            try:
                # Check if target is inside the project
                if target_path.exists() and root_path.resolve() in target_path.resolve().parents:
                    relative_url = make_relative(filepath, target_path.resolve())
                    # Keep anchors/query params if any
                    anchor_part = ""
                    if "#" in link_target:
                        anchor_part = "#" + link_target.split("#", 1)[1]
                    elif "?" in link_target:
                        anchor_part = "?" + link_target.split("?", 1)[1]
                        
                    new_target = relative_url + anchor_part
                    
                    # Perform string replacement
                    start, end = match.span(2)
                    new_content = new_content[:start] + new_target + new_content[end:]
                    modified = True
                    fixed_count += 1
                    print_colored(f"    - Fixed: Absolute path converted to '{new_target}'", GREEN)
                    # Use new target path for existence check
                    target_path = filepath.parent / relative_url
                else:
                    print_colored(f"    - Warning: Absolute link '{link_target}' points outside project root.", YELLOW)
                    broken_count += 1
            except Exception as e:
                print_colored(f"    - Error resolving absolute path '{link_target}': {e}", RED)
                broken_count += 1
        else:
            # 2. Local relative path validation
            # Resolve relative path from base file directory
            resolved_target = (filepath.parent / target_path_part).resolve()
            if not resolved_target.exists():
                print_colored(f"    - Warning: Broken relative link '{link_target}' (file not found)", YELLOW)
                broken_count += 1

    if modified and fix:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            print_colored(f"[-] Error writing file '{filepath}': {e}", RED)

    return fixed_count, broken_count

def audit_directory(project_path: str, fix: bool):
    """Scans and audits all Markdown files under project_path."""
    root = Path(project_path).resolve()
    print_colored(f"[*] Scanning Markdown files under '{root}'...", BLUE)
    
    md_files = list(Path(project_path).rglob("*.md"))
    print_colored(f"[*] Found {len(md_files)} Markdown files to check.", BLUE)

    total_fixed = 0
    total_broken = 0

    for filepath in md_files:
        print_colored(f"  Checking '{filepath.relative_to(root)}'...", CYAN)
        fixed, broken = audit_file(filepath, root, fix)
        total_fixed += fixed
        total_broken += broken

    print_colored("\n=== Run Summary ===", BOLD + CYAN)
    if fix:
        print_colored(f"Total absolute links fixed: {total_fixed}", GREEN)
    else:
        print_colored(f"Total absolute links needing fixes: {total_fixed}", YELLOW)
        
    if total_broken > 0:
        print_colored(f"Total broken or unresolvable links: {total_broken}", RED)
    else:
        print_colored("No broken local relative links detected!", GREEN)

def main():
    parser = argparse.ArgumentParser(description="Audits absolute/relative local Markdown links.")
    parser.add_argument("project_path", nargs="?", default=".", help="Root path of the project (default: .)")
    parser.add_argument("--fix", action="store_true", help="Fix files in-place (converts absolute to relative)")
    parser.add_argument("--dry-run", action="store_true", help="Only audit and list proposed updates without writing (default)")

    args = parser.parse_args()
    
    # Fix is false by default unless explicitly set
    fix_mode = args.fix and not args.dry_run
    
    if not fix_mode:
        print_colored("[*] Operating in DRY-RUN mode. No changes will be written.", YELLOW)
        
    audit_directory(args.project_path, fix_mode)

if __name__ == "__main__":
    main()
