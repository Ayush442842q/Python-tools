#!/usr/bin/env python3
"""
Markdown Heading & Section Anchor Validator

Scans Markdown (.md) files to parse headings, generate their slugified anchors,
and validate that all internal anchors (e.g., #anchor) and cross-file anchors
(e.g., other_file.md#anchor) resolve to valid headings.

Usage:
    python markdown_anchor_validator.py [path] [options]
"""

import os
import sys
import re
import argparse
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Regular expressions
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
REF_LINK_RE = re.compile(r'^\[([^\]]+)\]:\s*(\S+)', re.MULTILINE)

def slugify(heading_text):
    """
    Convert a heading text into a standard Markdown anchor slug (GitHub-style).
    e.g., "Features & Options! (v2.0)" -> "features--options-v20"
    """
    # Convert to lowercase
    slug = heading_text.strip().lower()
    
    # Remove HTML tags if present (basic strip)
    slug = re.sub(r'<[^>]+>', '', slug)
    
    # Remove standard markdown formatting inside heading (links, bold, code ticks, etc.)
    slug = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', slug) # links
    slug = slug.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
    slug = slug.replace('`', '')
    
    # Characters to remove: punctuation and special chars
    # We want to keep alphanumeric, spaces, and hyphens/underscores
    # Convert spaces/tabs to hyphens
    slug = re.sub(r'\s+', '-', slug)
    
    # Strip characters that are not letters, numbers, hyphens, or underscores
    # GitHub keeps underscores, hyphens, and alphanumeric
    slug = ''.join(c for c in slug if c.isalnum() or c in ('-', '_'))
    
    # Collapse multiple hyphens
    slug = re.compile(r'-+').sub('-', slug)
    
    return slug

def parse_markdown_file(filepath):
    """
    Parse a markdown file and return a dictionary of properties:
    - headings: list of tuples (level, text, slug, line_no)
    - anchors: set of slugs (including handling of duplicates, e.g. slug, slug-1, slug-2)
    - links: list of tuples (link_target, line_no, raw_match)
    - duplicate_headings: list of duplicate slugs found
    - structure_warnings: list of structural warning strings
    """
    headings = []
    anchors = set()
    links = []
    duplicate_headings = []
    structure_warnings = []
    
    try:
        lines = filepath.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception as e:
        return {
            "error": f"Failed to read file: {e}",
            "headings": [],
            "anchors": set(),
            "links": [],
            "duplicate_headings": [],
            "structure_warnings": []
        }
        
    last_level = 0
    slug_counts = {}
    
    in_code_block = False
    
    for idx, line in enumerate(lines):
        line_no = idx + 1
        
        # Track code blocks to skip code block content
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
            
        if in_code_block:
            continue
            
        # Parse headings
        heading_match = HEADING_RE.match(line)
        if heading_match:
            hashes, text = heading_match.groups()
            level = len(hashes)
            
            # Remove trailing hashes if any, e.g., "## Heading ##"
            text = text.rstrip('#').strip()
            
            base_slug = slugify(text)
            
            # Handle duplicate headings (GitHub adds numeric suffixes for duplicates)
            if base_slug not in slug_counts:
                slug_counts[base_slug] = 0
                slug = base_slug
            else:
                slug_counts[base_slug] += 1
                slug = f"{base_slug}-{slug_counts[base_slug]}"
                duplicate_headings.append((text, line_no, slug))
                
            headings.append((level, text, slug, line_no))
            anchors.add(slug)
            
            # Structure check (skipped levels, e.g., H1 -> H3)
            if last_level > 0 and level > last_level + 1:
                structure_warnings.append(
                    f"Line {line_no}: Skipped heading level from H{last_level} to H{level} ('{text}')"
                )
            last_level = level
            continue
            
        # Parse standard inline links: [text](url)
        for text, target in LINK_RE.findall(line):
            links.append((target.strip(), line_no, f"[{text}]({target})"))
            
    # Parse reference links at the end
    content = "\n".join(lines)
    for text, target in REF_LINK_RE.findall(content):
        links.append((target.strip(), 0, f"[{text}]: {target}"))
        
    return {
        "error": None,
        "headings": headings,
        "anchors": anchors,
        "links": links,
        "duplicate_headings": duplicate_headings,
        "structure_warnings": structure_warnings
    }

