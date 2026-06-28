#!/usr/bin/env python3
"""
HTML/CSS Inline Style Extractor & Consolidator
Scans HTML files for inline 'style="..."' attributes, extracts the rules,
replaces them with generated classes, and creates a consolidated stylesheet.
"""

import os
import re
import sys
import hashlib
import argparse
from typing import Dict, List, Tuple

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def normalize_style(style_str: str) -> str:
    """Normalize a style string by sorting and cleaning properties so identical styles match."""
    # Split by semicolon, clean, and sort
    parts = [p.strip() for p in style_str.split(';') if p.strip()]
    cleaned = []
    for part in parts:
        if ':' in part:
            prop, val = part.split(':', 1)
            cleaned.append(f"{prop.strip().lower()}: {val.strip()}")
    cleaned.sort()
    return "; ".join(cleaned) + ";"

def get_style_hash(style_str: str) -> str:
    """Generate a short stable hash for a style string."""
    norm = normalize_style(style_str)
    return hashlib.md5(norm.encode('utf-8')).hexdigest()[:6]

def consolidate_html_styles(html_content: str) -> Tuple[str, Dict[str, str]]:
    """
    Parses HTML tags, extracts inline styles, replaces/appends class names,
    and returns the updated HTML and a dictionary of class_name -> style_declarations.
    """
    style_to_class = {}  # normalized_style -> class_name
    class_to_decl = {}   # class_name -> raw_style
    
    # Regex to find HTML tags
    # This matches open tags like <div style="..." class="...">
    tag_pattern = re.compile(r'<[a-zA-Z0-9\-]+(?:\s+[a-zA-Z_:][a-zA-Z0-9_\-.:]*\s*=\s*(?:\'[^\']*\'|"[^"]*"|[^\s>]+))*\s*\/?>', re.DOTALL)
    
    # Inner attribute extractors
    style_attr_pattern = re.compile(r'\bstyle\s*=\s*(?P<q>["\'])(?P<val>.*?)(?P=q)', re.IGNORECASE | re.DOTALL)
    class_attr_pattern = re.compile(r'\bclass\s*=\s*(?P<q>["\'])(?P<val>.*?)(?P=q)', re.IGNORECASE | re.DOTALL)

    def replace_tag(match: re.Match) -> str:
        tag = match.group(0)
        
        style_match = style_attr_pattern.search(tag)
        if not style_match:
            return tag
            
        style_val = style_match.group('val').strip()
        if not style_val:
            return tag
            
        # Get hash and register class
        norm = normalize_style(style_val)
        if not norm:
            return tag
            
        if norm in style_to_class:
            class_name = style_to_class[norm]
        else:
            style_hash = get_style_hash(norm)
            class_name = f"sc-{style_hash}"
            style_to_class[norm] = class_name
            class_to_decl[class_name] = norm

        # Remove the style attribute from tag
        tag_no_style = style_attr_pattern.sub('', tag)
        
        # Check if tag already has a class attribute
        class_match = class_attr_pattern.search(tag_no_style)
        if class_match:
            existing_classes = class_match.group('val').strip()
            # Append new class if not already present
            if class_name not in existing_classes.split():
                new_class_val = f"{existing_classes} {class_name}"
                q = class_match.group('q')
                tag_new_class = tag_no_style.replace(class_match.group(0), f'class={q}{new_class_val}{q}')
            else:
                tag_new_class = tag_no_style
        else:
            # Insert new class attribute
            # We can put it right after the tag name
            tag_name_match = re.match(r'<[a-zA-Z0-9\-]+', tag_no_style)
            if tag_name_match:
                name_end = tag_name_match.end()
                tag_new_class = tag_no_style[:name_end] + f' class="{class_name}"' + tag_no_style[name_end:]
            else:
                tag_new_class = tag_no_style

        # Clean up potential double spaces left behind by style deletion
        tag_new_class = re.sub(r'\s{2,}', ' ', tag_new_class)
        tag_new_class = tag_new_class.replace(' >', '>')
        tag_new_class = tag_new_class.replace(' />', '/>')
        
        return tag_new_class

    updated_html = tag_pattern.sub(replace_tag, html_content)
    return updated_html, class_to_decl

def process_file(html_file: str, output_html: str, output_css: str, inline: bool):
    """Process a single HTML file and generate consolidated stylesheet."""
    if not os.path.exists(html_file):
        print(f"{RED}File not found: {html_file}{RESET}", file=sys.stderr)
        return False
        
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"{RED}Error reading {html_file}: {e}{RESET}", file=sys.stderr)
        return False
        
    updated_html, classes = consolidate_html_styles(html_content)
    
    if not classes:
        print(f"{YELLOW}No inline style attributes found to consolidate.{RESET}")
        return True
        
    # Build CSS text
    css_lines = []
    for cls, decl in sorted(classes.items()):
        css_lines.append(f".{cls} {{ {decl} }}")
    css_text = "\n".join(css_lines)
    
    print(f"{BOLD}{GREEN}Found and extracted {len(classes)} unique style declarations.{RESET}")
    
    if inline:
        # Insert style block in head
        head_match = re.search(r'</head>', updated_html, re.IGNORECASE)
        style_block = f"\n<style>\n{css_text}\n</style>\n"
        if head_match:
            idx = head_match.start()
            updated_html = updated_html[:idx] + style_block + updated_html[idx:]
            print(f"{GREEN}Inserted style block inside <head> tag.{RESET}")
        else:
            # Append at the beginning
            updated_html = style_block + updated_html
            print(f"{YELLOW}No <head> tag found, prepended style block to file.{RESET}")
    else:
        # Link external stylesheet
        if output_css:
            try:
                with open(output_css, 'w', encoding='utf-8') as css_f:
                    css_f.write(css_text)
                print(f"{GREEN}Saved CSS rules to external stylesheet: {output_css}{RESET}")
                
                # Check for head and insert link tag
                head_match = re.search(r'</head>', updated_html, re.IGNORECASE)
                link_tag = f'\n<link rel="stylesheet" href="{os.path.basename(output_css)}">\n'
                if head_match:
                    idx = head_match.start()
                    updated_html = updated_html[:idx] + link_tag + updated_html[idx:]
                    print(f"{GREEN}Inserted link tag inside <head> tag.{RESET}")
            except Exception as e:
                print(f"{RED}Error writing CSS file: {e}{RESET}", file=sys.stderr)
                
    try:
        with open(output_html or html_file, 'w', encoding='utf-8') as html_f:
            html_f.write(updated_html)
        print(f"{GREEN}Saved updated HTML file: {output_html or html_file}{RESET}")
    except Exception as e:
        print(f"{RED}Error writing HTML file: {e}{RESET}", file=sys.stderr)
        return False
        
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Extract inline style attributes from HTML and consolidate them into a clean stylesheet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/html_style_consolidator.py index.html --inline
  python tools/html_style_consolidator.py index.html -o index_clean.html -c styles.css
        """
    )
    parser.add_argument("html_file", help="Path to HTML file to process")
    parser.add_argument("-o", "--output-html", help="Path to save updated HTML file (overwrites original if omitted)")
    parser.add_argument("-c", "--output-css", help="Path to save extracted CSS rules (default: styles.css)", default="styles.css")
    parser.add_argument("--inline", action="store_true", help="Insert styles inside a <style> block in <head> instead of external stylesheet")
    
    args = parser.parse_args()
    
    process_file(
        html_file=args.html_file,
        output_html=args.output_html,
        output_css=args.output_css,
        inline=args.inline
    )

if __name__ == "__main__":
    main()
