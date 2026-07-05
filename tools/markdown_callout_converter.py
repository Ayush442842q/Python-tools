#!/usr/bin/env python3
"""
Markdown Callout & Alert Converter

Converts callout and alert blocks across various Markdown formats:
GitHub Alerts (> [!NOTE]), Obsidian Callouts (> [!info]), HTML alert elements,
and classic blockquotes (> **Note:**).
"""

import os
import sys
import re
import argparse

# Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Standard Callout Types
CALLOUT_TYPES = {
    'note': 'NOTE',
    'tip': 'TIP',
    'important': 'IMPORTANT',
    'warning': 'WARNING',
    'caution': 'CAUTION',
    'info': 'NOTE',
    'success': 'TIP',
    'danger': 'CAUTION',
    'bug': 'WARNING',
    'question': 'NOTE'
}

# Regex Patterns
GITHUB_ALERT_PATTERN = re.compile(r'^>\s*\[\!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$', re.IGNORECASE)
OBSIDIAN_CALLOUT_PATTERN = re.compile(r'^>\s*\[\!([a-z0-9_-]+)\]\s*(.*)$', re.IGNORECASE)
CLASSIC_BLOCKQUOTE_PATTERN = re.compile(r'^>\s*\*\*(Note|Tip|Important|Warning|Caution|Info):\*\*\s*(.*)$', re.IGNORECASE)


def convert_github_to_obsidian(content):
    """Converts > [!NOTE] to > [!note]."""
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        match = GITHUB_ALERT_PATTERN.match(line)
        if match:
            c_type = match.group(1).lower()
            rest = match.group(2)
            new_lines.append(f"> [!{c_type}] {rest}".rstrip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n"


def convert_obsidian_to_github(content):
    """Converts > [!note] to > [!NOTE] (normalizing type names)."""
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        match = OBSIDIAN_CALLOUT_PATTERN.match(line)
        if match:
            c_type_raw = match.group(1).lower()
            rest = match.group(2)
            c_type = CALLOUT_TYPES.get(c_type_raw, 'NOTE')
            new_lines.append(f"> [!{c_type}] {rest}".rstrip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n"


def convert_callouts_to_classic(content):
    """Converts > [!NOTE] or > [!note] to > **Note:**."""
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        match = OBSIDIAN_CALLOUT_PATTERN.match(line)
        if match:
            c_type = match.group(1).capitalize()
            rest = match.group(2)
            new_lines.append(f"> **{c_type}:** {rest}".rstrip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n"


def convert_classic_to_github(content):
    """Converts > **Note:** to > [!NOTE]."""
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        match = CLASSIC_BLOCKQUOTE_PATTERN.match(line)
        if match:
            c_type_raw = match.group(1).lower()
            rest = match.group(2)
            c_type = CALLOUT_TYPES.get(c_type_raw, 'NOTE')
            new_lines.append(f"> [!{c_type}] {rest}".rstrip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n"


def convert_github_to_html(content):
    """Converts GitHub alert blockquotes into HTML div blocks."""
    lines = content.splitlines()
    new_lines = []
    in_callout = False
    current_type = ""
    block_buffer = []

    def flush_block():
        nonlocal in_callout, current_type, block_buffer, new_lines
        if block_buffer:
            css_class = f"alert alert-{current_type.lower()}"
            new_lines.append(f'<div class="{css_class}">')
            for b in block_buffer:
                new_lines.append(f"  <p>{b}</p>")
            new_lines.append('</div>')
            block_buffer = []
            in_callout = False

    for line in lines:
        match = GITHUB_ALERT_PATTERN.match(line)
        if match:
            flush_block()
            in_callout = True
            current_type = match.group(1).upper()
            first_line = match.group(2).strip()
            if first_line:
                block_buffer.append(first_line)
        elif in_callout and line.startswith('>'):
            block_buffer.append(line[1:].strip())
        else:
            if in_callout:
                flush_block()
            new_lines.append(line)

    if in_callout:
        flush_block()

    return "\n".join(new_lines) + "\n"


CONVERTERS = {
    'gh-to-obsidian': convert_github_to_obsidian,
    'obsidian-to-gh': convert_obsidian_to_github,
    'callouts-to-classic': convert_callouts_to_classic,
    'classic-to-gh': convert_classic_to_github,
    'gh-to-html': convert_github_to_html,
}


def process_file(file_path, mode, in_place=False, dry_run=False, output_path=None):
    """Processes a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    converter = CONVERTERS[mode]
    converted = converter(content)

    if dry_run:
        print(f"{CYAN}--- DRY RUN ({file_path}) ---{RESET}")
        print(converted)
    elif in_place:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(converted)
        print(f"{GREEN}[SUCCESS]{RESET} Converted '{file_path}' in-place.")
    elif output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(converted)
        print(f"{GREEN}[SUCCESS]{RESET} Saved converted Markdown to '{output_path}'.")
    else:
        sys.stdout.write(converted)


def main():
    parser = argparse.ArgumentParser(
        description="Markdown Callout Converter - Transform callout and alert blocks across Markdown dialects."
    )
    parser.add_argument("target", help="Markdown file or directory to convert")
    parser.add_argument(
        "-m", "--mode",
        choices=list(CONVERTERS.keys()),
        default='obsidian-to-gh',
        help="Conversion mode (default: obsidian-to-gh)"
    )
    parser.add_argument("-o", "--output", help="Output file path (for single file conversion)")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify file(s) in-place")
    parser.add_argument("--dry-run", action="store_true", help="Preview output without making changes")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively process directory")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}[ERROR]{RESET} Path '{args.target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if os.path.isfile(args.target):
        process_file(args.target, args.mode, in_place=args.in_place, dry_run=args.dry_run, output_path=args.output)
    elif os.path.isdir(args.target):
        if not args.in_place and not args.dry_run:
            print(f"{RED}[ERROR]{RESET} Directory conversion requires --in-place or --dry-run flag.", file=sys.stderr)
            sys.exit(1)

        count = 0
        for root, _, files in os.walk(args.target):
            for file in files:
                if file.endswith(('.md', '.markdown')):
                    fp = os.path.join(root, file)
                    process_file(fp, args.mode, in_place=args.in_place, dry_run=args.dry_run)
                    count += 1
            if not args.recursive:
                break

        print(f"{GREEN}[SUCCESS]{RESET} Processed {count} Markdown files.")


if __name__ == '__main__':
    main()
