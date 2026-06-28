#!/usr/bin/env python3
"""
GitHub Issue Backup Tool

Downloads issues and their comments from a public/private GitHub repository and
saves them as structured local Markdown files. Perfect for offline reading, 
backups, migration, or creating documentation of repository discussions.

Usage:
    # Backup issues from public repository without token (subject to low rate limit)
    python tools/github_issue_backup.py psf/requests --limit 10

    # Backup issues using a GitHub Personal Access Token (for higher rate limit/private repos)
    python tools/github_issue_backup.py Ayush442842q/Python-tools --token YOUR_TOKEN --state open
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import argparse
from datetime import datetime

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_colored(text, color):
    """Print text with ANSI color."""
    print(f"{color}{text}{RESET}")

def make_request(url: str, token: str = None) -> tuple:
    """Helper to perform GitHub API requests with error handling."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "GitHub-Issue-Backup-Tool-Python")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    if token:
        req.add_header("Authorization", f"token {token}")
        
    try:
        with urllib.request.urlopen(req) as response:
            link_header = response.headers.get("Link", "")
            data = json.loads(response.read().decode("utf-8"))
            return data, link_header
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print_colored("[-] Error: Unauthorized. Check if your GITHUB_TOKEN is valid.", RED)
        elif e.code == 403:
            print_colored("[-] Error: Forbidden. You may have hit the GitHub API rate limit.", RED)
            print_colored("    Please provide a token using --token or set the GITHUB_TOKEN env var.", RED)
        elif e.code == 404:
            print_colored(f"[-] Error: Repository/Endpoint not found: {url}", RED)
        else:
            print_colored(f"[-] HTTP Error {e.code}: {e.reason}", RED)
        sys.exit(1)
    except Exception as e:
        print_colored(f"[-] Connection Error: {e}", RED)
        sys.exit(1)

def slugify(text: str) -> str:
    """Convert text to a clean slug for file naming."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text.strip("_")[:50]

def backup_issues(repo: str, output_dir: str, token: str, state: str, limit: int):
    """Downloads issues and comments and saves them in Markdown formats."""
    print_colored(f"[*] Starting backup of repository '{repo}' issues...", BLUE)
    os.makedirs(output_dir, exist_ok=True)
    
    issues_url = f"https://api.github.com/repos/{repo}/issues?state={state}&per_page=100"
    
    issues_downloaded = 0
    page = 1
    
    index_entries = []
    
    while True:
        url = f"{issues_url}&page={page}"
        print_colored(f"[*] Fetching issues page {page}...", BLUE)
        data, link_header = make_request(url, token)
        
        if not data:
            break
            
        for issue in data:
            # GitHub API returns pull requests as issues too, we want to distinguish or skip if desired.
            # We'll indicate it in the frontmatter, but download anyway as they contain discussions.
            is_pr = "pull_request" in issue
            
            number = issue["number"]
            title = issue["title"]
            user = issue["user"]["login"]
            created_at = issue["created_at"]
            body = issue["body"] or "*No description provided.*"
            comments_count = issue["comments"]
            labels = [l["name"] for l in issue.get("labels", [])]
            
            slug = slugify(title)
            filename = f"issue_{number}_{slug}.md" if not is_pr else f"pr_{number}_{slug}.md"
            filepath = os.path.join(output_dir, filename)
            
            print(f"  [{'PR' if is_pr else 'Issue'} #{number}] Saving: {title[:60]}...")
            
            # Fetch Comments if any
            comments_markdown = ""
            if comments_count > 0:
                comments_url = issue["comments_url"]
                comments_data, _ = make_request(comments_url, token)
                for comment in comments_data:
                    c_user = comment["user"]["login"]
                    c_date = comment["created_at"]
                    c_body = comment["body"] or ""
                    
                    comments_markdown += f"\n---\n\n### Comment by @{c_user} on {c_date}\n\n{c_body}\n"
                    
            # Build Markdown document with YAML-like frontmatter
            md_content = f"""---
title: "{title.replace('"', '\\"')}"
number: {number}
author: "{user}"
created_at: "{created_at}"
comments_count: {comments_count}
labels: {json.dumps(labels)}
type: "{'pull_request' if is_pr else 'issue'}"
state: "{issue['state']}"
url: "{issue['html_url']}"
---

# #{number} - {title}

**Opened by @{user} on {created_at}**
**State: {issue['state'].upper()}**

## Description

{body}

"""
            if comments_count > 0:
                md_content += f"\n## Discussion ({comments_count} comments)\n" + comments_markdown
                
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            index_entries.append({
                "number": number,
                "title": title,
                "type": "PR" if is_pr else "Issue",
                "state": issue["state"],
                "filename": filename
            })
            
            issues_downloaded += 1
            if limit and issues_downloaded >= limit:
                break
                
        if limit and issues_downloaded >= limit:
            break
            
        # Check Link header for next page
        if 'rel="next"' not in link_header:
            break
        page += 1
        
    # Write index/summary file
    index_path = os.path.join(output_dir, "README.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"# Backup of {repo} Issues\n\n")
        f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Type | # | Title | State | Link |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for entry in sorted(index_entries, key=lambda x: x["number"]):
            f.write(f"| {entry['type']} | {entry['number']} | {entry['title']} | {entry['state'].upper()} | [{entry['filename']}]({entry['filename']}) |\n")
            
    print()
    print_colored(f"[+] Backup completed successfully!", GREEN)
    print(f"    - Total items saved: {issues_downloaded}")
    print(f"    - Output directory:  {os.path.abspath(output_dir)}")
    print(f"    - Index file:        {os.path.abspath(index_path)}")

def main():
    parser = argparse.ArgumentParser(
        description="GitHub Issue Backup Tool - Download and back up issues/PRs from GitHub repositories."
    )
    parser.add_argument("repo", help="GitHub repository in format 'owner/repo' (e.g. psf/requests).")
    parser.add_argument("-o", "--output", default="issues_backup", 
                        help="Output directory to save issues (default: issues_backup).")
    parser.add_argument("-t", "--token", default=os.getenv("GITHUB_TOKEN"), 
                        help="GitHub Personal Access Token (defaults to GITHUB_TOKEN environment variable).")
    parser.add_argument("-s", "--state", choices=["open", "closed", "all"], default="all", 
                        help="Filter issues by state: open, closed, or all (default: all).")
    parser.add_argument("-l", "--limit", type=int, default=0, 
                        help="Limit the total number of issues to download (default: 0 = download all).")
                        
    args = parser.parse_args()
    
    # Simple validation of repository format
    if not re.match(r"^[\w.-]+/[\w.-]+$", args.repo):
        print_colored("[-] Error: Repository format must be 'owner/repo' (e.g. psf/requests).", RED)
        sys.exit(1)
        
    backup_issues(args.repo, args.output, args.token, args.state, args.limit)

if __name__ == "__main__":
    main()
