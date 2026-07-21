#!/usr/bin/env python3
"""
Sitemap Generator - Standalone website crawler and SEO sitemap builder

Crawls a target website recursively (within a domain, up to a specified depth 
and page count) and generates a standard XML Sitemap or text site hierarchy.
Uses only Python standard libraries.

Usage:
    python tools/sitemap_generator.py <url> [options]

Options:
    url                 Starting URL (e.g. https://example.com)
    -o, --output        Output file path (default: sitemap.xml)
    -d, --depth         Max crawling depth (default: 3)
    -m, --max-pages     Max pages to crawl (default: 50)
    -t, --type          Output format: xml, txt (default: xml)
    -v, --verbose       Show real-time crawling logs

Example:
    python tools/sitemap_generator.py https://example.com -d 2 -o my_sitemap.xml
"""

import argparse
import sys
import os
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from collections import deque
import ssl

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

class LinkExtractor(HTMLParser):
    """HTML parser to extract all href links from a page."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href')
            if href:
                # Remove anchor fragments
                href = href.split('#')[0].strip()
                if href:
                    # Resolve relative URLs to absolute
                    absolute_url = urllib.parse.urljoin(self.base_url, href)
                    self.links.add(absolute_url)

def get_domain(url):
    """Extract netloc/domain from a URL."""
    return urllib.parse.urlparse(url).netloc

def crawl_site(start_url, max_depth=3, max_pages=50, verbose=False):
    """Crawls pages recursively using BFS to extract internal links."""
    start_domain = get_domain(start_url)
    if not start_domain:
        print(f"{RED}Error: Invalid starting URL domain.{RESET}", file=sys.stderr)
        return []

    # Queue contains tuples of (url, current_depth)
    queue = deque([(start_url, 0)])
    visited = {start_url}
    pages_crawled = []

    # Create a custom SSL context to avoid certificate verification errors for self-signed or dev setups
    ssl_context = ssl._create_unverified_context()

    print(f"Starting crawl of domain: {BOLD}{start_domain}{RESET}")
    print("-----------------------------------------")

    while queue and len(visited) <= max_pages:
        current_url, depth = queue.popleft()
        
        if depth > max_depth:
            continue
            
        if verbose:
            print(f"[{len(pages_crawled) + 1}] Crawling: {current_url} (depth={depth})")
        else:
            sys.stdout.write(f"\rCrawling... Found {len(visited)} URLs, parsed {len(pages_crawled)} pages.")
            sys.stdout.flush()

        pages_crawled.append(current_url)

        try:
            # Add user-agent header to avoid 403 Forbidden errors
            req = urllib.request.Request(
                current_url, 
                headers={'User-Agent': 'Mozilla/5.0 (SitemapGenerator Crawler)'}
            )
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                # We only parse HTML documents
                content_type = response.info().get_content_type()
                if 'text/html' not in content_type:
                    continue
                    
                html_bytes = response.read()
                html_text = html_bytes.decode('utf-8', errors='ignore')
                
            parser = LinkExtractor(current_url)
            parser.feed(html_text)
            
            for link in parser.links:
                parsed_link = urllib.parse.urlparse(link)
                # Keep crawls restricted to the original domain and protocol http/https
                if parsed_link.netloc == start_domain and parsed_link.scheme in ('http', 'https'):
                    if link not in visited and len(visited) < max_pages:
                        visited.add(link)
                        queue.append((link, depth + 1))
                        
        except Exception as e:
            if verbose:
                print(f"{YELLOW}  Failed to crawl {current_url}: {e}{RESET}")
            continue

    if not verbose:
        sys.stdout.write("\n")
        sys.stdout.flush()

    print(f"\n{GREEN}✔ Crawl completed! Scanned {len(pages_crawled)} pages, found {len(visited)} URLs.{RESET}")
    return sorted(list(visited))

def generate_xml_sitemap(urls):
    """Format a list of URLs into standard XML sitemap format."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for url in urls:
        # XML escape special characters
        escaped_url = url.replace('&', '&amp;').replace("'", '&apos;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        lines.append('  <url>')
        lines.append(f'    <loc>{escaped_url}</loc>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines)

def generate_txt_sitemap(urls):
    """Format a list of URLs into a flat text list."""
    return '\n'.join(urls)

def main():
    parser = argparse.ArgumentParser(description="Standalone recursive Sitemap XML/TXT Generator")
    parser.add_argument('url', help="Starting URL to crawl (e.g. https://example.com)")
    parser.add_argument('-o', '--output', default='sitemap.xml', help="Output file path (default: sitemap.xml)")
    parser.add_argument('-d', '--depth', type=int, default=3, help="Max crawling depth (default: 3)")
    parser.add_argument('-m', '--max-pages', type=int, default=50, help="Max pages to crawl (default: 50)")
    parser.add_argument('-t', '--type', choices=['xml', 'txt'], default='xml', help="Output format: xml, txt")
    parser.add_argument('-v', '--verbose', action='store_true', help="Print crawl logs in real-time")
    
    args = parser.parse_args()
    
    start_url = args.url
    if not start_url.startswith(('http://', 'https://')):
        # Attempt to auto-fix starting protocol
        start_url = 'https://' + start_url
        
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"{BOLD}{GREEN}            SITEMAP GENERATOR            {RESET}")
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"Target: {start_url}")
    print(f"Max Depth: {args.depth} | Max Pages Limit: {args.max_pages}")
    print(f"Output: {args.output} ({args.type})")
    print()
    
    urls = crawl_site(start_url, max_depth=args.depth, max_pages=args.max_pages, verbose=args.verbose)
    
    if not urls:
        print(f"{RED}No URLs found. Sitemap was not created.{RESET}", file=sys.stderr)
        return 1
        
    if args.type == 'xml':
        sitemap_content = generate_xml_sitemap(urls)
    else:
        sitemap_content = generate_txt_sitemap(urls)
        
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(sitemap_content + '\n')
        print(f"{GREEN}✔ Successfully saved sitemap to {args.output}{RESET}")
    except Exception as e:
        print(f"{RED}Failed to write sitemap output to {args.output}: {e}{RESET}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
