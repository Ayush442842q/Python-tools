#!/usr/bin/env python3
"""
Markdown Unreferenced Assets Cleaner - Scans Markdown documents for referenced
local asset files (images, attachments) and cleans up unreferenced files in assets directories.
"""

import os
import re
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse, unquote

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_color(text, color):
    print(f"{color}{text}{RESET}")

def extract_references_from_markdown(file_path):
    """
    Parses a Markdown file and extracts all local file path references.
    Looks for standard links, images, HTML tags, and frontmatter paths.
    """
    references = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print_color(f"Error reading markdown file '{file_path}': {e}", RED)
        return references

    # 1. Standard markdown links and images: [text](link) and ![alt](image)
    # Match group 2 to skip potential brackets inside text
    markdown_link_pattern = re.compile(r'!?\[([^\]]*?)\]\((.*?)\)')
    for match in markdown_link_pattern.finditer(content):
        link = match.group(2).strip()
        # Strip simple quotes if present (e.g. from copy-pasting)
        link = link.strip('"\'')
        references.add(link)

    # 2. HTML img tags: <img src="path" />
    img_tag_pattern = re.compile(r'<img\s+[^>]*?src=["\'](.*?)["\']', re.IGNORECASE)
    for match in img_tag_pattern.finditer(content):
        references.add(match.group(1).strip())

    # 3. HTML anchor tags: <a href="path">
    a_tag_pattern = re.compile(r'<a\s+[^>]*?href=["\'](.*?)["\']', re.IGNORECASE)
    for match in a_tag_pattern.finditer(content):
        references.add(match.group(1).strip())

    # Filter references:
    # - Decode URL encodings (e.g. %20 -> space)
    # - Remove web URLs, mailto, anchor links
    # - Strip query parameters and fragment identifiers
    valid_local_paths = set()
    for ref in references:
        # Ignore empty
        if not ref:
            continue
        
        # Decode url encoding (like spaces, unicode)
        ref_decoded = unquote(ref)
        
        # Parse URL
        parsed = urlparse(ref_decoded)
        if parsed.scheme in ('http', 'https', 'ftp', 'mailto', 'data'):
            continue
        
        # We only care about the path component (strips query/anchor)
        local_path = parsed.path
        if local_path:
            valid_local_paths.add(local_path)

    return valid_local_paths

def scan_markdown_projects(docs_dir, assets_dir, excludes):
    docs_path = Path(docs_dir).resolve()
    assets_path = Path(assets_dir).resolve()

    if not docs_path.exists():
        print_color(f"Error: Documents directory '{docs_dir}' does not exist.", RED)
        sys.exit(1)
    if not assets_path.exists():
        print_color(f"Error: Assets directory '{assets_dir}' does not exist.", RED)
        sys.exit(1)

    print_color(f"Scanning Markdown files in: {docs_path}", BLUE)
    markdown_files = list(docs_path.rglob("*.md"))
    print(f"Found {len(markdown_files)} Markdown files.")

    # Exclude files in assets directory from being scanned as documents
    markdown_files = [f for f in markdown_files if not f.is_relative_to(assets_path)]

    # Collect all references and resolve their target paths
    referenced_absolute_paths = set()

    for md_file in markdown_files:
        local_refs = extract_references_from_markdown(md_file)
        md_dir = md_file.parent

        for ref in local_refs:
            # References could be:
            # 1. Absolute paths on system (unlikely but possible)
            # 2. Relative to the Markdown file directory (most common)
            # 3. Relative to the workspace root/docs_dir (common in wikis)
            path_rel_md = (md_dir / ref).resolve()
            path_rel_root = (docs_path / ref).resolve()

            if path_rel_md.is_relative_to(assets_path) and path_rel_md.exists():
                referenced_absolute_paths.add(path_rel_md)
            elif path_rel_root.is_relative_to(assets_path) and path_rel_root.exists():
                referenced_absolute_paths.add(path_rel_root)

    print_color(f"\nScanning asset files in: {assets_path}", BLUE)
    all_assets = []
    for p in assets_path.rglob("*"):
        if p.is_file():
            # Check exclusions
            is_excluded = False
            for pattern in excludes:
                if p.match(pattern):
                    is_excluded = True
                    break
            if not is_excluded:
                all_assets.append(p.resolve())

    print(f"Found {len(all_assets)} asset files (after exclusions).")

    unreferenced_assets = []
    referenced_count = 0
    total_savings = 0

    for asset in all_assets:
        if asset in referenced_absolute_paths:
            referenced_count += 1
        else:
            unreferenced_assets.append(asset)
            try:
                total_savings += asset.stat().st_size
            except OSError:
                pass

    return referenced_count, unreferenced_assets, total_savings

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Unreferenced Assets Cleaner - Find and clean up unused local files (images, attachments) referenced in Markdown documents."
    )
    parser.add_argument("-d", "--docs-dir", default=".", help="Directory containing Markdown documents (default: current directory)")
    parser.add_argument("-a", "--assets-dir", required=True, help="Directory containing asset files/images (e.g. 'assets' or 'images')")
    parser.add_argument("--delete", action="store_true", help="Delete unreferenced files from disk (runs in dry-run/preview mode by default)")
    parser.add_argument(
        "-e", "--exclude",
        action="append",
        default=[],
        help="Glob pattern to exclude asset files from deletion (can be specified multiple times, e.g. '*.gitkeep')"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print names of referenced asset files too")

    args = parser.parse_args()

    # ANSI support on Windows
    if sys.platform == "win32":
        os.system("")

    # Parse exclusions (ensure default gitkeep is present if not specified)
    excludes = args.exclude if args.exclude else ["*.gitkeep", ".gitignore"]

    ref_count, unref_assets, savings_bytes = scan_markdown_projects(args.docs_dir, args.assets_dir, excludes)

    # Format savings size
    savings_str = ""
    if savings_bytes < 1024:
        savings_str = f"{savings_bytes} B"
    elif savings_bytes < 1024 * 1024:
        savings_str = f"{savings_bytes / 1024:.2f} KB"
    else:
        savings_str = f"{savings_bytes / (1024 * 1024):.2f} MB"

    print_color(f"\n--- Scan Summary ---", BLUE)
    print(f"Referenced assets: {ref_count}")
    print(f"Unreferenced assets: {len(unref_assets)}")
    print(f"Potential space savings: {savings_str}")

    if not unref_assets:
        print_color("\nSuccess: No unreferenced assets found!", GREEN)
        return

    print_color(f"\nUnreferenced files list:", YELLOW)
    for asset in sorted(unref_assets):
        try:
            rel = asset.relative_to(Path(args.assets_dir).resolve())
        except ValueError:
            rel = asset.name
        print(f" - {rel}")

    if args.delete:
        print_color(f"\nDeleting {len(unref_assets)} unreferenced asset files...", RED)
        deleted_count = 0
        for asset in unref_assets:
            try:
                asset.unlink()
                deleted_count += 1
            except Exception as e:
                print_color(f"Error deleting file '{asset}': {e}", RED)
        print_color(f"Successfully deleted {deleted_count} files.", GREEN)
    else:
        print_color("\n[NOTE] This was a dry run. To delete these files, run again with the --delete flag.", YELLOW)

if __name__ == "__main__":
    main()
