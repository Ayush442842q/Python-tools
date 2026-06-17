#!/usr/bin/env python3
"""
Markdown Image Localizer

Scan a Markdown file for remote image links (http/https), download them
locally, and update the references in the Markdown file to point to local paths.

Usage:
    python tools/markdown_image_localizer.py <markdown_file> [options]

Requirements:
    - Python 3.6+
"""

import os
import sys
import re
import argparse
import urllib.request
import urllib.parse
import hashlib

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def sanitize_filename(filename):
    """Sanitize the filename to be safe for saving on disk."""
    # Remove query parameters if any
    filename = filename.split("?")[0].split("#")[0]
    # Keep only alphanumeric, hyphens, underscores, and dots
    filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    return filename

def download_image(url, output_dir, use_color=True):
    """Download an image from a URL and save it to the output directory."""
    try:
        # Generate a clean filename
        parsed_url = urllib.parse.urlparse(url)
        path_segments = parsed_url.path.split("/")
        filename = path_segments[-1] if path_segments[-1] else "image"
        
        filename = sanitize_filename(filename)
        # Add an extension if none exists
        if "." not in filename:
            filename += ".png"
            
        dest_path = os.path.join(output_dir, filename)
        
        # Resolve naming conflicts
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dest_path):
            filename = f"{base}_{counter}{ext}"
            dest_path = os.path.join(output_dir, filename)
            counter += 1
            
        # Download the file
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ImageDownloader/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(dest_path, "wb") as f:
                f.write(response.read())
                
        return filename, None
    except Exception as e:
        return None, str(e)

def localize_images(md_file, output_dir, inplace, use_color=True):
    """Scan and localize images in a markdown file."""
    if not os.path.exists(md_file):
        return f"Markdown file not found: {md_file}"
        
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading markdown file: {e}"

    # Regex pattern to match markdown image syntax: ![alt](url)
    # Group 1 is the alt text, Group 2 is the image URL
    img_pattern = re.compile(r'\!\[(.*?)\]\(((https?://\S+?))\)')
    
    matches = img_pattern.findall(content)
    if not matches:
        print_colored("No remote images found in the markdown file.", YELLOW, use_color)
        return None

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Found {len(matches)} remote image references.")
    print(f"Saving downloaded images to: {os.path.abspath(output_dir)}")

    updated_content = content
    downloaded_count = 0
    failed_count = 0

    # Avoid downloading duplicates in the same run
    url_to_local_path = {}

    for alt, url, _ in matches:
        if url in url_to_local_path:
            local_path = url_to_local_path[url]
            # Replace reference in content
            # Escape parenthesis and brackets in URL to safely replace
            escaped_url = re.escape(url)
            updated_content = re.sub(r'\!\[(' + re.escape(alt) + r')\]\(' + escaped_url + r'\)', f'![\\1]({local_path})', updated_content)
            continue
            
        print(f"Downloading: {url} ... ", end="", flush=True)
        filename, err = download_image(url, output_dir, use_color)
        if filename:
            # We want to reference it relative to the Markdown file directory
            # For simplicity, we assume output_dir is relative to target location
            local_rel_path = os.path.join(os.path.basename(output_dir), filename).replace("\\", "/")
            url_to_local_path[url] = local_rel_path
            
            escaped_url = re.escape(url)
            updated_content = re.sub(r'\!\[(' + re.escape(alt) + r')\]\(' + escaped_url + r'\)', f'![\\1]({local_rel_path})', updated_content)
            
            print_colored("Done", GREEN, use_color)
            downloaded_count += 1
        else:
            print_colored(f"Failed ({err})", RED, use_color)
            failed_count += 1

    # Save output
    if inplace:
        out_file = md_file
    else:
        base, ext = os.path.splitext(md_file)
        out_file = f"{base}_localized{ext}"

    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print_colored(f"\nSaved updated markdown to: {out_file}", GREEN, use_color)
    except Exception as e:
        return f"Error writing updated markdown file: {e}"

    print(f"Summary: {downloaded_count} downloaded successfully, {failed_count} failed.")
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Localize remote images referenced in a Markdown file.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the Markdown file (.md)")
    parser.add_argument(
        "-o", "--output-dir", 
        default="images", 
        help="Directory to save downloaded images (default: 'images')"
    )
    parser.add_argument(
        "-i", "--inplace", 
        action="store_true", 
        help="Overwrite the original Markdown file (default is to save as file_localized.md)"
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    # Determine real output directory path relative to the markdown file
    md_dir = os.path.dirname(os.path.abspath(args.file))
    target_output_dir = os.path.join(md_dir, args.output_dir)

    err = localize_images(args.file, target_output_dir, args.inplace, use_color)
    if err:
        print_colored(f"Error: {err}", RED, use_color)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
