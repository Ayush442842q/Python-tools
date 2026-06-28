#!/usr/bin/env python3
"""
Subreddit Scraper and Media Downloader
-------------------------------------
Scrapes top/hot/new posts, comments, and media from specified subreddits
using Reddit's public JSON feeds without requiring API credentials or OAuth.
Supports exporting metadata to JSON, CSV, and Markdown, and downloading images/videos.

Author: Antigravity
License: MIT
"""

import os
import sys
import json
import csv
import urllib.request
import urllib.parse
import argparse
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Constants
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def clean_filename(name: str) -> str:
    """Remove invalid characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")


def fetch_reddit_json(url: str, user_agent: str) -> Optional[Dict[str, Any]]:
    """Fetch JSON from Reddit with proper User-Agent headers to avoid HTTP 429."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching data from {url}: {e}", file=sys.stderr)
    return None


def scrape_posts(subreddit: str, sort: str = "hot", limit: int = 25, time_filter: str = "all", user_agent: str = DEFAULT_USER_AGENT) -> List[Dict[str, Any]]:
    """Scrape posts from a subreddit using the public JSON feed."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    if sort == "top":
        url += f"&t={time_filter}"
        
    print(f"Fetching posts from r/{subreddit} (sorted by {sort})...")
    data = fetch_reddit_json(url, user_agent)
    if not data:
        return []

    posts = []
    try:
        children = data.get("data", {}).get("children", [])
        for child in children:
            post_data = child.get("data", {})
            created_utc = post_data.get("created_utc", 0)
            posts.append({
                "id": post_data.get("id"),
                "title": post_data.get("title"),
                "author": post_data.get("author"),
                "score": post_data.get("score"),
                "num_comments": post_data.get("num_comments"),
                "url": post_data.get("url"),
                "selftext": post_data.get("selftext"),
                "permalink": f"https://www.reddit.com{post_data.get('permalink')}",
                "created_at": datetime.fromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                "is_self": post_data.get("is_self", True),
                "subreddit": post_data.get("subreddit")
            })
    except KeyError as e:
        print(f"Error parsing Reddit JSON response: {e}", file=sys.stderr)
        
    return posts


def scrape_post_comments(permalink: str, limit: int = 10, user_agent: str = DEFAULT_USER_AGENT) -> List[Dict[str, Any]]:
    """Scrape comments from a specific post permalink using its public JSON feed."""
    url = f"{permalink.rstrip('/')}.json?limit={limit}"
    data = fetch_reddit_json(url, user_agent)
    if not data or not isinstance(data, list) or len(data) < 2:
        return []

    comments = []
    try:
        comment_list = data[1].get("data", {}).get("children", [])
        for item in comment_list:
            if item.get("kind") == "t1":
                c_data = item.get("data", {})
                created_utc = c_data.get("created_utc", 0)
                comments.append({
                    "id": c_data.get("id"),
                    "author": c_data.get("author"),
                    "body": c_data.get("body"),
                    "score": c_data.get("score"),
                    "created_at": datetime.fromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception as e:
        print(f"Error parsing comments: {e}", file=sys.stderr)
        
    return comments


def download_media(url: str, output_dir: str, title: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """Download image or media file from URL."""
    # Check if URL is an image
    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    
    # Handle Imgur, i.redd.it, etc.
    if not ext and "imgur.com" in parsed.netloc:
        url = url + ".jpg"
        ext = ".jpg"
        
    if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        return False
        
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{clean_filename(title)[:50]}{ext}"
    output_path = os.path.join(output_dir, filename)
    
    print(f"Downloading media: {url} -> {output_path}")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}", file=sys.stderr)
        return False


def save_to_markdown(posts: List[Dict[str, Any]], filename: str, include_comments: bool = False, user_agent: str = DEFAULT_USER_AGENT) -> None:
    """Save posts and optionally their comments to a Markdown file."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Subreddit Scraped Posts - {posts[0]['subreddit'] if posts else 'N/A'}\n")
        f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for idx, post in enumerate(posts, 1):
            f.write(f"## {idx}. [{post['title']}]({post['permalink']})\n")
            f.write(f"**Author:** {post['author']} | **Score:** {post['score']} | **Comments:** {post['num_comments']} | **Date:** {post['created_at']}\n\n")
            
            if post['selftext']:
                # Indent body text slightly
                indented_body = "\n".join([f"> {line}" for line in post['selftext'].splitlines()])
                f.write(f"{indented_body}\n\n")
            elif post['url'] and not post['is_self']:
                f.write(f"Link URL: <{post['url']}>\n\n")
                
            if include_comments:
                comments = scrape_post_comments(post['permalink'], limit=5, user_agent=user_agent)
                if comments:
                    f.write("### Top Comments\n")
                    for c in comments:
                        f.write(f"- **{c['author']}** ({c['score']} points) [{c['created_at']}]:\n")
                        f.write(f"  {c['body'].replace(chr(10), '  ' + chr(10))}\n")
                    f.write("\n")
            f.write("---\n\n")
    print(f"Saved {len(posts)} posts to Markdown file: {filename}")


