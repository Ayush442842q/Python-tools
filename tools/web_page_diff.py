#!/usr/bin/env python3
"""
Web Page Content Diff Tool
Fetches and compares the text or HTML content of two URLs or local HTML files.
Supports side-by-side terminal diff or generating an interactive HTML diff report.
"""

import argparse
import difflib
import os
import re
import sys
import urllib.request
from typing import List, Tuple
from html.parser import HTMLParser

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"

class TextExtractor(HTMLParser):
    """Parses HTML and extracts visible text content."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_ignored_tag = False
        self.ignored_tags = {'script', 'style', 'head', 'meta', 'link', 'noscript'}

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.in_ignored_tag = True

    def handle_endtag(self, tag):
        if tag in self.ignored_tags:
            self.in_ignored_tag = False

    def handle_data(self, data):
        if not self.in_ignored_tag:
            clean_data = data.strip()
            if clean_data:
                self.text.append(clean_data)

    def get_text(self) -> str:
        return "\n".join(self.text)

def fetch_content(source: str) -> str:
    """Fetches content from a URL or reads it from a local file."""
    if source.startswith("http://") or source.startswith("https://"):
        try:
            req = urllib.request.Request(
                source, 
                headers={'User-Agent': 'Web-Page-Diff-Tool/1.0 (Python Utility)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                charset = response.info().get_content_charset() or 'utf-8'
                return response.read().decode(charset, errors='replace')
        except Exception as e:
            print(f"{COLOR_RED}Error fetching URL '{source}': {e}{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        if not os.path.exists(source):
            print(f"{COLOR_RED}Error: File '{source}' does not exist.{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(source, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            print(f"{COLOR_RED}Error reading file '{source}': {e}{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)

def get_clean_text(html: str) -> List[str]:
    """Extracts visible text from HTML and returns it as a list of lines."""
    extractor = TextExtractor()
    extractor.feed(html)
    text = extractor.get_text()
    # Normalize multiple newlines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines

def main():
    parser = argparse.ArgumentParser(description="Fetch and compare content from two URLs or local HTML files.")
    parser.add_argument("source1", help="URL or path to first HTML file")
    parser.add_argument("source2", help="URL or path to second HTML file")
    parser.add_argument("-r", "--raw", action="store_true", help="Compare raw HTML instead of extracted text")
    parser.add_argument("-o", "--html-output", help="Path to write a visual HTML diff report")
    parser.add_argument("-c", "--context", type=int, default=3, help="Number of context lines to show around changes")
    
    args = parser.parse_args()
    
    print(f"{COLOR_CYAN}Loading Source 1: {args.source1}...{COLOR_RESET}")
    content1 = fetch_content(args.source1)
    print(f"{COLOR_CYAN}Loading Source 2: {args.source2}...{COLOR_RESET}")
    content2 = fetch_content(args.source2)
    
    if args.raw:
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        mode_desc = "Raw HTML"
    else:
        lines1 = get_clean_text(content1)
        lines2 = get_clean_text(content2)
        mode_desc = "Extracted Text"
        
    print(f"\n{COLOR_BOLD}Comparing contents ({mode_desc})...{COLOR_RESET}\n")
    
    if args.html_output:
        # Generate visual HTML diff report using difflib.HtmlDiff
        differ = difflib.HtmlDiff()
        html_diff = differ.make_file(
            lines1, 
            lines2, 
            fromdesc=args.source1, 
            todesc=args.source2,
            context=True,
            numlines=args.context
        )
        try:
            with open(args.html_output, 'w', encoding='utf-8') as f:
                f.write(html_diff)
            print(f"{COLOR_GREEN}✔ HTML diff report written to {args.html_output}{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error writing HTML report: {e}{COLOR_RESET}", file=sys.stderr)
    else:
        # Generate terminal-based unified diff
        diff = list(difflib.unified_diff(
            lines1, 
            lines2, 
            fromfile=args.source1, 
            tofile=args.source2,
            n=args.context,
            lineterm=''
        ))
        
        if not diff:
            print(f"{COLOR_GREEN}✔ Sources are identical ({mode_desc}).{COLOR_RESET}")
            return
            
        for line in diff:
            if line.startswith('+++') or line.startswith('---'):
                print(f"{COLOR_BOLD}{line}{COLOR_RESET}")
            elif line.startswith('@@'):
                print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
            elif line.startswith('+'):
                print(f"{COLOR_GREEN}{line}{COLOR_RESET}")
            elif line.startswith('-'):
                print(f"{COLOR_RED}{line}{COLOR_RESET}")
            else:
                print(line)

if __name__ == "__main__":
    main()
