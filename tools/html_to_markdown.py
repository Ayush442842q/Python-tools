#!/usr/bin/env python3
"""
HTML to Markdown Converter

A standalone utility to convert HTML documents or fragments into clean, 
standard Markdown format using Python's built-in html.parser.

Usage:
    python tools/html_to_markdown.py [options] [html_file]

Examples:
    python tools/html_to_markdown.py index.html
    python tools/html_to_markdown.py --ignore-links page.html -o page.md
    curl -s https://example.com | python tools/html_to_markdown.py > example.md
"""

import argparse
import html
import sys
from html.parser import HTMLParser
from pathlib import Path

class HTMLToMarkdownParser(HTMLParser):
    def __init__(self, ignore_links=False, ignore_images=False):
        super().__init__()
        self.ignore_links = ignore_links
        self.ignore_images = ignore_images
        
        # Output accumulation
        self.markdown_parts = []
        
        # Parser state
        self.tag_stack = []
        self.list_state = []  # Stack of dicts: {'type': 'ul'/'ol', 'index': int}
        self.current_link = None
        self.in_pre = False
        self.in_style_or_script = False
        
        # Buffer to aggregate inline content to avoid unnecessary spacing issues
        self.inline_buffer = []
        
        # Table parsing state
        self.table_data = []  # List of rows, each is list of cell texts
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_th = False

    def flush_buffer(self):
        """Append inline buffer content to the main markdown output."""
        if self.inline_buffer:
            text = "".join(self.inline_buffer)
            self.markdown_parts.append(text)
            self.inline_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()
        self.tag_stack.append(tag_lower)
        
        if tag_lower in ('style', 'script', 'head', 'meta', 'link'):
            self.in_style_or_script = True
            return
            
        if self.in_style_or_script:
            return

        # Handle block-level tags by flushing previous buffer
        if tag_lower in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'pre', 'blockquote', 'hr', 'table', 'tr', 'div'):
            self.flush_buffer()

        if tag_lower == 'pre':
            self.in_pre = True
            self.markdown_parts.append("\n```\n")
            
        elif tag_lower == 'code':
            if not self.in_pre:
                self.inline_buffer.append("`")
                
        elif tag_lower in ('strong', 'b'):
            self.inline_buffer.append("**")
            
        elif tag_lower in ('em', 'i'):
            self.inline_buffer.append("*")
            
        elif tag_lower == 'blockquote':
            self.markdown_parts.append("\n> ")
            
        elif tag_lower == 'a':
            href = attrs_dict.get('href', '')
            if href and not self.ignore_links:
                self.current_link = href
                self.inline_buffer.append("[")
                
        elif tag_lower == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', 'Image')
            if src and not self.ignore_images:
                self.flush_buffer()
                self.markdown_parts.append(f"\n![{alt}]({src})\n")
                
        elif tag_lower == 'hr':
            self.markdown_parts.append("\n---\n")
            
        elif tag_lower == 'ul':
            self.list_state.append({'type': 'ul', 'index': 0})
            self.markdown_parts.append("\n")
            
        elif tag_lower == 'ol':
            self.list_state.append({'type': 'ol', 'index': 1})
            self.markdown_parts.append("\n")
            
        elif tag_lower == 'li':
            indent = "  " * (len(self.list_state) - 1)
            if self.list_state:
                lst = self.list_state[-1]
                if lst['type'] == 'ul':
                    self.markdown_parts.append(f"{indent}- ")
                else:
                    self.markdown_parts.append(f"{indent}{lst['index']}. ")
                    lst['index'] += 1
            else:
                self.markdown_parts.append("- ")
                
        elif tag_lower == 'table':
            self.in_table = True
            self.table_data = []
            
        elif tag_lower == 'tr':
            self.current_row = []
            
        elif tag_lower in ('td', 'th'):
            self.current_cell = []
            self.in_th = (tag_lower == 'th')

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        
        # Pop from stack
        if self.tag_stack and self.tag_stack[-1] == tag_lower:
            self.tag_stack.pop()
            
        if tag_lower in ('style', 'script', 'head', 'meta', 'link'):
            self.in_style_or_script = False
            return
            
        if self.in_style_or_script:
            return

        if tag_lower == 'pre':
            self.flush_buffer()
            self.in_pre = False
            # Strip trailing newline inside markdown block before closing
            if self.markdown_parts and self.markdown_parts[-1].endswith('\n'):
                self.markdown_parts[-1] = self.markdown_parts[-1][:-1]
            self.markdown_parts.append("\n```\n")
            
        elif tag_lower == 'code':
            if not self.in_pre:
                self.inline_buffer.append("`")
                
        elif tag_lower in ('strong', 'b'):
            self.inline_buffer.append("**")
            
        elif tag_lower in ('em', 'i'):
            self.inline_buffer.append("*")
            
        elif tag_lower == 'a':
            if self.current_link and not self.ignore_links:
                self.inline_buffer.append(f"]({self.current_link})")
                self.current_link = None
                
        elif tag_lower == 'p':
            self.flush_buffer()
            self.markdown_parts.append("\n\n")
            
        elif tag_lower in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.flush_buffer()
            level = int(tag_lower[1])
            header_text = self.markdown_parts.pop() if self.markdown_parts else ""
            self.markdown_parts.append(f"\n{'#' * level} {header_text.strip()}\n\n")
            
        elif tag_lower in ('ul', 'ol'):
            if self.list_state:
                self.list_state.pop()
            self.flush_buffer()
            self.markdown_parts.append("\n")
            
        elif tag_lower == 'li':
            self.flush_buffer()
            self.markdown_parts.append("\n")
            
        elif tag_lower == 'blockquote':
            self.flush_buffer()
            self.markdown_parts.append("\n\n")
            
        elif tag_lower in ('td', 'th'):
            cell_text = "".join(self.current_cell).strip().replace('\n', ' ')
            self.current_row.append((cell_text, self.in_th))
            self.in_th = False
            
        elif tag_lower == 'tr':
            if self.current_row:
                self.table_data.append(self.current_row)
                
        elif tag_lower == 'table':
            self.in_table = False
            self.render_table()

    def handle_data(self, data):
        if self.in_style_or_script:
            return
            
        if self.in_table:
            # We are inside td or th
            if self.tag_stack and self.tag_stack[-1] in ('td', 'th'):
                self.current_cell.append(data)
            return

        if self.in_pre:
            self.markdown_parts.append(data)
        else:
            # Normalize whitespace outside pre blocks
            clean_data = data if self.tag_stack and self.tag_stack[-1] == 'code' else ' '.join(data.split())
            if clean_data:
                # Add spaces if necessary to avoid slamming inline tags together
                if data.startswith(' ') and self.inline_buffer and not self.inline_buffer[-1].endswith(' '):
                    self.inline_buffer.append(' ')
                self.inline_buffer.append(html.unescape(clean_data))
                if data.endswith(' '):
                    self.inline_buffer.append(' ')

    def render_table(self):
        """Format the parsed table details as a Markdown table."""
        if not self.table_data:
            return
            
        self.flush_buffer()
        self.markdown_parts.append("\n")
        
        # Determine number of columns
        max_cols = max(len(row) for row in self.table_data)
        
        # Setup column alignments and widths
        widths = [0] * max_cols
        for row in self.table_data:
            for idx, cell in enumerate(row):
                widths[idx] = max(widths[idx], len(cell[0]))
                
        # Fill table rows
        for r_idx, row in enumerate(self.table_data):
            row_str = "|"
            for c_idx in range(max_cols):
                val = row[c_idx][0] if c_idx < len(row) else ""
                w = max(widths[c_idx], 3)
                row_str += f" {val.ljust(w)} |"
            self.markdown_parts.append(row_str + "\n")
            
            # Print alignment separator line after first row (headers)
            if r_idx == 0:
                sep_str = "|"
                for c_idx in range(max_cols):
                    w = max(widths[c_idx], 3)
                    sep_str += f" {'-' * w} |"
                self.markdown_parts.append(sep_str + "\n")
                
        self.markdown_parts.append("\n")

    def get_markdown(self):
        self.flush_buffer()
        raw_md = "".join(self.markdown_parts)
        
        # Post-process cleanup of empty lines and excessive spaces
        lines = raw_md.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_lines.append(line.rstrip())
            
        result = "\n".join(cleaned_lines)
        # Collapse multiple empty lines (max 2 consecutive empty lines)
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")
            
        return result.strip() + "\n"

