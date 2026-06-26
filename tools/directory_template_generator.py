#!/usr/bin/env python3
"""
Directory Template Generator - Generate directories and files from a text tree/outline

This tool takes a text-based representation of a directory tree (such as Unicode
drawings, bulleted lists, or indented text) and instantiates the actual files
and folders on your file system. It supports specifying inline file contents using colons.

Usage:
    python tools/directory_template_generator.py tree.txt [-o ./output_dir]
    cat tree.txt | python tools/directory_template_generator.py -o ./output_dir
    python tools/directory_template_generator.py --text "project/\n├── README.md: 'Hello'\n└── src/\n    └── main.py"
"""

import argparse
import os
import re
import sys
from typing import List, Tuple, Dict, Optional


def get_indent_and_clean_name(line: str) -> Tuple[int, str]:
    """
    Extracts the indentation depth and the trailing name with content.
    Replaces branch symbols and bullet points with spaces to calculate depth.
    """
    line_r = line.rstrip()
    if not line_r:
        return 0, ""

    # Match structural indicators, spaces, tabs, tree branches, bullets
    # Examples: "│   ├── main.py", "  - README.md: 'content'"
    match = re.match(r'^([│\s├└─├─└─|┌\+\-\*•\s]*)', line_r)
    prefix = match.group(1) if match else ""
    
    # Calculate depth using string length, converting tabs to 4 spaces
    indent = 0
    for char in prefix:
        if char == '\t':
            indent += 4
        else:
            indent += 1
            
    name_and_content = line_r[len(prefix):].strip()
    return indent, name_and_content


def parse_tree_outline(lines: List[str]) -> List[Tuple[str, str, bool]]:
    """
    Parses a list of tree outline lines.
    Returns a list of tuples: (relative_path, content, is_directory).
    """
    parsed_items: List[Tuple[str, str, bool]] = []
    # Stack stores (indent_level, folder_or_file_name)
    stack: List[Tuple[int, str]] = []

    # Filter out empty lines
    active_lines = [line for line in lines if line.strip()]
    
    for idx, line in enumerate(active_lines):
        indent, name_with_content = get_indent_and_clean_name(line)
        if not name_with_content:
            continue

        # Extract file content if a colon exists (e.g. "README.md: 'Hello World'")
        content = ""
        name = name_with_content
        if ":" in name_with_content:
            # Slices at first colon only
            parts = name_with_content.split(':', 1)
            name = parts[0].strip()
            content = parts[1].strip()
            # Strip outer quotes if any
            if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
                content = content[1:-1]
            # Replace escaped newlines
            content = content.replace('\\n', '\n')

        # Pop from stack until the parent indentation level is smaller than the current level
        while stack and stack[-1][0] >= indent:
            stack.pop()

        # Add current item to stack
        stack.append((indent, name))

        # Reconstruct path from the current stack
        path_components = [item[1] for item in stack]
        rel_path = "/".join(path_components)

        # Decide if directory or file
        is_dir = False
        # 1. Ends with slash -> Directory
        if name.endswith('/') or name.endswith('\\'):
            is_dir = True
            # Strip trailing slash for creation
            rel_path = rel_path.rstrip('/\\')
        # 2. Content specified -> File
        elif content:
            is_dir = False
        # 3. Check next line's indentation. If next line is deeper, this is a directory.
        elif idx + 1 < len(active_lines):
            next_indent, next_name = get_indent_and_clean_name(active_lines[idx + 1])
            if next_indent > indent:
                is_dir = True
        # 4. Check file extension as fallback
        elif '.' not in name:
            is_dir = True

        parsed_items.append((rel_path, content, is_dir))

    return parsed_items


def create_directory_structure(
    items: List[Tuple[str, str, bool]], 
    output_dir: str, 
    dry_run: bool = False
) -> None:
    """Creates the files and folders described in items under output_dir."""
    print("=" * 60)
    print(f"Instantiating Directory Template under: {output_dir}")
    if dry_run:
        print("--- DRY RUN: No modifications will be written ---")
    print("=" * 60)

    for rel_path, content, is_dir in items:
        # Construct absolute path safely
        dest_path = os.path.normpath(os.path.join(output_dir, rel_path))
        
        # Security check: prevent writing outside of target directory
        if not os.path.abspath(dest_path).startswith(os.path.abspath(output_dir)):
            print(f"Error: Path '{rel_path}' attempts directory traversal. Skipping.", file=sys.stderr)
            continue

        if is_dir:
            print(f"[Folder] Creating: {rel_path}/")
            if not dry_run:
                os.makedirs(dest_path, exist_ok=True)
        else:
            print(f"[File]   Creating: {rel_path} " + (f"({len(content)} bytes)" if content else ""))
            if not dry_run:
                # Ensure parent directories exist
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                try:
                    with open(dest_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                except IOError as e:
                    print(f"Error writing to file '{rel_path}': {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate folders and files from a text outline or tree diagram."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Input text file containing the directory outline (reads from stdin if omitted or '-')"
    )
    parser.add_argument(
        "-t", "--text",
        help="Raw string representation of directory structure (newline separated)"
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Target output directory (default: current directory)"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Simulate template creation and list actions without writing changes"
    )

    args = parser.parse_args()

    # Get lines of input structure
    lines: List[str] = []
    
    if args.text:
        # Split on newline characters
        lines = args.text.splitlines()
    else:
        # Determine input stream
        if not args.file or args.file == '-':
            if sys.stdin.isatty():
                parser.print_help()
                sys.exit(0)
            input_stream = sys.stdin
        else:
            try:
                input_stream = open(args.file, 'r', encoding='utf-8')
            except IOError as e:
                print(f"Error opening file: {e}", file=sys.stderr)
                sys.exit(1)
                
        try:
            lines = input_stream.readlines()
        finally:
            if input_stream is not sys.stdin:
                input_stream.close()

    if not lines:
        print("Error: No input text provided.", file=sys.stderr)
        sys.exit(1)

    # Parse and execute
    output_dir = os.path.abspath(args.output)
    items = parse_tree_outline(lines)
    create_directory_structure(items, output_dir, args.dry_run)
    print("-" * 60)
    print("Done!")


if __name__ == '__main__':
    main()
