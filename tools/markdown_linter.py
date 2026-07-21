#!/usr/bin/env python3
"""
Markdown Linter - Scan and validate Markdown file formatting and structure

This tool checks markdown files for structural issues, accessibility violations,
and style guidelines (e.g., header hierarchy jumps, multiple top-level H1 headers,
missing alt texts for images, trailing whitespaces, and blank lines before headers).

Usage:
    python tools/markdown_linter.py [FILES_OR_DIRECTORIES] [--strict]

Example:
    python tools/markdown_linter.py README.md tools/
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class MarkdownLinter:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors: List[Tuple[int, str, str, str]] = []  # (line_no, rule_id, description, line_content)
        
    def add_error(self, line_no: int, rule_id: str, desc: str, content: str = ""):
        self.errors.append((line_no, rule_id, desc, content.strip()))

    def lint(self) -> bool:
        """Runs all linting checks. Returns True if no issues were found."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.add_error(0, "MD000", f"Failed to read file: {e}")
            return False

        h1_count = 0
        last_header_level = 0
        consecutive_blank_lines = 0
        
        for idx, line in enumerate(lines):
            line_no = idx + 1
            is_blank = not line.strip()

            # Rule MD003: Consecutive blank lines
            if is_blank:
                consecutive_blank_lines += 1
                if consecutive_blank_lines > 1:
                    self.add_error(line_no, "MD003", "Multiple consecutive blank lines", line)
            else:
                consecutive_blank_lines = 0

            # Rule MD004: Trailing whitespace
            if not is_blank and line.endswith((' \n', '\t\n', ' \r\n', '\t\r\n')):
                # Markdown allows 2 spaces at the end of a line for line breaks. 
                # Let's flag only if there are more than 2 spaces, or a tab.
                stripped_r = line.rstrip('\r\n')
                trailing_spaces = len(stripped_r) - len(stripped_r.rstrip(' '))
                if trailing_spaces > 2 or '\t' in stripped_r[-trailing_spaces:]:
                    self.add_error(line_no, "MD004", "Trailing spaces or tabs at end of line", line)

            # Check for headers
            header_match = re.match(r'^(#{1,6})(?:\s+(.*)|$)', line)
            if header_match:
                level_str = header_match.group(1)
                header_text = header_match.group(2)
                level = len(level_str)

                # Rule MD007: Space after header hashtag
                if not header_text:
                    self.add_error(line_no, "MD007", "Header has no space after '#' character or is empty", line)
                
                # Rule MD002: Single top-level H1 header
                if level == 1:
                    h1_count += 1
                    if h1_count > 1:
                        self.add_error(line_no, "MD002", "Multiple top-level H1 headings in one file", line)
                
                # Rule MD001: Header hierarchy incrementation
                if last_header_level > 0 and level > last_header_level + 1:
                    self.add_error(
                        line_no, 
                        "MD001", 
                        f"Heading level jumps too fast (H{last_header_level} to H{level})", 
                        line
                    )
                last_header_level = level

                # Rule MD006: Header should have a blank line before it
                if idx > 0:
                    prev_line = lines[idx - 1]
                    if prev_line.strip() and not prev_line.startswith('#'):
                        self.add_error(line_no, "MD006", "Heading should be preceded by a blank line", line)

            # Rule MD005: Image alt texts
            # Match image patterns: ![alt](url)
            images = re.findall(r'!\[(.*?)\]\(.*?\)', line)
            for alt_text in images:
                if not alt_text.strip():
                    self.add_error(line_no, "MD005", "Image missing alt text (accessibility violation)", line)

        return len(self.errors) == 0


def scan_path(target_path: Path) -> List[Path]:
    """Returns a list of markdown files found under the target path."""
    md_files = []
    if target_path.is_file():
        if target_path.suffix.lower() in ('.md', '.markdown'):
            md_files.append(target_path)
    elif target_path.is_dir():
        for root, _, files in os.walk(target_path):
            # Ignore hidden directories like .git
            if any(part.startswith('.') for part in Path(root).parts):
                continue
            for file in files:
                filepath = Path(root) / file
                if filepath.suffix.lower() in ('.md', '.markdown'):
                    md_files.append(filepath)
    return md_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown Lint Utility")
    parser.add_argument(
        "targets", 
        nargs="*", 
        default=["."], 
        help="Files or directories to scan (default: current directory)"
    )
    parser.add_argument(
        "--strict", 
        action="store_true", 
        help="Fail on any warnings or formatting anomalies"
    )
    
    args = parser.parse_args()
    
    all_files: List[Path] = []
    for t in args.targets:
        p = Path(t)
        if not p.exists():
            print(f"Error: Target path '{t}' does not exist.", file=sys.stderr)
            return 1
        all_files.extend(scan_path(p))

    if not all_files:
        print("No markdown files found to scan.")
        return 0

    print("=" * 60)
    print(f"Scanning {len(all_files)} Markdown files for syntax/formatting rules...")
    print("=" * 60)

    total_errors = 0
    files_with_issues = 0

    for filepath in sorted(all_files):
        linter = MarkdownLinter(filepath)
        linter.lint()
        
        if linter.errors:
            files_with_issues += 1
            total_errors += len(linter.errors)
            # Display relative path for brevity
            try:
                rel_path = filepath.relative_to(Path.cwd())
            except ValueError:
                rel_path = filepath
                
            print(f"\n{rel_path}:")
            for line_no, rule, desc, content in linter.errors:
                print(f"  Line {line_no:3}: [{rule}] {desc}")
                if content:
                    print(f"            > {content[:60]}")
                    
    print("\n" + "=" * 60)
    print(f"Scan Finished:")
    print(f"  Files Checked:       {len(all_files)}")
    print(f"  Files with Issues:   {files_with_issues}")
    print(f"  Total Violations:    {total_errors}")
    print("=" * 60)

    # Return exit codes
    if total_errors > 0 and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
