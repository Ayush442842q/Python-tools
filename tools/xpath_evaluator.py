#!/usr/bin/env python3
"""
XPath Query Evaluator & HTML/XML Parser CLI
Evaluates XPath queries against local XML/HTML files or remote URLs,
returning matching elements, attributes, or texts.

Usage:
    python tools/xpath_evaluator.py index.html "//a[@href]"
    python tools/xpath_evaluator.py https://example.com "//h1/text()"
"""

import argparse
import html.parser
import sys
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


class HTMLToElementTreeBuilder(html.parser.HTMLParser):
    """Parses HTML into an xml.etree.ElementTree.Element structure gracefully."""
    
    def __init__(self):
        super().__init__()
        self.root = ET.Element("html")
        self.stack = [self.root]
        
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        parent = self.stack[-1]
        elem = ET.SubElement(parent, tag)
        for key, val in attrs:
            elem.set(key, val or "")
        self.stack.append(elem)
        
    def handle_endtag(self, tag: str):
        # We search from the end of the stack to close the matching tag
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                # Remove everything above this element from stack
                self.stack = self.stack[:i]
                break
                
    def handle_data(self, data: str):
        if not data.strip():
            return
        parent = self.stack[-1]
        if len(parent) == 0:
            # No children yet, set text
            if parent.text:
                parent.text += data
            else:
                parent.text = data
        else:
            # Add to tail of last child
            last_child = parent[-1]
            if last_child.tail:
                last_child.tail += data
            else:
                last_child.tail = data


def serialize_element(elem: ET.Element, depth: int = 0) -> str:
    """Pretty prints an element tree structure back to clean string."""
    indent = "  " * depth
    tag = elem.tag
    attrs_str = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
    attrs_str = f" {attrs_str}" if attrs_str else ""
    
    lines = []
    text = elem.text.strip() if elem.text else ""
    
    if len(elem) == 0:
        if text:
            lines.append(f"{indent}<{tag}{attrs_str}>{text}</{tag}>")
        else:
            lines.append(f"{indent}<{tag}{attrs_str} />")
    else:
        lines.append(f"{indent}<{tag}{attrs_str}>")
        if text:
            lines.append(f"{indent}  {text}")
        for child in elem:
            lines.append(serialize_element(child, depth + 1))
        lines.append(f"{indent}</{tag}>")
        
    if elem.tail and elem.tail.strip():
        lines.append(f"{indent}{elem.tail.strip()}")
        
    return "\n".join(lines)


def fetch_remote_url(url: str) -> str:
    """Fetches HTML/XML content from a remote URL."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")
    except Exception as e:
        print_colored(f"[!] Failed to fetch URL '{url}': {e}", COLOR_FAIL)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="XPath Query Evaluator & HTML/XML Parser CLI utility.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("source", help="Path to local file OR remote URL (starts with http/https)")
    parser.add_argument("xpath", help="XPath query (e.g. '//a', './/div[@class=\"content\"]', './/title')")
    
    parser.add_argument("--xml", "-x", action="store_true", help="Parse strictly as XML instead of HTML")
    
    args = parser.parse_args()
    
    # Load content
    if args.source.startswith("http://") or args.source.startswith("https://"):
        print_colored(f"[*] Fetching remote content from '{args.source}'...", COLOR_CYAN)
        content = fetch_remote_url(args.source)
    else:
        if not os.path.exists(args.source):
            print_colored(f"[!] File not found: {args.source}", COLOR_FAIL)
            sys.exit(1)
        print_colored(f"[*] Reading file '{args.source}'...", COLOR_CYAN)
        try:
            with open(args.source, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print_colored(f"[!] Failed to read file: {e}", COLOR_FAIL)
            sys.exit(1)
            
    # Parse content
    print_colored("[*] Parsing content...", COLOR_CYAN)
    if args.xml:
        try:
            root = ET.fromstring(content)
        except Exception as e:
            print_colored(f"[!] XML Parsing Error: {e}", COLOR_FAIL)
            sys.exit(1)
    else:
        builder = HTMLToElementTreeBuilder()
        builder.feed(content)
        root = builder.root
        
    # Evaluate XPath
    # Note: ElementTree's xpath support is basic compared to lxml, but it supports standard paths
    # like .//tag, .//tag[@attrib], etc.
    # To support /text() we check if path ends with /text()
    xpath_query = args.xpath
    get_text_only = False
    get_attrib = None
    
    if xpath_query.endswith("/text()"):
        xpath_query = xpath_query[:-7]
        get_text_only = True
    elif "/@" in xpath_query:
        parts = xpath_query.split("/@")
        xpath_query = parts[0]
        get_attrib = parts[1]
        
    print_colored(f"[*] Evaluating XPath query: '{xpath_query}'", COLOR_CYAN)
    
    try:
        # If query is absolute (starts with /), ElementTree needs relative format (starts with .)
        if xpath_query.startswith("/"):
            query_to_run = "." + xpath_query
        else:
            query_to_run = xpath_query
            
        matches = root.findall(query_to_run)
    except Exception as e:
        print_colored(f"[!] XPath Evaluation Error: {e}", COLOR_FAIL)
        print("Note: ElementTree supports standard relative syntax (e.g., './/div[@class=\"name\"]')")
        sys.exit(1)
        
    if not matches:
        print_colored("[*] No matching elements found.", COLOR_WARNING)
        sys.exit(0)
        
    print_colored(f"\n[+] Found {len(matches)} matching node(s):", COLOR_GREEN)
    print_colored("=" * 60, COLOR_BLUE)
    
    for idx, match in enumerate(matches, 1):
        print_colored(f"Match #{idx}:", COLOR_BOLD + COLOR_CYAN)
        if get_text_only:
            txt = match.text.strip() if match.text else ""
            print(txt)
        elif get_attrib:
            val = match.get(get_attrib)
            if val is not None:
                print(f"{get_attrib} = {val}")
            else:
                print(f"[Attribute '{get_attrib}' not present on element]")
        else:
            try:
                print(serialize_element(match))
            except Exception:
                print(ET.tostring(match, encoding="utf-8").decode("utf-8", errors="ignore"))
        print_colored("-" * 60, COLOR_BLUE)


if __name__ == "__main__":
    main()
