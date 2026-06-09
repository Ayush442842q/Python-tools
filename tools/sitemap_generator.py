#!/usr/bin/env python3
"""
Sitemap Generator

Crawls a website starting from a base URL up to a maximum depth/page limit,
discovers all internal links, and generates a standard sitemap.xml file.
Uses only Python built-in modules.

Usage:
    python tools/sitemap_generator.py https://example.com [--max-pages 100] [--max-depth 3] [-o sitemap.xml]
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
from xml.dom import minidom

class LinkParser(HTMLParser):
    """Simple HTML Parser to extract href links from a page."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value:
                    # Ignore anchors, mailto:, javascript:, tel:
                    if value.startswith(('#', 'mailto:', 'javascript:', 'tel:')):
                        continue
                    # Resolve relative URLs
                    absolute = urllib.parse.urljoin(self.base_url, value)
                    # Strip URL fragment (#heading)
                    absolute = urllib.parse.urlsplit(absolute)._replace(fragment='').geturl()
                    self.links.add(absolute)

def fetch_page_links(url, domain, user_agent):
    """Fetches a page and parses all internal URLs from it."""
    headers = {'User-Agent': user_agent}
    req = urllib.request.Request(url, headers=headers)
    try:
        # Ignore SSL errors for scraping if they occur, but try to open normally
        with urllib.request.urlopen(req, timeout=8) as response:
            content_type = response.info().get_content_type()
            if 'text/html' not in content_type:
                return set()
            
            html_bytes = response.read()
            # Attempt decoding, fallback to ignore errors
            try:
                html_text = html_bytes.decode('utf-8')
            except UnicodeDecodeError:
                html_text = html_bytes.decode('latin-1', errors='ignore')
                
            parser = LinkParser(url)
            parser.feed(html_text)
            
            # Filter links to keep only internal ones (same domain)
            internal_links = set()
            for link in parser.links:
                parsed_link = urllib.parse.urlparse(link)
                # Check if it has same netloc (domain)
                if parsed_link.netloc == domain:
                    internal_links.add(link)
                    
            return internal_links
    except Exception as e:
        # Silently catch fetch errors to continue crawl (e.g. 404, timeouts)
        return set()

def crawl_site(base_url, max_pages, max_depth, delay, user_agent):
    """Crawls pages starting from base_url, adhering to constraints."""
    parsed_base = urllib.parse.urlparse(base_url)
    domain = parsed_base.netloc
    
    if not domain:
        print(f"Error: Invalid URL scheme or domain for: {base_url}", file=sys.stderr)
        return []

    # Queue of tuples: (url, depth)
    queue = [(base_url, 0)]
    visited = {} # url -> lastmod (simulated as current crawl date)
    
    print(f"Starting crawl of domain: {domain}")
    print(f"Limits: max depth = {max_depth}, max pages = {max_pages}, delay = {delay}s")
    print("-" * 50)
    
    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        
        # Skip if already visited
        if url in visited:
            continue
            
        print(f"[{len(visited) + 1}/{max_pages}] Crawling: {url} (Depth: {depth})")
        
        visited[url] = time.strftime('%Y-%m-%d')
        
        if depth < max_depth:
            # Fetch links
            discovered = fetch_page_links(url, domain, user_agent)
            
            # Add new links to queue
            for link in discovered:
                if link not in visited and link not in [q[0] for q in queue]:
                    queue.append((link, depth + 1))
                    
        # Throttle request rate
        if delay > 0 and queue:
            time.sleep(delay)

    print("-" * 50)
    print(f"Crawl completed. Discovered {len(visited)} total pages.")
    return visited

def generate_sitemap_xml(urls_with_dates, output_file):
    """Generates a sitemap.xml file from crawled URLs."""
    urlset = Element('urlset', {
        'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'
    })
    
    for url, date in sorted(urls_with_dates.items()):
        url_el = SubElement(urlset, 'url')
        loc_el = SubElement(url_el, 'loc')
        loc_el.text = url
        lastmod_el = SubElement(url_el, 'lastmod')
        lastmod_el.text = date
        changefreq_el = SubElement(url_el, 'changefreq')
        changefreq_el.text = 'weekly'
        priority_el = SubElement(url_el, 'priority')
        # Simple heuristic: homepage is 1.0, deeper paths are 0.5 - 0.8
        path = urllib.parse.urlparse(url).path.strip('/')
        if not path:
            priority_el.text = '1.0'
        else:
            depth = len(path.split('/'))
            priority = max(0.2, 0.9 - (depth * 0.15))
            priority_el.text = f"{priority:.2f}"

    # Format XML nicely using minidom
    xml_str = tostring(urlset, 'utf-8')
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        print(f"Sitemap written successfully to: {os.path.abspath(output_file)}")
        return True
    except Exception as e:
        print(f"Error saving sitemap: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate a standard XML sitemap by crawling a website.")
    parser.add_argument('url', help='The base URL of the website to crawl (must include http:// or https://)')
    parser.add_argument('-m', '--max-pages', type=int, default=50, help='Maximum number of pages to crawl (default: 50)')
    parser.add_argument('-d', '--max-depth', type=int, default=3, help='Maximum crawling depth (default: 3)')
    parser.add_argument('-w', '--delay', type=float, default=0.2, help='Wait time (in seconds) between requests (default: 0.2)')
    parser.add_argument('-o', '--output', default='sitemap.xml', help='Output file path (default: sitemap.xml)')
    parser.add_argument('--user-agent', default='SitemapGeneratorBot/1.0', help='User Agent header string')
    args = parser.parse_args()

    # Normalize starting URL
    start_url = args.url.strip()
    if not (start_url.startswith('http://') or start_url.startswith('https://')):
        start_url = 'https://' + start_url
        
    crawled_urls = crawl_site(
        base_url=start_url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        user_agent=args.user_agent
    )
    
    if not crawled_urls:
        print("Error: No pages crawled. Sitemap generation aborted.", file=sys.stderr)
        return 1

    success = generate_sitemap_xml(crawled_urls, args.output)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
