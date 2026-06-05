#!/usr/bin/env python3
"""
Regex Tester

Test regular expressions against text or file input, with group capture details and highlighted matches.

Usage:
    python tools/regex_tester.py "pattern" "text to search"
    python tools/regex_tester.py "pattern" -f input.txt
"""

import argparse
import re
import sys

# ANSI Escape Sequences for coloring
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def main():
    parser = argparse.ArgumentParser(description="Regex Tester - Test regular expressions with group details and highlighting")
    parser.add_argument('pattern', help='The regular expression pattern to test')
    parser.add_argument('text', nargs='?', help='The text string to search against')
    parser.add_argument('-f', '--file', help='Path to a file to search against')
    parser.add_argument('-i', '--ignore-case', action='store_true', help='Perform case-insensitive matching')
    
    args = parser.parse_args()

    # Get input text
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            return 1
        except Exception as e:
            print(f"Error reading file: {e}")
            return 1
    elif args.text is not None:
        text = args.text
    else:
        print("Error: You must provide either a text string or a file with -f/--file.")
        parser.print_help()
        return 1

    flags = re.IGNORECASE if args.ignore_case else 0

    try:
        regex = re.compile(args.pattern, flags)
    except re.error as e:
        print(f"Error: Invalid regex pattern: {e}")
        return 1

    matches = list(regex.finditer(text))

    if not matches:
        print(f"No matches found for pattern: '{args.pattern}'")
        return 0

    print(f"Found {len(matches)} match(es):\n")

    # Highlight matches in the text
    # We will reconstruct the text with highlights
    highlighted_text = ""
    last_idx = 0
    for match in matches:
        start, end = match.span()
        # Add text before match
        highlighted_text += text[last_idx:start]
        # Add highlighted match
        highlighted_text += f"{GREEN}{BOLD}{text[start:end]}{RESET}"
        last_idx = end
    highlighted_text += text[last_idx:]

    print(f"{BOLD}Highlighted Output:{RESET}")
    print("-" * 40)
    print(highlighted_text)
    print("-" * 40)
    print()

    # Print details for each match and its groups
    print(f"{BOLD}Match Details:{RESET}")
    for idx, match in enumerate(matches, 1):
        start, end = match.span()
        print(f"Match {idx}: '{match.group(0)}' (Indices: {start}-{end})")
        if match.groups():
            print("  Capture Groups:")
            for g_idx, group in enumerate(match.groups(), 1):
                g_start, g_end = match.span(g_idx)
                print(f"    Group {g_idx}: '{group}' (Indices: {g_start}-{g_end})")
        if match.groupdict():
            print("  Named Groups:")
            for name, val in match.groupdict().items():
                g_start, g_end = match.span(name)
                print(f"    {name}: '{val}' (Indices: {g_start}-{g_end})")
        print()

    return 0

if __name__ == "__main__":
    # Standard cmd.exe on Windows doesn't support ANSI codes by default, so we enable it
    if sys.platform == 'win32':
        import os
        os.system('') # this enables ANSI escape sequences on Windows 10+ command prompt
    sys.exit(main())
