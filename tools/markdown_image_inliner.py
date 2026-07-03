#!/usr/bin/env python3
"""
Markdown Image Inliner
----------------------
Scans Markdown files for local (and optionally remote) image links,
converts the images into Base64-encoded Data URIs, and updates
the references inline. This renders the Markdown files fully self-contained.

Author: Antigravity
License: MIT
"""

import os
import re
import sys
import base64
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Regex for Markdown images: ![alt](url)
IMAGE_REGEX = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.ico': 'image/x-icon'
}

def print_status(message, color=RESET, prefix="[*]"):
    print(f"{color}{prefix} {message}{RESET}")

def get_mime_type(filepath_or_url):
    ext = os.path.splitext(filepath_or_url.split('?')[0].lower())[1]
    return MIME_TYPES.get(ext, 'application/octet-stream')

def download_remote_image(url, timeout=10):
    """Downloads remote image and returns (bytes, mime_type)."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            # Try to get mime type from response headers first
            content_type = response.headers.get('Content-Type')
            if content_type and content_type.startswith('image/'):
                return data, content_type
            return data, get_mime_type(url)
    except Exception as e:
        raise RuntimeError(f"Failed downloading {url}: {e}")

def convert_to_base64_uri(image_data, mime_type):
    b64_str = base64.b64encode(image_data).decode('utf-8')
    return f"data:{mime_type};base64,{b64_str}"

def process_markdown_content(content, file_dir, inline_remote, timeout):
    """Parses content, encodes images, returns updated content and stats."""
    inlined_count = 0
    skipped_count = 0
    error_count = 0
    
    # We use a mutable container to track changes
    def replacer(match):
        nonlocal inlined_count, skipped_count, error_count
        alt_text = match.group(1)
        url_or_path = match.group(2).strip()
        
        # Check if already a Data URI
        if url_or_path.startswith('data:image/'):
            skipped_count += 1
            return match.group(0)
            
        is_remote = url_or_path.startswith(('http://', 'https://'))
        
        try:
            if is_remote:
                if not inline_remote:
                    skipped_count += 1
                    return match.group(0)
                print_status(f"Downloading remote image: {url_or_path}", BLUE)
                img_data, mime_type = download_remote_image(url_or_path, timeout)
            else:
                # Local file path resolution relative to the Markdown file directory
                # Strip URL decoding in case path was URL-encoded
                decoded_path = urllib.parse.unquote(url_or_path)
                local_path = Path(file_dir) / decoded_path
                
                if not local_path.exists():
                    print_status(f"Local file not found: {url_or_path} (Resolved: {local_path})", RED, "[-]")
                    error_count += 1
                    return match.group(0)
                    
                print_status(f"Reading local image: {decoded_path}", BLUE)
                with open(local_path, 'rb') as f:
                    img_data = f.read()
                mime_type = get_mime_type(str(local_path))
            
            b64_uri = convert_to_base64_uri(img_data, mime_type)
            inlined_count += 1
            return f"![{alt_text}]({b64_uri})"
            
        except Exception as e:
            print_status(f"Error inlining {url_or_path}: {e}", RED, "[-]")
            error_count += 1
            return match.group(0)
            
    updated_content = IMAGE_REGEX.sub(replacer, content)
    return updated_content, inlined_count, skipped_count, error_count

def process_file(filepath, inline_remote, backup, dry_run, timeout):
    print_status(f"Processing file: {filepath}", BOLD)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        file_dir = os.path.dirname(os.path.abspath(filepath))
        updated_content, inlined, skipped, errors = process_markdown_content(
            content, file_dir, inline_remote, timeout
        )
        
        if inlined > 0:
            if dry_run:
                print_status(f"[DRY-RUN] Would inline {inlined} images in {filepath}", GREEN, "[+]")
            else:
                if backup:
                    backup_path = filepath + ".bak"
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print_status(f"Backup created: {backup_path}", YELLOW)
                    
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                print_status(f"Successfully inlined {inlined} images in {filepath}", GREEN, "[+]")
        else:
            print_status(f"No changes made to {filepath} (Skipped: {skipped}, Errors: {errors})")
            
        return inlined, skipped, errors
    except Exception as e:
        print_status(f"Error processing {filepath}: {e}", RED, "[-]")
        return 0, 0, 1

def main():
    parser = argparse.ArgumentParser(
        description="Scan Markdown files and inline images as Base64 Data URIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="Path to markdown file or directory containing markdown files.")
    parser.add_argument("--remote", action="store_true", help="Download and inline remote images (http/https).")
    parser.add_argument("--backup", action="store_true", help="Create a backup file (.bak) before modifying.")
    parser.add_argument("--dry-run", action="store_true", help="Preview which files and images would be inlined without modifying them.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds for remote downloads.")
    parser.add_argument("--recursive", "-r", action="store_true", help="Process directories recursively.")
    
    args = parser.parse_args()
    
    target_path = Path(args.path)
    if not target_path.exists():
        print_status(f"Path does not exist: {args.path}", RED, "[-]")
        sys.exit(1)
        
    markdown_files = []
    if target_path.is_file():
        markdown_files.append(target_path)
    else:
        pattern = "**/*.md" if args.recursive else "*.md"
        markdown_files.extend(target_path.glob(pattern))
        
    if not markdown_files:
        print_status("No Markdown (.md) files found.", YELLOW)
        sys.exit(0)
        
    print_status(f"Found {len(markdown_files)} Markdown file(s) to scan.", BOLD)
    
    total_inlined = 0
    total_skipped = 0
    total_errors = 0
    
    for filepath in markdown_files:
        inlined, skipped, errors = process_file(
            str(filepath), args.remote, args.backup, args.dry_run, args.timeout
        )
        total_inlined += inlined
        total_skipped += skipped
        total_errors += errors
        print("-" * 50)
        
    print_status("Processing Summary:", BOLD)
    print(f"  Inlined: {GREEN}{total_inlined}{RESET}")
    print(f"  Skipped: {YELLOW}{total_skipped}{RESET}")
    print(f"  Errors:  {RED}{total_errors}{RESET}")

if __name__ == "__main__":
    main()