def main():
    parser = argparse.ArgumentParser(description="Validate Markdown heading anchors and links.")
    parser.add_argument("path", nargs="?", default=".", help="File or directory path to scan (default: current directory)")
    parser.add_argument("--check-structure", action="store_true", help="Report heading hierarchy issues (e.g. skipping levels)")
    parser.add_argument("--report-duplicates", action="store_true", help="Report duplicate headings (which cause suffix anchors)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    target_path = Path(args.path)
    if not target_path.exists():
        print(f"Error: Path '{target_path}' does not exist.")
        sys.exit(1)
        
    md_files = []
    if target_path.is_file():
        if target_path.suffix.lower() == ".md":
            md_files.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            # Ignore standard build/cache directories
            if any(part in root.split(os.sep) for part in [".git", "venv", ".venv", "env", "node_modules", "build", "dist"]):
                continue
            for file in files:
                if file.endswith(".md"):
                    md_files.append(Path(root) / file)
                    
    if not md_files:
        print("No Markdown files (.md) found to validate.")
        sys.exit(0)
        
    # First pass: parse all files to gather their headings and anchors
    file_data = {}
    for filepath in md_files:
        rel_path = filepath.relative_to(target_path) if target_path.is_dir() else filepath.name
        rel_str = str(rel_path).replace("\\", "/")
        file_data[rel_str] = {
            "abs_path": filepath,
            "parsed": parse_markdown_file(filepath)
        }
        
    errors_count = 0
    warnings_count = 0
    json_results = []
    
    # Second pass: validate links in each file
    for file_rel, data in sorted(file_data.items()):
        parsed = data["parsed"]
        if parsed["error"]:
            print(f"{RED}Error reading {file_rel}: {parsed['error']}{RESET}")
            errors_count += 1
            continue
            
        file_errors = []
        file_warnings = []
        
        # Validate duplicate headings
        if args.report_duplicates and parsed["duplicate_headings"]:
            for text, line, slug in parsed["duplicate_headings"]:
                file_warnings.append({
                    "type": "duplicate_heading",
                    "line": line,
                    "message": f"Duplicate heading '{text}' creates slug anchor '{slug}'",
                    "details": text
                })
                warnings_count += 1
                
        # Validate structure warnings
        if args.check_structure and parsed["structure_warnings"]:
            for warning in parsed["structure_warnings"]:
                file_warnings.append({
                    "type": "heading_structure",
                    "line": int(warning.split(":")[0].replace("Line ", "")),
                    "message": warning,
                    "details": warning
                })
                warnings_count += 1
                
        # Validate links
        for target, line_no, raw in parsed["links"]:
            # Check only local/anchor links
            if target.startswith(('http://', 'https://', 'mailto:', 'tel:', 'javascript:')):
                continue
                
            # Parse target into file path and anchor
            parts = target.split('#')
            target_file_str = parts[0]
            anchor = parts[1] if len(parts) > 1 else None
            
            # Case 1: Self-referencing anchor (e.g., "#features")
            if not target_file_str:
                if anchor:
                    # Clean URL encoding (e.g. %20 -> space) if present, though anchor slugs shouldn't have spaces
                    anchor_clean = anchor.strip()
                    if anchor_clean not in parsed["anchors"]:
                        file_errors.append({
                            "type": "broken_anchor",
                            "line": line_no,
                            "message": f"Broken local anchor: '{target}' (heading not found)",
                            "link": raw
                        })
                        errors_count += 1
                continue
                
            # Case 2: Cross-file link (e.g., "docs/setup.md" or "docs/setup.md#installation")
            # Resolve relative file path
            curr_file_dir = data["abs_path"].parent
            # Unquote URL characters (e.g. %20 to spaces)
            target_file_str_clean = urllib_unquote(target_file_str)
            target_file_path = (curr_file_dir / target_file_str_clean).resolve()
            
            # Determine relative path from target root to check if it's in our parsed files
            # This makes cross-referencing files in the workspace fast
            matched_key = None
            for key, other_data in file_data.items():
                if other_data["abs_path"].resolve() == target_file_path:
                    matched_key = key
                    break
                    
            if matched_key:
                # Target file exists in our project scan!
                if anchor:
                    other_parsed = file_data[matched_key]["parsed"]
                    anchor_clean = anchor.strip()
                    if anchor_clean not in other_parsed["anchors"]:
                        file_errors.append({
                            "type": "broken_anchor",
                            "line": line_no,
                            "message": f"Broken anchor in '{target_file_str}': target heading '#{anchor}' not found",
                            "link": raw
                        })
                        errors_count += 1
            else:
                # File is outside or not a markdown file we parsed, let's verify if the file exists on disk
                if not target_file_path.exists():
                    file_errors.append({
                        "type": "missing_file",
                        "line": line_no,
                        "message": f"Broken link: Target path does not exist on disk: '{target_file_str}'",
                        "link": raw
                    })
                    errors_count += 1
                    
        if args.json:
            json_results.append({
                "file": file_rel,
                "errors": file_errors,
                "warnings": file_warnings,
                "headings_count": len(parsed["headings"]),
                "anchors_count": len(parsed["anchors"])
            })
        else:
            # Print file summary
            if file_errors or file_warnings:
                print(f"\n{BOLD}{CYAN}File: {file_rel}{RESET} ({len(parsed['headings'])} headings)")
                for err in file_errors:
                    line_prefix = f"Line {err['line']}: " if err['line'] > 0 else ""
                    print(f"  {RED}[ERROR] {line_prefix}{err['message']}{RESET}")
                    print(f"    Source link: {err['link']}")
                for warn in file_warnings:
                    print(f"  {YELLOW}[WARN] {warn['message']}{RESET}")
            elif len(md_files) == 1 or target_path.is_file():
                print(f"\n{GREEN}✔ File {file_rel} is clean! ({len(parsed['headings'])} headings, {len(parsed['links'])} links validated){RESET}")
                
    if args.json:
        import json
        output = {
            "summary": {
                "total_files": len(md_files),
                "total_errors": errors_count,
                "total_warnings": warnings_count
            },
            "results": json_results
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{BOLD}=== VALIDATION SUMMARY ===={RESET}")
        print(f"Files Scanned:   {len(md_files)}")
        print(f"Total Errors:    {RED if errors_count > 0 else GREEN}{errors_count}{RESET}")
        print(f"Total Warnings:  {YELLOW if warnings_count > 0 else GREEN}{warnings_count}{RESET}")
        print("="*27 + "\n")
        
    if errors_count > 0:
        sys.exit(1)

def urllib_unquote(s):
    """Simple replacement for urllib.parse.unquote to avoid imports if unnecessary."""
    # Convert %20 to space, %2f to /, etc.
    # Standard library import is fine
    import urllib.parse
    return urllib.parse.unquote(s)

if __name__ == "__main__":
    main()
