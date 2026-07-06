#!/usr/bin/env python3
import os
import argparse
import sys
from html.parser import HTMLParser

# Simple ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

class DOMAnalyzer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.max_depth = 0
        self.current_depth = 0
        self.total_nodes = 0
        self.stack = []
        self.max_depth_stack = []
        
        # Payload size tracking
        self.inline_style_bytes = 0
        self.inline_script_bytes = 0
        self.svg_elements_count = 0
        self.svg_data_bytes = 0
        self.in_style = False
        self.in_script = False
        self.in_svg = False
        self.deep_nodes = [] # tuples of (line, path, depth)
        
        # Deep element threshold
        self.depth_threshold = 20

    def handle_starttag(self, tag, attrs):
        self.current_depth += 1
        self.total_nodes += 1
        self.stack.append(tag)
        
        # Track maximum depth
        if self.current_depth > self.max_depth:
            self.max_depth = self.current_depth
            self.max_depth_stack = list(self.stack)

        # Track special tag contexts
        if tag == "style":
            self.in_style = True
        elif tag == "script":
            self.in_script = True
        elif tag == "svg":
            self.in_svg = True
            self.svg_elements_count += 1

        # Track attributes payload (e.g. inline style attributes)
        for attr, val in attrs:
            if attr == "style" and val:
                self.inline_style_bytes += len(val)

        # Record deep nodes exceeding threshold
        if self.current_depth >= self.depth_threshold:
            self.deep_nodes.append((self.getpos()[0], " > ".join(self.stack), self.current_depth))

    def handle_endtag(self, tag):
        # Gracefully handle mismatching closing tags by popping if present
        if tag in self.stack:
            while self.stack:
                popped = self.stack.pop()
                self.current_depth -= 1
                if popped == tag:
                    break
        
        if tag == "style":
            self.in_style = False
        elif tag == "script":
            self.in_script = False
        elif tag == "svg":
            self.in_svg = False

    def handle_data(self, data):
        # Accumulate inline script/style/svg payload byte sizes
        size = len(data)
        if self.in_style:
            self.inline_style_bytes += size
        elif self.in_script:
            self.inline_script_bytes += size
        elif self.in_svg:
            self.svg_data_bytes += size

def analyze_html_file(file_path, threshold=20, verbose=False):
    """
    Reads and parses HTML file, returning DOMAnalyzer instance or None.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
        return None

    analyzer = DOMAnalyzer()
    analyzer.depth_threshold = threshold
    try:
        analyzer.feed(content)
        analyzer.close()
    except Exception as e:
        if verbose:
            print(f"{COLOR_YELLOW}Warning: HTML Parser encountered an exception on {file_path}: {e}{COLOR_RESET}")
    
    return analyzer

def print_report(file_path, analyzer, verbose=False):
    if not analyzer or analyzer.total_nodes == 0:
        print(f"{COLOR_YELLOW}No HTML DOM tags found in {file_path}.{COLOR_RESET}")
        return

    print(f"\n{COLOR_CYAN}{COLOR_BOLD}HTML DOM Report: {file_path}{COLOR_RESET}")
    print(f"  {COLOR_BOLD}Total DOM Nodes:{COLOR_RESET} {analyzer.total_nodes}")
    
    depth_color = COLOR_GREEN
    if analyzer.max_depth >= 32:
        depth_color = COLOR_RED
    elif analyzer.max_depth >= 20:
        depth_color = COLOR_YELLOW
        
    print(f"  {COLOR_BOLD}Max DOM Depth:{COLOR_RESET} {depth_color}{analyzer.max_depth}{COLOR_RESET} (threshold: {analyzer.depth_threshold})")
    
    if analyzer.max_depth_stack:
        path = " > ".join(analyzer.max_depth_stack)
        print(f"    {COLOR_BLUE}Deepest Path:{COLOR_RESET} {path}")
        
    print(f"  {COLOR_BOLD}Payload Breakdown:{COLOR_RESET}")
    print(f"    - Inline Style Bytes: {analyzer.inline_style_bytes} bytes")
    print(f"    - Inline Script Bytes: {analyzer.inline_script_bytes} bytes")
    print(f"    - SVG Elements: {analyzer.svg_elements_count} ({analyzer.svg_data_bytes} inline bytes)")
    
    # Recommendations
    recs = []
    if analyzer.max_depth >= 32:
        recs.append("- Critical: Max DOM depth exceeds 32. This can cause poor rendering performance (Lighthouse warning). Flatten nested elements.")
    elif analyzer.max_depth >= 20:
        recs.append("- Warning: Max DOM depth is over 20. Look for repetitive structures that can be flattened.")
        
    if analyzer.inline_style_bytes > 5000:
        recs.append("- Recommendation: Large volume of inline styles (>5KB). Extract styles into external stylesheet or classes.")
        
    if analyzer.inline_script_bytes > 10000:
        recs.append("- Recommendation: Large volume of inline JS (>10KB). Extract scripts into external .js files to leverage browser caching.")
        
    if analyzer.svg_data_bytes > 20000:
        recs.append("- Recommendation: Heavy inline SVG vectors (>20KB). Consider moving static SVGs to separate files or image components.")

    if recs:
        print(f"  {COLOR_YELLOW}{COLOR_BOLD}Optimization Recommendations:{COLOR_RESET}")
        for rec in recs:
            print(f"    {rec}")
            
    if verbose and analyzer.deep_nodes:
        print(f"  {COLOR_BOLD}Deep Elements (>= {analyzer.depth_threshold} levels):{COLOR_RESET}")
        # Print top 10 deepest nodes
        sorted_nodes = sorted(analyzer.deep_nodes, key=lambda x: x[2], reverse=True)[:10]
        for line, path, depth in sorted_nodes:
            print(f"    Line {line}: [Depth {depth}] {path}")

def main():
    parser = argparse.ArgumentParser(
        description="Statically analyze HTML files to measure DOM complexity, depth, and inline payloads."
    )
    parser.add_argument("path", help="Path to an HTML file or directory to scan")
    parser.add_argument(
        "-t", "--threshold", 
        type=int, 
        default=20, 
        help="DOM depth threshold warning level (default: 20)"
    )
    parser.add_argument(
        "-e", "--extensions", 
        default="html,htm,xhtml", 
        help="Comma-separated file extensions to scan (default: html,htm,xhtml)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed deep node lists")
    args = parser.parse_args()

    extensions = [f".{ext.strip().lower()}" for ext in args.extensions.split(",")]
    
    if not os.path.exists(args.path):
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting HTML DOM Depth & Payload Analyzer...{COLOR_RESET}")
    print("-" * 65)

    if os.path.isfile(args.path):
        analyzer = analyze_html_file(args.path, args.threshold, args.verbose)
        print_report(args.path, analyzer, args.verbose)
    else:
        for root, _, files in os.walk(args.path):
            if "node_modules" in root or ".git" in root:
                continue
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() in extensions:
                    analyzer = analyze_html_file(os.path.join(root, file), args.threshold, args.verbose)
                    if analyzer:
                        print_report(os.path.join(root, file), analyzer, args.verbose)

    print("-" * 65)
    print(f"{COLOR_GREEN}Analysis complete.{COLOR_RESET}")

if __name__ == "__main__":
    main()
