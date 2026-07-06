#!/usr/bin/env python3
"""
markdown_collapsible_section_generator - Markdown Collapsible Section Generator

Automatically converts designated Markdown headings (e.g., ### level 3 or deeper)
or long sections (> N lines) into HTML <details><summary> title </summary> collapsible dropdowns.

Usage:
    python tools/markdown_collapsible_section_generator.py <input_md> [options]

Examples:
    python tools/markdown_collapsible_section_generator.py README.md --level 3 --output collapsible_README.md
    python tools/markdown_collapsible_section_generator.py doc.md --min-lines 15 --in-place
    python tools/markdown_collapsible_section_generator.py doc.md --dry-run
"""

import argparse
import os
import re
import sys
from typing import List, Tuple, Dict, Any


def parse_markdown_sections(lines: List[str], target_level: int, min_lines: int) -> str:
    """Scan lines and encapsulate headings at or below target_level into HTML <details> blocks."""
    output_lines = []
    i = 0
    n = len(lines)

    heading_regex = re.compile(r'^(#{1,6})\s+(.+)$')

    while i < n:
        line = lines[i]
        match = heading_regex.match(line)

        if match:
            hashes, title = match.group(1), match.group(2).strip()
            level = len(hashes)

            if level >= target_level:
                # Collect all lines belonging to this section until next heading of same or higher level
                section_body = []
                j = i + 1
                while j < n:
                    next_match = heading_regex.match(lines[j])
                    if next_match:
                        next_level = len(next_match.group(1))
                        if next_level <= level:
                            break
                    section_body.append(lines[j])
                    j += 1

                # Check minimum line threshold for wrapping
                if len(section_body) >= min_lines:
                    output_lines.append(f"<details>")
                    output_lines.append(f"<summary><b>{title}</b></summary>\n")
                    output_lines.append(line)  # Keep original heading inside or remove
                    output_lines.extend(section_body)
                    output_lines.append("</details>\n")
                    i = j
                    continue

        output_lines.append(line)
        i += 1

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown headings and long sections into interactive collapsible <details><summary> HTML blocks."
    )
    parser.add_argument("input_md", help="Path to Markdown file")
    parser.add_argument("-o", "--output", help="Path to output file (default: stdout unless --in-place is set)")
    parser.add_argument("-l", "--level", type=int, default=3, help="Heading level to trigger collapsible wrapping (e.g. 3 for ### headings, default: 3)")
    parser.add_argument("-m", "--min-lines", type=int, default=1, help="Minimum line count required in section to wrap (default: 1)")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify input Markdown file in-place")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Preview collapsible section replacements without writing file")

    args = parser.parse_args()

    if not os.path.exists(args.input_md):
        print(f"Error: Input file '{args.input_md}' does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(args.input_md, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    lines = content.splitlines()
    transformed_content = parse_markdown_sections(lines, args.level, args.min_lines)

    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    if args.dry_run:
        print("=== DRY RUN PREVIEW ===")
        try:
            print(transformed_content[:1500] + ("\n..." if len(transformed_content) > 1500 else ""))
        except UnicodeEncodeError:
            print(transformed_content[:1500].encode('ascii', errors='replace').decode('ascii'))
        print("\n[!] Dry run finished. No files modified.")
        return

    if args.in_place:
        target_path = args.input_md
    elif args.output:
        target_path = args.output
    else:
        print(transformed_content)
        return

    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(transformed_content)
    print(f"[+] Successfully generated collapsible Markdown at: {target_path}")


if __name__ == "__main__":
    main()
