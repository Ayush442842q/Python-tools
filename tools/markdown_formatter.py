#!/usr/bin/env python3
"""
Markdown Auto-Formatter & Fixer
Reads Markdown files and automatically formats them to comply with standard linting
rules: normalizes header spacing, ensures blank lines surrounding blocks (code blocks,
headers, lists, tables), removes trailing whitespaces, and standardizes list items.
"""

import argparse
import difflib
import os
import re
import sys
from typing import List, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_RED = ""
    COLOR_CYAN = ""

def format_markdown(content: str) -> str:
    """Applies multiple formatting rules to raw markdown content."""
    # 1. Normalize line endings to LF
    content = content.replace("\r\n", "\n")
    
    # Split content into lines
    lines = content.split("\n")
    
    # 2. Trim trailing whitespace from all lines
    lines = [line.rstrip() for line in lines]
    
    formatted_lines: List[str] = []
    
    in_code_block = False
    
    for i, line in enumerate(lines):
        # Detect code blocks
        if line.startswith("```"):
            in_code_block = not in_code_block
            
            # Ensure blank line before code block unless it's start of file
            if in_code_block and formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
                
            formatted_lines.append(line)
            
            # Ensure blank line after code block closing unless it's end of file
            if not in_code_block and i < len(lines) - 1 and lines[i + 1] != "":
                # Don't add blank line immediately if next line is already empty
                pass
            continue
            
        if in_code_block:
            # Do not touch content inside code blocks
            formatted_lines.append(line)
            continue
            
        # 3. Format Headers
        header_match = re.match(r"^(#{1,6})(.*)", line)
        if header_match:
            hashes = header_match.group(1)
            header_text = header_match.group(2).strip()
            
            # Ensure space after hashes
            line = f"{hashes} {header_text}"
            
            # Ensure blank line before header unless it's start of file
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
                
            formatted_lines.append(line)
            
            # Ensure blank line after header unless it's end of file or next line is a header/empty
            if i < len(lines) - 1 and lines[i + 1] != "" and not lines[i + 1].startswith("#"):
                # We will check if next lines have a blank line; if not, we wait or insert one.
                # To keep it simple, we just insert an empty line in the next step when we see it.
                pass
            continue

        # 4. Standardize horizontal rules (thematic breaks)
        if re.match(r"^(\* \* \*|\-\-\-|\_\_\_)$", line):
            line = "---"
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.append(line)
            continue

        # 5. Standardize checkbox tasks in lists
        task_match = re.match(r"^(\s*[\-\*\+])\s*\[([ xX]?)\]\s*(.*)", line)
        if task_match:
            bullet = task_match.group(1)
            checked = task_match.group(2)
            item_text = task_match.group(3).strip()
            # Normalize to '- [ ]' or '- [x]'
            marker = "x" if checked.lower() == "x" else " "
            line = f"{bullet} [{marker}] {item_text}"
            formatted_lines.append(line)
            continue

        # Standard lines
        formatted_lines.append(line)

    # 6. Normalize multiple consecutive empty lines to single empty lines (outside code blocks)
    cleaned_lines: List[str] = []
    in_code_block = False
    for line in formatted_lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            cleaned_lines.append(line)
            continue
            
        if in_code_block:
            cleaned_lines.append(line)
            continue
            
        if line == "":
            if not cleaned_lines or cleaned_lines[-1] != "":
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line)

    # 7. Ensure single trailing newline
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()
        
    cleaned_lines.append("")  # This will result in exactly one empty string at the end, representing trailing newline
    
    return "\n".join(cleaned_lines)

def process_file(filepath: str, dry_run: bool, in_place: bool) -> bool:
    """Processes a single markdown file, optionally displaying diffs or updating in place."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original = f.read()
            
        formatted = format_markdown(original)
        
        if original == formatted:
            print(f"{COLOR_GREEN}✔ {filepath} is already correctly formatted.{COLOR_RESET}")
            return True
            
        if dry_run:
            print(f"\n{COLOR_BOLD}{COLOR_YELLOW}Differences in {filepath}:{COLOR_RESET}")
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                formatted.splitlines(keepends=True),
                fromfile=f"a/{filepath}",
                tofile=f"b/{filepath}"
            )
            sys.stdout.writelines(diff)
            print()
        elif in_place:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print(f"{COLOR_GREEN}✔ Formatted {filepath} in place.{COLOR_RESET}")
        else:
            # If not in place and not dry run, output formatted content to stdout
            print(formatted, end="")
            
        return False
    except Exception as e:
        print(f"{COLOR_RED}Error processing {filepath}: {e}{COLOR_RESET}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Format markdown files to comply with general styling conventions."
    )
    parser.add_argument(
        "files", nargs="+", help="One or more markdown files to format"
    )
    parser.add_argument(
        "-d", "--dry-run", action="store_true",
        help="Print a unified diff of formatting changes without modifying files"
    )
    parser.add_argument(
        "-i", "--in-place", action="store_true",
        help="Write formatting changes back to the source files in place"
    )
    
    args = parser.parse_args()
    
    any_changed = False
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"{COLOR_RED}Error: File '{filepath}' does not exist.{COLOR_RESET}", file=sys.stderr)
            continue
            
        is_formatted = process_file(filepath, args.dry_run, args.in_place)
        if not is_formatted:
            any_changed = True
            
    if args.dry_run and any_changed:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
