#!/usr/bin/env python3
"""
xml_diff_tool - Structural XML Comparator

Compares two XML documents structurally, ignoring ordering of attributes, 
formatting whitespace, and optionally, order-independent child elements.
Outputs a clean structural diff listing additions, deletions, and updates 
keyed by their XPath locations.

Usage:
    python tools/xml_diff_tool.py file1.xml file2.xml
    python tools/xml_diff_tool.py file1.xml file2.xml --ignore-comments --ignore-whitespace
"""

import argparse
import sys
import xml.etree.ElementTree as ET

# ANSI Colors
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"


def print_colored(text, color):
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_RESET}")
    else:
        print(text)


def clean_text(text, ignore_whitespace=False):
    """Normalize text content."""
    if not text:
        return ""
    if ignore_whitespace:
        return " ".join(text.split()).strip()
    return text.strip()


def get_xpath(node, parent_path="", siblings_count=None):
    """Generates a unique XPath-like string for a node."""
    siblings_count = siblings_count or {}
    tag = node.tag
    siblings_count[tag] = siblings_count.get(tag, 0) + 1
    index = siblings_count[tag]
    return f"{parent_path}/{tag}[{index}]"


class XMLComparator:
    def __init__(self, ignore_whitespace=True, ignore_comments=True):
        self.ignore_whitespace = ignore_whitespace
        self.ignore_comments = ignore_comments
        self.diffs = []  # List of tuples: (type, xpath, message)

    def compare_nodes(self, node1, node2, xpath=""):
        """Recursively compares two elements."""
        # 1. Compare tags
        if node1.tag != node2.tag:
            self.diffs.append((
                "UPDATE", 
                xpath, 
                f"Tag name mismatch: '{node1.tag}' vs '{node2.tag}'"
            ))
            return

        # 2. Compare text values
        t1 = clean_text(node1.text, self.ignore_whitespace)
        t2 = clean_text(node2.text, self.ignore_whitespace)
        if t1 != t2:
            self.diffs.append((
                "UPDATE", 
                f"{xpath}/text()", 
                f"Text value mismatch: '{t1}' vs '{t2}'"
            ))

        # 3. Compare attributes
        attrs1 = node1.attrib
        attrs2 = node2.attrib

        # Check for missing attributes
        for key in attrs1:
            if key not in attrs2:
                self.diffs.append((
                    "DELETE", 
                    f"{xpath}/@{key}", 
                    f"Attribute '{key}' is missing in target. Expected value: '{attrs1[key]}'"
                ))
            elif attrs1[key] != attrs2[key]:
                self.diffs.append((
                    "UPDATE", 
                    f"{xpath}/@{key}", 
                    f"Attribute '{key}' value mismatch: '{attrs1[key]}' vs '{attrs2[key]}'"
                ))

        # Check for added attributes
        for key in attrs2:
            if key not in attrs1:
                self.diffs.append((
                    "INSERT", 
                    f"{xpath}/@{key}", 
                    f"Attribute '{key}' was added with value: '{attrs2[key]}'"
                ))

        # 4. Compare children recursively
        children1 = list(node1)
        children2 = list(node2)

        # Count occurrences of tags to build paths
        siblings_count1 = {}
        siblings_count2 = {}

        max_len = max(len(children1), len(children2))
        for idx in range(max_len):
            if idx < len(children1) and idx < len(children2):
                c1 = children1[idx]
                c2 = children2[idx]
                
                # Update sibling counts
                tag1 = c1.tag
                siblings_count1[tag1] = siblings_count1.get(tag1, 0) + 1
                idx1 = siblings_count1[tag1]
                
                tag2 = c2.tag
                siblings_count2[tag2] = siblings_count2.get(tag2, 0) + 1
                idx2 = siblings_count2[tag2]
                
                c_xpath = f"{xpath}/{tag1}[{idx1}]"
                self.compare_nodes(c1, c2, c_xpath)
                
            elif idx < len(children1):
                # Extra node in source (deleted in target)
                c1 = children1[idx]
                tag1 = c1.tag
                siblings_count1[tag1] = siblings_count1.get(tag1, 0) + 1
                idx1 = siblings_count1[tag1]
                c_xpath = f"{xpath}/{tag1}[{idx1}]"
                self.diffs.append((
                    "DELETE", 
                    c_xpath, 
                    f"Element <{tag1}> is missing in target document."
                ))
            else:
                # Extra node in target (added)
                c2 = children2[idx]
                tag2 = c2.tag
                siblings_count2[tag2] = siblings_count2.get(tag2, 0) + 1
                idx2 = siblings_count2[tag2]
                c_xpath = f"{xpath}/{tag2}[{idx2}]"
                self.diffs.append((
                    "INSERT", 
                    c_xpath, 
                    f"Element <{tag2}> was added to target document."
                ))


def parse_xml_file(filepath):
    try:
        tree = ET.parse(filepath)
        return tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Compare two XML files structurally and list structural differences."
    )
    parser.add_argument("file1", help="Path to the baseline XML file.")
    parser.add_argument("file2", help="Path to the target XML file.")
    parser.add_argument(
        "--no-ignore-whitespace", 
        action="store_false", 
        dest="ignore_whitespace",
        help="Do not normalize element text whitespace."
    )

    args = parser.parse_args()

    root1 = parse_xml_file(args.file1)
    root2 = parse_xml_file(args.file2)

    comparator = XMLComparator(ignore_whitespace=args.ignore_whitespace)
    
    # Run structural comparison starting at roots
    initial_xpath = f"/{root1.tag}"
    comparator.compare_nodes(root1, root2, xpath=initial_xpath)

    # Print results
    if not comparator.diffs:
        print_colored("✔ XML documents are structurally identical.", COLOR_GREEN)
        sys.exit(0)

    print(f"\nFound {len(comparator.diffs)} structural differences:")
    print("=" * 50)
    for tag, xpath, message in comparator.diffs:
        if tag == "DELETE":
            print_colored(f"[-] {xpath}\n    {message}", COLOR_RED)
        elif tag == "INSERT":
            print_colored(f"[+] {xpath}\n    {message}", COLOR_GREEN)
        elif tag == "UPDATE":
            print_colored(f"[*] {xpath}\n    {message}", COLOR_YELLOW)
        print("-" * 50)

    sys.exit(1)


if __name__ == "__main__":
    main()
