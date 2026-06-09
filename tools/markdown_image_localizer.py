#!/usr/bin/env python3
"""
Markdown Image Localizer

Parses a Markdown file, downloads all remote image URLs (http/https) referenced
within it, saves them to a local assets folder, and updates the Markdown file
references to point to the local copies.

Usage:
    python tools/markdown_image_localizer.py path/to/document.md [--output-dir assets] [--dry-run]
"""

import argparse
import hashlib
import os
import re
import sys
import urllib.parse
import urllib.request

# Regular expressions for markdown images and HTML image tags
MARKDOWN_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\((https?://[^\s\)]+)\)')
HTML_IMAGE_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE)

def get_image_filename(url, index):
    """Generate a clean and safe filename for the image."""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    
    # Try to extract the extension
    base = os.path.basename(path)
    name, ext = os.path.splitext(base)
    
    # Standardize image extensions or default to png
    ext = ext.lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']:
        ext = '.png'
        
    # Generate unique name using URL hash to avoid collisions
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    
    # Clean the name to be safe
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    if not clean_name:
        clean_name = f"image_{index}"
        
    return f"{clean_name}_{url_hash}{ext}"

def download_image(url, filepath):
    """Download image with a standard User-Agent header."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Download remote images from a Markdown file and localize their paths.")
    parser.add_argument('markdown_file', help='Path to the Markdown file')
    parser.add_argument('-o', '--output-dir', default='images', help='Directory to save the downloaded images (default: images)')
    parser.add_argument('-d', '--dry-run', action='store_true', help='Scan for remote images without downloading or modifying files')
    parser.add_argument('--inplace', action='store_true', help='Overwrite the original markdown file directly instead of creating a *.local.md copy')
    args = parser.parse_args()

    if not os.path.isfile(args.markdown_file):
        print(f"Error: Markdown file '{args.markdown_file}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(args.markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # Find all unique remote image URLs
    md_images = MARKDOWN_IMAGE_RE.findall(content)
    html_images = HTML_IMAGE_RE.findall(content)
    
    # Extract only the URL part from markdown matches
    remote_urls = set([url for _, url in md_images] + html_images)
    
    if not remote_urls:
        print("No remote images found in the markdown file.")
        return 0

    print(f"Found {len(remote_urls)} unique remote image URL(s) to localize:")
    for url in remote_urls:
        print(f" - {url}")

    if args.dry_run:
        print("\nDry-run mode. No files were modified.")
        return 0

    # Ensure output directory exists
    # Create output dir relative to the markdown file's directory
    md_dir = os.path.dirname(os.path.abspath(args.markdown_file))
    target_dir = os.path.join(md_dir, args.output_dir)
    
    os.makedirs(target_dir, exist_ok=True)
    print(f"\nImages will be saved to: {target_dir}")

    # Process and download images
    url_to_local_map = {}
    downloaded_count = 0
    failed_count = 0
    
    for i, url in enumerate(sorted(remote_urls), start=1):
        filename = get_image_filename(url, i)
        filepath = os.path.join(target_dir, filename)
        
        # Local path relative to the markdown file for inclusion
        relative_path = os.path.join(args.output_dir, filename).replace('\\', '/')
        
        print(f"[{i}/{len(remote_urls)}] Downloading image...")
        if download_image(url, filepath):
            url_to_local_map[url] = relative_path
            downloaded_count += 1
        else:
            failed_count += 1

    # Update markdown content
    new_content = content
    
    # 1. Update Markdown format: ![alt](url)
    def md_replace(match):
        alt, url = match.group(1), match.group(2)
        if url in url_to_local_map:
            return f"![{alt}]({url_to_local_map[url]})"
        return match.group(0)
    
    new_content = MARKDOWN_IMAGE_RE.sub(md_replace, new_content)
    
    # 2. Update HTML format: <img src="url">
    def html_replace(match):
        url = match.group(1)
        if url in url_to_local_map:
            # Reconstruct the img tag with updated src
            orig = match.group(0)
            return orig.replace(url, url_to_local_map[url])
        return match.group(0)

    new_content = HTML_IMAGE_RE.sub(html_replace, new_content)

    # Save output file
    if args.inplace:
        output_file = args.markdown_file
    else:
        base, ext = os.path.splitext(args.markdown_file)
        output_file = f"{base}.local{ext}"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"\nLocal copy saved to: {output_file}")
    except Exception as e:
        print(f"Error saving modified markdown file: {e}", file=sys.stderr)
        return 1

    print("\nSummary:")
    print(f" - Total remote images identified: {len(remote_urls)}")
    print(f" - Successfully downloaded & updated: {downloaded_count}")
    print(f" - Failed downloads (kept original URLs): {failed_count}")
    
    return 0 if failed_count == 0 else 2

if __name__ == "__main__":
    sys.exit(main())
