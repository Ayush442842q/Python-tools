#!/usr/bin/env python3
"""
HTML/CSS Inliner
Inlines CSS rules directly into HTML elements' `style` attributes.
Particularly useful for HTML emails and newsletters where external/head styles are unsupported.
Features a built-in, lightweight HTML DOM builder and CSS selector matcher.
"""

import argparse
import os
import re
import sys
from html.parser import HTMLParser

# ANSI Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
END = "\033[0m"

def log_info(msg):
    print(f"{BLUE}[INFO]{END} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{END} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{END} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{END} {msg}", file=sys.stderr)

class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag.lower()
        # Parse attributes into a case-insensitive dictionary
        self.attrs = {k.lower(): v for k, v in attrs}
        self.parent = parent
        self.children = []
        self.text = ""
        self.is_comment = False

    def get_classes(self):
        return self.attrs.get("class", "").split()

    def get_id(self):
        return self.attrs.get("id", "")

class DOMBuilder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node("root", [])
        self.current = self.root
        # Void/self-closing elements in HTML
        self.void_elements = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
            'link', 'meta', 'param', 'source', 'track', 'wbr'
        }

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, parent=self.current)
        self.current.children.append(node)
        if tag.lower() not in self.void_elements:
            self.current = node

    def handle_endtag(self, tag):
        tag = tag.lower()
        # Find the matching parent to handle unclosed tags gracefully
        temp = self.current
        while temp and temp.tag != tag and temp.tag != "root":
            temp = temp.parent
        if temp and temp.tag == tag:
            self.current = temp.parent

    def handle_data(self, data):
        if self.current.tag in {"style", "script"}:
            self.current.text += data
        else:
            node = Node("#text", [])
            node.text = data
            self.current.children.append(node)

    def handle_comment(self, data):
        node = Node("#comment", [])
        node.text = data
        self.current.children.append(node)

def parse_css(css_text):
    """Parses CSS text into a list of (selector, declarations) tuples, skipping media queries."""
    # Remove CSS comments
    css_clean = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)
    
    # Simple check for media queries (we want to skip them so they remain in style tags)
    # We strip media queries from the CSS we process, but they'll be left in the HTML's style tag.
    media_queries = []
    
    # Find and extract media queries: @media ... { ... }
    # Since media queries can have nested braces, a simple regex is used for typical email media queries.
    media_pattern = re.compile(r'@media[^{]+\{(?:[^{}]+|\{[^{}]*\})*\}', re.IGNORECASE)
    for match in media_pattern.finditer(css_clean):
        media_queries.append(match.group(0))
    
    # Strip media queries from the css we will inline
    css_for_inlining = media_pattern.sub('', css_clean)

    rules = []
    # Match selectors and their code blocks
    pattern = re.compile(r'([^{]+)\{([^}]+)\}')
    for match in pattern.finditer(css_for_inlining):
        selector = match.group(1).strip()
        decls_str = match.group(2).strip()
        
        # Parse declarations
        decls = {}
        for decl in decls_str.split(';'):
            if not decl.strip():
                continue
            parts = decl.split(':', 1)
            if len(parts) == 2:
                prop = parts[0].strip().lower()
                val = parts[1].strip()
                decls[prop] = val
                
        # Split multi-selectors (e.g. h1, h2, h3)
        for sel in selector.split(','):
            rules.append((sel.strip(), decls))
            
    return rules, media_queries

def match_simple_selector(node, selector):
    """Matches a simple selector (no spaces, e.g. 'div.info#main') against a node."""
    if node.tag in {"root", "#text", "#comment"}:
        return False

    # Extract tag, classes, and ids
    # A selector can be: tag, .class, #id, tag.class, tag#id, .class.class, etc.
    match = re.match(r'^([a-zA-Z0-9*-]*)([^ ]*)$', selector)
    if not match:
        return False
    
    tag_part, rest = match.groups()
    
    # 1. Tag Match
    if tag_part and tag_part != "*":
        if node.tag != tag_part.lower():
            return False
            
    # 2. ID Match (e.g. #header)
    ids = re.findall(r'#([a-zA-Z0-9_-]+)', rest)
    for ident in ids:
        if node.get_id() != ident:
            return False
            
    # 3. Class Match (e.g. .btn)
    classes = re.findall(r'\.([a-zA-Z0-9_-]+)', rest)
    node_classes = node.get_classes()
    for cls in classes:
        if cls not in node_classes:
            return False
            
    return True

