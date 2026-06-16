#!/usr/bin/env python3
"""
RSS & Atom Feed Reader

A command-line interface to subscribe to, list, update, and search RSS/Atom feeds.
Subscribed feeds are cached locally in the user's home directory.
Parsed using Python's built-in XML parsing libraries.

Usage:
    python tools/rss_feed_reader.py add "https://news.ycombinator.com/rss" --name "Hacker News"
    python tools/rss_feed_reader.py list
    python tools/rss_feed_reader.py read
    python tools/rss_feed_reader.py read "Hacker News" -n 5
    python tools/rss_feed_reader.py search "python"
    python tools/rss_feed_reader.py remove "Hacker News"
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"

# Default subscription database path
DB_PATH = Path.home() / ".rss_subscriptions.json"

DEFAULT_FEEDS = {
    "Hacker News": "https://news.ycombinator.com/rss",
    "Python.org Blog": "https://www.python.org/blogs/feed/"
}

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def load_subscriptions() -> Dict[str, str]:
    """Loads subscriptions from the database file, creating it with defaults if not exists."""
    if not DB_PATH.exists():
        save_subscriptions(DEFAULT_FEEDS)
        return DEFAULT_FEEDS
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(color_text(f"[-] Warning: Failed to load subscriptions: {e}. Using defaults.", COLOR_YELLOW))
        return DEFAULT_FEEDS

def save_subscriptions(subscriptions: Dict[str, str]):
    """Saves subscriptions to the database file."""
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(subscriptions, f, indent=4)
    except Exception as e:
        print(color_text(f"[-] Error: Failed to save subscriptions: {e}", COLOR_RED), file=sys.stderr)

def strip_html(html_text: str) -> str:
    """Strips HTML tags and unescapes HTML entities for clean CLI output."""
    if not html_text:
        return ""
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', html_text)
    # Unescape HTML entities
    return html.unescape(text).strip()

def clean_tag(tag: str) -> str:
    """Strips namespace brackets from XML tag names."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

def fetch_and_parse_feed(url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetches a feed URL and parses it as either RSS 2.0 or Atom 1.0."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSS-Feed-Reader/1.0"}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req, timeout=timeout) as response:
        xml_data = response.read()
        
    root = ET.fromstring(xml_data)
    tag = clean_tag(root.tag).lower()
    
    feed_title = "Unknown Feed"
    articles = []
    
    if tag == 'feed':  # Atom Format
        # Extract feed title
        for child in root:
            if clean_tag(child.tag) == 'title':
                feed_title = child.text or feed_title
                break
                
        # Extract entries
        for child in root:
            if clean_tag(child.tag) == 'entry':
                title = ""
                link = ""
                summary = ""
                pub_date = ""
                for prop in child:
                    ptag = clean_tag(prop.tag)
                    if ptag == 'title':
                        title = prop.text or ""
                    elif ptag == 'link':
                        link = prop.attrib.get('href', '') or prop.text or ""
                    elif ptag == 'summary' or ptag == 'content':
                        summary = prop.text or ""
                    elif ptag == 'updated' or ptag == 'published':
                        pub_date = prop.text or ""
                        
                articles.append({
                    "title": strip_html(title),
                    "link": link.strip(),
                    "description": strip_html(summary),
                    "pub_date": pub_date.strip()
                })
                
    elif tag == 'rss':  # RSS Format
        channel = root.find('channel')
        if channel is not None:
            title_el = channel.find('title')
            if title_el is not None:
                feed_title = title_el.text or feed_title
                
            for item in channel.findall('item'):
                title = item.find('title')
                title = title.text if title is not None else ""
                link = item.find('link')
                link = link.text if link is not None else ""
                description = item.find('description')
                description = description.text if description is not None else ""
                
                pub_date = item.find('pubDate')
                if pub_date is None:
                    pub_date = item.find('pubdate')
                pub_date = pub_date.text if pub_date is not None else ""
                
                articles.append({
                    "title": strip_html(title),
                    "link": link.strip(),
                    "description": strip_html(description),
                    "pub_date": pub_date.strip()
                })
    else:
        raise ValueError(f"Unsupported feed format: {root.tag}")
        
    return {
        "title": feed_title,
        "articles": articles
    }

def print_articles(feed_name: str, articles: List[Dict[str, Any]], limit: int):
    """Prints a list of articles to the terminal."""
    print("\n" + color_text(f"=== {feed_name} (Top {min(limit, len(articles))}) ===", COLOR_BOLD + COLOR_CYAN))
    
    for i, art in enumerate(articles[:limit], 1):
        print(f"\n{color_text(f'{i}. {art['title']}', COLOR_BOLD)}")
        if art['pub_date']:
            print(f"   {color_text('Published:', COLOR_DIM)} {art['pub_date']}")
        if art['link']:
            print(f"   {color_text('Link:', COLOR_DIM)} {color_text(art['link'], COLOR_GREEN)}")
        if art['description']:
            # Truncate summary to keep console neat
            summary = art['description']
            if len(summary) > 180:
                summary = summary[:177] + "..."
            print(f"   {color_text('Summary:', COLOR_DIM)} {summary}")
            
    print(color_text("=" * (len(feed_name) + 14), COLOR_DIM))

