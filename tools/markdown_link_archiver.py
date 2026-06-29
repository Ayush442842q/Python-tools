#!/usr/bin/env python3
"""
Markdown External Link Archiver
Scans Markdown files for external links, checks their uptime/status,
and archives them locally or submits them to the Internet Archive (Wayback Machine).
"""

import os
import re
import sys
import argparse
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import List, Dict, Tuple, Set
import concurrent.futures

# Regular expression to extract markdown links: [text](url)
# Ignoring local paths (not starting with http/https)
LINK_REGEX = re.compile(r'\[([^\]]+)\]\(((https?://[^\)]+))\)')

class MarkdownLinkArchiver:
    def __init__(self, check_timeout: float = 8.0, user_agent: str = None):
        self.timeout = check_timeout
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def scan_file(self, filepath: str) -> List[Tuple[int, str, str]]:
        """Scan a single markdown file and return a list of (line_num, link_text, url)."""
        links = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for idx, line in enumerate(f, 1):
                    # Find all links on this line
                    matches = LINK_REGEX.findall(line)
                    for match in matches:
                        link_text, url = match[0], match[1]
                        links.append((idx, link_text, url.strip()))
        except Exception as e:
            print(f"[-] Error reading file {filepath}: {e}", file=sys.stderr)
        return links

    def check_url(self, url: str) -> Tuple[int, str]:
        """Check if a URL is reachable. Returns (status_code, status_message/error)."""
        req = urllib.request.Request(
            url,
            headers={'User-Agent': self.user_agent},
            method='HEAD'  # Try HEAD request first for speed
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status, "OK"
        except urllib.error.HTTPError as e:
            # Some servers block HEAD request, try GET as fallback
            try:
                req.method = 'GET'
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return response.status, "OK"
            except urllib.error.HTTPError as e_inner:
                return e_inner.code, str(e_inner.reason)
            except Exception as e_inner:
                return 0, str(e_inner)
        except urllib.error.URLError as e:
            return 0, str(e.reason)
        except Exception as e:
            return 0, str(e)

    def archive_locally(self, url: str, archive_dir: str) -> Tuple[bool, str]:
        """Download URL content and save it locally in the archive directory."""
        os.makedirs(archive_dir, exist_ok=True)
        # Generate a safe filename from URL
        parsed = urllib.parse.urlparse(url)
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in parsed.netloc + parsed.path)
        if not safe_name.endswith('.html'):
            safe_name += '.html'
        
        filepath = os.path.join(archive_dir, safe_name)
        req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read()
                # Inject a banner indicating when it was archived
                meta_banner = (
                    f"<!-- Archived from {url} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n"
                    f"<div style='background:#fff3cd;color:#856404;padding:15px;text-align:center;"
                    f"font-family:sans-serif;border-bottom:1px solid #ffeeba;'>"
                    f"This is a local offline archive of <a href='{url}'>{url}</a>, "
                    f"captured on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.</div>\n"
                ).encode('utf-8')
                
                with open(filepath, 'wb') as f:
                    f.write(meta_banner + content)
            return True, filepath
        except Exception as e:
            return False, str(e)

    def archive_wayback(self, url: str) -> Tuple[bool, str]:
        """Submit the URL to Internet Archive (Wayback Machine)."""
        wayback_url = f"https://web.archive.org/save/{url}"
        req = urllib.request.Request(
            wayback_url,
            headers={'User-Agent': self.user_agent}
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as response:
                # Wayback save request triggers asynchronous archiving
                return True, f"Submitted successfully: https://web.archive.org/web/*/{url}"
        except Exception as e:
            return False, f"Failed to submit to Wayback Machine: {e}"

def process_file_links(filepath: str, archiver: MarkdownLinkArchiver, args) -> Dict:
    results = {
        "file": filepath,
        "links": []
    }
    
    file_links = archiver.scan_file(filepath)
    if not file_links:
        return results

    # Get unique URLs in the file to avoid duplicate checking/archiving in the same run
    unique_urls = list(set(link[2] for link in file_links))
    url_statuses = {}
    url_local_paths = {}
    url_wayback_info = {}

    print(f"[*] Checking {len(unique_urls)} unique external links in {os.path.basename(filepath)}...")
    
    # Check URLs in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(archiver.check_url, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                status, reason = future.result()
                url_statuses[url] = (status, reason)
            except Exception as exc:
                url_statuses[url] = (0, str(exc))

    # Archive locally or via Wayback if requested
    for url, (status, reason) in url_statuses.items():
        if status == 200 or status == 301 or status == 302:
            if args.archive_local:
                print(f"  [+] Archiving locally: {url}")
                success, path_or_err = archiver.archive_locally(url, args.archive_local)
                if success:
                    url_local_paths[url] = path_or_err
                else:
                    print(f"    [-] Local archive failed: {path_or_err}")
            
            if args.wayback:
                print(f"  [+] Submitting to Wayback Machine: {url}")
                success, msg = archiver.archive_wayback(url)
                url_wayback_info[url] = msg
        else:
            print(f"  [!] Link offline/error ({status}): {url} - {reason}")

    # Build results object and modify markdown file if rewrite is requested
    new_content_lines = []
    modified = False
    
    if args.rewrite and (url_local_paths or url_wayback_info):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                new_line = line
                matches = LINK_REGEX.findall(line)
                for match in matches:
                    text, url = match[0], match[1]
                    if url in url_local_paths:
                        # Compute relative path from Markdown file to the archive folder
                        rel_path = os.path.relpath(url_local_paths[url], os.path.dirname(filepath)).replace('\\', '/')
                        # Rewrite: [text](url) -> [text (Local Archive)](rel_path)
                        new_line = new_line.replace(f"[{text}]({url})", f"[{text} (Local Offline)]({rel_path})")
                        modified = True
                    elif url in url_wayback_info and args.wayback_rewrite:
                        # Rewrite link to Wayback machine link
                        wb_url = f"https://web.archive.org/web/2/{url}"
                        new_line = new_line.replace(f"[{text}]({url})", f"[{text} (Wayback Archive)]({wb_url})")
                        modified = True
                new_content_lines.append(new_line)
            
            if modified:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(new_content_lines)
                print(f"[+] Updated link references in {filepath}")
        except Exception as e:
            print(f"[-] Error rewriting {filepath}: {e}", file=sys.stderr)

    for line_num, text, url in file_links:
        status, reason = url_statuses.get(url, (0, "Not Checked"))
        results["links"].append({
            "line": line_num,
            "text": text,
            "url": url,
            "status": status,
            "reason": reason,
            "local_path": url_local_paths.get(url, None),
            "wayback": url_wayback_info.get(url, None)
        })
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Markdown External Link Checker & Archiver")
    parser.add_argument("path", help="Path to markdown file or directory containing markdown files")
    parser.add_argument("-t", "--timeout", type=float, default=8.0, help="HTTP connection timeout in seconds (default: 8.0)")
    parser.add_argument("-al", "--archive-local", metavar="DIR", help="Save copies of online links in this directory")
    parser.add_argument("-wb", "--wayback", action="store_true", help="Submit links to Wayback Machine")
    parser.add_argument("-rw", "--rewrite", action="store_true", help="Rewrite links in Markdown to local archive paths")
    parser.add_argument("-wr", "--wayback-rewrite", action="store_true", help="Rewrite links to Wayback Machine if offline")
    args = parser.parse_args()

    archiver = MarkdownLinkArchiver(check_timeout=args.timeout)

    # Gather files
    files = []
    if os.path.isdir(args.path):
        for root, _, filenames in os.walk(args.path):
            for f in filenames:
                if f.endswith('.md'):
                    files.append(os.path.join(root, f))
    elif os.path.isfile(args.path) and args.path.endswith('.md'):
        files.append(args.path)
    else:
        print("[-] Target path is not a Markdown file or folder containing Markdown files.")
        sys.exit(1)

    if not files:
        print("[*] No Markdown files found.")
        return

    print(f"[*] Scanning {len(files)} Markdown file(s) for external links...")
    
    total_links_found = 0
    dead_links_count = 0
    all_results = []

    for f in files:
        res = process_file_links(f, archiver, args)
        all_results.append(res)
        
        file_links_count = len(res["links"])
        total_links_found += file_links_count
        
        file_dead = [l for l in res["links"] if l["status"] not in (200, 301, 302)]
        dead_links_count += len(file_dead)
        
        if file_links_count > 0:
            print(f"[i] File: {os.path.basename(f)}: Found {file_links_count} links. Dead: {len(file_dead)}.")

    print("\n--- Summary Report ---")
    print(f"Total Markdown files scanned: {len(files)}")
    print(f"Total external links checked: {total_links_found}")
    print(f"Total dead/broken links:      {dead_links_count}")

    if dead_links_count > 0:
        print("\nBroken links list:")
        for res in all_results:
            file_dead = [l for l in res["links"] if l["status"] not in (200, 301, 302)]
            if file_dead:
                print(f" File: {res['file']}")
                for l in file_dead:
                    print(f"  Line {l['line']:3d}: [{l['text']}]({l['url']}) -> Code {l['status']} ({l['reason']})")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exited by user.")
        sys.exit(0)
