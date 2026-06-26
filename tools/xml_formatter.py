#!/usr/bin/env python3
"""
XML Validator, Beautifier, and Minifier
Parses, pretty-prints, minifies, and syntax-checks XML files/streams.
Provides clean line and column error reporting for malformed XML.
"""

import sys
import os
import argparse
import xml.etree.ElementTree as ET

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"

def supports_color():
    """Returns True if the terminal supports colored output."""
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

def clean_xml_whitespace(elem):
    """Recursively strip trailing/leading whitespace from text nodes to prepare for formatting."""
    if elem.text:
        elem.text = elem.text.strip()
    if elem.tail:
        elem.tail = elem.tail.strip()
    for child in elem:
        clean_xml_whitespace(child)

def indent_element(elem, level=0, indent_str="  "):
    """Recursively indent XML elements to produce pretty-printed layout."""
    indent_spacing = "\n" + (level * indent_str)
    next_indent_spacing = "\n" + ((level + 1) * indent_str)
    
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = next_indent_spacing
        else:
            elem.text = next_indent_spacing + elem.text.strip() + next_indent_spacing
            
        for i, child in enumerate(elem):
            indent_element(child, level + 1, indent_str)
            if i < len(elem) - 1:
                child.tail = next_indent_spacing
            else:
                child.tail = indent_spacing
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent_spacing

def minify_element(elem):
    """Strip all whitespace and newlines between tags."""
    if elem.text:
        elem.text = elem.text.strip()
    if elem.tail:
        elem.tail = elem.tail.strip()
    for child in elem:
        minify_element(child)
        child.tail = ""

def format_xml(xml_string, pretty=True, indent_size=2, use_tabs=False, minify=False):
    """Parses and formats XML string according to settings."""
    try:
        # ET.fromstring parses XML strings
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        # Raise standard parser error details
        raise e
        
    if minify:
        minify_element(root)
        root.tail = ""
        # Write back to bytes
        formatted_bytes = ET.tostring(root, encoding="utf-8")
        return formatted_bytes.decode("utf-8")
    else:
        clean_xml_whitespace(root)
        indent_str = "\t" if use_tabs else (" " * indent_size)
        indent_element(root, level=0, indent_str=indent_str)
        formatted_bytes = ET.tostring(root, encoding="utf-8")
        
        # Include XML declaration if it was present
        header = ""
        if xml_string.strip().startswith("<?xml"):
            # Extract original declaration
            decl_match = ET.re.match(r"<\?xml.*?\?>", xml_string.strip())
            if decl_match:
                header = decl_match.group(0) + "\n"
                
        return header + formatted_bytes.decode("utf-8")

def main():
    parser = argparse.ArgumentParser(
        description="XML Validator, Beautifier, and Minifier - Clean, format, minify, and check XML data.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", nargs="?", help="Path to XML file. If omitted, reads from standard input (stdin)")
    parser.add_argument("--in-place", "-i", action="store_true", help="Modify file in-place (requires file argument)")
    parser.add_argument("--minify", "-m", action="store_true", help="Minify XML (removes pretty formatting and spaces)")
    parser.add_argument("--indent", "-s", type=int, default=2, help="Number of spaces for indentation (default: 2)")
    parser.add_argument("--tabs", "-t", action="store_true", help="Use tabs for indentation instead of spaces")
    parser.add_argument("--check", "-c", action="store_true", help="Check syntax only and report status without printing output")
    
    args = parser.parse_args()
    
    # Read input XML
    xml_content = ""
    source_name = "stdin"
    
    if args.file:
        source_name = args.file
        if not os.path.exists(args.file):
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} File '{args.file}' not found.", file=sys.stderr)
            return 1
        if os.path.isdir(args.file):
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} '{args.file}' is a directory.", file=sys.stderr)
            return 1
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                xml_content = f.read()
        except Exception as e:
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} Could not read file: {e}", file=sys.stderr)
            return 1
    else:
        if args.in_place:
            print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} In-place editing (-i) requires a file argument.", file=sys.stderr)
            return 1
        # Read from stdin
        if sys.stdin.isatty():
            print("Reading XML from stdin... (Press Ctrl+D or Ctrl+Z on Windows to complete)")
        xml_content = sys.stdin.read()
        
    if not xml_content.strip():
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} Input XML is empty.", file=sys.stderr)
        return 1

    try:
        formatted_xml = format_xml(
            xml_content, 
            pretty=not args.minify, 
            indent_size=args.indent, 
            use_tabs=args.tabs, 
            minify=args.minify
        )
    except ET.ParseError as e:
        print(f"{COLOR_RED}{COLOR_BOLD}XML Syntax Error in {source_name}:{COLOR_RESET}", file=sys.stderr)
        print(f"  {COLOR_BOLD}Message:{COLOR_RESET} {e}", file=sys.stderr)
        
        # Display the line where error occurred if possible
        try:
            lines = xml_content.splitlines()
            err_line_no, err_col = e.position # position is (line, column)
            if 0 < err_line_no <= len(lines):
                print(f"  {COLOR_BOLD}Line {err_line_no}:{COLOR_RESET}", file=sys.stderr)
                # Show context line
                bad_line = lines[err_line_no - 1]
                print(f"    {bad_line}", file=sys.stderr)
                # Arrow pointer
                pointer = " " * (err_col + 4) + "^"
                print(pointer, file=sys.stderr)
        except Exception:
            pass
        return 2

    # If only checking syntax, we stop here
    if args.check:
        print(f"{COLOR_GREEN}{COLOR_BOLD}Valid XML:{COLOR_RESET} '{source_name}' is well-formed.")
        return 0

    # Output results
    if args.in_place and args.file:
        try:
            with open(args.file, "w", encoding="utf-8") as f:
                f.write(formatted_xml)
            print(f"{COLOR_GREEN}Success:{COLOR_RESET} Formatted '{args.file}' in-place.")
        except Exception as e:
            print(f"{COLOR_RED}{COLOR_BOLD}Error writing to file:{COLOR_RESET} {e}", file=sys.stderr)
            return 1
    else:
        # Print to stdout
        sys.stdout.write(formatted_xml)
        if not formatted_xml.endswith("\n"):
            sys.stdout.write("\n")
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
