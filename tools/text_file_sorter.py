#!/usr/bin/env python3
"""
Text File Sorter - Sorts lines in a text file based on various criteria.
Supports alphabetical, numerical, line length, field-based sorting,
case-insensitive sorting, deduplication, and reverse ordering.
"""

import argparse
import os
import re
import sys


def extract_numeric(text):
    """Helper to extract the first numeric value from a string for sorting."""
    match = re.search(r'-?\d+(?:\.\d+)?', text)
    return float(match.group()) if match else float('-inf')


def sort_lines(lines, criteria='alpha', ignore_case=False, reverse=False, delimiter=None, field=None):
    """Sorts a list of lines based on the specified criteria and options."""
    
    def get_sort_key(line):
        stripped = line.rstrip('\r\n')
        
        # If field sorting is requested
        if delimiter is not None and field is not None:
            parts = stripped.split(delimiter)
            if 0 <= field < len(parts):
                key_text = parts[field]
            else:
                key_text = ""
        else:
            key_text = stripped
            
        if criteria == 'numeric':
            return extract_numeric(key_text)
        elif criteria == 'length':
            return len(key_text)
        else: # alpha
            return key_text.lower() if ignore_case else key_text

    # Sort using the custom key
    return sorted(lines, key=get_sort_key, reverse=reverse)


def main():
    parser = argparse.ArgumentParser(
        description="Sort lines in a text file based on various criteria."
    )
    parser.add_argument("input_file", help="Path to the input text file.")
    parser.add_argument(
        "-o", "--output", 
        help="Path to the output file (if omitted, prints to stdout. Use '-' for in-place sorting)."
    )
    parser.add_argument(
        "-c", "--criteria", 
        choices=["alpha", "numeric", "length"], 
        default="alpha",
        help="Sorting criteria: alpha (alphabetical, default), numeric (by first number found), or length (by line length)."
    )
    parser.add_argument(
        "-i", "--ignore-case", 
        action="store_true", 
        help="Ignore case when sorting alphabetically."
    )
    parser.add_argument(
        "-r", "--reverse", 
        action="store_true", 
        help="Reverse the sort order."
    )
    parser.add_argument(
        "-u", "--unique", 
        action="store_true", 
        help="Remove duplicate lines."
    )
    parser.add_argument(
        "-d", "--delimiter", 
        help="Delimiter to split fields (for field-based sorting)."
    )
    parser.add_argument(
        "-f", "--field", 
        type=int, 
        help="0-indexed field number to sort by (requires --delimiter)."
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Print sorting summary to stderr."
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        return 1

    if args.field is not None and args.delimiter is None:
        print("Error: --field requires --delimiter to be specified.", file=sys.stderr)
        return 1

    try:
        with open(args.input_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    original_count = len(lines)

    if args.unique:
        # Deduplicate while preserving order (before sorting is fine since we sort anyway)
        seen = set()
        deduped_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                deduped_lines.append(line)
        lines = deduped_lines

    sorted_lines = sort_lines(
        lines, 
        criteria=args.criteria, 
        ignore_case=args.ignore_case, 
        reverse=args.reverse, 
        delimiter=args.delimiter, 
        field=args.field
    )

    # Determine output target
    if args.output == '-':
        output_file = args.input_file
    else:
        output_file = args.output

    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(sorted_lines)
            if args.verbose:
                action = "Sorted in-place" if args.output == '-' else f"Sorted into '{output_file}'"
                print(f"{action}: {len(sorted_lines)} lines (original: {original_count}).", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output: {e}", file=sys.stderr)
            return 1
    else:
        for line in sorted_lines:
            sys.stdout.write(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
