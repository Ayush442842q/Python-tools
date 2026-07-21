#!/usr/bin/env python3
"""
RSS & Atom Feed Reader - Aggregates and displays RSS/Atom web feeds

This tool fetches RSS or Atom feeds from a given URL, parses the XML content,
and outputs formatted article headlines, dates, and links. It supports filtering
by keywords, limiting article counts, and exporting the feeds to a styled HTML report.

Usage:
    python tools/rss_feed_reader.py FEED_URL [options]

Options:
    -n, --limit N           Limit the number of articles shown (default: 10)
    -f, --filter WORD       Only show articles containing keyword (case-insensitive)
    -o, --output FILE       Export parsed feed to a styled HTML report
    -v, --verbose           Print debug info like HTTP requests and raw tags
    -h, --help              Show this help message and exit

Example:
    python tools/rss_feed_reader.py https://news.ycombinator.com/rss -n 5
"""

import argparse
import html
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def fetch_xml(url: str, verbose: bool) -> bytes:
    """Fetch raw XML data from URL with User-Agent header."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSSReader/1.0"}
    req = urllib.request.Request(url, headers=headers)
    if verbose:
        print(f"Fetching feed from: {url}...")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()
    except Exception as e:
        print(f"Error fetching feed: {e}", file=sys.stderr)
        sys.exit(1)


def parse_feed(xml_data: bytes) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """
    Parses RSS or Atom XML structure.
    Returns: (feed_metadata, list_of_articles)
    """
    root = ET.fromstring(xml_data)
    
    feed_meta = {"title": "Unknown Feed", "link": "", "description": ""}
    articles = []
    
    # Detect Atom namespace
    atom_ns = ""
    if "http://www.w3.org/2005/Atom" in root.tag:
        atom_ns = "{http://www.w3.org/2005/Atom}"
        
    # Check if Atom feed
    if root.tag == f"{atom_ns}feed":
        # Atom Metadata
        title_el = root.find(f"{atom_ns}title")
        if title_el is not None:
            feed_meta["title"] = title_el.text or ""
            
        link_el = root.find(f"{atom_ns}link")
        if link_el is not None:
            feed_meta["link"] = link_el.get("href", "")
            
        desc_el = root.find(f"{atom_ns}subtitle")
        if desc_el is not None:
            feed_meta["description"] = desc_el.text or ""
            
        # Atom Entries
        for entry in root.findall(f"{atom_ns}entry"):
            art = {"title": "", "link": "", "pub_date": "", "summary": ""}
            
            t = entry.find(f"{atom_ns}title")
            if t is not None:
                art["title"] = t.text or ""
                
            l = entry.find(f"{atom_ns}link")
            if l is not None:
                art["link"] = l.get("href", "")
                
            # Try updated or published
            d = entry.find(f"{atom_ns}updated")
            if d is None:
                d = entry.find(f"{atom_ns}published")
            if d is not None:
                art["pub_date"] = d.text or ""
                
            s = entry.find(f"{atom_ns}summary")
            if s is None:
                s = entry.find(f"{atom_ns}content")
            if s is not None:
                art["summary"] = s.text or ""
                
            articles.append(art)
            
    # Check if RSS feed
    elif root.tag == "rss":
        channel = root.find("channel")
        if channel is not None:
            # RSS Metadata
            t = channel.find("title")
            if t is not None:
                feed_meta["title"] = t.text or ""
                
            l = channel.find("link")
            if l is not None:
                feed_meta["link"] = l.text or ""
                
            d = channel.find("description")
            if d is not None:
                feed_meta["description"] = d.text or ""
                
            # RSS Items
            for item in channel.findall("item"):
                art = {"title": "", "link": "", "pub_date": "", "summary": ""}
                
                t_item = item.find("title")
                if t_item is not None:
                    art["title"] = t_item.text or ""
                    
                l_item = item.find("link")
                if l_item is not None:
                    art["link"] = l_item.text or ""
                    
                d_item = item.find("pubDate")
                if d_item is not None:
                    art["pub_date"] = d_item.text or ""
                    
                s_item = item.find("description")
                if s_item is not None:
                    art["summary"] = s_item.text or ""
                    
                articles.append(art)
                
    return feed_meta, articles


def clean_html(raw_html: str) -> str:
    """Basic helper to strip simple HTML tags from descriptions."""
    import re
    if not raw_html:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', '', raw_html)
    # Unescape HTML entities
    return html.unescape(clean).strip()


def export_html(meta: Dict[str, str], articles: List[Dict[str, str]], filepath: str) -> None:
    """Exports parsed feeds into a neat responsive HTML report."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(meta['title'])} - Feed Aggregator</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f7f9fa;
        }}
        header {{
            background: linear-gradient(135deg, #ff6600, #ff8833);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        header h1 {{ margin: 0 0 10px 0; }}
        header a {{ color: white; text-decoration: underline; }}
        .article-card {{
            background: white;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }}
        .article-card:hover {{ transform: translateY(-2px); }}
        .article-card h2 {{ margin: 0 0 10px 0; font-size: 1.4rem; }}
        .article-card h2 a {{ color: #0066cc; text-decoration: none; }}
        .article-card h2 a:hover {{ text-decoration: underline; }}
        .date {{ font-size: 0.85rem; color: #777; margin-bottom: 10px; }}
        .summary {{ color: #555; }}
    </style>
</head>
<body>
    <header>
        <h1>{html.escape(meta['title'])}</h1>
        <p>{html.escape(meta['description'])}</p>
        <p><a href="{html.escape(meta['link'])}" target="_blank">Visit original source website</a></p>
    </header>
    <main>
    """
    
    for art in articles:
        html_content += f"""
        <article class="article-card">
            <h2><a href="{html.escape(art['link'])}" target="_blank">{html.escape(art['title'])}</a></h2>
            <div class="date">{html.escape(art['pub_date'])}</div>
            <div class="summary">{html.escape(clean_html(art['summary'])[:300])}...</div>
        </article>
        """
        
    html_content += """
    </main>
</body>
</html>
    """
    
    write_mode = "w"
    with open(filepath, write_mode, encoding="utf-8") as f:
        f.write(html_content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone RSS & Atom Feed Reader.")
    parser.add_argument("url", help="Feed URL (RSS or Atom)")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max articles to show")
    parser.add_argument("-f", "--filter", help="Filter articles by keyword")
    parser.add_argument("-o", "--output", help="Path to write styled HTML report")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print debug/verbose log")
    
    args = parser.parse_args()
    
    xml_data = fetch_xml(args.url, args.verbose)
    
    if args.verbose:
        print("Parsing XML structure...")
    try:
        meta, articles = parse_feed(xml_data)
    except Exception as e:
        print(f"Error parsing feed XML: {e}", file=sys.stderr)
        return 1
        
    # Apply keyword filter
    if args.filter:
        kw = args.filter.lower()
        articles = [a for a in articles if kw in a["title"].lower() or kw in a["summary"].lower()]
        
    # Limit count
    articles = articles[:args.limit]
    
    # Print terminal output
    print(f"\n======================================================================")
    print(f" FEED: {meta['title']}")
    print(f" {meta['description']}")
    print(f" Source: {meta['link']}")
    print(f"======================================================================\n")
    
    if not articles:
        print("No articles found matching filters.")
    else:
        for idx, art in enumerate(articles, 1):
            print(f"{idx}. {art['title']}")
            if art['pub_date']:
                print(f"   Date: {art['pub_date']}")
            print(f"   Link: {art['link']}")
            
            clean_desc = clean_html(art['summary'])
            if clean_desc:
                # Truncate preview description
                preview = clean_desc[:180] + ("..." if len(clean_desc) > 180 else "")
                print(f"   Summary: {preview}")
            print()
            
    # Export to HTML if requested
    if args.output:
        try:
            export_html(meta, articles, args.output)
            print(f"Successfully exported {len(articles)} feed entries to HTML report at: {args.output}")
        except Exception as e:
            print(f"Error exporting HTML file: {e}", file=sys.stderr)
            return 1
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
