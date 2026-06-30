#!/usr/bin/env python3
"""
XML to Markdown Document Converter
Converts an XML structure into a clean, hierarchical Markdown outline.
Supports collapsible HTML details tags for deep nodes, formatting of attributes, and text contents.
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET

def format_attributes(attrib):
    """Formats element attributes as code blocks or italic key/values."""
    if not attrib:
        return ""
    parts = []
    for k, v in attrib.items():
        parts.append(f'`{k}="{v}"`')
    return " [" + ", ".join(parts) + "]"

def convert_to_markdown_plain(element, depth=0):
    """Converts XML element tree to plain markdown with indentations."""
    lines = []
    indent = "  " * depth
    attribs_str = format_attributes(element.attrib)
    
    text = element.text.strip() if element.text else ""
    # Truncate text if long
    if len(text) > 80:
        text = text[:77] + "..."
    
    node_desc = f"{indent}- **{element.tag}**{attribs_str}"
    if text:
        node_desc += f": *{text}*"
        
    lines.append(node_desc)
    
    for child in element:
        child_lines = convert_to_markdown_plain(child, depth + 1)
        lines.extend(child_lines)
        
    return lines

def convert_to_markdown_collapsible(element, depth=0):
    """Converts XML element tree using HTML details and summary for collapsibility."""
    lines = []
    indent = "  " * depth
    attribs_str = format_attributes(element.attrib)
    
    text = element.text.strip() if element.text else ""
    if len(text) > 100:
        text = text[:97] + "..."

    has_children = len(element) > 0
    
    if has_children:
        lines.append(f"{indent}<details>")
        lines.append(f"{indent}  <summary><b>{element.tag}</b>{attribs_str}</summary>")
        lines.append(f"{indent}  <ul>")
        
        if text:
            lines.append(f"{indent}    <li>Text: <i>{text}</i></li>")
            
        for child in element:
            child_lines = convert_to_markdown_collapsible(child, depth + 2)
            for cl in child_lines:
                lines.append(f"{indent}    {cl}")
                
        lines.append(f"{indent}  </ul>")
        lines.append(f"{indent}</details>")
    else:
        # Leaf node
        node_str = f"<b>{element.tag}</b>{attribs_str}"
        if text:
            node_str += f": <i>{text}</i>"
        lines.append(f"<li>{node_str}</li>")
        
    return lines

def main():
    parser = argparse.ArgumentParser(description="XML to Markdown Document Converter")
    parser.add_argument("xml_file", help="Path to the XML file to convert")
    parser.add_argument("-o", "--output", help="Path to write the markdown output (default: print to stdout)")
    parser.add_argument("-c", "--collapsible", action="store_true", help="Use collapsible HTML <details> tags")
    
    args = parser.parse_args()

    if not os.path.exists(args.xml_file):
        print(f"Error: XML file '{args.xml_file}' does not exist.")
        sys.exit(1)

    try:
        tree = ET.parse(args.xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Invalid XML syntax: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    title = f"# XML Structure: {os.path.basename(args.xml_file)}\n"
    
    if args.collapsible:
        markdown_lines = convert_to_markdown_collapsible(root)
        # Wrap root level single leaf nodes in ul if necessary
        if len(root) == 0:
            markdown_content = title + "<ul>\n" + "\n".join(markdown_lines) + "\n</ul>"
        else:
            markdown_content = title + "\n".join(markdown_lines)
    else:
        markdown_lines = convert_to_markdown_plain(root)
        markdown_content = title + "\n".join(markdown_lines)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_content + "\n")
            print(f"Success: Saved markdown structure to '{args.output}'")
        except Exception as e:
            print(f"Error writing to output file: {e}")
            sys.exit(1)
    else:
        print(markdown_content)

if __name__ == "__main__":
    main()