def save_to_csv(posts: List[Dict[str, Any]], filename: str) -> None:
    """Save posts to a CSV file."""
    if not posts:
        return
    keys = posts[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(posts)
    print(f"Saved {len(posts)} posts to CSV file: {filename}")


def save_to_json(posts: List[Dict[str, Any]], filename: str) -> None:
    """Save posts to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)
    print(f"Saved {len(posts)} posts to JSON file: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape posts and media from subreddits using public JSON feeds (no API keys required)."
    )
    parser.add_argument("subreddit", help="Name of the subreddit (e.g. 'python')")
    parser.add_argument("--sort", choices=["hot", "new", "top", "rising"], default="hot", help="Sort order for posts")
    parser.add_argument("--limit", type=int, default=25, help="Number of posts to fetch (max 100)")
    parser.add_argument("--time-filter", choices=["hour", "day", "week", "month", "year", "all"], default="all",
                        help="Time filter for top posts (only applies to sort='top')")
    parser.add_argument("--format", choices=["markdown", "json", "csv"], default="markdown", help="Output export format")
    parser.add_argument("--output", help="Output filename (defaults to subreddit_posts.<format>)")
    parser.add_argument("--download-dir", help="Directory to download media to (only images/gifs from post links)")
    parser.add_argument("--include-comments", action="store_true", help="Include top comments in Markdown output")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="Custom User-Agent header to use")

    args = parser.parse_args()

    # Normalize subreddit name
    subreddit = args.subreddit.strip().lower()
    
    # Scrape posts
    posts = scrape_posts(subreddit, sort=args.sort, limit=args.limit, time_filter=args.time_filter, user_agent=args.user_agent)
    
    if not posts:
        print(f"No posts found for r/{subreddit} or an error occurred.")
        return 1

    # Output filename determination
    output_filename = args.output
    if not output_filename:
        ext = "md" if args.format == "markdown" else args.format
        output_filename = f"{subreddit}_posts.{ext}"

    # Export formatting
    if args.format == "markdown":
        save_to_markdown(posts, output_filename, include_comments=args.include_comments, user_agent=args.user_agent)
    elif args.format == "csv":
        save_to_csv(posts, output_filename)
    elif args.format == "json":
        save_to_json(posts, output_filename)

    # Media download handling
    if args.download_dir:
        print(f"Scanning {len(posts)} posts for downloadable media...")
        media_count = 0
        for post in posts:
            if not post["is_self"] and post["url"]:
                if download_media(post["url"], args.download_dir, post["title"], user_agent=args.user_agent):
                    media_count += 1
        print(f"Successfully downloaded {media_count} media files to {args.download_dir}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
