#!/usr/bin/env python3
"""
Markdown Table of Contents (TOC) Generator
Scans a Markdown file and automatically generates a Table of Contents based on heading levels.
Supports inline insertion/updating of the TOC.
"""

import argparse
import os
import sys
import re

def make_anchor(text):
    # Lowercase
    anchor = text.lower()
    # Remove HTML tags
    anchor = re.sub(r'<[^>]+>', '', anchor)
    # Remove characters that are not alphanumeric, space, hyphen, underscore
    anchor = re.sub(r'[^\w\s-]', '', anchor)
    # Replace spaces and underscores with hyphens
    anchor = re.sub(r'[\s_]+', '-', anchor)
    # Replace multiple consecutive hyphens with one
    anchor = re.sub(r'-+', '-', anchor)
    # Strip leading/trailing hyphens
    return anchor.strip('-')

def get_headings(file_content):
    lines = file_content.splitlines()
    inside_code_block = False
    code_block_char = None
    headings = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check for code blocks
        if not inside_code_block:
            if stripped.startswith("```"):
                inside_code_block = True
                code_block_char = "```"
                continue
            elif stripped.startswith("~~~"):
                inside_code_block = True
                code_block_char = "~~~"
                continue
        else:
            if stripped.startswith(code_block_char):
                inside_code_block = False
                code_block_char = None
                continue
                
        if inside_code_block:
            continue
            
        # Parse ATX heading (1 to 6 hashes)
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            hashes = match.group(1)
            level = len(hashes)
            title = match.group(2).strip()
            # Remove trailing hashes
            title = re.sub(r'\s+#+$', '', title).strip()
            
            # Clean markdown formatting inside the heading for display
            display_title = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title) # links
            display_title = display_title.replace('**', '').replace('__', '').replace('*', '').replace('_', '').replace('`', '')
            
            headings.append({
                'level': level,
                'title': display_title,
                'raw_title': title
            })
            
    return headings

def generate_toc(headings, min_depth, max_depth):
    if not headings:
        return ""
        
    filtered_headings = [h for h in headings if min_depth <= h['level'] <= max_depth]
    if not filtered_headings:
        return ""
        
    min_level = min(h['level'] for h in filtered_headings)
    
    anchor_counts = {}
    def get_unique_anchor(text):
        base = make_anchor(text)
        if base not in anchor_counts:
            anchor_counts[base] = 0
            return base
        else:
            anchor_counts[base] += 1
            return f"{base}-{anchor_counts[base]}"
            
    toc_lines = []
    for h in filtered_headings:
        indent = "  " * (h['level'] - min_level)
        anchor = get_unique_anchor(h['title'])
        toc_lines.append(f"{indent}- [{h['title']}](#{anchor})")
        
    return "\n".join(toc_lines)

def insert_toc_in_content(file_content, toc_text):
    pattern = re.compile(r'(<!--\s*TOC\s*-->)(.*?)(<!--\s*/TOC\s*-->)', re.DOTALL | re.IGNORECASE)
    if pattern.search(file_content):
        new_content = pattern.sub(f"<!-- TOC -->\n\n{toc_text}\n\n<!-- /TOC -->", file_content)
        return new_content, True
        
    # Prepend or insert after the first title H1
    lines = file_content.splitlines()
    insert_idx = 0
    inside_code = False
    for idx, line in enumerate(lines):
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            inside_code = not inside_code
            continue
        if inside_code:
            continue
        if re.match(r'^#\s+', line):
            insert_idx = idx + 1
            break
            
    toc_block = f"\n<!-- TOC -->\n\n{toc_text}\n\n<!-- /TOC -->\n"
    lines.insert(insert_idx, toc_block)
    return "\n".join(lines), False

def main():
    parser = argparse.ArgumentParser(
        description="Scans a Markdown file and automatically generates a Table of Contents."
    )
    parser.add_argument("file", help="Path to the Markdown file")
    parser.add_argument("-o", "--output", help="Path to write the updated Markdown file (default: stdout or inline)")
    parser.add_argument("--min-depth", type=int, default=1, choices=range(1, 7), help="Minimum heading level to include (default: 1)")
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 7), help="Maximum heading level to include (default: 4)")
    parser.add_argument("-i", "--inline", action="store_true", help="Modify the input file in-place, inserting or updating the TOC")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"[ERROR] Markdown file '{args.file}' does not exist.")
        sys.exit(1)

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read markdown file: {e}")
        sys.exit(1)

    headings = get_headings(content)
    if not headings:
        print("[WARNING] No headings found in the Markdown file.")
        sys.exit(0)

    toc_text = generate_toc(headings, args.min_depth, args.max_depth)

    if not toc_text.strip():
        print("[WARNING] No headings matched the depth filters.")
        sys.exit(0)

    if args.inline:
        new_content, updated = insert_toc_in_content(content, toc_text)
        try:
            with open(args.file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            if updated:
                print(f"[PASS] Successfully updated TOC in '{args.file}'")
            else:
                print(f"[PASS] Successfully inserted new TOC block in '{args.file}'")
        except Exception as e:
            print(f"[ERROR] Failed to write to file: {e}")
            sys.exit(1)
            
    elif args.output:
        # If writing to a different output file, we also insert/update the TOC block
        new_content, _ = insert_toc_in_content(content, toc_text)
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[PASS] TOC-generated Markdown written to '{args.output}'")
        except Exception as e:
            print(f"[ERROR] Failed to write to output file: {e}")
            sys.exit(1)
    else:
        # Just print the raw TOC to stdout
        print(toc_text)

if __name__ == "__main__":
    main()
