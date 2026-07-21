#!/usr/bin/env python3
"""
Regex Tester & Matcher

A command-line tool to test regular expressions against text inputs or files.
Highlights matches using ANSI colors and displays captured groups.

Usage:
    python regex_tester.py -p "pattern" -t "text to test" [options]
"""

import sys
import os
import re
import argparse

def highlight_matches(pattern, text, flags, color_code="31"):
    """Find and colorize all matches in the text."""
    # ANSI escape colors
    color_start = f"\033[1;{color_code}m"
    color_end = "\033[0m"
    
    # We compile the regex to find all matching ranges
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        print(f"Regex Compilation Error: {e}", file=sys.stderr)
        return None, []
        
    matches = list(rx.finditer(text))
    if not matches:
        return text, []

    # Reconstruct text with color markers by working backwards to keep indices correct
    highlighted = text
    for match in reversed(matches):
        start, end = match.span()
        # Skip empty matches to prevent infinite loops or corrupt tags
        if start == end:
            continue
        highlighted = highlighted[:start] + color_start + highlighted[start:end] + color_end + highlighted[end:]
        
    return highlighted, matches

def main():
    parser = argparse.ArgumentParser(
        description="Test regular expression patterns against text or files with colored matching and group output.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--pattern", "-p",
        required=True,
        help="The regular expression pattern to test."
    )
    
    # Input source (either direct text or file)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--text", "-t",
        help="Text string to test the pattern against."
    )
    group.add_argument(
        "--file", "-f",
        help="Path to a file to search for matches."
    )
    
    # Regex flags
    parser.add_argument(
        "--ignore-case", "-i",
        action="store_true",
        help="Enable case-insensitive matching (re.IGNORECASE)."
    )
    parser.add_argument(
        "--multiline", "-m",
        action="store_true",
        help="Enable multiline matching (re.MULTILINE)."
    )
    parser.add_argument(
        "--dotall", "-s",
        action="store_true",
        help="Make '.' match any character including newline (re.DOTALL)."
    )
    
    # Customization
    parser.add_argument(
        "--color", "-c",
        default="31",
        choices=["31", "32", "33", "34", "35", "36"],
        help="ANSI color code for matches (31=Red, 32=Green, 33=Yellow, 34=Blue, 35=Magenta, 36=Cyan)."
    )
    parser.add_argument(
        "--no-highlight",
        action="store_true",
        help="Disable ANSI colorized output."
    )
    
    args = parser.parse_args()
    
    # Get test text
    test_text = ""
    if args.text is not None:
        test_text = args.text
    else:
        file_path = os.path.abspath(args.file)
        if not os.path.exists(file_path):
            print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                test_text = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 1
            
    # Set regex flags
    flags = 0
    if args.ignore_case:
        flags |= re.IGNORECASE
    if args.multiline:
        flags |= re.MULTILINE
    if args.dotall:
        flags |= re.DOTALL
        
    # Perform matching
    highlighted_text, matches = highlight_matches(args.pattern, test_text, flags, args.color)
    
    if highlighted_text is None:
        # regex failed to compile
        return 1
        
    print("\n" + "="*40)
    print(f"Pattern: {args.pattern}")
    print(f"Flags: " + (" ".join(f for f in ["IGNORECASE" if args.ignore_case else "", 
                                            "MULTILINE" if args.multiline else "", 
                                            "DOTALL" if args.dotall else ""] if f) or "None"))
    print("="*40)
    
    if not matches:
        print("\nNo matches found.")
        return 0
        
    print(f"\nFound {len(matches)} match(es):")
    for idx, match in enumerate(matches, 1):
        start, end = match.span()
        print(f"\nMatch {idx} (Span: {start}-{end}): '{match.group(0)}'")
        
        # Display capture groups if any
        if match.groups():
            print("  Groups:")
            for g_idx, group_val in enumerate(match.groups(), 1):
                # Print group name if it is a named group
                g_name = list(match.groupdict().keys())[list(match.groupdict().values()).index(group_val)] if group_val in match.groupdict().values() else None
                name_str = f" (Name: {g_name})" if g_name else ""
                print(f"    Group {g_idx}{name_str}: '{group_val}'")
                
    if not args.no_highlight:
        print("\n" + "-"*15 + " Highlighted Text " + "-"*15)
        print(highlighted_text)
        print("-"*48)
    
    return 0

if __name__ == "__main__":
    # Windows ANSI terminal colors enablement
    if sys.platform == "win32":
        os.system("")
    sys.exit(main())