def main():
    parser = argparse.ArgumentParser(
        description="Convert HTML documents or snippets to clean Markdown format."
    )
    parser.add_argument(
        'html_file',
        nargs='?',
        help='Path to the HTML file. If omitted, reads from standard input.'
    )
    parser.add_argument(
        '-o', '--output',
        help='Write Markdown output to a file instead of stdout'
    )
    parser.add_argument(
        '--ignore-links',
        action='store_true',
        help='Convert hyperlinks into plain text (removes href references)'
    )
    parser.add_argument(
        '--ignore-images',
        action='store_true',
        help='Ignore image tags completely'
    )
    
    args = parser.parse_args()
    
    # Read HTML content
    html_content = ""
    if args.html_file:
        try:
            with open(args.html_file, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
        except Exception as e:
            print(f"Error reading HTML file '{args.html_file}': {e}", file=sys.stderr)
            return 1
    else:
        # Check if stdin is a TTY (user did not pipe anything)
        if sys.stdin.isatty():
            print("Error: No input HTML file provided, and standard input is empty.", file=sys.stderr)
            parser.print_help()
            return 1
        html_content = sys.stdin.read()
        
    # Parse HTML
    parser_instance = HTMLToMarkdownParser(
        ignore_links=args.ignore_links,
        ignore_images=args.ignore_images
    )
    try:
        parser_instance.feed(html_content)
        parser_instance.close()
        markdown_output = parser_instance.get_markdown()
    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)
        return 1
        
    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_output)
            print(f"Markdown successfully saved to {args.output}")
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(markdown_output, end="")
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
