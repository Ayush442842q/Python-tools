#!/usr/bin/env python3
"""
CSS Minifier

Minifies CSS files by removing comments, unnecessary whitespace, and line breaks.

Usage:
    python tools/css_minifier.py input.css [-o output.css]
"""

import argparse
import os
import re
import sys

def minify_css(css_content):
    # Remove comments
    css = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    # Remove whitespace around selectors and properties
    css = re.sub(r'\s*([\{\};:,])\s*', r'\1', css)
    # Remove multiple spaces/newlines
    css = re.sub(r'\s+', ' ', css)
    # Trim leading and trailing whitespace
    return css.strip()

def main():
    parser = argparse.ArgumentParser(description="CSS Minifier - Minify CSS files")
    parser.add_argument('input', help='Path to the input CSS file')
    parser.add_argument('-o', '--output', help='Path to the output minified CSS file')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File '{args.input}' not found.")
        return 1

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return 1

    minified_content = minify_css(original_content)
    
    orig_size = len(original_content.encode('utf-8'))
    min_size = len(minified_content.encode('utf-8'))
    reduction = ((orig_size - min_size) / orig_size * 100) if orig_size > 0 else 0

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(minified_content)
            print(f"Minified CSS saved to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}")
            return 1
    else:
        print("Minified Output:")
        print(minified_content)
        print()

    print("Statistics:")
    print(f"  Original Size:  {orig_size} bytes")
    print(f"  Minified Size:  {min_size} bytes")
    print(f"  Reduction:      {reduction:.2f}%")

    return 0

if __name__ == "__main__":
    sys.exit(main())
