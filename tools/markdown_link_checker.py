#!/usr/bin/env python3
"""
Markdown Link Checker

Extracts and checks the validity of links in a Markdown file.
Supports checking local relative file paths and HTTP/HTTPS URLs.

Usage:
    python tools/markdown_link_checker.py document.md [--online]
"""

import argparse
import os
import re
import sys
import urllib.request
import urllib.error

def extract_links(markdown_content):
    # Match standard Markdown links: [text](url)
    # Ignore images: ![text](url) by making sure there's no preceding '!'
    pattern = r'(?<!\!)\[([^\]]+)\]\(([^)]+)\)'
    return re.findall(pattern, markdown_content)

def check_local_link(base_path, target_path):
    # Resolve relative path based on the markdown file's directory
    dir_name = os.path.dirname(base_path)
    # Remove anchors like #section
    clean_target = target_path.split('#')[0]
    if not clean_target:
        return True # Just an anchor to the same file
    
    full_path = os.path.join(dir_name, clean_target)
    return os.path.exists(full_path)

def check_online_link(url, timeout=5):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status in (200, 301, 302)
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Markdown Link Checker")
    parser.add_argument('file', help='Path to the Markdown file to check')
    parser.add_argument('--online', action='store_true', help='Verify HTTP/HTTPS links online')
    parser.add_argument('--timeout', type=int, default=5, help='Timeout in seconds for online checks')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        return 1

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return 1

    links = extract_links(content)
    if not links:
        print("No links found in the file.")
        return 0

    print(f"Found {len(links)} link(s) in '{args.file}':\n")
    
    broken_count = 0
    checked_count = 0

    for text, url in links:
        checked_count += 1
        is_web_url = url.startswith(('http://', 'https://'))
        
        status = "UNKNOWN"
        is_valid = True

        if is_web_url:
            if args.online:
                is_valid = check_online_link(url, args.timeout)
                status = "VALID" if is_valid else "BROKEN"
            else:
                status = "SKIPPED (use --online)"
        else:
            # Handle local file links (ignoring absolute/system links and mailto/anchors)
            if url.startswith('mailto:') or url.startswith('javascript:'):
                status = "SKIPPED (special protocol)"
            else:
                is_valid = check_local_link(args.file, url)
                status = "VALID" if is_valid else "BROKEN"

        if not is_valid:
            broken_count += 1
            print(f"[Broken] [{text}]({url}) -> {status}")
        else:
            print(f"[OK] [{text}]({url}) -> {status}")

    print("\nSummary:")
    print(f"  Total links checked: {checked_count}")
    print(f"  Broken links: {broken_count}")

    return 1 if broken_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
