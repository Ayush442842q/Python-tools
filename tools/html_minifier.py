#!/usr/bin/env python3
"""
HTML Minifier

Minifies HTML files by removing whitespace, comments, and line breaks.
Preserves formatting inside tags like <pre>, <textarea>, <script>, and <style>
using placeholder substitution.

Usage:
    python tools/html_minifier.py -i index.html -o index.min.html
    python tools/html_minifier.py -i index.html --keep-comments
    cat index.html | python tools/html_minifier.py --aggressive
"""

import argparse
import os
import re
import sys

def minify_html(html_content, keep_comments=False, aggressive=False):
    """
    Minifies HTML content by removing comments and collapsing whitespace.
    Protects contents of <pre>, <textarea>, <script>, and <style> tags.
    """
    placeholders = []
    
    # Regex to find tags whose contents must be preserved
    preserve_patterns = [
        r'<pre[^>]*?>.*?</pre>',
        r'<textarea[^>]*?>.*?</textarea>',
        r'<script[^>]*?>.*?</script>',
        r'<style[^>]*?>.*?</style>'
    ]
    
    # Combine preserve patterns
    combined_preserve_re = re.compile('|'.join(preserve_patterns), re.DOTALL | re.IGNORECASE)
    
    def preserve_callback(match):
        placeholder = f"___PRESERVE_PLACEHOLDER_{len(placeholders)}___"
        placeholders.append(match.group(0))
        return placeholder

    # 1. Temporarily replace preserved tags with placeholders
    processed_html = combined_preserve_re.sub(preserve_callback, html_content)

    # 2. Handle HTML comments if we are not keeping them
    if not keep_comments:
        # Regex to match HTML comments, excluding conditional comments
        # Conditional comments: <!--[if ...]> ... <![endif]-->
        # We strip normal comments <!-- ... -->
        comment_re = re.compile(r'<!--(?!\[if ).*?-->', re.DOTALL)
        processed_html = comment_re.sub('', processed_html)

    # 3. Collapse/minify whitespace
    if aggressive:
        # Aggressive mode: Collapse all whitespace to a single space, then remove spaces between tags
        # Collapse multiple whitespaces (including newlines) into a single space
        processed_html = re.sub(r'\s+', ' ', processed_html)
        # Remove whitespace between tags (e.g. "> <" becomes "><")
        # Note: This can sometimes affect inline formatting, hence 'aggressive' flag
        processed_html = re.sub(r'>\s+<', '><', processed_html)
        processed_html = re.sub(r'^\s+<', '<', processed_html)
        processed_html = re.sub(r'>\s+$', '>', processed_html)
    else:
        # Standard mode: Safe whitespace collapsing
        # Collapse whitespace to a single space
        processed_html = re.sub(r'\s+', ' ', processed_html)
        # Strip leading/trailing whitespace of the overall content
        processed_html = processed_html.strip()

    # 4. Restore preserved tags
    for i, original_content in enumerate(placeholders):
        placeholder = f"___PRESERVE_PLACEHOLDER_{i}___"
        processed_html = processed_html.replace(placeholder, original_content)

    return processed_html

def main():
    parser = argparse.ArgumentParser(
        description="HTML Minifier - Minify HTML code by stripping comments and reducing spacing."
    )
    parser.add_argument(
        '-i', '--input',
        help='Path to the input HTML file. If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-o', '--output',
        help='Path to save the minified HTML. If omitted, prints to console.'
    )
    parser.add_argument(
        '--keep-comments',
        action='store_true',
        help='Preserve HTML comments (removed by default)'
    )
    parser.add_argument(
        '--aggressive',
        action='store_true',
        help='Aggressive minification: removes whitespace between adjacent HTML tags'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for files (default: utf-8)'
    )

    args = parser.parse_args()

    # Read HTML content
    if args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', encoding=args.encoding, errors='replace') as f:
                html_content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            html_content = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not html_content.strip():
        print("[ERROR] Input HTML content is empty.", file=sys.stderr)
        return 1

    # Perform minification
    minified = minify_html(html_content, keep_comments=args.keep_comments, aggressive=args.aggressive)

    # Save or print output
    if args.output:
        try:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(minified)
            # Compare sizes
            original_size = len(html_content.encode(args.encoding, errors='replace'))
            minified_size = len(minified.encode(args.encoding, errors='replace'))
            reduction = ((original_size - minified_size) / original_size) * 100 if original_size > 0 else 0
            print(f"[OK] HTML minified successfully and written to '{args.output}'.")
            print(f"     Size reduction: {original_size} bytes -> {minified_size} bytes ({reduction:.2f}% decrease)")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        # Print to console
        print(minified)

    return 0

if __name__ == '__main__':
    sys.exit(main())
