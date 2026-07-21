#!/usr/bin/env python3
"""
File Regex Replacer
Search and replace text in multiple files using regular expressions.

Usage:
    python tools/file_regex_replacer.py <pattern> <replacement> <files...> [options]

Arguments:
    pattern                Regular expression to search for
    replacement            Replacement text (supports backreferences like \\1)
    files                  One or more file paths or glob patterns to process

Options:
    -d, --dry-run          Show what changes would be made without writing to files
    -i, --ignore-case      Perform case-insensitive search
    -b, --backup           Create a backup (.bak) of changed files before modifying
    -e, --extensions EXTS  Comma-separated list of file extensions to target (e.g., txt,py)
    -v, --verbose          Print details of every match
    -h, --help             Show this help message and exit

Example:
    python tools/file_regex_replacer.py "Version: ([0-9.]+)" "Version: 1.2.3" config.txt
    python tools/file_regex_replacer.py "TODO:? (.*)" "FIXED: \\1" tools/*.py --dry-run
"""

import argparse
import fnmatch
import glob
import os
import re
import sys


def process_file(file_path, pattern_re, replacement, dry_run, backup, verbose):
    """Process a single file, finding and replacing matches."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        return 0, 0

    # Find matches
    matches = list(pattern_re.finditer(content))
    if not matches:
        return 0, 0

    new_content, count = pattern_re.subn(replacement, content)
    
    # Analyze changes line by line for user feedback
    orig_lines = content.splitlines()
    new_lines = new_content.splitlines()

    print(f"\nFile: {file_path} ({count} matches)")
    
    if verbose or dry_run:
        # Show a simple diff-like view
        diff_count = 0
        for i, (orig_line, new_line) in enumerate(zip(orig_lines, new_lines), 1):
            if orig_line != new_line:
                print(f"  Line {i}:")
                print(f"    - {orig_line}")
                print(f"    + {new_line}")
                diff_count += 1
                if diff_count >= 10 and not verbose:
                    print("    ... (truncated remaining diffs, use --verbose to show all)")
                    break

    if not dry_run:
        if backup:
            backup_path = file_path + '.bak'
            try:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  Created backup: {backup_path}")
            except Exception as e:
                print(f"  Failed to create backup: {e}", file=sys.stderr)
                return count, 0
                
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"  Successfully updated file.")
        except Exception as e:
            print(f"  Error writing file: {e}", file=sys.stderr)
            return count, 0

    return count, 1


def main():
    parser = argparse.ArgumentParser(description="Search and replace text in files using regular expressions.")
    parser.add_argument('pattern', help='Regex pattern to search for')
    parser.add_argument('replacement', help='Replacement text (supports \\1, \\g<1>, etc.)')
    parser.add_argument('files', nargs='+', help='File paths, directories, or glob patterns')
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help='Show changes without writing to files')
    parser.add_argument('-i', '--ignore-case', action='store_true',
                        help='Perform case-insensitive search')
    parser.add_argument('-b', '--backup', action='store_true',
                        help='Create a .bak backup file before modifying')
    parser.add_argument('-e', '--extensions', default='',
                        help='Comma-separated list of target file extensions (e.g. py,txt)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show verbose output of all replacements')
    
    args = parser.parse_args()

    # Compile regex pattern
    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        pattern_re = re.compile(args.pattern, flags)
    except re.error as e:
        print(f"Error: Invalid regex pattern '{args.pattern}': {e}", file=sys.stderr)
        return 1

    # Parse extensions filter
    target_exts = None
    if args.extensions:
        target_exts = {ext.strip().lower().lstrip('.') for ext in args.extensions.split(',')}

    # Resolve file paths (handling wildcard globs)
    matched_files = set()
    for file_pattern in args.files:
        # Check if the path is a directory
        if os.path.isdir(file_pattern):
            for root, _, filenames in os.walk(file_pattern):
                for filename in filenames:
                    matched_files.add(os.path.join(root, filename))
        else:
            # Use glob to expand wildcards
            for path in glob.glob(file_pattern, recursive=True):
                if os.path.isfile(path):
                    matched_files.add(path)
                elif os.path.isdir(path):
                    for root, _, filenames in os.walk(path):
                        for filename in filenames:
                            matched_files.add(os.path.join(root, filename))

    # Filter by extension if specified
    final_files = []
    for file_path in sorted(matched_files):
        if target_exts:
            ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
            if ext not in target_exts:
                continue
        final_files.append(file_path)

    if not final_files:
        print("No files matched the search criteria.", file=sys.stderr)
        return 0

    print(f"Scanning {len(final_files)} files for pattern: r'{args.pattern}'")
    if args.dry_run:
        print("[Dry Run Mode] No changes will be written to disk.")

    total_matches = 0
    modified_files = 0

    for file_path in final_files:
        matches, modified = process_file(
            file_path, 
            pattern_re, 
            args.replacement, 
            args.dry_run, 
            args.backup, 
            args.verbose
        )
        total_matches += matches
        modified_files += modified

    action_word = "would be modified" if args.dry_run else "modified"
    print(f"\nSummary: Found {total_matches} matches across {len(final_files)} files. {modified_files} files {action_word}.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
