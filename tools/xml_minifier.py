#!/usr/bin/env python3
"""
XML Minifier & Compressor

A standalone utility to minify XML files by stripping comments, namespace
definition spaces, structural indentation whitespace, and empty line breaks.
It preserves namespace prefix mappings by reading and registering them beforehand.

Usage:
    python xml_minifier.py input.xml -o output.min.xml
"""

import os
import sys
import argparse
import re
import xml.etree.ElementTree as ET


def register_all_namespaces(xml_file):
    """Parses namespaces in the file and registers them to keep original prefixes during output."""
    namespaces = {}
    try:
        # Search for xmlns:prefix="uri" using regex on the raw text
        with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Match xmlns:prefix="uri" or xmlns="uri"
            matches = re.findall(r'xmlns:?([^=]*)=["\']([^"\']*)["\']', content)
            for prefix, uri in matches:
                # If prefix is empty, it's the default namespace
                # ElementTree handles default namespaces automatically, but we register named ones
                if prefix:
                    ET.register_namespace(prefix, uri)
                    namespaces[prefix] = uri
    except Exception:
        # If anything fails, we fall back to ElementTree's default namespace generation
        pass
    return namespaces


def minify_node(node):
    """Recursively strips whitespace from text and tail of XML nodes."""
    if node.text:
        # If it's just spacing/newlines, strip it completely
        if node.text.isspace():
            node.text = None
        else:
            # Otherwise collapse whitespaces
            node.text = re.sub(r'\s+', ' ', node.text).strip()
            
    if node.tail:
        if node.tail.isspace():
            node.tail = None
        else:
            node.tail = re.sub(r'\s+', ' ', node.tail).strip()
            
    for child in node:
        minify_node(child)


def minify_xml(input_path, output_path, keep_declaration=True):
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        return 1

    # 1. Register namespaces to maintain original prefixes
    register_all_namespaces(input_path)

    # 2. Parse XML document
    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"XML Parsing Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # 3. Clean whitespace recursively
    minify_node(root)

    # 4. Serialize to string
    try:
        # ElementTree output
        minified_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=False)
        minified_str = minified_bytes.decode('utf-8')
        
        # Strip trailing/leading spaces from tags and ensure single line
        # ElementTree might output a bit of spacing for empty elements, which is fine, 
        # but let's clean any double-whitespace in tags
        minified_str = re.sub(r'>\s+<', '><', minified_str)
        
        # Prepare header
        header = ""
        if keep_declaration:
            # Extract original XML declaration if it exists
            try:
                with open(input_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('<?xml'):
                        header = first_line + "\n"
            except Exception:
                # Fallback to default declaration
                header = '<?xml version="1.0" encoding="utf-8"?>\n'

        final_output = header + minified_str

        # Calculate compression ratio
        original_size = os.path.getsize(input_path)
        minified_size = len(final_output.encode('utf-8'))
        ratio = (1 - (minified_size / original_size)) * 100 if original_size > 0 else 0

        # Save to output file
        with open(output_path, 'w', encoding='utf-8') as out_file:
            out_file.write(final_output)

        print(f"XML minified successfully.")
        print(f"  Original Size: {original_size} bytes")
        print(f"  Minified Size: {minified_size} bytes")
        print(f"  Compression Ratio: {ratio:.2f}% reduction")
        return 0

    except Exception as e:
        print(f"Error during serialization or write: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Minify XML files by removing spacing, comments, and formatting templates."
    )
    parser.add_argument("input_file", help="Path to input XML file")
    parser.add_argument(
        "-o", "--output", 
        help="Path to output minified XML file. Defaults to <input_base>.min.xml"
    )
    parser.add_argument(
        "--no-decl", 
        action="store_false", 
        dest="keep_decl",
        help="Do not output or prepend the XML <?xml ... ?> declaration header"
    )

    args = parser.parse_args()

    if not args.output:
        base, ext = os.path.splitext(args.input_file)
        args.output = base + ".min" + ext

    sys.exit(minify_xml(args.input_file, args.output, args.keep_decl))


if __name__ == "__main__":
    main()
