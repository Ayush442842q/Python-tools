#!/usr/bin/env python3
"""
XML XPath Tester

A command-line tool to run XPath-like queries on XML files using Python's
built-in `xml.etree.ElementTree`. Supports namespaces, attribute filters,
text extraction, node serialization, and pretty-printing of result matches.

Usage:
    python tools/xml_xpath_tester.py -i file.xml -q ".//item[@status='active']" [options]

Options:
    -i, --input PATH      Path to the source XML file
    -q, --query XPATH     XPath query to evaluate
    -n, --ns NAMESPACES   Comma-separated namespace prefixes and URIs,
                          e.g., "ns=http://example.com,soap=http://schemas..."
    -t, --text-only       Print only the text content of matching nodes
    -a, --attribute ATTR  Print only the value of the specified attribute
    --xml-only            Print raw, formatted XML of matching nodes
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def supports_color() -> bool:
    """Returns True if the terminal supports ANSI colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty


def color_text(text: str, color_code: str) -> str:
    """Colors text for terminal output if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text


def indent_xml_element(elem: ET.Element, level: int = 0):
    """Recursively formats/indents an ElementTree element in-place."""
    i = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml_element(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level > 0:
            if not elem.tail or not elem.tail.strip():
                elem.tail = i


def parse_namespaces(ns_str: str) -> Dict[str, str]:
    """Parses a namespace string (e.g. 'ns=uri,soap=uri2') into a dictionary."""
    namespaces = {}
    if not ns_str:
        return namespaces
    
    parts = ns_str.split(",")
    for part in parts:
        if "=" in part:
            prefix, uri = part.split("=", 1)
            namespaces[prefix.strip()] = uri.strip()
        else:
            # Default namespace
            namespaces[""] = part.strip()
    return namespaces


def serialize_element(elem: ET.Element) -> str:
    """Pretty-prints an XML element to a string representation."""
    # Create a deep copy of the element to format in-place without altering the original tree
    import copy
    elem_copy = copy.deepcopy(elem)
    indent_xml_element(elem_copy, level=0)
    try:
        return ET.tostring(elem_copy, encoding="utf-8").decode("utf-8").strip()
    except Exception as e:
        return f"<SerializationError: {str(e)}>"


def format_node_summary(elem: ET.Element, index: int) -> str:
    """Generates a brief summary line of an XML node (tag, attributes, text snippet)."""
    attrs = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
    attr_str = f" [{attrs}]" if attrs else ""
    
    text_snippet = ""
    if elem.text and elem.text.strip():
        txt = elem.text.strip()
        if len(txt) > 40:
            txt = txt[:37] + "..."
        text_snippet = f" -> {color_text(f'\"{txt}\"', COLOR_GREEN)}"
        
    return f"{color_text(f'#{index}', COLOR_YELLOW)} <{color_text(elem.tag, COLOR_CYAN)}{attr_str}>{text_snippet}"


def main():
    parser = argparse.ArgumentParser(
        description="XML XPath Tester - Evaluate XPath queries against XML documents with built-in ElementTree."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input XML file")
    parser.add_argument("-q", "--query", required=True, help="XPath-like query expression (e.g., './/item', 'channel/title')")
    parser.add_argument("-n", "--ns", help="Optional namespace mappings. Format: prefix=uri,prefix2=uri2")
    parser.add_argument("-t", "--text-only", action="store_true", help="Print only matching text nodes")
    parser.add_argument("-a", "--attribute", help="Print only the value of the specified attribute")
    parser.add_argument("--xml-only", action="store_true", help="Print raw indented XML string of matching nodes")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(color_text(f"Error: Input XML file does not exist at '{args.input}'", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    namespaces = parse_namespaces(args.ns)

    try:
        # Load and parse XML
        tree = ET.parse(args.input)
        root = tree.getroot()
    except ET.ParseError as e:
        print(color_text(f"XML Parse Error: {str(e)}", COLOR_RED), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(color_text(f"Error loading file: {str(e)}", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    # Evaluate XPath
    try:
        # ElementTree findall supports a subset of XPath
        matches = root.findall(args.query, namespaces)
    except Exception as e:
        print(color_text(f"XPath Evaluation Error: {str(e)}", COLOR_RED), file=sys.stderr)
        print("\nNote: standard xml.etree.ElementTree supports a subset of XPath syntax.", file=sys.stderr)
        print("Supported constructs: tag, *, ., //, [tag], [@attrib], [@attrib='value'], [position]", file=sys.stderr)
        sys.exit(1)

    if not matches:
        print(color_text(f"No matches found for query: '{args.query}'", COLOR_YELLOW))
        sys.exit(0)

    # Output matches
    if args.text_only:
        for match in matches:
            if match.text:
                txt = match.text.strip()
                if txt:
                    print(txt)
    elif args.attribute:
        for match in matches:
            val = match.attrib.get(args.attribute)
            if val is not None:
                print(val)
    elif args.xml_only:
        for i, match in enumerate(matches):
            if i > 0:
                print("\n" + "-"*40 + "\n")
            print(serialize_element(match))
    else:
        print(color_text(f"Found {len(matches)} matching node(s) for query: '{args.query}'\n", COLOR_GREEN))
        for i, match in enumerate(matches, 1):
            print(format_node_summary(match, i))
            # Indent and print the serialized node structure slightly indented
            serialized = serialize_element(match)
            # Indent lines
            indented = "\n".join("  " + line for line in serialized.split("\n"))
            print(indented)
            print()


if __name__ == "__main__":
    main()
