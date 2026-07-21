#!/usr/bin/env python3
"""
Web Archiver - Bundle a web page and its assets into a single self-contained HTML file

This tool fetches a URL and archives its content. It parses the HTML to find external
images, stylesheets, and scripts, fetches them, and embeds them inline (using base64
for images) to produce a single offline-viewable .html file.

Usage:
    python tools/web_archiver.py <url> [--output OUTPUT_FILE]

Example:
    python tools/web_archiver.py https://example.com --output tools/example_archived.html
"""

import argparse
import base64
import os
import re
import sys
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple

class AssetExtractor(HTMLParser):
    """HTML Parser to extract asset URLs from img, link, and script tags."""
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.images: Set[str] = set()
        self.stylesheets: Set[str] = set()
        self.scripts: Set[str] = set()

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        attrs_dict = dict(attrs)
        
        if tag == "img" and "src" in attrs_dict:
            src = attrs_dict["src"]
            if not src.startswith("data:"):
                abs_url = urllib.parse.urljoin(self.base_url, src)
                self.images.add(abs_url)
                
        elif tag == "link" and attrs_dict.get("rel") == "stylesheet" and "href" in attrs_dict:
            href = attrs_dict["href"]
            abs_url = urllib.parse.urljoin(self.base_url, href)
            self.stylesheets.add(abs_url)
            
        elif tag == "script" and "src" in attrs_dict:
            src = attrs_dict["src"]
            abs_url = urllib.parse.urljoin(self.base_url, src)
            self.scripts.add(abs_url)

def fetch_asset(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Fetch an asset and return its binary content and content-type."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WebArchiver/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read()
            content_type = response.info().get_content_type()
            return content, content_type
    except Exception as e:
        print(f"Warning: Failed to fetch asset '{url}': {e}", file=sys.stderr)
        return None, None

def get_image_mimetype(content_type: Optional[str], url: str) -> str:
    """Infer image mime-type from content type headers or file extension."""
    if content_type:
        return content_type
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower().strip(".")
    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"
    elif ext in ["png", "gif", "svg", "webp", "bmp", "ico"]:
        return f"image/{ext}"
    return "image/png"

def archive_page(url: str) -> str:
    """Download page and inline all its external CSS, JS, and image assets."""
    print(f"Fetching main page: {url}...")
    html_bytes, _ = fetch_asset(url)
    if not html_bytes:
        raise ValueError("Could not download the main page HTML content.")
        
    html = html_bytes.decode("utf-8", errors="replace")
    
    # Extract assets
    extractor = AssetExtractor(url)
    extractor.feed(html)
    
    # Fetch and inline stylesheets
    for style_url in extractor.stylesheets:
        print(f"  Inlining stylesheet: {style_url}...")
        css_bytes, _ = fetch_asset(style_url)
        if css_bytes:
            css_text = css_bytes.decode("utf-8", errors="replace")
            # Replace link tag with style block. Make a regex to find link tag with this URL.
            # Handle variations in whitespace and attributes.
            escaped_url = re.escape(style_url.replace(url, "").strip("/"))
            pattern = rf'<link[^>]*href=["\']?[^"\'>]*{escaped_url}[^"\'>]*["\']?[^>]*>'
            
            # Simple match of the URL pattern in the link tag
            html = re.sub(
                rf'<link[^>]*href=["\']?[^"\'>]*{re.escape(urllib.parse.urlparse(style_url).path)}[^"\'>]*["\']?[^>]*>',
                f"<style>\n/* Archived from {style_url} */\n{css_text}\n</style>",
                html,
                flags=re.IGNORECASE
            )
            # Fallback direct replacement
            html = html.replace(
                style_url,
                f"data:text/css;base64,{base64.b64encode(css_bytes).decode('utf-8')}"
            )
            
    # Fetch and inline scripts
    for script_url in extractor.scripts:
        print(f"  Inlining script: {script_url}...")
        js_bytes, _ = fetch_asset(script_url)
        if js_bytes:
            js_text = js_bytes.decode("utf-8", errors="replace")
            html = html.replace(
                script_url,
                f"data:application/javascript;base64,{base64.b64encode(js_bytes).decode('utf-8')}"
            )

    # Fetch and inline images as base64 data URIs
    for img_url in extractor.images:
        print(f"  Inlining image: {img_url}...")
        img_bytes, ctype = fetch_asset(img_url)
        if img_bytes:
            mimetype = get_image_mimetype(ctype, img_url)
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            data_uri = f"data:{mimetype};base64,{b64_str}"
            # Safely replace all occurrences of this image URL in the document
            # Handles quotes surrounding the URL
            html = html.replace(img_url, data_uri)
            # Handle relative path references as parsed originally
            parsed_url = urllib.parse.urlparse(img_url)
            relative_path = parsed_url.path.lstrip("/")
            if relative_path:
                html = html.replace(relative_path, data_uri)
                
    return html

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive a web page and all its assets into a single standalone HTML file."
    )
    parser.add_argument("url", help="The web page URL to archive")
    parser.add_argument(
        "--output", "-o",
        help="Path to save the archived HTML file (default: archived_page.html)"
    )
    
    args = parser.parse_args()
    target_url = args.url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = "https://" + target_url
        
    output_file = args.output
    if not output_file:
        parsed = urllib.parse.urlparse(target_url)
        domain = parsed.netloc.replace(".", "_")
        output_file = f"archived_{domain}.html"
        
    try:
        archived_html = archive_page(target_url)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(archived_html)
        print("=" * 60)
        print(f"Successfully archived page: {target_url}")
        print(f"Output saved to: {output_file} ({len(archived_html)/1024:.1f} KB)")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"Error: Failed to archive web page: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
