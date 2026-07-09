#!/usr/bin/env python3
"""
Markdown to RSS Compiler - Generate RSS 2.0 or Atom XML feeds from a directory of Markdown posts.
"""

import argparse
import email.utils
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.sax.saxutils import escape

# Regex to parse simple markdown to HTML (headings, bold, italics, links, lists)
MD_LINKS = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
MD_ITALIC = re.compile(r"\*([^*]+)\*")
MD_HEADINGS = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

def md_to_html(md_text: str) -> str:
    """Very basic Markdown to HTML converter for RSS feed descriptions."""
    html = md_text
    # Escape HTML tags first
    html = escape(html)
    
    # Headings
    def replace_heading(match):
        level = len(match.group(1))
        return f"<h{level}>{match.group(2)}</h{level}>"
    html = MD_HEADINGS.sub(replace_heading, html)

    # Links, Bold, Italic
    html = MD_LINKS.sub(r'<a href="\2">\1</a>', html)
    html = MD_BOLD.sub(r"<strong>\1</strong>", html)
    html = MD_ITALIC.sub(r"<em>\1</em>", html)
    
    # Paragraphs (split by double newline)
    paragraphs = html.split("\n\n")
    html_paragraphs = []
    for p in paragraphs:
        p_stripped = p.strip()
        if p_stripped:
            if p_stripped.startswith("<h") and p_stripped.endswith(">"):
                html_paragraphs.append(p_stripped)
            else:
                html_paragraphs.append(f"<p>{p_stripped.replace('\n', '<br />')}</p>")
                
    return "".join(html_paragraphs)

def parse_frontmatter(file_path: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter and separate it from body content."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter = {}
    body = content

    # Check if file starts with frontmatter delimiter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_block = parts[1]
            body = parts[2].strip()
            
            # Simple YAML-like parser
            for line in yaml_block.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip().lower()] = val.strip().strip('"').strip("'")

    return frontmatter, body

def format_rfc822_date(date_str: str) -> str:
    """Converts YYYY-MM-DD or ISO dates into RFC 822 format."""
    try:
        # Try YYYY-MM-DD HH:MM:SS
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            # Try YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            # Fallback to current time
            dt = datetime.now()
            
    return email.utils.format_datetime(dt)

def format_iso_date(date_str: str) -> str:
    """Converts date into ISO 8601 format for Atom feeds."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime.now()
            
    return dt.isoformat() + "Z"

def generate_rss(items: list, site_meta: dict) -> str:
    """Generate RSS 2.0 feed XML string."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = site_meta["title"]
    ET.SubElement(channel, "link").text = site_meta["link"]
    ET.SubElement(channel, "description").text = site_meta["description"]
    ET.SubElement(channel, "language").text = site_meta.get("language", "en-us")
    ET.SubElement(channel, "lastBuildDate").text = email.utils.format_datetime(datetime.now())
    ET.SubElement(channel, "generator").text = "Markdown to RSS Compiler"

    for item in items:
        rss_item = ET.SubElement(channel, "item")
        ET.SubElement(rss_item, "title").text = item["title"]
        ET.SubElement(rss_item, "link").text = item["link"]
        ET.SubElement(rss_item, "guid", isPermaLink="true").text = item["link"]
        ET.SubElement(rss_item, "pubDate").text = format_rfc822_date(item["date"])
        ET.SubElement(rss_item, "description").text = item["description"]
        if item.get("author"):
            ET.SubElement(rss_item, "author").text = item["author"]

    # Convert to string and format
    xml_str = ET.tostring(rss, encoding="utf-8")
    # Pretty print helper
    import xml.dom.minidom
    dom = xml.dom.minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def generate_atom(items: list, site_meta: dict) -> str:
    """Generate Atom 1.0 feed XML string."""
    feed = ET.Element("feed", xmlns="http://www.w3.org/2005/Atom")

    ET.SubElement(feed, "title").text = site_meta["title"]
    ET.SubElement(feed, "subtitle").text = site_meta["description"]
    ET.SubElement(feed, "id").text = site_meta["link"]
    ET.SubElement(feed, "updated").text = format_iso_date(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ET.SubElement(feed, "generator").text = "Markdown to RSS Compiler"
    
    link_self = ET.SubElement(feed, "link", rel="self", href=site_meta.get("feed_url", site_meta["link"] + "/feed.xml"))
    link_alt = ET.SubElement(feed, "link", rel="alternate", href=site_meta["link"])

    for item in items:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "title").text = item["title"]
        ET.SubElement(entry, "id").text = item["link"]
        ET.SubElement(entry, "updated").text = format_iso_date(item["date"])
        ET.SubElement(entry, "link", href=item["link"])
        ET.SubElement(entry, "summary", type="html").text = item["description"]
        
        if item.get("author"):
            author = ET.SubElement(entry, "author")
            ET.SubElement(author, "name").text = item["author"]

    xml_str = ET.tostring(feed, encoding="utf-8")
    import xml.dom.minidom
    dom = xml.dom.minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def main():
    parser = argparse.ArgumentParser(description="Compile a folder of Markdown posts into an RSS or Atom XML feed.")
    parser.add_argument("dir", help="Directory containing markdown files.")
    parser.add_argument("-o", "--output", default="feed.xml", help="Output file path (default: feed.xml)")
    parser.add_argument("--format", choices=["rss", "atom"], default="rss", help="Output format: 'rss' (default) or 'atom'.")
    parser.add_argument("--site-title", default="My Markdown Blog", help="Site title for the feed.")
    parser.add_argument("--site-link", default="https://example.com", help="Base site URL.")
    parser.add_argument("--site-desc", default="A blog generated from markdown files.", help="Feed description.")
    parser.add_argument("--limit", type=int, default=20, help="Max number of items to include in feed.")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"Error: Directory '{args.dir}' does not exist.")
        exit(1)

    items = []
    for file in os.listdir(args.dir):
        if file.endswith(".md"):
            file_path = os.path.join(args.dir, file)
            meta, body = parse_frontmatter(file_path)
            
            # Skip draft files
            if meta.get("draft") == "true":
                continue

            # Extracted metadata fields
            title = meta.get("title", os.path.splitext(file)[0].replace("-", " ").replace("_", " ").title())
            date = meta.get("date", datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d"))
            author = meta.get("author", "")
            
            # Build item link
            slug = meta.get("slug", os.path.splitext(file)[0])
            link = f"{args.site_link.rstrip('/')}/{slug}"
            
            # Description from frontmatter or fall back to body summary
            desc_raw = meta.get("description") or meta.get("summary")
            if not desc_raw:
                # Grab first 300 characters of the body
                desc_raw = body[:300] + ("..." if len(body) > 300 else "")
            
            description = md_to_html(desc_raw)

            items.append({
                "title": title,
                "date": date,
                "author": author,
                "link": link,
                "description": description
            })

    # Sort items by date descending
    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:args.limit]

    site_meta = {
        "title": args.site_title,
        "link": args.site_link,
        "description": args.site_desc,
        "feed_url": f"{args.site_link.rstrip('/')}/{args.output}"
    }

    if args.format == "rss":
        xml_content = generate_rss(items, site_meta)
    else:
        xml_content = generate_atom(items, site_meta)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"Generated {args.format.upper()} feed with {len(items)} items at '{args.output}'.")

if __name__ == "__main__":
    main()
