#!/usr/bin/env python3
"""
HTML Semantic Outline & Heading Auditor - Analyze HTML document hierarchy for SEO and accessibility.
"""

import sys
import argparse
from html.parser import HTMLParser
import urllib.request
import urllib.error

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'cyan': '\033[96m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

class SemanticOutlineParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.outline = []  # List of dicts representing outline nodes
        self.warnings = []
        self.current_tag = None
        self.current_data = []
        self.h1_count = 0
        
        # Track active semantic containers
        self.container_stack = []
        
        # Tags we care about
        self.semantic_containers = {'header', 'nav', 'main', 'section', 'article', 'aside', 'footer'}
        self.headings = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        self.current_data = []
        
        if tag in self.semantic_containers:
            self.container_stack.append(tag)
            # Add container entry to the outline
            self.outline.append({
                'type': 'container',
                'name': tag,
                'attrs': dict(attrs),
                'depth': len(self.container_stack) - 1
            })
            
        elif tag in self.headings:
            # We will capture heading text in handle_data and endtag
            pass

    def handle_data(self, data):
        if self.current_tag in self.headings:
            self.current_data.append(data)

    def handle_endtag(self, tag):
        if tag in self.semantic_containers:
            if self.container_stack and self.container_stack[-1] == tag:
                self.container_stack.pop()
                
        elif tag in self.headings:
            level = int(tag[1])
            heading_text = "".join(self.current_data).strip()
            
            if tag == 'h1':
                self.h1_count += 1
                
            self.outline.append({
                'type': 'heading',
                'level': level,
                'text': heading_text or "[Empty Heading]",
                'containers': list(self.container_stack)
            })
            
        if self.current_tag == tag:
            self.current_tag = None

    def get_audit_report(self):
        warnings = []
        
        # 1. H1 Count check
        if self.h1_count == 0:
            warnings.append({
                'level': 'error',
                'msg': "Missing H1 heading. A single H1 tag is recommended for proper page hierarchy and SEO."
            })
        elif self.h1_count > 1:
            warnings.append({
                'level': 'warning',
                'msg': f"Multiple H1 headings detected ({self.h1_count} found). While HTML5 permits this inside nested sections, standard SEO practices recommend a single H1 per page."
            })
            
        # 2. Heading level skips check
        last_level = 0
        for node in self.outline:
            if node['type'] == 'heading':
                curr_level = node['level']
                if last_level > 0 and curr_level > last_level + 1:
                    warnings.append({
                        'level': 'warning',
                        'msg': f"Heading skip detected: H{last_level} followed directly by H{curr_level} (text: '{node['text']}')"
                    })
                last_level = curr_level
                
                # Check for empty headings
                if node['text'] == "[Empty Heading]":
                    warnings.append({
                        'level': 'error',
                        'msg': f"Empty heading tag <{tag}> found."
                    })
                    
        # 3. Check for main semantic tags usage
        outline_types = [node['name'] for node in self.outline if node['type'] == 'container']
        if 'main' not in outline_types:
            warnings.append({
                'level': 'warning',
                'msg': "Missing <main> tag. Pages should contain a <main> element indicating the central page content."
            })
        if 'nav' not in outline_types:
            warnings.append({
                'level': 'info',
                'msg': "No <nav> tag found. Navigation sections should typically be wrapped in a <nav> container."
            })
            
        return warnings

def print_outline(outline, colors):
    print(f"\n{colors['bold']}{colors['blue']}=== Page Semantic Outline ==={colors['reset']}")
    
    # Calculate indent base
    for node in outline:
        if node['type'] == 'container':
            indent = "  " * node['depth']
            tag_name = node['name']
            cls = node['attrs'].get('class', '')
            id_val = node['attrs'].get('id', '')
            details = f"class='{cls}'" if cls else ""
            details += f" id='{id_val}'" if id_val else ""
            details = f" ({details.strip()})" if details else ""
            
            print(f"{indent}{colors['cyan']}<{tag_name}>{colors['reset']}{details}")
            
        elif node['type'] == 'heading':
            level = node['level']
            # Headings get indented based on their level + nesting depth
            indent = "  " * (level - 1)
            marker = f"H{level}:"
            
            # Highlight headings based on level
            col = colors['green'] if level <= 2 else colors['yellow']
            print(f"{indent}{colors['bold']}{col}{marker}{colors['reset']} {node['text']}")

def main():
    parser = argparse.ArgumentParser(
        description="HTML Semantic Outline & Heading Auditor - Parse local/remote HTML files and audit structure."
    )
    parser.add_argument("source", help="Path to local HTML file, URL (http/https), or '-' for stdin")
    parser.add_argument("--only-headings", action="store_true", help="Display headings only, exclude semantic containers")
    parser.add_argument("--only-warnings", action="store_true", help="Display audit warnings only")
    
    args = parser.parse_args()
    
    colors = {
        'red': get_color('red'),
        'green': get_color('green'),
        'yellow': get_color('yellow'),
        'blue': get_color('blue'),
        'bold': get_color('bold'),
        'cyan': get_color('cyan'),
        'reset': get_color('reset')
    }
    
    html_content = ""
    source = args.source
    
    try:
        if source == "-":
            html_content = sys.stdin.read()
        elif source.startswith("http://") or source.startswith("https://"):
            print(f"Fetching remote URL: {source}...", file=sys.stderr)
            req = urllib.request.Request(
                source, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) HTML-Auditor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
        else:
            with open(source, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()
    except Exception as e:
        print(f"{colors['red']}Error reading source '{source}': {e}{colors['reset']}", file=sys.stderr)
        sys.exit(1)
        
    # Run Parser
    parser_inst = SemanticOutlineParser()
    parser_inst.feed(html_content)
    
    # Filter outline if only-headings was requested
    outline = parser_inst.outline
    if args.only_headings:
        outline = [node for node in outline if node['type'] == 'heading']
        
    if not args.only_warnings:
        print_outline(outline, colors)
        
    # Get and print audit warnings
    warnings = parser_inst.get_audit_report()
    
    print(f"\n{colors['bold']}{colors['blue']}=== Structure & Accessibility Audit ==={colors['reset']}")
    if not warnings:
        print(f"{colors['green']}✔ Page structure looks excellent! No warnings or errors found.{colors['reset']}")
    else:
        errors = 0
        warns = 0
        infos = 0
        for w in warnings:
            if w['level'] == 'error':
                prefix = f"[{colors['red']}ERROR{colors['reset']}]"
                errors += 1
            elif w['level'] == 'warning':
                prefix = f"[{colors['yellow']}WARN {colors['reset']}]"
                warns += 1
            else:
                prefix = f"[{colors['cyan']}INFO {colors['reset']}]"
                infos += 1
                
            print(f" {prefix} {w['msg']}")
            
        print(f"\nSummary: {colors['red'] if errors else colors['green']}{errors} error(s){colors['reset']}, "
              f"{colors['yellow'] if warns else colors['reset']}{warns} warning(s){colors['reset']}, {infos} info(s)")

if __name__ == '__main__':
    main()
