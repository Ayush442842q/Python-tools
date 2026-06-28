#!/usr/bin/env python3
"""
Markdown Link Replacer
Batch replace/update markdown links across files with pattern matching.

Usage:
    python markdown_link_replacer.py --old "https://old-domain.com" --new "https://new-domain.com" [files...]
    python markdown_link_replacer.py --old-pattern "github.com/[^/]+/repo" --new "gitlab.com/group/repo" --regex
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


def find_markdown_files(paths: List[str], recursive: bool = False) -> List[Path]:
    """Find all markdown files in given paths."""
    md_files = []
    
    for path in paths:
        path_obj = Path(path)
        if path_obj.is_file() and path_obj.suffix.lower() in ['.md', '.markdown']:
            md_files.append(path_obj)
        elif path_obj.is_dir():
            pattern = "**/*.md" if recursive else "*.md"
            md_files.extend(path_obj.glob(pattern))
            # Also check .markdown extension
            pattern = "**/*.markdown" if recursive else "*.markdown"
            md_files.extend(path_obj.glob(pattern))
    
    return list(set(md_files))


def parse_markdown_links(content: str) -> List[Dict]:
    """Extract all links from markdown content."""
    links = []
    
    # Pattern for [text](url) or [text](url "title")
    pattern = r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)'
    
    for match in re.finditer(pattern, content):
        links.append({
            "full_match": match.group(0),
            "text": match.group(1),
            "url": match.group(2),
            "title": match.group(3) or None,
            "start": match.start(),
            "end": match.end()
        })
    
    # Pattern for reference links [text][ref] and [ref][]
    ref_pattern = r'\[([^\]]+)\]\[([^\]]*)\]'
    for match in re.finditer(ref_pattern, content):
        text = match.group(1)
        ref = match.group(2) or text  # If empty, use text as ref
        
        # Find the reference definition
        ref_def_pattern = rf'^\[?\s*{re.escape(ref)}\s*\]?:\s*([^\s]+)(?:\s+"([^"]*)")?'
        ref_match = re.search(ref_def_pattern, content, re.MULTILINE | re.IGNORECASE)
        
        if ref_match:
            links.append({
                "full_match": match.group(0),
                "text": text,
                "url": ref_match.group(1),
                "title": ref_match.group(2) or None,
                "start": match.start(),
                "end": match.end(),
                "type": "reference"
            })
    
    # Pattern for bare URLs and autolinks
    url_pattern = r'<?(https?://[^>\s]+)>?'
    for match in re.finditer(url_pattern, content):
        url = match.group(1)
        # Skip if this is already part of a [text](url) pattern
        if not any(l["start"] <= match.start() < l["end"] for l in links):
            links.append({
                "full_match": match.group(0),
                "text": url,
                "url": url,
                "title": None,
                "start": match.start(),
                "end": match.end(),
                "type": "bare"
            })
    
    return links


def replace_links_in_content(
    content: str,
    old_pattern: str,
    new_pattern: str,
    use_regex: bool = False
) -> Tuple[str, int, List[Dict]]:
    """
    Replace links matching old_pattern with new_pattern.
    
    Returns:
        Tuple of (new_content, replacement_count, list of replacements made)
    """
    links = parse_markdown_links(content)
    replacements = []
    replacement_count = 0
    
    if use_regex:
        try:
            old_regex = re.compile(old_pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    
    def should_replace(url: str) -> bool:
        if use_regex:
            return bool(old_regex.search(url))
        else:
            return old_pattern in url
    
    def make_replacement(url: str) -> str:
        if use_regex:
            return old_regex.sub(new_pattern, url)
        else:
            return url.replace(old_pattern, new_pattern)
    
    # Process links in reverse order to maintain position accuracy
    new_content = content
    for link in sorted(links, key=lambda x: x["start"], reverse=True):
        if should_replace(link["url"]):
            new_url = make_replacement(link["url"])
            
            if new_url != link["url"]:
                # Construct the new link text
                if link.get("type") == "reference":
                    old_link = link["full_match"]
                elif link.get("type") == "bare":
                    if link["full_match"].startswith("<"):
                        old_link = f"<{link['url']}>"
                    else:
                        old_link = link["url"]
                else:
                    if link["title"]:
                        old_link = f'[{link["text"]}]({link["url"]} "{link["title"]}")'
                    else:
                        old_link = f'[{link["text"]}]({link["url"]})'
                
                if link.get("type") == "reference":
                    if link["title"]:
                        new_link = f'[{link["text"]}]({new_url} "{link["title"]}")'
                    else:
                        new_link = f'[{link["text"]}]({new_url})'
                elif link.get("type") == "bare":
                    new_link = new_url
                else:
                    if link["title"]:
                        new_link = f'[{link["text"]}]({new_url} "{link["title"]}")'
                    else:
                        new_link = f'[{link["text"]}]({new_url})'
                
                # Replace in content
                new_content = new_content[:link["start"]] + new_link + new_content[link["end"]:]
                
                replacements.append({
                    "file": None,  # Will be set by caller
                    "old_url": link["url"],
                    "new_url": new_url,
                    "context": link["text"],
                    "position": link["start"]
                })
                replacement_count += 1
    
    return new_content, replacement_count, replacements


def format_output(results: List[Dict], json_format: bool = False) -> str:
    """Format replacement results for output."""
    if json_format:
        return json.dumps(results, indent=2)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("MARKDOWN LINK REPLACER")
    output_lines.append("=" * 80)
    
    total_replacements = 0
    files_with_changes = 0
    
    for result in results:
        file_path = result["file"]
        replacements = result.get("replacements", [])
        
        if replacements:
            files_with_changes += 1
            total_replacements += len(replacements)
            
            output_lines.append(f"\n📝 {file_path} ({len(replacements)} replacements)")
            
            for i, repl in enumerate(replacements, 1):
                output_lines.append(f"  {i}. {repl['old_url']}")
                output_lines.append(f"     → {repl['new_url']}")
                if repl.get("context"):
                    output_lines.append(f"     Context: [{repl['context']}]")
        else:
            output_lines.append(f"\n✓ {file_path} (no changes)")
    
    output_lines.append("\n" + "=" * 80)
    output_lines.append(f"Summary: {files_with_changes} files modified, {total_replacements} total replacements")
    output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Batch replace/update markdown links across files with pattern matching."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Markdown files to process (default: current directory)"
    )
    parser.add_argument(
        "--old", "-o",
        type=str,
        required=True,
        help="Old URL pattern to replace (or regex pattern if --regex)"
    )
    parser.add_argument(
        "--new", "-n",
        type=str,
        required=True,
        help="New URL pattern (or replacement regex if --regex)"
    )
    parser.add_argument(
        "--regex", "-r",
        action="store_true",
        help="Treat patterns as regular expressions"
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directories for markdown files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be replaced without modifying files"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--backup", "-b",
        action="store_true",
        help="Create backup files (.bak extension)"
    )
    
    args = parser.parse_args()
    
    # Determine files to process
    if args.files:
        paths = args.files
    else:
        paths = ["."]
    
    md_files = find_markdown_files(paths, recursive=args.recursive)
    
    if not md_files:
        print("No markdown files found to process.")
        sys.exit(0)
    
    print(f"Found {len(md_files)} markdown file(s)")
    print(f"Replacing: '{args.old}' → '{args.new}'")
    if args.regex:
        print("Mode: Regular expression")
    else:
        print("Mode: Substring match")
    if args.dry_run:
        print("Mode: Dry run (no changes)")
    print()
    
    results = []
    
    for file_path in md_files:
        try:
            content = file_path.read_text(encoding='utf-8')
            
            new_content, count, replacements = replace_links_in_content(
                content,
                args.old,
                args.new,
                use_regex=args.regex
            )
            
            # Set file path in replacements
            for repl in replacements:
                repl["file"] = str(file_path)
            
            results.append({
                "file": str(file_path),
                "replacements": replacements,
                "count": count
            })
            
            if count > 0 and not args.dry_run:
                if args.backup:
                    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                    backup_path.write_text(content, encoding='utf-8')
                
                file_path.write_text(new_content, encoding='utf-8')
                
        except Exception as e:
            results.append({
                "file": str(file_path),
                "error": str(e),
                "replacements": [],
                "count": 0
            })
    
    output = format_output(results, json_format=args.json)
    print(output)
    
    # Exit with error if any failures
    errors = sum(1 for r in results if r.get("error"))
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()