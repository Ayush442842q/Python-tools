#!/usr/bin/env python3
"""
Web Asset Extractor & Downloader

Crawls a target webpage, extracts all linked media assets (images, stylesheets, 
scripts, documents), and downloads them into organized local subdirectories. 
Also rewrites the local HTML to link to downloaded local assets.

Usage:
    python tools/web_asset_downloader.py <url> --output-dir <dir_path> [options]

Example:
    python tools/web_asset_downloader.py https://example.com --output-dir example_page --no-scripts
"""

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Set, Tuple

# Default User-Agent to avoid simple bot blocks
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class AssetParser(HTMLParser):
    """Parses HTML to find asset links and tags."""
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.assets: Dict[str, Set[str]] = {
            'images': set(),
            'css': set(),
            'js': set(),
            'links': set()
        }

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        attrs_dict = dict(attrs)
        
        # 1. Images
        if tag == 'img' and 'src' in attrs_dict:
            src = attrs_dict['src']
            if src.strip():
                self.assets['images'].add(self.resolve_url(src))
                
        # 2. Stylesheets
        if tag == 'link' and attrs_dict.get('rel') == 'stylesheet' and 'href' in attrs_dict:
            href = attrs_dict['href']
            if href.strip():
                self.assets['css'].add(self.resolve_url(href))
                
        # 3. Scripts
        if tag == 'script' and 'src' in attrs_dict:
            src = attrs_dict['src']
            if src.strip():
                self.assets['js'].add(self.resolve_url(src))
                
        # 4. Other interesting tags (source, track, embed)
        if tag in ('source', 'embed') and 'src' in attrs_dict:
            src = attrs_dict['src']
            if src.strip():
                self.assets['images'].add(self.resolve_url(src))

    def resolve_url(self, url: str) -> str:
        """Converts relative URLs to absolute URLs using the base URL."""
        return urllib.parse.urljoin(self.base_url, url)

def download_file(url: str, dest_path: str, user_agent: str) -> bool:
    """Downloads a file from a URL to a local destination."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': user_agent}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}", file=sys.stderr)
        return False

def sanitize_filename(url: str) -> str:
    """Generates a safe local filename based on URL path."""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if not path or path.endswith('/'):
        path += 'index'
        
    filename = os.path.basename(path)
    
    # Remove query string parameters and fragment
    filename = filename.split('?')[0].split('#')[0]
    
    # Make filename safe
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    # Make sure we don't have empty name
    if not filename:
        filename = "asset"
        
    return filename

def main() -> int:
    parser = argparse.ArgumentParser(description="Download webpage and organize all its external assets locally.")
    parser.add_argument("url", help="URL of the webpage to scrape and download")
    parser.add_argument("-o", "--output-dir", required=True, help="Local directory to store assets and index.html")
    parser.add_argument("--no-images", action="store_true", help="Do not download images")
    parser.add_argument("--no-css", action="store_true", help="Do not download CSS files")
    parser.add_argument("--no-js", action="store_true", help="Do not download JavaScript files")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent header value")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress status")
    
    args = parser.parse_args()
    
    # Create target directories
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    
    subdirs = {
        'images': os.path.join(out_dir, 'images'),
        'css': os.path.join(out_dir, 'css'),
        'js': os.path.join(out_dir, 'js')
    }
    
    for folder in subdirs.values():
        os.makedirs(folder, exist_ok=True)
        
    url = args.url
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    print(f"Fetching main page: {url}")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': args.user_agent}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            html_content = response.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error fetching main page: {e}", file=sys.stderr)
        return 1
        
    # Parse HTML for assets
    parser_instance = AssetParser(url)
    parser_instance.feed(html_content)
    
    # Maps of: absolute_url -> local_relative_path
    rewrites: Dict[str, str] = {}
    
    # 1. Download images
    if not args.no_images:
        print(f"Downloading {len(parser_instance.assets['images'])} images...")
        for img_url in sorted(parser_instance.assets['images']):
            # Filter non-HTTP(S) URLs (e.g. data:image, about:blank)
            if not img_url.startswith(('http://', 'https://')):
                continue
            name = sanitize_filename(img_url)
            # Handle duplicates
            dest = os.path.join(subdirs['images'], name)
            counter = 1
            while os.path.exists(dest):
                base, ext = os.path.splitext(name)
                dest = os.path.join(subdirs['images'], f"{base}_{counter}{ext}")
                counter += 1
            
            if args.verbose:
                print(f"Downloading image: {img_url} -> {os.path.basename(dest)}")
                
            if download_file(img_url, dest, args.user_agent):
                rewrites[img_url] = f"images/{os.path.basename(dest)}"
                
    # 2. Download CSS
    if not args.no_css:
        print(f"Downloading {len(parser_instance.assets['css'])} CSS files...")
        for css_url in sorted(parser_instance.assets['css']):
            if not css_url.startswith(('http://', 'https://')):
                continue
            name = sanitize_filename(css_url)
            if not name.endswith('.css'):
                name += '.css'
            dest = os.path.join(subdirs['css'], name)
            counter = 1
            while os.path.exists(dest):
                base, ext = os.path.splitext(name)
                dest = os.path.join(subdirs['css'], f"{base}_{counter}{ext}")
                counter += 1
                
            if args.verbose:
                print(f"Downloading CSS: {css_url} -> {os.path.basename(dest)}")
                
            if download_file(css_url, dest, args.user_agent):
                rewrites[css_url] = f"css/{os.path.basename(dest)}"
                
    # 3. Download JS
    if not args.no_js:
        print(f"Downloading {len(parser_instance.assets['js'])} JS files...")
        for js_url in sorted(parser_instance.assets['js']):
            if not js_url.startswith(('http://', 'https://')):
                continue
            name = sanitize_filename(js_url)
            if not name.endswith('.js'):
                name += '.js'
            dest = os.path.join(subdirs['js'], name)
            counter = 1
            while os.path.exists(dest):
                base, ext = os.path.splitext(name)
                dest = os.path.join(subdirs['js'], f"{base}_{counter}{ext}")
                counter += 1
                
            if args.verbose:
                print(f"Downloading JS: {js_url} -> {os.path.basename(dest)}")
                
            if download_file(js_url, dest, args.user_agent):
                rewrites[js_url] = f"js/{os.path.basename(dest)}"
                
    # Rewrite HTML references
    print("Rewriting HTML content with local asset links...")
    rewritten_html = html_content
    for remote_url, local_rel_path in rewrites.items():
        # Escape for safe replacement in HTML
        # Resolve common variants of URL references:
        # 1. As absolute url: http://domain.com/path/file.png
        # 2. Or relative path if it matches what was in HTML: /path/file.png
        # We replace the remote_url itself first:
        rewritten_html = rewritten_html.replace(remote_url, local_rel_path)
        
        # Parse path out to also catch relative path tags in HTML
        parsed_remote = urllib.parse.urlparse(remote_url)
        # Catch relative root path
        if parsed_remote.path:
            rewritten_html = rewritten_html.replace(parsed_remote.path, local_rel_path)
            # Catch relative query path
            raw_path_query = parsed_remote.path + (f"?{parsed_remote.query}" if parsed_remote.query else "")
            rewritten_html = rewritten_html.replace(raw_path_query, local_rel_path)
            
    # Write output file
    index_path = os.path.join(out_dir, 'index.html')
    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(rewritten_html)
        print(f"Finished! Main index file written to {index_path}")
        print(f"Assets stored in: {out_dir}")
    except Exception as e:
        print(f"Error saving index.html: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
