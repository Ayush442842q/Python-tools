#!/usr/bin/env python3
"""
Web Content Extractor (Reader Mode) - Extract main article text content from webpages

This tool downloads a webpage from a URL and extracts its core content (headlines,
paragraphs, lists, and code blocks) while stripping away advertisements, sidebars,
navigation menus, and footers. It uses heuristics similar to Readability.js.

Usage:
    python tools/web_content_extractor.py [URL] [--format {markdown,text,json}] [--output FILE]

Example:
    python tools/web_content_extractor.py https://example.com/blog-post --format markdown
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional, Tuple

class DOMNode:
    def __init__(self, tag: str, attrs: List[Tuple[str, str]], parent: Optional['DOMNode'] = None):
        self.tag = tag.lower()
        self.attrs = {k.lower(): v for k, v in attrs if v is not None}
        self.parent = parent
        self.children: List['DOMNode'] = []
        self.text_list: List[str] = []
        self.score = 0.0

    @property
    def text(self) -> str:
        return "".join(self.text_list).strip()

    @property
    def full_text(self) -> str:
        """Returns combined text of this node and all descendants."""
        result = []
        if self.text_list:
            result.append("".join(self.text_list))
        for child in self.children:
            result.append(child.full_text)
        return " ".join("".join(result).split())

    def get_attr_string(self) -> str:
        """Combines class and ID names for scoring lookup."""
        elements = []
        if 'class' in self.attrs:
            elements.append(self.attrs['class'])
        if 'id' in self.attrs:
            elements.append(self.attrs['id'])
        return " ".join(elements).lower()

class DOMBuilder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = DOMNode('root', [])
        self.current = self.root
        self.ignored_tags = {'script', 'style', 'noscript', 'iframe', 'svg', 'canvas', 'form', 'select', 'button'}

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.ignored_tags:
            # Create a placeholder dummy node that won't collect text or be traversed
            node = DOMNode(tag, attrs, self.current)
            self.current.children.append(node)
            self.current = node
            return
            
        node = DOMNode(tag, attrs, self.current)
        self.current.children.append(node)
        self.current = node

    def handle_endtag(self, tag):
        if self.current.parent:
            self.current = self.current.parent

    def handle_data(self, data):
        # Only record data if not in ignored tags
        curr = self.current
        ignored = False
        while curr:
            if curr.tag in self.ignored_tags:
                ignored = True
                break
            curr = curr.parent
            
        if not ignored:
            self.current.text_list.append(data)

def calculate_link_density(node: DOMNode) -> float:
    """Calculates the ratio of text inside links to total text in the element."""
    text_len = len(node.full_text)
    if text_len == 0:
        return 0.0
        
    link_text_len = 0
    # Walk tree to find 'a' tags
    nodes_to_check = [node]
    while nodes_to_check:
        curr = nodes_to_check.pop()
        if curr.tag == 'a':
            link_text_len += len(curr.full_text)
        nodes_to_check.extend(curr.children)
        
    return link_text_len / text_len

def score_node(node: DOMNode):
    """Assigns content scores to structural elements using heuristics."""
    if node.tag not in ('div', 'section', 'article', 'main', 'p', 'blockquote', 'td'):
        return
        
    node_text = node.full_text
    word_count = len(node_text.split())
    if word_count < 5:
        return
        
    # Start score based on element type
    score = 0.0
    if node.tag == 'p':
        score += 1.0
    elif node.tag == 'blockquote':
        score += 3.0
    elif node.tag == 'article':
        score += 15.0
    elif node.tag == 'main':
        score += 20.0
        
    # Score based on class and ID attributes
    attr_str = node.get_attr_string()
    
    # Positive attributes
    positive_regex = re.compile(r'article|body|content|entry|main|story|text|post|blog', re.I)
    # Negative attributes
    negative_regex = re.compile(r'sidebar|foot|header|nav|menu|ad|comment|social|share|widget|login|author', re.I)
    
    if positive_regex.search(attr_str):
        score += 25.0
    if negative_regex.search(attr_str):
        score -= 25.0
        
    # Score based on text content features (commas, sentence length)
    commas_count = node_text.count(',') + node_text.count('\u3001') # Support CJK commas
    score += min(commas_count, 10.0)
    
    # Text length score
    score += min(word_count / 100.0, 5.0)
    
    node.score = score

def find_best_content_node(node: DOMNode) -> DOMNode:
    """Traverses the DOM tree to find the node with the highest readability score."""
    best_node = node
    
    def traverse(curr: DOMNode):
        nonlocal best_node
        score_node(curr)
        if curr.score > best_node.score:
            best_node = curr
        for child in curr.children:
            traverse(child)
            
    traverse(node)
    return best_node

def extract_metadata(root: DOMNode) -> Dict[str, str]:
    """Extracts title and meta information from the page header."""
    metadata = {"title": "Untitled Article"}
    
    nodes = [root]
    while nodes:
        curr = nodes.pop()
        if curr.tag == 'title':
            metadata['title'] = html.unescape(curr.text)
        elif curr.tag == 'meta':
            name = curr.attrs.get('name') or curr.attrs.get('property')
            content = curr.attrs.get('content')
            if name and content:
                name = name.lower()
                if 'title' in name:
                    metadata['title'] = html.unescape(content)
                elif 'description' in name:
                    metadata['description'] = html.unescape(content)
                elif 'author' in name:
                    metadata['author'] = html.unescape(content)
                elif 'date' in name or 'published' in name:
                    metadata['date'] = html.unescape(content)
        nodes.extend(curr.children)
        
    return metadata

def node_to_markdown(node: DOMNode) -> str:
    """Converts a content DOM node and its children into structured Markdown."""
    lines = []
    
    def render(curr: DOMNode, in_list: bool = False):
        if curr.tag in ('script', 'style', 'noscript', 'iframe', 'svg', 'form'):
            return
            
        # Avoid link-dense blocks inside candidate nodes (they might be inline menus)
        if curr.tag == 'div' and calculate_link_density(curr) > 0.6:
            return
            
        tag = curr.tag
        text = html.unescape(curr.text).strip()
        
        if tag.startswith('h') and len(tag) == 2 and tag[1].isdigit():
            level = int(tag[1])
            if text:
                lines.append(f"\n{'#' * level} {text}\n")
        elif tag == 'p':
            if text:
                lines.append(f"\n{text}\n")
        elif tag == 'blockquote':
            if text:
                lines.append(f"\n> {text.replace(chr(10), chr(10) + '> ')}\n")
        elif tag in ('ul', 'ol'):
            for child in curr.children:
                render(child, in_list=True)
            lines.append("\n") # Padding after lists
        elif tag == 'li':
            if text:
                bullet = "-" if not in_list else "  -"
                lines.append(f"{bullet} {text}")
        elif tag == 'pre':
            # Preformatted code blocks
            code_text = html.unescape(curr.full_text).strip()
            if code_text:
                lines.append(f"\n```\n{code_text}\n```\n")
        elif tag == 'a':
            # Handle inline link formatting if parent is paragraph
            href = curr.attrs.get('href', '')
            if text and href and curr.parent and curr.parent.tag == 'p':
                # Avoid rendering massive javascript URLs
                if not href.startswith('javascript:'):
                    lines.append(f"[{text}]({href})")
            elif text:
                lines.append(text)
        else:
            # Inline tags (span, strong, em) or neutral blocks (div)
            if text:
                if tag in ('strong', 'b'):
                    lines.append(f" **{text}** ")
                elif tag in ('em', 'i'):
                    lines.append(f" *{text}* ")
                else:
                    # Divs or unrecognized wrappers
                    if tag in ('div', 'section', 'article') and text:
                        lines.append(f"\n{text}\n")
                    else:
                        lines.append(text)
                        
            # Walk children
            # If we already handled block styling, skip children to avoid duplicate text
            if tag not in ('pre', 'blockquote'):
                for child in curr.children:
                    render(child, in_list)

    render(node)
    
    # Clean up double spacing and formatting artifacts
    md_text = "".join(lines)
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    return md_text.strip()

def main():
    parser = argparse.ArgumentParser(
        description="Extract the core article text from a webpage, omitting navigation, sidebars, and ads."
    )
    parser.add_argument('url', help='The URL of the webpage to extract content from')
    parser.add_argument('--format', choices=['markdown', 'text', 'json'], default='markdown',
                        help='Output format (default: markdown)')
    parser.add_argument('--output', help='File path to write the output to (prints to stdout if omitted)')
    
    args = parser.parse_args()
    
    try:
        print(f"Fetching content from {args.url}...", file=sys.stderr)
        
        req = urllib.request.Request(
            args.url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            html_data = response.read().decode(charset, errors='ignore')
            
        print("Parsing webpage structure...", file=sys.stderr)
        builder = DOMBuilder()
        builder.feed(html_data)
        
        metadata = extract_metadata(builder.root)
        print(f"Title: {metadata['title']}", file=sys.stderr)
        
        best_content = find_best_content_node(builder.root)
        
        # Check if we successfully found an element with text
        if not best_content or len(best_content.full_text) < 100:
            print("Warning: Heuristic search did not find a strong article body. Falling back to body tag.", file=sys.stderr)
            # Find body
            body_node = None
            nodes = [builder.root]
            while nodes:
                curr = nodes.pop()
                if curr.tag == 'body':
                    body_node = curr
                    break
                nodes.extend(curr.children)
            best_content = body_node or builder.root
            
        out_stream = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout
        
        try:
            if args.format == 'json':
                article_data = {
                    "url": args.url,
                    "title": metadata.get("title", ""),
                    "description": metadata.get("description", ""),
                    "author": metadata.get("author", ""),
                    "date": metadata.get("date", ""),
                    "markdown": node_to_markdown(best_content),
                    "text": " ".join(best_content.full_text.split())
                }
                out_stream.write(json.dumps(article_data, indent=2))
            elif args.format == 'text':
                out_stream.write(f"{metadata['title']}\n")
                out_stream.write("=" * len(metadata['title']) + "\n\n")
                out_stream.write(" ".join(best_content.full_text.split()))
            else: # markdown
                out_stream.write(f"# {metadata['title']}\n\n")
                if 'description' in metadata:
                    out_stream.write(f"> *{metadata['description']}*\n\n")
                out_stream.write(node_to_markdown(best_content))
                out_stream.write("\n")
                
            if args.output:
                print(f"Extraction successful! Content saved to {args.output}", file=sys.stderr)
                
        finally:
            if args.output:
                out_stream.close()
                
    except Exception as e:
        print(f"Error extracting content: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
