#!/usr/bin/env python3
"""
Unicode Inspector - Inspect strings or files for Unicode code points and encodings

This tool takes a text string or file, analyzes each character, and details
its Unicode code point (e.g. U+0041), UTF-8 bytes, official Unicode name,
and general category. It also provides a summary of character distributions.

Usage:
    python tools/unicode_inspector.py "TEXT_TO_INSPECT" [options]
    python tools/unicode_inspector.py -f file.txt [options]

Options:
    -f, --file PATH       Path to a text file to inspect
    -l, --limit N         Limit character inspection to first N chars (default: 100)
    -s, --summary         Show only the summary analysis (no character-by-character table)
    -h, --help            Show this help message and exit

Example:
    python tools/unicode_inspector.py "Hello, 世界! 🐍"
"""

import argparse
import collections
import os
import sys
import unicodedata
from typing import Dict, List, Tuple


# Friendly names for Unicode categories
CATEGORY_MAP = {
    'Lu': 'Letter, Uppercase',
    'Ll': 'Letter, Lowercase',
    'Lt': 'Letter, Titlecase',
    'Lm': 'Letter, Modifier',
    'Lo': 'Letter, Other',
    'Mn': 'Mark, Nonspacing',
    'Mc': 'Mark, Spacing Combining',
    'Me': 'Mark, Enclosing',
    'Nd': 'Number, Decimal Digit',
    'Nl': 'Number, Letter',
    'No': 'Number, Other',
    'Pc': 'Punctuation, Connector',
    'Pd': 'Punctuation, Dash',
    'Ps': 'Punctuation, Open',
    'Pe': 'Punctuation, Close',
    'Pi': 'Punctuation, Initial Quote',
    'Pf': 'Punctuation, Final Quote',
    'Po': 'Punctuation, Other',
    'Sm': 'Symbol, Math',
    'Sc': 'Symbol, Currency',
    'Sk': 'Symbol, Modifier',
    'So': 'Symbol, Other',
    'Zs': 'Separator, Space',
    'Zl': 'Separator, Line',
    'Zp': 'Separator, Paragraph',
    'Cc': 'Other, Control',
    'Cf': 'Other, Format',
    'Cs': 'Other, Surrogate',
    'Co': 'Other, Private Use',
    'Cn': 'Other, Not Assigned'
}


def get_display_char(char: str) -> str:
    """Format invisible or control characters for display."""
    if char == '\n':
        return '\\n'
    elif char == '\t':
        return '\\t'
    elif char == '\r':
        return '\\r'
    elif char == ' ':
        return '[Space]'
    
    # Check if control character
    category = unicodedata.category(char)
    if category.startswith('C') or category == 'Zs':
        return f"[{category}]"
        
    return char


def inspect_text(text: str, limit: int, summary_only: bool):
    """Analyze text and print details and summary reports."""
    total_chars = len(text)
    inspect_limit = min(total_chars, limit)

    if not summary_only:
        print("=" * 105)
        print(f"{'Idx':<4} | {'Char':<8} | {'Code Point':<10} | {'UTF-8 Bytes (Hex)':<18} | {'Category':<22} | Name")
        print("=" * 105)
        
        for idx in range(inspect_limit):
            char = text[idx]
            code_point = f"U+{ord(char):04X}"
            utf8_bytes = " ".join(f"{b:02X}" for b in char.encode('utf-8'))
            category_code = unicodedata.category(char)
            category_desc = CATEGORY_MAP.get(category_code, category_code)
            
            try:
                name = unicodedata.name(char)
            except ValueError:
                name = "<unknown>"

            display_char = get_display_char(char)
            print(f"{idx:<4} | {display_char:<8} | {code_point:<10} | {utf8_bytes:<18} | {category_desc[:22]:<22} | {name}")
            
        if total_chars > limit:
            print("-" * 105)
            print(f"... and {total_chars - limit} more characters (use --limit to show more) ...")
            
        print("=" * 105)

    # Compute summary metrics
    categories = collections.Counter()
    scripts = collections.Counter()
    unicode_blocks = collections.Counter()
    non_ascii_count = 0

    for char in text:
        cat = unicodedata.category(char)
        categories[cat] += 1
        if ord(char) > 127:
            non_ascii_count += 1

    print("\nSummary Analysis:")
    print(f"  Total Characters: {total_chars}")
    print(f"  ASCII Characters: {total_chars - non_ascii_count}")
    print(f"  Non-ASCII Characters: {non_ascii_count}")
    print("\n  Category Breakdown:")
    for cat_code, count in categories.most_common():
        cat_desc = CATEGORY_MAP.get(cat_code, cat_code)
        pct = (count / total_chars) * 100
        print(f"    {cat_desc:<25} ({cat_code}): {count:<5} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Inspect details of Unicode characters and encodings.")
    parser.add_argument("text", nargs="?", default="", help="Text to inspect")
    parser.add_argument("-f", "--file", help="Path to text file to inspect")
    parser.add_argument("-l", "--limit", type=int, default=100, help="Maximum number of characters to display (default: 100)")
    parser.add_argument("-s", "--summary", action="store_true", help="Only output summary diagnostics")

    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1
        try:
            with open(args.file, 'r', encoding='utf-8', errors='replace') as f:
                text_content = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 1
    else:
        text_content = args.text

    if not text_content:
        # If no arguments are provided, print usage
        parser.print_help()
        return 0

    inspect_text(text_content, args.limit, args.summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
