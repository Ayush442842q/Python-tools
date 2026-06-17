#!/usr/bin/env python3
"""
Web Broken Link Checker - Recursively crawls a starting website URL
up to a maximum depth and checks all internal/external links for broken statuses.
Uses multi-threading for fast concurrent HTTP requests.
"""

import argparse
import concurrent.futures
from html.parser import HTMLParser
import os
import sys
import time
import urllib.parse
import urllib.request


class LinkParser(HTMLParser):
    """HTML Parser to extract all href attributes from anchor tags."""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href":
                    self.links.append(value)


def check_url(url, timeout=5):
    """Sends a HEAD or GET request to verify if a URL is accessible."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "Unsupported scheme"

    # Set User-Agent to mimic a browser
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Try HEAD request first for efficiency
    try:
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            if status < 400:
                return True, f"HTTP {status}"
    except Exception:
        # Fall back to GET if HEAD is rejected or fails
        pass

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            if status < 400:
                return True, f"HTTP {status}"
            else:
                return False, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_all_page_links(url, timeout=5):
    """Fetches the HTML of a page and extracts all hyperlinks."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Check content type is HTML
            info = response.info()
            content_type = info.get("Content-Type", "")
            if "text/html" not in content_type:
                return []
                
            html_bytes = response.read()
            html_text = html_bytes.decode("utf-8", errors="replace")
            
            parser = LinkParser()
            parser.feed(html_text)
            return parser.links
    except Exception:
        return []


def crawl_website(start_url, max_depth=2, max_workers=10, timeout=5):
    """Recursively crawls website and checks all links."""
    start_parsed = urllib.parse.urlparse(start_url)
    base_netloc = start_parsed.netloc

    # Structures to track state
    visited_pages = set()
    to_crawl = [(start_url, 0)] # (url, current_depth)
    
    # Links to verify: maps url to set of source pages where it was found
    all_found_links = {}
    
    print(f"Crawling website structure: {start_url} (depth limit: {max_depth})...")
    
    while to_crawl:
        current_url, depth = to_crawl.pop(0)
        
        # Clean URL fragments
        current_url = urllib.parse.urljoin(current_url, urllib.parse.urlparse(current_url).path)
        
        if current_url in visited_pages:
            continue
        visited_pages.add(current_url)

        # Retrieve links from page if within depth limit
        if depth <= max_depth:
            print(f"  [Crawl] Reading links on: {current_url} (depth {depth})")
            raw_links = get_all_page_links(current_url, timeout)
            
            for raw_link in raw_links:
                # Resolve relative URL
                absolute_url = urllib.parse.urljoin(current_url, raw_link)
                # Strip fragments
                absolute_url = urllib.parse.urljoin(absolute_url, urllib.parse.urlparse(absolute_url).path)
                
                # Check if it has HTTP/HTTPS scheme
                parsed_link = urllib.parse.urlparse(absolute_url)
                if parsed_link.scheme not in ("http", "https"):
                    continue

                if absolute_url not in all_found_links:
                    all_found_links[absolute_url] = set()
                all_found_links[absolute_url].add(current_url)

                # Queue internal links for crawling if we haven't visited them and not past depth limit
                if parsed_link.netloc == base_netloc and absolute_url not in visited_pages and depth < max_depth:
                    to_crawl.append((absolute_url, depth + 1))

    # Verify all unique found links concurrently
    links_to_check = list(all_found_links.keys())
    print(f"\nVerifying {len(links_to_check)} unique URL(s) using {max_workers} thread(s)...")

    broken_links = []
    success_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Map URL check tasks
        future_to_url = {executor.submit(check_url, url, timeout): url for url in links_to_check}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                is_ok, reason = future.result()
                if is_ok:
                    success_count += 1
                else:
                    sources = all_found_links[url]
                    broken_links.append((url, reason, sources))
            except Exception as e:
                sources = all_found_links[url]
                broken_links.append((url, f"Executor Error: {str(e)}", sources))

    return success_count, broken_links


def main():
    parser = argparse.ArgumentParser(
        description="Scan website to find broken links recursively."
    )
    parser.add_argument("url", help="Starting URL to crawl (must include scheme, e.g., https://example.com).")
    parser.add_argument(
        "-d", "--depth", 
        type=int, 
        default=2, 
        help="Maximum link crawling depth (default: 2)."
    )
    parser.add_argument(
        "-w", "--workers", 
        type=int, 
        default=10, 
        help="Number of concurrent validator threads (default: 10)."
    )
    parser.add_argument(
        "-t", "--timeout", 
        type=int, 
        default=5, 
        help="Timeout in seconds for HTTP requests (default: 5)."
    )

    args = parser.parse_args()

    # Simple validation of start URL format
    if not (args.url.startswith("http://") or args.url.startswith("https://")):
        print("Error: Starting URL must begin with 'http://' or 'https://'", file=sys.stderr)
        return 1

    start_time = time.time()
    success, broken = crawl_website(
        args.url, 
        max_depth=args.depth, 
        max_workers=args.workers, 
        timeout=args.timeout
    )
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print(" SCAN RESULTS SUMMARY")
    print("=" * 60)
    print(f"Scan Duration: {elapsed:.2f} seconds")
    print(f"Working Links: {success}")
    print(f"Broken Links : {len(broken)}")
    print("=" * 60)

    if broken:
        print("\nBroken links details:")
        for idx, (url, reason, sources) in enumerate(broken, 1):
            print(f"\n{idx}. Broken URL: {url}")
            print(f"   Reason:     {reason}")
            print("   Found on source page(s):")
            for src in sources:
                print(f"     * {src}")
        return 1
    else:
        print("\nAll links are functioning correctly!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
