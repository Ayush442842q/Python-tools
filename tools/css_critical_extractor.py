#!/usr/bin/env python3
"""
CSS Critical Style Extractor
Parses HTML and CSS files to extract and bundle only the style rules
that match selectors present in the HTML files, helping eliminate unused CSS bloat.

Features:
1. Recursively scans HTML files for classes, IDs, and tags.
2. Parses CSS files and dissects selectors.
3. Resolves selector matching against HTML occurrences (including support for compound and nested selectors).
4. Retains crucial global rules (e.g., body, html, universal resets).
5. Outputs a minified, cleaned stylesheet containing only the used rules.
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_CYAN = ""


def extract_html_identifiers(html_content: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Extracts all tags, class names, and IDs from HTML content.
    Returns (tags, classes, ids).
    """
    tags = set()
    classes = set()
    ids = set()
    
    # 1. Extract class attributes: class="name1 name2" or class='name1'
    class_matches = re.findall(r'class=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    for match in class_matches:
        for cls in match.split():
            classes.add(cls.strip())
            
    # 2. Extract id attributes: id="name"
    id_matches = re.findall(r'id=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    for match in id_matches:
        ids.add(match.strip())
        
    # 3. Extract HTML tags, e.g. <div class="..."> or <p>
    tag_matches = re.findall(r'<([a-zA-Z0-9:-]+)[^>]*>', html_content)
    for tag in tag_matches:
        # Strip closing slash for self-closing tags
        clean_tag = tag.rstrip("/").strip().lower()
        if clean_tag:
            tags.add(clean_tag)
            
    return tags, classes, ids


def parse_css_rules(css_content: str) -> List[Tuple[str, str]]:
    """
    Parses CSS content and extracts selector blocks.
    Returns a list of tuples: (selector, rule_body).
    """
    rules = []
    
    # Clean comments
    css_clean = re.sub(r"/\*.*?\*/", "", css_content, flags=re.DOTALL)
    
    # Simple regex to split by braces
    matches = re.findall(r"([^{]+)\{([^}]+)\}", css_clean)
    for sel, body in matches:
        sel_clean = sel.strip()
        body_clean = body.strip()
        if sel_clean and body_clean:
            # A rule can have multiple comma-separated selectors
            rules.append((sel_clean, body_clean))
            
    return rules


def selector_matches_html(selector: str, html_tags: Set[str], html_classes: Set[str], html_ids: Set[str]) -> bool:
    """
    Simple heuristic checking if a CSS selector could match elements present in the HTML sets.
    """
    # Global resets and structural elements are always kept
    if selector in ("*", "html", "body") or selector.startswith(":root") or selector.startswith("::") or selector.startswith("@"):
        return True
        
    # Split compound selectors (by commas)
    sub_selectors = [s.strip() for s in selector.split(",")]
    
    for sub in sub_selectors:
        # Parse tokens
        # Classes: .classname
        classes = re.findall(r"\.([a-zA-Z0-9_-]+)", sub)
        # IDs: #idname
        ids = re.findall(r"#([a-zA-Z0-9_-]+)", sub)
        # Tags (any word not preceded by . or #, and not a pseudo-class/attribute)
        # Clean pseudo-classes and attributes first
        cleaned_sub = re.sub(r"::[a-zA-Z0-9_-]+", "", sub)
        cleaned_sub = re.sub(r":[a-zA-Z0-9_-]+(?:\([^)]*\))?", "", cleaned_sub)
        cleaned_sub = re.sub(r"\[[^\]]+\]", "", cleaned_sub)
        
        tags = re.findall(r"\b([a-zA-Z0-9:-]+)\b", cleaned_sub)
        
        # Verify classes
        class_match = True
        for cls in classes:
            if cls not in html_classes:
                class_match = False
                break
                
        # Verify IDs
        id_match = True
        for ident in ids:
            if ident not in html_ids:
                id_match = False
                break
                
        # Verify tags
        tag_match = True
        for tag in tags:
            tag_lower = tag.lower()
            # Ignore numbers or keyword tokens in selectors (like 'px', 'em', combinators)
            if tag_lower in ("and", "or", "not", "only", "screen", "hover", "active", "focus", "visited"):
                continue
            if tag_lower not in html_tags:
                tag_match = False
                break
                
        # If any sub-selector fully matches, the compound selector is kept
        if class_match and id_match and tag_match:
            return True
            
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Extracts only the critical CSS rules used by specific HTML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("html", help="Path to HTML file or directory of HTML files")
    parser.add_argument("css", help="Path to the source CSS stylesheet")
    parser.add_argument("--output", help="Optional output path for cleaned CSS. Defaults to stdout.")
    parser.add_argument("--verbose", action="store_true", help="Print summary detail statistics")
    
    args = parser.parse_args()
    
    # 1. Verify CSS exists
    if not os.path.exists(args.css):
        print(f"{COLOR_RED}Error: CSS file '{args.css}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    with open(args.css, "r", encoding="utf-8") as f:
        css_content = f.read()
        
    # 2. Extract HTML symbols
    html_tags = set()
    html_classes = set()
    html_ids = set()
    
    html_files_read = 0
    
    if os.path.isfile(args.html):
        with open(args.html, "r", encoding="utf-8") as f:
            t, c, i = extract_html_identifiers(f.read())
            html_tags.update(t)
            html_classes.update(c)
            html_ids.update(i)
        html_files_read = 1
    elif os.path.isdir(args.html):
        for root, _, files in os.walk(args.html):
            for file in files:
                if file.endswith((".html", ".htm", ".php")):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        t, c, i = extract_html_identifiers(f.read())
                        html_tags.update(t)
                        html_classes.update(c)
                        html_ids.update(i)
                    html_files_read += 1
    else:
        print(f"{COLOR_RED}Error: HTML path '{args.html}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    if html_files_read == 0:
        print(f"{COLOR_YELLOW}No HTML files found to audit against.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    # 3. Parse and filter CSS rules
    rules = parse_css_rules(css_content)
    cleaned_rules = []
    
    kept_count = 0
    pruned_count = 0
    
    for selector, body in rules:
        if selector_matches_html(selector, html_tags, html_classes, html_ids):
            cleaned_rules.append(f"{selector} {{ {body} }}")
            kept_count += 1
        else:
            pruned_count += 1
            
    cleaned_css = "\n".join(cleaned_rules)
    
    # 4. Save/Report results
    if args.output:
        with open(args.output, "w", encoding="utf-8") as out:
            out.write(cleaned_css)
        print(f"{COLOR_GREEN}Successfully extracted critical CSS to '{args.output}'.{COLOR_RESET}")
        if args.verbose:
            print(f"  HTML Files Scanned   : {html_files_read}")
            print(f"  Unique Classes Found : {len(html_classes)}")
            print(f"  Unique IDs Found     : {len(html_ids)}")
            print(f"  Rules Kept           : {kept_count}")
            print(f"  Rules Pruned         : {pruned_count} ({pruned_count / max(1, kept_count + pruned_count) * 100:.1f}%)")
    else:
        print(cleaned_css)


if __name__ == "__main__":
    main()
