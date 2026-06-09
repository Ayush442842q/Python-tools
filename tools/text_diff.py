#!/usr/bin/env python3
"""
Text Diff Tool

Compares two text files and prints a colored diff highlighting additions,
deletions, and modifications in the terminal. Supports unified diff format,
case-insensitive comparison, ignoring whitespace changes, and disabling color.

Usage:
    python tools/text_diff.py file1.txt file2.txt
    python tools/text_diff.py file1.txt file2.txt --no-color
    python tools/text_diff.py file1.txt file2.txt -w --context 5
"""

import argparse
import difflib
import os
import sys

# ANSI Escape Sequences for Terminal Colors
COLOR_RESET = "\033[0m"
COLOR_ADDED = "\033[32m"      # Green
COLOR_DELETED = "\033[31m"    # Red
COLOR_HEADER = "\033[36m"     # Cyan
COLOR_LINE_NUM = "\033[33m"   # Yellow / Brown

def init_ansi_terminal():
    """
    Enables ANSI terminal processing on Windows if supported.
    """
    if os.name == 'nt':
        try:
            # os.system('') initiates ANSI sequence parsing in Windows Command Prompt/PowerShell
            os.system('')
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(
        description="Text Diff Tool - Compare two text files with colored command-line output."
    )
    parser.add_argument('file1', help='Path to the first (original) file')
    parser.add_argument('file2', help='Path to the second (modified) file')
    parser.add_argument(
        '-c', '--context', 
        type=int, 
        default=3, 
        help='Number of context lines to display (default: 3)'
    )
    parser.add_argument(
        '-w', '--ignore-whitespace', 
        action='store_true', 
        help='Ignore whitespace changes during comparison'
    )
    parser.add_argument(
        '-i', '--ignore-case', 
        action='store_true', 
        help='Ignore case differences during comparison'
    )
    parser.add_argument(
        '--no-color', 
        action='store_true', 
        help='Disable colored terminal output'
    )

    args = parser.parse_args()

    # Check file existence
    if not os.path.isfile(args.file1):
        print(f"[ERROR] Original file '{args.file1}' does not exist.", file=sys.stderr)
        return 1
    if not os.path.isfile(args.file2):
        print(f"[ERROR] Modified file '{args.file2}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(args.file1, 'r', encoding='utf-8', errors='replace') as f1:
            file1_lines = f1.readlines()
        with open(args.file2, 'r', encoding='utf-8', errors='replace') as f2:
            file2_lines = f2.readlines()
    except Exception as e:
        print(f"[ERROR] Failed to read files: {e}", file=sys.stderr)
        return 1

    # Optional: Normalizations
    f1_compare = list(file1_lines)
    f2_compare = list(file2_lines)

    if args.ignore_case or args.ignore_whitespace:
        # Preprocess lines for comparison only
        def normalize_line(line):
            if args.ignore_whitespace:
                # Remove all spaces/tabs and strip line ends
                line = "".join(line.split())
            else:
                line = line.rstrip()
            if args.ignore_case:
                line = line.lower()
            return line

        # Standard unified diff works on sequences. If we do normalization,
        # we can still run unified_diff but we might want the diff index mapping.
        # Alternatively, we can use difflib.SequenceMatcher.
        # For a simple and robust solution, let's compare normalized lists to get generator indices,
        # or use difflib.unified_diff on normalized lists but show the original lines.
        # Let's perform standard diff on normalized/preprocessed contents, or use difflib's built-in hooks if possible.
        # Since difflib.unified_diff does line-by-line string matching, if we normalize, the output diff lines
        # will show the normalized text, which isn't ideal.
        # Instead, let's use a custom diff sequence generator or match lines ignoring whitespace when checking.
        # A simpler way when ignoring whitespace/case:
        # We can construct a customized matcher or just diff the normalized lines.
        # Let's generate a diff based on normalized lines but replace diff lines back with original lines where possible,
        # or just run unified_diff on the original lines but strip them.
        # Let's keep it simple: if ignore_whitespace or ignore_case is requested, we do the diff on processed versions.
        # Let's see: difflib.unified_diff accepts any sequence of strings.
        pass

    # To show clean diffs, let's use difflib.unified_diff
    # We will pass original lines to unified_diff
    # If the user specified ignore_whitespace or ignore_case, we can use a custom compare key.
    # Since difflib doesn't easily support custom key functions in unified_diff directly,
    # we can do it by passing list of wrapper objects or pre-processed lines.
    # Let's define a line wrapper class for comparing that inherits from str
    # to satisfy difflib's strict string type checks on newer Python versions.
    class DiffLine(str):
        def __new__(cls, original, key):
            obj = str.__new__(cls, original)
            obj.key = key
            return obj

        def __eq__(self, other):
            if isinstance(other, DiffLine):
                return self.key == other.key
            return str(self) == str(other)

        def __hash__(self):
            return hash(self.key)

    # Wrap lines with computed normalization keys
    f1_wrapped = []
    for line in file1_lines:
        key = line
        if args.ignore_whitespace:
            key = "".join(key.split())
        else:
            key = key.rstrip('\r\n')
        if args.ignore_case:
            key = key.lower()
        f1_wrapped.append(DiffLine(line, key))

    f2_wrapped = []
    for line in file2_lines:
        key = line
        if args.ignore_whitespace:
            key = "".join(key.split())
        else:
            key = key.rstrip('\r\n')
        if args.ignore_case:
            key = key.lower()
        f2_wrapped.append(DiffLine(line, key))

    diff = difflib.unified_diff(
        f1_wrapped,
        f2_wrapped,
        fromfile=args.file1,
        tofile=args.file2,
        n=args.context
    )

    # Initialize terminal color support
    if not args.no_color:
        init_ansi_terminal()

    has_differences = False
    
    # Process and print diff
    for line in diff:
        has_differences = True
        
        # Convert to string (works for both standard str and DiffLine subclass)
        line_str = str(line)

        # Remove trailing newline for clean print
        clean_line = line_str.rstrip('\r\n')

        if args.no_color:
            print(clean_line)
        else:
            # Color code lines based on unified diff format
            if clean_line.startswith('+++') or clean_line.startswith('---'):
                print(f"{COLOR_HEADER}{clean_line}{COLOR_RESET}")
            elif clean_line.startswith('@@'):
                print(f"{COLOR_LINE_NUM}{clean_line}{COLOR_RESET}")
            elif clean_line.startswith('+'):
                print(f"{COLOR_ADDED}{clean_line}{COLOR_RESET}")
            elif clean_line.startswith('-'):
                print(f"{COLOR_DELETED}{clean_line}{COLOR_RESET}")
            else:
                print(clean_line)

    if not has_differences:
        print("[OK] No differences found. The files are identical.")
        return 0

    return 0

if __name__ == '__main__':
    sys.exit(main())
