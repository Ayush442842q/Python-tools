#!/usr/bin/env python3
"""
JSON to XML Converter

Converts JSON files or raw JSON text inputs into XML format.
Supports customizable root elements, custom indentation, converting JSON keys
starting with "@" to XML attributes, and handling "#text" fields for element values.

Usage:
    python tools/json_to_xml.py -i data.json -o data.xml
    python tools/json_to_xml.py -i data.json --root data --indent "  "
    cat data.json | python tools/json_to_xml.py
"""

import argparse
import json
import os
import sys
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

def dict_to_xml_element(data, parent_tag, parent_el=None):
    """
    Recursively builds XML elements from a JSON-derived dict/list/primitive structure.
    """
    # 1. Handle dict payload
    if isinstance(data, dict):
        # Create the element
        el = Element(parent_tag) if parent_el is None else SubElement(parent_el, parent_tag)
        
        # We must process attributes first before sub-elements
        # Attributes start with '@'
        sub_elements_to_process = []
        for k, v in data.items():
            if k.startswith('@'):
                attr_name = k[1:]
                el.set(attr_name, str(v) if v is not None else "")
            elif k == '#text':
                if v is not None:
                    el.text = str(v)
            else:
                sub_elements_to_process.append((k, v))
                
        # Now process child elements
        for k, v in sub_elements_to_process:
            if isinstance(v, list):
                # For lists, repeat the element tag for each item
                for item in v:
                    dict_to_xml_element(item, k, el)
            else:
                dict_to_xml_element(v, k, el)
                
        return el

    # 2. Handle list payload (this shouldn't happen at root level unless handled,
    # but handles nested lists where repeating tag names makes sense)
    elif isinstance(data, list):
        # If parent_el is none, we must create a container
        el = Element(parent_tag) if parent_el is None else parent_el
        for item in data:
            dict_to_xml_element(item, "item", el)
        return el

    # 3. Handle primitive payload (str, int, float, bool, None)
    else:
        el = Element(parent_tag) if parent_el is None else SubElement(parent_el, parent_tag)
        if data is not None:
            # Convert bool to lower case string to match common XML/JSON conversions
            if isinstance(data, bool):
                el.text = str(data).lower()
            else:
                el.text = str(data)
        return el

def pretty_print_xml(element, indent="  "):
    """
    Formats the XML element tree with indentation.
    """
    raw_xml = tostring(element, encoding='utf-8')
    parsed = minidom.parseString(raw_xml)
    # minidom toprettyxml adds empty lines for mixed content, so we clean it up
    pretty_xml = parsed.toprettyxml(indent=indent, encoding='utf-8').decode('utf-8')
    
    # Remove blank lines introduced by toprettyxml
    cleaned_lines = [line for line in pretty_xml.splitlines() if line.strip()]
    return "\n".join(cleaned_lines)

def main():
    parser = argparse.ArgumentParser(
        description="JSON to XML Converter - Convert JSON structures into XML format."
    )
    parser.add_argument(
        '-i', '--input',
        help='Path to the input JSON file. If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-o', '--output',
        help='Path to save the output XML. If omitted, prints to console.'
    )
    parser.add_argument(
        '-r', '--root',
        default='root',
        help='Name of the root XML element (default: root). Ignored if top-level JSON is an object with a single key.'
    )
    parser.add_argument(
        '--indent',
        default='  ',
        help='Indentation string (default: two spaces). Use empty string for minified output.'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for files (default: utf-8)'
    )

    args = parser.parse_args()

    # Read JSON input
    if args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', encoding=args.encoding) as f:
                json_content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            json_content = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not json_content.strip():
        print("[ERROR] Input JSON content is empty.", file=sys.stderr)
        return 1

    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decoding failed: {e}", file=sys.stderr)
        return 1

    # Determine root element tag
    root_tag = args.root
    
    # If the root element in JSON is a dictionary with a single key-value pair,
    # and that value is a dictionary or list, we can use that key as the root tag
    if isinstance(data, dict) and len(data) == 1:
        key = list(data.keys())[0]
        # Ignore keys starting with @ or # as they are special
        if not key.startswith('@') and not key.startswith('#'):
            root_tag = key
            data = data[key]

    try:
        root_el = dict_to_xml_element(data, root_tag)
    except Exception as e:
        print(f"[ERROR] Failed to convert data structure: {e}", file=sys.stderr)
        return 1

    # Format output
    if args.indent:
        xml_output = pretty_print_xml(root_el, indent=args.indent)
    else:
        # Minified XML
        xml_output = '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(root_el, encoding='utf-8').decode('utf-8')

    # Output XML
    if args.output:
        try:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(xml_output + "\n")
            print(f"[OK] XML output successfully written to '{args.output}'.")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(xml_output)

    return 0

if __name__ == '__main__':
    sys.exit(main())
