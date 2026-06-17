#!/usr/bin/env python3
"""
HTML Link Extractor
Parses HTML files using the standard library to extract and categorize
hyperlinks, images, stylesheets, and scripts, exporting them to JSON, CSV, or text.
"""

import sys
import os
import json
import csv
import argparse
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

class LinkExtractionParser(HTMLParser):
    """HTML Parser that collects links, images, styles, and scripts."""
    def __init__(self, base_url=None):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.images = []
        self.styles = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Hyperlinks: <a href="...">
        if tag == 'a' and 'href' in attrs_dict:
            url = attrs_dict['href'].strip()
            if url:
                abs_url = urljoin(self.base_url, url) if self.base_url else url
                text = attrs_dict.get('title', '').strip()
                self.links.append({'raw': url, 'resolved': abs_url, 'tag': tag, 'attr': 'href'})

        # Images: <img src="...">
        elif tag == 'img' and 'src' in attrs_dict:
            url = attrs_dict['src'].strip()
            if url:
                abs_url = urljoin(self.base_url, url) if self.base_url else url
                self.images.append({'raw': url, 'resolved': abs_url, 'tag': tag, 'attr': 'src'})

        # Stylesheets: <link rel="stylesheet" href="...">
        elif tag == 'link' and attrs_dict.get('rel') == 'stylesheet' and 'href' in attrs_dict:
            url = attrs_dict['href'].strip()
            if url:
                abs_url = urljoin(self.base_url, url) if self.base_url else url
                self.styles.append({'raw': url, 'resolved': abs_url, 'tag': tag, 'attr': 'href'})

        # Scripts: <script src="...">
        elif tag == 'script' and 'src' in attrs_dict:
            url = attrs_dict['src'].strip()
            if url:
                abs_url = urljoin(self.base_url, url) if self.base_url else url
                self.scripts.append({'raw': url, 'resolved': abs_url, 'tag': tag, 'attr': 'src'})

def export_csv(data, output_path):
    """Export list of links to a CSV file."""
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Type", "Raw URL", "Resolved URL", "HTML Tag", "Attribute"])
            for category, items in data.items():
                for item in items:
                    writer.writerow([category, item['raw'], item['resolved'], item['tag'], item['attr']])
        print(f"Exported CSV results to '{output_path}'")
        return True
    except Exception as e:
        print(f"Error exporting CSV to '{output_path}': {e}", file=sys.stderr)
        return False

def export_json(data, output_path):
    """Export results to a JSON file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Exported JSON results to '{output_path}'")
        return True
    except Exception as e:
        print(f"Error exporting JSON to '{output_path}': {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="HTML Link Extractor - Extract links, images, styles, and scripts from HTML files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("html_file", help="Path to the HTML file to parse")
    parser.add_argument("--base-url", "-b", help="Base URL to resolve relative paths (e.g. https://example.com/)")
    parser.add_argument("--type", "-t", choices=['all', 'links', 'images', 'styles', 'scripts'], default='all',
                        help="Filter output by resource type (default: all)")
    parser.add_argument("--export", "-e", choices=['json', 'csv', 'txt'], help="Export format")
    parser.add_argument("--output", "-o", help="Path to output file for export")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.html_file):
        print(f"Error: HTML file '{args.html_file}' does not exist.", file=sys.stderr)
        return 1
        
    try:
        with open(args.html_file, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
    except Exception as e:
        print(f"Error reading HTML file: {e}", file=sys.stderr)
        return 1
        
    parser_instance = LinkExtractionParser(base_url=args.base_url)
    parser_instance.feed(html_content)
    
    # Structure collected data
    data = {}
    if args.type in ('all', 'links'):
        data['links'] = parser_instance.links
    if args.type in ('all', 'images'):
        data['images'] = parser_instance.images
    if args.type in ('all', 'styles'):
        data['styles'] = parser_instance.styles
    if args.type in ('all', 'scripts'):
        data['scripts'] = parser_instance.scripts
        
    # Standard terminal output
    if not args.export:
        for category, items in data.items():
            print(f"=== Extracted {category.capitalize()} ({len(items)}) ===")
            for item in items:
                res = f" -> {item['resolved']}" if item['resolved'] != item['raw'] else ""
                print(f"  {item['raw']}{res}")
            print()
            
    # Export output
    if args.export:
        if not args.output:
            print("Error: Export format specified, but no --output file path provided.", file=sys.stderr)
            return 1
            
        if args.export == 'json':
            export_json(data, args.output)
        elif args.export == 'csv':
            export_csv(data, args.output)
        elif args.export == 'txt':
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    for category, items in data.items():
                        f.write(f"=== {category.upper()} ===\n")
                        for item in items:
                            f.write(f"{item['resolved']}\n")
                        f.write("\n")
                print(f"Exported text results to '{args.output}'")
            except Exception as e:
                print(f"Error exporting txt to '{args.output}': {e}", file=sys.stderr)
                return 1
                
    return 0

if __name__ == "__main__":
    sys.exit(main())