def match_selector(node, selector):
    """Matches a full selector (including descendant combinators, e.g., 'div .box p') against a node."""
    parts = selector.split()
    if not parts:
        return False

    # Match the last selector part to the node itself
    if not match_simple_selector(node, parts[-1]):
        return False

    # If it's a descendant selector (e.g., 'div p'), verify ancestors
    current_ancestor = node.parent
    for part in reversed(parts[:-1]):
        while current_ancestor and current_ancestor.tag != "root":
            if match_simple_selector(current_ancestor, part):
                break
            current_ancestor = current_ancestor.parent
        else:
            return False  # Required ancestor not found
        current_ancestor = current_ancestor.parent
        
    return True

def parse_style_attribute(style_str):
    """Parses existing inline style string into a dictionary."""
    if not style_str:
        return {}
    decls = {}
    for decl in style_str.split(';'):
        if not decl.strip():
            continue
        parts = decl.split(':', 1)
        if len(parts) == 2:
            prop = parts[0].strip().lower()
            val = parts[1].strip()
            decls[prop] = val
    return decls

def serialize_style_attribute(style_dict):
    """Serializes style dictionary back to style string."""
    return "; ".join(f"{k}: {v}" for k, v in style_dict.items()) + (";" if style_dict else "")

def inline_styles(node, css_rules):
    """Recursively traverses DOM to inline CSS styles."""
    if node.tag not in {"root", "#text", "#comment", "style", "script", "link", "meta", "head"}:
        # Find all matching rules
        matched_decls = {}
        for selector, decls in css_rules:
            if match_selector(node, selector):
                # Later rules override earlier ones
                matched_decls.update(decls)
                
        if matched_decls:
            # Parse existing styles (which override stylesheet styles)
            existing_styles = parse_style_attribute(node.attrs.get("style", ""))
            
            # Merge: inline styles take precedence over sheet styles
            final_styles = matched_decls.copy()
            final_styles.update(existing_styles)
            
            # Save styles back to attribute
            node.attrs["style"] = serialize_style_attribute(final_styles)

    # Recurse children
    for child in node.children:
        inline_styles(child, css_rules)

def collect_styles(node, internal_css_texts, external_links):
    """Traverses DOM to find internal style tags and external stylesheet links."""
    if node.tag == "style":
        internal_css_texts.append((node, node.text))
    elif node.tag == "link" and node.attrs.get("rel") == "stylesheet":
        href = node.attrs.get("href")
        if href:
            external_links.append((node, href))
            
    for child in node.children:
        collect_styles(child, internal_css_texts, external_links)

def serialize_dom(node):
    """Serializes the HTML DOM node tree back into a single HTML string."""
    if node.tag == "root":
        return "".join(serialize_dom(c) for c in node.children)
    if node.tag == "#text":
        return node.text
    if node.tag == "#comment":
        return f"<!--{node.text}-->"

    # Reconstruct attributes
    attrs_str = ""
    for k, v in node.attrs.items():
        attrs_str += f' {k}="{v}"'

    # Check for self-closing tags
    void_elements = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
        'link', 'meta', 'param', 'source', 'track', 'wbr'
    }
    if node.tag in void_elements:
        return f"<{node.tag}{attrs_str}>"

    # Standard elements
    inner_content = ""
    if node.tag in {"style", "script"}:
        inner_content = node.text
    else:
        inner_content = "".join(serialize_dom(c) for c in node.children)
        
    return f"<{node.tag}{attrs_str}>{inner_content}</{node.tag}>"

