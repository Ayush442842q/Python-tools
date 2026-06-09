#!/usr/bin/env python3
"""
XML to JSON Converter

Converts XML files or raw XML text inputs into JSON format.
Supports stripping XML namespaces, ignoring attributes, automatic type conversion
(numbers/booleans), custom JSON indentation, and file or standard input.

Usage:
    python tools/xml_to_json.py -i data.xml -o data.json
    python tools/xml_to_json.py -i data.xml --indent 2
    cat data.xml | python tools/xml_to_json.py --strip-namespaces --no-type-conversion
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

def parse_value(text, skip_conversion=False):
    """
    Attempts to parse text string into a Python typed value (int, float, bool, None).
    If skip_conversion is True, or parsing fails, returns the original text.
    """
    if skip_conversion:
        return text

    # Handle empty or whitespace-only text
    if not text:
        return None

    lower_text = text.strip().lower()
    
    # Booleans
    if lower_text == 'true':
        return True
    if lower_text == 'false':
        return False
    
    # Nulls
    if lower_text in ('null', 'none'):
        return None

    # Integers
    try:
        # Check if it looks like a phone number or zip code with leading zeros
        # (which shouldn't be converted to int if it changes the value representation, e.g. "01234")
        if text.strip().startswith('0') and len(text.strip()) > 1 and text.strip().isdigit():
            return text
        return int(text)
    except ValueError:
        pass

    # Floats
    try:
        return float(text)
    except ValueError:
        pass

    return text

def xml_element_to_dict(element, strip_namespaces=False, skip_attributes=False, skip_conversion=False):
    """
    Recursively converts an XML Element into a dict/list structure.
    """
    # Get the tag name (optionally stripped of namespaces)
    tag = element.tag
    if strip_namespaces and tag.startswith('{'):
        tag = tag.split('}', 1)[1]

    node = {}

    # 1. Process Attributes
    if not skip_attributes and element.attrib:
        for k, v in element.attrib.items():
            attr_key = k
            if strip_namespaces and attr_key.startswith('{'):
                attr_key = attr_key.split('}', 1)[1]
            node[f"@{attr_key}"] = parse_value(v, skip_conversion)

    # 2. Process Children
    children = list(element)
    if children:
        grouped_children = {}
        for child in children:
            child_tag = child.tag
            if strip_namespaces and child_tag.startswith('{'):
                child_tag = child_tag.split('}', 1)[1]
                
            child_val = xml_element_to_dict(
                child, 
                strip_namespaces=strip_namespaces, 
                skip_attributes=skip_attributes, 
                skip_conversion=skip_conversion
            )
            # Group child elements by tag
            grouped_children.setdefault(child_tag, []).append(child_val)

        # Merge grouped children into the node dict
        for child_tag, items in grouped_children.items():
            if len(items) == 1:
                node[child_tag] = items[0]
            else:
                node[child_tag] = items

    # 3. Process Text Content
    text_val = element.text.strip() if element.text else ""
    if text_val:
        parsed_text = parse_value(text_val, skip_conversion)
        if not node:
            # If there are no attributes and no children, return the value directly
            return parsed_text
        else:
            # If we already have attributes or children, place the text content in '#text'
            node["#text"] = parsed_text
    elif not node and not children:
        # Empty XML element with no children, attributes, or text content
        return None

    return node

def convert_xml_to_json(xml_str, strip_namespaces=False, skip_attributes=False, skip_conversion=False):
    """
    Parses an XML string and returns the JSON representation.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        raise ValueError(f"XML parsing failed: {e}")

    # Build the parsed tree
    root_tag = root.tag
    if strip_namespaces and root_tag.startswith('{'):
        root_tag = root_tag.split('}', 1)[1]

    root_dict = xml_element_to_dict(
        root, 
        strip_namespaces=strip_namespaces, 
        skip_attributes=skip_attributes, 
        skip_conversion=skip_conversion
    )
    
    # Return structured dict representing the root element
    return {root_tag: root_dict}

def main():
    parser = argparse.ArgumentParser(
        description="XML to JSON Converter - Convert XML structures into JSON format."
    )
    parser.add_argument(
        '-i', '--input',
        help='Path to the input XML file. If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-o', '--output',
        help='Path to save the output JSON. If omitted, prints to console.'
    )
    parser.add_argument(
        '--indent',
        type=int,
        default=4,
        help='Indentation level for output JSON (default: 4). Use -1 for a minified JSON string.'
    )
    parser.add_argument(
        '--strip-namespaces',
        action='store_true',
        help='Strip namespace prefixes from XML tags and attributes'
    )
    parser.add_argument(
        '--no-attributes',
        action='store_true',
        help='Do not include XML attributes in the JSON output'
    )
    parser.add_argument(
        '--no-type-conversion',
        action='store_true',
        help='Keep all values as strings instead of auto-converting to numbers/booleans'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for files (default: utf-8)'
    )

    args = parser.parse_args()

    # Read XML input
    if args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', encoding=args.encoding, errors='replace') as f:
                xml_content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            xml_content = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not xml_content.strip():
        print("[ERROR] Input XML content is empty.", file=sys.stderr)
        return 1

    try:
        parsed_dict = convert_xml_to_json(
            xml_content,
            strip_namespaces=args.strip_namespaces,
            skip_attributes=args.no_attributes,
            skip_conversion=args.no_type-conversion if 'no_type-conversion' in args else args.no_type_conversion
        )
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    # Format JSON output
    indent_val = args.indent if args.indent >= 0 else None
    separators_val = (',', ':') if args.indent < 0 else None
    
    json_output = json.dumps(parsed_dict, indent=indent_val, separators=separators_val, ensure_ascii=False)

    # Output JSON
    if args.output:
        try:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(json_output + "\n")
            print(f"[OK] JSON output successfully written to '{args.output}'.")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(json_output)

    return 0

if __name__ == '__main__':
    sys.exit(main())
