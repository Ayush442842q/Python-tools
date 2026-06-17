#!/usr/bin/env python3
"""
Markdown Table of Contents Generator
Generates a Table of Contents (TOC) with anchor links for Markdown files.
"""

import sys
import os
import re
import argparse

def slugify(text, existing_slugs):
    """
    Generate a GitHub-compatible anchor slug for a header.
    Ref: https://github.com/jch/html-pipeline/blob/master/lib/html/pipeline/toc_filter.rb
    """
    # Lowercase
    slug = text.lower()
    # Remove HTML tags
    slug = re.sub(r'<[^>]+>', '', slug)
    # Remove non-alphanumeric, non-space, non-dash, non-underscore characters
    slug = re.sub(r'[^\w\s-]', '', slug)
    # Replace spaces and tabs with dashes
    slug = re.sub(r'[\s]+', '-', slug)
    # Ensure it's not starting/ending with multiple dashes
    slug = slug.strip('-')
    
    # Handle duplicate slugs
    original_slug = slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{original_slug}-{counter}"
        counter += 1
        
    existing_slugs.add(slug)
    return slug

def parse_markdown_headers(lines, min_depth=1, max_depth=6):
    """
    Extract headings from markdown lines, ignoring headings inside code blocks.
    """
    headers = []
    in_code_block = False
    
    # Matches # Heading, ## Heading, etc.
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # Toggle code block state
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
            
        if in_code_block:
            continue
            
        match = header_pattern.match(stripped)
        if match:
            hashes, text = match.groups()
            depth = len(hashes)
            if min_depth <= depth <= max_depth:
                # Strip markdown formatting from header text for anchor rendering
                clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text) # Remove links
                clean_text = re.sub(r'[*_`]', '', clean_text) # Remove bold/italic/code highlights
                headers.append({
                    'depth': depth,
                    'text': clean_text.strip(),
                    'raw': text.strip(),
                    'line': line_num
                })
    return headers

def generate_toc(headers, indent_spaces=2, bullet='-'):
    """
    Build the Table of Contents string from headers.
    """
    if not headers:
        return ""
        
    existing_slugs = set()
    toc_lines = []
    base_depth = min(h['depth'] for h in headers)
    
    for h in headers:
        slug = slugify(h['text'], existing_slugs)
        # Calculate indentation based on depth relative to base_depth
        indent = ' ' * (indent_spaces * (h['depth'] - base_depth))
        toc_lines.append(f"{indent}{bullet} [{h['text']}](#{slug})")
        
    return "\n".join(toc_lines)

def update_file_with_toc(file_path, toc_content, marker_start="<!-- TOC_START -->", marker_end="<!-- TOC_END -->"):
    """
    Insert or update TOC in a file between designated markers.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        return False

    pattern = re.compile(rf"({re.escape(marker_start)}).*?({re.escape(marker_end)})", re.DOTALL)
    
    if not pattern.search(content):
        print(f"Error: Markers '{marker_start}' and '{marker_end}' not found in '{file_path}'.", file=sys.stderr)
        print("To insert TOC automatically, add these markers to your markdown file.", file=sys.stderr)
        return False
        
    replacement = f"\\1\n\n{toc_content}\n\n\\2"
    new_content = pattern.sub(replacement, content)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"Error writing to file '{file_path}': {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Table of Contents Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", nargs="?", help="Markdown file to parse (reads from stdin if omitted)")
    parser.add_argument("--output", "-o", help="File to write TOC output to (otherwise printed or updated in-place)")
    parser.add_argument("--in-place", "-i", action="store_true", help="Insert or update TOC directly in the input file")
    parser.add_argument("--indent", type=int, default=2, help="Number of spaces for indentation level (default: 2)")
    parser.add_argument("--bullet", default="-", choices=["-", "*", "+"], help="Bullet character to use (default: '-')")
    parser.add_argument("--min-depth", type=int, default=1, choices=range(1, 7), help="Minimum heading depth to include (default: 1)")
    parser.add_argument("--max-depth", type=int, default=6, choices=range(1, 7), help="Maximum heading depth to include (default: 6)")
    parser.add_argument("--marker-start", default="<!-- TOC_START -->", help="Start marker for in-place updates")
    parser.add_argument("--marker-end", default="<!-- TOC_END -->", help="End marker for in-place updates")
    
    args = parser.parse_args()
    
    # Read lines
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: File '{args.input_file}' not found.", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            parser.print_help()
            return 0
        lines = sys.stdin.readlines()
        
    headers = parse_markdown_headers(lines, args.min_depth, args.max_depth)
    toc = generate_toc(headers, args.indent, args.bullet)
    
    if not toc:
        print("No headings found matching criteria.", file=sys.stderr)
        return 0
        
    if args.in_place:
        if not args.input_file:
            print("Error: Input file must be specified for in-place updates.", file=sys.stderr)
            return 1
        success = update_file_with_toc(args.input_file, toc, args.marker_start, args.marker_end)
        if success:
            print(f"Successfully updated TOC in '{args.input_file}'")
        return 0 if success else 1
        
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(toc + "\n")
            print(f"Successfully wrote TOC to '{args.output}'")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(toc)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
