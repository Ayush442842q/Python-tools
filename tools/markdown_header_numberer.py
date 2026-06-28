#!/usr/bin/env python3
"""
Markdown Header Numberer
Automatically insert, update, or strip sequential section numbering (e.g. 1., 1.1, 1.1.1)
from Markdown headers (# through ######) based on their hierarchical nesting levels.
"""

import argparse
import os
import re
import sys
from typing import List

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_CYAN = "\033[36m"

# Regex to match Markdown headers and separate the hash marks, existing numbering, and heading text
# Match pattern: ^(#{1,6})\s+((?:\d+\.)*\d+\s+)?(.*)$
HEADER_RE = re.compile(r'^(#{1,6})\s+(?:(?:\d+\.)+\d*\s+)?(.*)$')

def number_markdown(
    lines: List[str], 
    start_level: int = 1, 
    strip: bool = False
) -> List[str]:
    """Processes lines and adds/updates/strips sequential numbering."""
    counters = [0] * 7 # Level index 1 to 6 (0 index unused)
    output_lines = []
    
    for line in lines:
        match = HEADER_RE.match(line)
        if not match:
            # Not a heading line
            output_lines.append(line)
            continue
            
        hashes, text = match.groups()
        level = len(hashes)
        
        # If the header level is less than our starting level for numbering,
        # we treat it as unnumbered but clean off any existing number prefix.
        if level < start_level or strip:
            output_lines.append(f"{hashes} {text}")
            continue
            
        # Adjust counters for heading level
        counters[level] += 1
        # Reset all sub-level counters
        for i in range(level + 1, 7):
            counters[i] = 0
            
        # Build the number string using counters from start_level to current level
        num_parts = [str(counters[i]) for i in range(start_level, level + 1)]
        num_str = ".".join(num_parts)
        
        # Add a trailing dot for top-level headers (e.g., "1. Heading" vs "1.1 Heading")
        if len(num_parts) == 1:
            num_str += "."
            
        output_lines.append(f"{hashes} {num_str} {text}")
        
    return output_lines

def main():
    parser = argparse.ArgumentParser(
        description="Insert, update, or strip sequential section numbering in Markdown documents."
    )
    parser.add_argument("file", help="Path to the Markdown file to process")
    parser.add_argument(
        "-o", "--output", 
        help="Path to write the output file (default: overwrite the input file in-place)"
    )
    parser.add_argument(
        "-s", "--strip", 
        action="store_true", 
        help="Strip all section numbering from headers instead of adding/updating them"
    )
    parser.add_argument(
        "-l", "--start-level", 
        type=int, 
        default=1, 
        choices=range(1, 7),
        help="Heading level to start numbering from (default: 1, i.e., '#' level. Use 2 to start at '##')"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"{COLOR_RED}Error: File '{args.file}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except Exception as e:
        print(f"{COLOR_RED}Error reading file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{COLOR_CYAN}Processing '{args.file}'...{COLOR_RESET}")
    result_lines = number_markdown(lines, start_level=args.start_level, strip=args.strip)
    
    output_path = args.output if args.output else args.file
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(result_lines) + "\n")
        
        action = "Stripped numbering from" if args.strip else "Updated numbering in"
        print(f"{COLOR_GREEN}✔ Success! {action} '{output_path}'{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Error writing output file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
