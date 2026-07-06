#!/usr/bin/env python3
"""
Markdown to OPML Converter - Converts Markdown headings and lists into OPML outline format.
Useful for importing document hierarchies into mind-mapping tools (like XMind) or RSS readers.
"""

import os
import re
import sys
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

# ANSI color codes for TUI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"

def log_success(message):
    print(f"{COLOR_GREEN}[✓] {message}{COLOR_RESET}")

def log_warn(message):
    print(f"{COLOR_YELLOW}[!] {message}{COLOR_RESET}")

def log_error(message):
    print(f"{COLOR_RED}[✗] {message}{COLOR_RESET}", file=sys.stderr)

def log_info(message):
    print(f"{COLOR_BLUE}[i] {message}{COLOR_RESET}")

def clean_markdown_formatting(text):
    """Removes basic markdown text formatting like bold, italic, and links for clean OPML text."""
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Links [text](url) -> text (url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    return text.strip()

def parse_markdown_to_tree(md_content, title="Outline"):
    """Parses markdown lines into a structured tree of nested dictionaries."""
    lines = md_content.splitlines()
    
    # Root node
    root = {"text": title, "children": []}
    
    # Stack tracks current path from root. Each entry is (depth, node_reference)
    # depth for headings is 1-6 (number of hashes).
    # depth for lists is 10 + indent_spaces.
    stack = [(-1, root)]
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # 1. Check for headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = clean_markdown_formatting(heading_match.group(2))
            
            node = {"text": text, "children": []}
            
            # Pop elements from stack that have depth >= current heading level
            while stack and stack[-1][0] >= level:
                stack.pop()
                
            # Add to parent
            parent = stack[-1][1]
            parent["children"].append(node)
            stack.append((level, node))
            continue
            
        # 2. Check for list items (unordered or ordered)
        ul_match = re.match(r'^(\s*)([*+-])\s+(.*)', line)
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        
        if ul_match or ol_match:
            match = ul_match or ol_match
            indent = len(match.group(1))
            text = clean_markdown_formatting(match.group(3))
            
            node = {"text": text, "children": []}
            
            # Assign lists a depth offset to distinguish them from headings
            # Heading levels are 1-6, list levels start at 10 + indent
            list_depth = 10 + indent
            
            # Pop elements from stack that are deeper or equal
            while stack and stack[-1][0] >= list_depth:
                stack.pop()
                
            # If stack top is a heading, we can nest the list under it directly
            # If stack top is another list item at a lesser indent, we nest under it
            # If stack top has depth >= list_depth, we popped it already.
            parent = stack[-1][1]
            parent["children"].append(node)
            stack.append((list_depth, node))
            
    return root

def build_opml_element(node, parent_element=None):
    """Recursively builds XML elements for the OPML outline."""
    if parent_element is None:
        # Create root <opml> structure
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        title_elem = ET.SubElement(head, "title")
        title_elem.text = node["text"]
        
        body = ET.SubElement(opml, "body")
        for child in node["children"]:
            build_opml_element(child, body)
        return opml
    else:
        # Create <outline> element
        outline = ET.SubElement(parent_element, "outline", text=node["text"])
        for child in node["children"]:
            build_opml_element(child, outline)
        return outline

def prettify_xml(elem):
    """Returns a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Pretty print with 2 spaces indent
    pretty_str = reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")
    # Fix spacing issues occasionally added by minidom on plain text
    # by stripping blank lines that minidom sometimes inserts
    return "\n".join([line for line in pretty_str.splitlines() if line.strip()])

def main():
    parser = argparse.ArgumentParser(description="Convert Markdown outlines and lists to OPML 2.0 format.")
    parser.add_argument("input", help="Path to input Markdown (.md) file.")
    parser.add_argument("-o", "--output", help="Path to save output OPML (.opml) file.")
    parser.add_argument("-t", "--title", help="Title for the OPML document (defaults to input filename).")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        log_error(f"Input file not found: {args.input}")
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        log_error(f"Failed to read input file: {e}")
        sys.exit(1)
        
    log_info(f"Parsing Markdown file: {args.input}")
    
    doc_title = args.title or os.path.splitext(os.path.basename(args.input))[0].replace("_", " ").title()
    tree = parse_markdown_to_tree(md_content, title=doc_title)
    
    # Check if we parsed anything
    if not tree["children"]:
        log_warn("No headings or list structures were found in the Markdown file.")
        
    opml_xml = build_opml_element(tree)
    pretty_opml = prettify_xml(opml_xml)
    
    # Determine output path
    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.input)
        output_path = base + ".opml"
        
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty_opml)
        log_success(f"Successfully converted and saved to: {output_path}")
    except Exception as e:
        log_error(f"Failed to write output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
