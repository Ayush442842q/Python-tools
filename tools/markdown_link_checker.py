#!/usr/bin/env python3
"""
Markdown Link Checker

Scans markdown (.md) files in a directory for broken links.
Checks both relative local file paths and external HTTP/HTTPS URLs.

Usage:
    python markdown_link_checker.py [path] [options]
"""

import os
import sys
import re
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Regular expressions for markdown links
# Matches standard links: [text](url)
STANDARD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
# Matches reference links: [text]: url
REFERENCE_LINK_RE = re.compile(r'^\[([^\]]+)\]:\s*(\S+)', re.MULTILINE)

def check_local_link(base_path, link_path):
    """Verify if a local relative file/directory link exists."""
    # Clean query parameters or anchors
    clean_path = link_path.split('#')[0].split('?')[0]
    if not clean_path:
        # Self-referencing anchor link, e.g. [header](#header)
        return True
    
    # URL unescape (e.g. %20 -> space)
    clean_path = urllib.parse.unquote(clean_path)
    
    # Check if path is absolute relative to root or relative to the markdown file
    target_path = Path(base_path).parent / clean_path
    return target_path.exists()

def check_external_url(url, timeout=5):
    """Verify if an external HTTP/HTTPS link is reachable."""
    try:
        # Build request with a User-Agent to avoid generic blocking
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python-LinkChecker/1.0'}
        )
        # Try HEAD request first to save bandwidth
        req.method = 'HEAD'
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status < 400
    except urllib.error.HTTPError as e:
        # Some servers block HEAD requests, retry with GET
        if e.code in [404, 403, 405]:
            try:
                req.method = 'GET'
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.status < 400
            except Exception:
                return False
        return False
    except Exception:
        return False

def scan_markdown_file(file_path, check_external=False, timeout=5):
    """Scan a markdown file and return a list of broken links."""
    broken_links = []
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    # Find standard links
    links = [match[1] for match in STANDARD_LINK_RE.findall(content)]
    # Find reference links
    links.extend([match[1] for match in REFERENCE_LINK_RE.findall(content)])
    
    # Filter and check links
    for link in links:
        link = link.strip()
        
        # Skip mailto, tel, javascript links
        if link.startswith(('mailto:', 'tel:', 'javascript:')):
            continue
            
        is_external = link.startswith(('http://', 'https://'))
        
        if is_external:
            if check_external:
                if not check_external_url(link, timeout):
                    broken_links.append((link, "Broken external URL"))
        else:
            # Local link
            if not check_local_link(file_path, link):
                broken_links.append((link, "Local path not found"))
                
    return broken_links

def main():
    parser = argparse.ArgumentParser(
        description="Scan markdown files in a directory for broken links.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to scan (file or directory). Defaults to current directory."
    )
    parser.add_argument(
        "--external", "-e",
        action="store_true",
        help="Check external HTTP/HTTPS links (can be slow)."
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=5,
        help="Timeout in seconds for external URL checks (default: 5)."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show OK files and progress details."
    )
    
    args = parser.parse_args()
    
    target_path = Path(args.path).resolve()
    if not target_path.exists():
        print(f"Error: Path '{args.path}' does not exist.")
        return 1
        
    md_files = []
    if target_path.is_file():
        if target_path.suffix.lower() == '.md':
            md_files.append(target_path)
    else:
        # Recursively find markdown files
        md_files = list(target_path.rglob('*.md'))
        
    if not md_files:
        print("No markdown (.md) files found to scan.")
        return 0
        
    print(f"Found {len(md_files)} markdown file(s) to scan.")
    if args.external:
        print("External link checking is enabled. This may take a while...")
        
    total_broken = 0
    scanned_files = 0
    
    for md_file in md_files:
        scanned_files += 1
        rel_path = os.path.relpath(md_file, start=os.getcwd())
        if args.verbose:
            print(f"Scanning {rel_path}...", end="", flush=True)
            
        broken = scan_markdown_file(md_file, args.external, args.timeout)
        
        if broken:
            if not args.verbose:
                print(f"Broken links in {rel_path}:")
            else:
                print(" FAIL")
                
            for link, reason in broken:
                print(f"  - [{reason}] -> {link}")
            total_broken += len(broken)
        elif args.verbose:
            print(" OK")
            
    print("\n--- Summary ---")
    print(f"Scanned files: {scanned_files}")
    print(f"Total broken links: {total_broken}")
    
    return 1 if total_broken > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
