#!/usr/bin/env python3
"""
Markdown to Plain Text Converter - Strips Markdown syntax to produce clean, readable plain text.
"""

import sys
import re
import argparse

def remove_markdown(markdown_text, keep_urls=False, exclude_code=False):
    """
    Strip markdown formatting from text.
    """
    text = markdown_text
    
    # 1. Handle code blocks
    if exclude_code:
        # Remove code blocks entirely
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`\n]+`', '', text)
    else:
        # Just strip code block markers
        text = re.sub(r'```[a-zA-Z0-9_-]*\n([\s\S]*?)```', r'\1', text)
        text = re.sub(r'`([^`\n]+)`', r'\1', text)

    # 2. Blockquotes
    text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)

    # 3. HTML tags (like <kbd>, <a>, etc.)
    text = re.sub(r'<[^>]*>', '', text)

    # 4. Headers: convert '# Header' to 'Header'
    text = re.sub(r'^#+\s+(.*?)\s*#*$', r'\1', text, flags=re.MULTILINE)

    # 5. Images: remove ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)

    # 6. Links: convert [text](url) to 'text' or 'text (url)'
    if keep_urls:
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    else:
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)

    # 7. Inline formatting: Bold, Italic, Strikethrough
    # **bold** and __bold__
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    # *italic* and _italic_
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # ~~strikethrough~~
    text = re.sub(r'(~~)(.*?)\1', r'\2', text)

    # 8. Tables
    # Remove table divider lines (e.g. |---|---|)
    text = re.sub(r'^\s*\|?\s*:?-+:?\s*\|(?:\s*:?-+:?\s*\|)*\s*$', '', text, flags=re.MULTILINE)
    # Strip table boundary pipes
    text = re.sub(r'^\s*\|\s*(.*?)\s*\|\s*$', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'\s*\|\s*', '  ', text)

    # 9. List items (ordered and unordered)
    # Unordered list markers (*, -, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Ordered list markers (1., 2.)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # 10. Horizontal rules (---, ***, ___)
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Clean up empty lines / multiple spacing
    lines = [line.rstrip() for line in text.split('\n')]
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append('')
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
            
    return '\n'.join(cleaned_lines).strip()

def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown files to clean, readable plain text."
    )
    parser.add_argument('input_file', nargs='?', help="Path to the Markdown file. Reads from stdin if not specified.")
    parser.add_argument('-o', '--output', help="Path to write the plain text output. Prints to stdout if not specified.")
    parser.add_argument('--keep-urls', action='store_true', help="Keep URLs next to link text in the output.")
    parser.add_argument('--exclude-code', action='store_true', help="Completely remove code blocks from the text.")
    
    args = parser.parse_args()
    
    # Read content
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.input_file}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            parser.print_help()
            return
        content = sys.stdin.read()
        
    plain_text = remove_markdown(content, keep_urls=args.keep_urls, exclude_code=args.exclude_code)
    
    # Write content
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(plain_text + '\n')
            print(f"Plain text successfully written to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(plain_text)

if __name__ == '__main__':
    main()
