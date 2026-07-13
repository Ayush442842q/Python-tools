#!/usr/bin/env python3
"""
markdown_wiki_converter - Convert wiki-style double-bracket links to standard Markdown links

Scans Markdown documents in a directory and converts Obsidian-style or GitHub Wiki-style
links like [[Page Name]], [[Page Name|Custom Label]], or [[Page Name#Header]] into portable
standard relative Markdown links: [Custom Label](page-name.md#header).

Usage:
    python tools/markdown_wiki_converter.py /path/to/docs [options]

Example:
    python tools/markdown_wiki_converter.py docs/ --slugify kebab --verbose
"""

import argparse
import os
import sys
import re


# Regular expression to match wiki links: [[Page Name]] or [[Page Name|Label]]
# Matches: [[target]] or [[target|label]] or [[target#header]] or [[target#header|label]]
WIKI_LINK_RE = re.compile(r'\[\[([^\]|#]+)(#[^\]|]+)?(?:\|([^\]]+))?\]\]')


def slugify_name(name, style='kebab'):
    """Convert a page name to a clean filename format."""
    name = name.strip()
    if style == 'kebab':
        # Lowercase and replace spaces/special chars with hyphens
        s = name.lower()
        s = re.sub(r'[^a-z0-9_\-\s]', '', s)
        s = re.sub(r'[\s_]+', '-', s)
        return re.sub(r'-+', '-', s)
    elif style == 'snake':
        # Lowercase and replace spaces/special chars with underscores
        s = name.lower()
        s = re.sub(r'[^a-z0-9_\-\s]', '', s)
        s = re.sub(r'[\s\-]+', '_', s)
        return re.sub(r'_+', '_', s)
    elif style == 'preserve':
        # Preserve case, just replace spaces with %20 or hyphens/underscores
        s = re.sub(r'[\\/*?:"<>|]', '', name)
        return s.replace(' ', '-')
    else:
        return name


def convert_wiki_links(file_path, slug_style='kebab', extension='.md', dry_run=False, verbose=False):
    """Parse a file and replace all wiki-style links with standard links."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0, 0

    replacements_made = 0
    matches = list(WIKI_LINK_RE.finditer(content))
    
    if not matches:
        return 0, 0

    new_content = []
    last_idx = 0

    for match in matches:
        full_match = match.group(0)
        target = match.group(1).strip()
        header = match.group(2) or ''
        label = match.group(3)
        
        # Format header anchor slug (e.g. #My Header -> #my-header)
        header_slug = ''
        if header:
            h_text = header.lstrip('#').strip()
            # Simple slugification for anchors
            h_slug = h_text.lower().replace(' ', '-')
            h_slug = re.sub(r'[^a-z0-9\-]', '', h_slug)
            header_slug = f"#{h_slug}"

        # If no label is specified, use the target page name as the label
        display_label = label.strip() if label else target

        # Generate standard relative path link
        slugged_target = slugify_name(target, style=slug_style)
        target_link = f"{slugged_target}{extension}{header_slug}"

        standard_link = f"[{display_label}]({target_link})"

        # Append preceding content and the replacement link
        new_content.append(content[last_idx:match.start()])
        new_content.append(standard_link)
        last_idx = match.end()
        replacements_made += 1

        if verbose:
            print(f"  Converted in {os.path.basename(file_path)}:")
            print(f"    {full_match}  =>  {standard_link}")

    new_content.append(content[last_idx:])
    final_content = "".join(new_content)

    if not dry_run and replacements_made > 0:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
        except Exception as e:
            print(f"Error writing to {file_path}: {e}")
            return replacements_made, 0

    return replacements_made, 1


def main():
    parser = argparse.ArgumentParser(
        description="Convert wiki-style [[Link]] syntax to standard relative Markdown links"
    )
    parser.add_argument(
        "directory",
        help="Directory containing Markdown files to scan"
    )
    parser.add_argument(
        "-s", "--slugify",
        choices=["kebab", "snake", "preserve", "none"],
        default="kebab",
        help="File naming slugification style to apply to targets (default: kebab)"
    )
    parser.add_argument(
        "-e", "--extension",
        default=".md",
        help="File extension for the target links (default: .md)"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Preview link conversions without editing files on disk"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Display detailed conversion logs"
    )

    args = parser.parse_args()

    target_dir = os.path.abspath(args.directory)
    if not os.path.isdir(target_dir):
        print(f"Error: '{target_dir}' is not a valid directory.")
        return 1

    print(f"Scanning directory: {target_dir}")
    if args.dry_run:
        print("  *** DRY RUN MODE - No files will be modified ***")

    total_files_checked = 0
    total_files_modified = 0
    total_links_converted = 0

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(('.md', '.markdown')):
                file_path = os.path.join(root, file)
                total_files_checked += 1
                
                count, modified = convert_wiki_links(
                    file_path,
                    slug_style=args.slugify,
                    extension=args.extension,
                    dry_run=args.dry_run,
                    verbose=args.verbose
                )
                
                if count > 0:
                    total_links_converted += count
                    if modified:
                        total_files_modified += 1

    print("\nWiki Converter Summary:")
    print(f"  Markdown files checked: {total_files_checked}")
    print(f"  Files modified: {total_files_modified if not args.dry_run else 0} (matched: {total_files_modified})")
    print(f"  Total wiki-links converted: {total_links_converted}")
    if args.dry_run:
        print("  (Dry run complete. No files were written.)")
    else:
        print("  Conversion complete!")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
