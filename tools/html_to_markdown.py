#!/usr/bin/env python3
"""
HTML to Markdown Converter

Converts HTML text or files into formatted Markdown. Leverages Python's built-in
html.parser library to ensure a standalone script without external dependencies.

Usage:
    python tools/html_to_markdown.py [input_file] [options]

Options:
    input_file          HTML file to convert (reads from stdin if omitted or '-')
    -o, --output        Output file to write Markdown (default: print to stdout)
    -g, --ignore-links  Ignore hyperlinks (convert to plain text)
    -i, --ignore-images Ignore image tags

Example:
    python tools/html_to_markdown.py index.html -o README.md
    echo "<h1>Hello World</h1><p>This is <b>bold</b>!</p>" | python tools/html_to_markdown.py
"""

import argparse
import sys
import os
from html.parser import HTMLParser
import re

class HTMLToMarkdownParser(HTMLParser):
    def __init__(self, ignore_links=False, ignore_images=False):
        super().__init__()
        self.ignore_links = ignore_links
        self.ignore_images = ignore_images
        
        # State tracking
        self.markdown = []
        self.tag_stack = []
        self.list_counters = [] # Stores current list type or numbered count
        self.href = None
        self.alt = None
        self.in_pre = False
        self.in_code = False
        self.in_blockquote = False
        self.newline_buffer = 0

    def add_text(self, text):
        if not text:
            return
        # If we are in code block (pre), preserve spaces and newlines
        if self.in_pre:
            self.markdown.append(text)
            self.newline_buffer = 0
            return
            
        # Clean up whitespace for ordinary text
        text = text.replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        # If we just had structural elements (like block elements), ensure newlines
        if self.newline_buffer > 0:
            self.markdown.append('\n' * self.newline_buffer)
            self.newline_buffer = 0
            
        self.markdown.append(text)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.tag_stack.append(tag)
        
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.newline_buffer = 2
            level = int(tag[1])
            self.add_text('#' * level + ' ')
            
        elif tag == 'p':
            self.newline_buffer = 2
            
        elif tag in ('b', 'strong'):
            self.markdown.append('**')
            
        elif tag in ('i', 'em'):
            self.markdown.append('*')
            
        elif tag == 'code':
            self.in_code = True
            if self.in_pre:
                pass # Already handled by pre
            else:
                self.markdown.append('`')
                
        elif tag == 'pre':
            self.in_pre = True
            self.newline_buffer = 2
            self.markdown.append('```\n')
            
        elif tag == 'blockquote':
            self.in_blockquote = True
            self.newline_buffer = 1
            self.markdown.append('> ')
            
        elif tag == 'a' and not self.ignore_links:
            self.href = attrs_dict.get('href', '')
            self.markdown.append('[')
            
        elif tag == 'img' and not self.ignore_images:
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', 'Image')
            self.markdown.append(f'![{alt}]({src})')
            
        elif tag == 'ul':
            self.list_counters.append('ul')
            self.newline_buffer = 1
            
        elif tag == 'ol':
            self.list_counters.append(1)
            self.newline_buffer = 1
            
        elif tag == 'li':
            # Compute indentation
            indent = '    ' * (len(self.list_counters) - 1)
            if self.list_counters:
                current_list = self.list_counters[-1]
                if current_list == 'ul':
                    prefix = '- '
                else:
                    prefix = f'{current_list}. '
                    self.list_counters[-1] += 1
            else:
                prefix = '- '
            
            self.newline_buffer = 1
            self.add_text(f'{indent}{prefix}')
            
        elif tag == 'br':
            self.markdown.append('\n')
            
        elif tag == 'hr':
            self.newline_buffer = 1
            self.add_text('---\n')
            self.newline_buffer = 1

    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'):
            self.newline_buffer = 2
            
        elif tag in ('b', 'strong'):
            self.markdown.append('**')
            
        elif tag in ('i', 'em'):
            self.markdown.append('*')
            
        elif tag == 'code':
            self.in_code = False
            if not self.in_pre:
                self.markdown.append('`')
                
        elif tag == 'pre':
            self.in_pre = False
            self.markdown.append('\n```')
            self.newline_buffer = 2
            
        elif tag == 'blockquote':
            self.in_blockquote = False
            self.newline_buffer = 2
            
        elif tag == 'a' and not self.ignore_links:
            if self.href:
                self.markdown.append(f']({self.href})')
            else:
                self.markdown.append(']')
            self.href = None
            
        elif tag in ('ul', 'ol'):
            if self.list_counters:
                self.list_counters.pop()
            self.newline_buffer = 2
            
        elif tag == 'li':
            self.newline_buffer = 1

    def handle_data(self, data):
        self.add_text(data)

    def get_markdown(self):
        result = ''.join(self.markdown)
        # Clean up excessive newlines
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

def main():
    parser = argparse.ArgumentParser(description="Convert HTML to Markdown")
    parser.add_argument('input_file', nargs='?', default='-', 
                        help="HTML file to parse (default or '-': read from stdin)")
    parser.add_argument('-o', '--output', help="Output file path for Markdown")
    parser.add_argument('-g', '--ignore-links', action='store_true', help="Convert hyperlinks to plain text")
    parser.add_argument('-i', '--ignore-images', action='store_true', help="Skip image conversion")
    
    args = parser.parse_args()
    
    # Read HTML content
    if args.input_file == '-':
        html_content = sys.stdin.read()
    else:
        if not os.path.exists(args.input_file):
            print(f"Error: File '{args.input_file}' not found.", file=sys.stderr)
            return 1
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            print(f"Error reading file '{args.input_file}': {e}", file=sys.stderr)
            return 1
            
    # Parse HTML
    parser = HTMLToMarkdownParser(ignore_links=args.ignore_links, ignore_images=args.ignore_images)
    try:
        parser.feed(html_content)
        parser.close()
    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)
        return 1
        
    markdown_out = parser.get_markdown()
    
    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_out + '\n')
            print(f"Success: HTML converted and saved to {args.output}")
        except Exception as e:
            print(f"Error writing output to '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(markdown_out)
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
