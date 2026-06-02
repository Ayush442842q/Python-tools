#!/usr/bin/env python3
"""
Markdown to HTML Converter

A simple command-line tool to convert Markdown files to standalone HTML.

Usage:
    python tools/markdown_to_html_converter.py input.md [-o output.html]
"""

import argparse
import sys
import re

def simple_markdown_to_html(md_text):
    # Very basic naive markdown parser for demonstration
    html = md_text
    # Headers
    html = re.sub(r'^### (.*)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*)', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    # Paragraphs (simplified)
    html = '<p>' + html.replace('\n\n', '</p>\n<p>') + '</p>'
    return f"<!DOCTYPE html>\n<html>\n<head>\n<title>Markdown Export</title>\n</head>\n<body>\n{html}\n</body>\n</html>"

def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to HTML")
    parser.add_argument('input', help='Input Markdown file')
    parser.add_argument('-o', '--output', help='Output HTML file', default=None)
    args = parser.parse_args()

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {args.input}")
        return 1

    html_content = simple_markdown_to_html(md_content)

    out_file = args.output if args.output else args.input.rsplit('.', 1)[0] + '.html'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Successfully converted {args.input} to {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