def main():
    parser = argparse.ArgumentParser(
        description="Pure-Python HTML/CSS Style Inliner. Merges stylesheet rules into HTML element inline style attributes."
    )
    parser.add_argument("-i", "--html", required=True, help="Input HTML file path")
    parser.add_argument("-c", "--css", help="Optional external CSS file to inline (overrides/complements HTML stylesheets)")
    parser.add_argument("-o", "--output", help="Output HTML file path (default: [input]_inlined.html)")
    parser.add_argument("-r", "--remove-style-tags", action="store_true", 
                        help="Completely remove style tags after inlining (non-media-query styles will be deleted)")

    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("")

    if not os.path.exists(args.html):
        log_error(f"HTML file not found: {args.html}")
        sys.exit(1)

    # Read HTML
    try:
        with open(args.html, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        log_error(f"Failed to read HTML: {e}")
        sys.exit(1)

    log_info("Parsing HTML...")
    builder = DOMBuilder()
    builder.feed(html_content)
    
    # Collect internal style tags and links
    internal_style_nodes = []
    style_texts = []
    link_nodes = []
    link_hrefs = []
    
    collect_styles(builder.root, internal_style_nodes, link_nodes)
    
    # Compile CSS text
    compiled_css_text = ""
    
    # 1. Read internal CSS
    for node, text in internal_style_nodes:
        compiled_css_text += "\n" + text
        
    # 2. Read external CSS if specified via argument
    if args.css:
        if os.path.exists(args.css):
            try:
                with open(args.css, "r", encoding="utf-8") as f:
                    compiled_css_text += "\n" + f.read()
                log_info(f"Loaded CSS from CLI argument: {args.css}")
            except Exception as e:
                log_error(f"Failed to read CSS file: {args.css}. Error: {e}")
        else:
            log_warning(f"CSS file not found: {args.css}")
            
    # 3. Read linked CSS files (only local paths relative to HTML file)
    html_dir = os.path.dirname(os.path.abspath(args.html))
    for node, href in link_nodes:
        # Check if local file
        if not href.startswith(("http://", "https://", "//")):
            local_css_path = os.path.join(html_dir, href)
            if os.path.exists(local_css_path):
                try:
                    with open(local_css_path, "r", encoding="utf-8") as f:
                        compiled_css_text += "\n" + f.read()
                    log_info(f"Loaded linked local CSS: {href}")
                    # Remove the stylesheet link node from the DOM since it's now inlined
                    node.parent.children.remove(node)
                except Exception as e:
                    log_warning(f"Failed to read linked CSS {href}: {e}")
            else:
                log_warning(f"Linked CSS file not found locally: {href}")

    # Parse CSS rules
    log_info("Parsing CSS rules...")
    css_rules, media_queries = parse_css(compiled_css_text)
    log_info(f"Found {len(css_rules)} CSS selectors to inline.")
    if media_queries:
        log_info(f"Preserved {len(media_queries)} media query blocks for responsive email design.")

    # Inline styles recursively
    log_info("Inlining styles...")
    inline_styles(builder.root, css_rules)

    # Clean style tags
    for node, text in internal_style_nodes:
        if args.remove_style_tags:
            # Remove style tag entirely
            node.parent.children.remove(node)
        else:
            # Replace style tag contents with ONLY media queries (to keep responsiveness)
            if media_queries:
                node.text = "\n" + "\n\n".join(media_queries) + "\n"
            else:
                node.parent.children.remove(node)

    # Serialize back to HTML
    output_html = serialize_dom(builder.root)
    
    # Save output
    if args.output:
        dest_path = args.output
    else:
        base, ext = os.path.splitext(args.html)
        dest_path = f"{base}_inlined{ext}"

    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(output_html)
        log_success(f"Inlined HTML saved successfully: {dest_path}")
    except Exception as e:
        log_error(f"Failed to write output HTML: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