def main():
    parser = argparse.ArgumentParser(
        description="RSS & Atom Feed Reader: Subscribe to and read web feeds in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")
    
    # Add Subparser
    add_parser = subparsers.add_parser("add", help="Subscribe to a new RSS/Atom feed")
    add_parser.add_argument("url", help="Feed URL")
    add_parser.add_argument("-n", "--name", required=True, help="Name for the subscription")
    
    # List Subparser
    subparsers.add_parser("list", help="List all subscribed feeds")
    
    # Remove Subparser
    remove_parser = subparsers.add_parser("remove", help="Unsubscribe from a feed")
    remove_parser.add_argument("name", help="Name of the subscription to remove")
    
    # Read Subparser
    read_parser = subparsers.add_parser("read", help="Read articles from feeds")
    read_parser.add_argument("name", nargs="?", help="Specific feed name (optional, reads all if omitted)")
    read_parser.add_argument("-n", "--limit", type=int, default=5, help="Number of articles to show per feed (default: 5)")
    
    # Search Subparser
    search_parser = subparsers.add_parser("search", help="Search article titles for a keyword across all feeds")
    search_parser.add_argument("keyword", help="Keyword to search for")
    search_parser.add_argument("-n", "--limit", type=int, default=5, help="Max search results (default: 5)")

    args = parser.parse_args()
    
    subscriptions = load_subscriptions()
    
    if args.command == "add":
        if args.name in subscriptions:
            print(color_text(f"[-] A subscription named '{args.name}' already exists.", COLOR_YELLOW))
            sys.exit(1)
            
        print(f"Validating feed at: {args.url} ...")
        try:
            feed = fetch_and_parse_feed(args.url)
            subscriptions[args.name] = args.url
            save_subscriptions(subscriptions)
            print(color_text(f"[+] Successfully subscribed to '{args.name}' ({feed['title']})!", COLOR_GREEN))
        except Exception as e:
            print(color_text(f"[-] Failed to validate feed: {e}", COLOR_RED), file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "list":
        print("\n" + color_text("Subscribed Feeds:", COLOR_BOLD))
        print("-" * 50)
        for name, url in subscriptions.items():
            print(f"- {color_text(name, COLOR_CYAN)} ({url})")
        print("-" * 50)
        
    elif args.command == "remove":
        if args.name not in subscriptions:
            print(color_text(f"[-] Subscription '{args.name}' not found.", COLOR_RED), file=sys.stderr)
            sys.exit(1)
        del subscriptions[args.name]
        save_subscriptions(subscriptions)
        print(color_text(f"[+] Unsubscribed from '{args.name}'.", COLOR_GREEN))
        
    elif args.command == "read":
        if args.name:
            if args.name not in subscriptions:
                print(color_text(f"[-] Subscription '{args.name}' not found.", COLOR_RED), file=sys.stderr)
                sys.exit(1)
            url = subscriptions[args.name]
            try:
                feed = fetch_and_parse_feed(url)
                print_articles(args.name, feed["articles"], args.limit)
            except Exception as e:
                print(color_text(f"[-] Error reading feed '{args.name}': {e}", COLOR_RED), file=sys.stderr)
        else:
            if not subscriptions:
                print("No feeds subscribed yet. Add one with the 'add' command.")
                return
            for name, url in subscriptions.items():
                try:
                    feed = fetch_and_parse_feed(url)
                    print_articles(name, feed["articles"], args.limit)
                except Exception as e:
                    print(color_text(f"[-] Error reading feed '{name}': {e}", COLOR_RED), file=sys.stderr)
                    
    elif args.command == "search":
        keyword = args.keyword.lower()
        print(f"Searching for '{keyword}' across all subscribed feeds...")
        found_any = False
        
        for name, url in subscriptions.items():
            try:
                feed = fetch_and_parse_feed(url)
                matching = []
                for art in feed["articles"]:
                    if keyword in art["title"].lower() or keyword in art["description"].lower():
                        matching.append(art)
                if matching:
                    found_any = True
                    print_articles(f"{name} (Matches)", matching, args.limit)
            except Exception as e:
                print(color_text(f"[-] Error checking feed '{name}': {e}", COLOR_RED), file=sys.stderr)
                
        if not found_any:
            print("No matching articles found.")

if __name__ == "__main__":
    main()
