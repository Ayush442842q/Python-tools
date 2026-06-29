#!/usr/bin/env python3
"""
Source Code Link Auditor
Recursively scans source files (.py, .js, .html, .css, .md, .json, etc.)
for HTTP/HTTPS URLs and tests them in parallel to find dead or redirected links.
"""

import os
import re
import sys
import argparse
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
from typing import List, Dict, Tuple, Set

# Regex pattern to match HTTP/HTTPS URLs
URL_REGEX = re.compile(r'https?://[^\s\'"<>`]+')

# Default extensions to scan
DEFAULT_EXTENSIONS = {'.py', '.js', '.ts', '.html', '.htm', '.css', '.md', '.json', '.txt', '.yml', '.yaml', '.toml'}

class LinkAuditor:
    def __init__(self, timeout: float = 6.0, max_workers: int = 15, user_agent: str = None):
        self.timeout = timeout
        self.max_workers = max_workers
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def scan_file(self, filepath: str) -> List[Tuple[int, str]]:
        """Scan a file and return a list of (line_number, url) tuples."""
        found_links = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    urls = URL_REGEX.findall(line)
                    for url in urls:
                        # Clean trailing punctuation commonly caught in regex
                        cleaned_url = url.rstrip('.,;:)!]}?"\'')
                        found_links.append((line_num, cleaned_url))
        except Exception as e:
            print(f"[-] Error reading file {filepath}: {e}", file=sys.stderr)
        return found_links

    def check_link(self, url: str) -> Dict:
        """Check HTTP status of a link. Returns a status dictionary."""
        # Clean the URL representation
        req = urllib.request.Request(
            url,
            headers={'User-Agent': self.user_agent},
            method='HEAD'
        )
        
        result = {
            "url": url,
            "status": 0,
            "msg": "Unknown",
            "redirect_url": None
        }

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result["status"] = response.status
                result["msg"] = "OK"
                
                # Check for redirects if the URL redirected transparently
                final_url = response.geturl()
                if final_url != url:
                    result["redirect_url"] = final_url
                    result["msg"] = "Redirected"
            return result
        except urllib.error.HTTPError as e:
            # If HEAD fails, try GET since some servers reject HEAD
            try:
                req.method = 'GET'
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    result["status"] = response.status
                    result["msg"] = "OK"
                    final_url = response.geturl()
                    if final_url != url:
                        result["redirect_url"] = final_url
                        result["msg"] = "Redirected"
                return result
            except urllib.error.HTTPError as e_inner:
                result["status"] = e_inner.code
                result["msg"] = str(e_inner.reason)
                return result
            except Exception as e_inner:
                result["status"] = 0
                result["msg"] = str(e_inner)
                return result
        except urllib.error.URLError as e:
            result["status"] = 0
            result["msg"] = str(e.reason)
            return result
        except Exception as e:
            result["status"] = 0
            result["msg"] = str(e)
            return result

def main():
    parser = argparse.ArgumentParser(description="Source Code Link Auditor")
    parser.add_argument("directory", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("-t", "--timeout", type=float, default=6.0, help="Timeout in seconds for URL requests (default: 6.0)")
    parser.add_argument("-w", "--workers", type=int, default=15, help="Number of concurrent threads (default: 15)")
    parser.add_argument("-e", "--extensions", help="Comma-separated file extensions to include (e.g. .py,.js)")
    parser.add_argument("-a", "--all-status", action="store_true", help="Show all link check results (by default shows only redirects and errors)")
    args = parser.parse_args()

    extensions = DEFAULT_EXTENSIONS
    if args.extensions:
        extensions = set(ext.strip() for ext in args.extensions.split(','))

    auditor = LinkAuditor(timeout=args.timeout, max_workers=args.workers)

    print(f"[*] Scanning directory '{args.directory}' for source files...")
    
    # Gather target files
    target_files = []
    for root, dirs, files in os.walk(args.directory):
        # Skip git or build cache folders
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', '.venv', 'build', 'dist')]
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in extensions:
                target_files.append(os.path.join(root, file))

    if not target_files:
        print("[!] No matching source files found.")
        return

    print(f"[*] Found {len(target_files)} source files. Extracting URLs...")

    # Extract all links
    url_occurrences = [] # List of dict: {"file", "line", "url"}
    unique_urls = set()

    for filepath in target_files:
        links = auditor.scan_file(filepath)
        for line_num, url in links:
            url_occurrences.append({
                "file": filepath,
                "line": line_num,
                "url": url
            })
            unique_urls.add(url)

    if not unique_urls:
        print("[*] No HTTP/HTTPS links found in the source code files.")
        return

    print(f"[*] Found {len(url_occurrences)} total URL occurrences ({len(unique_urls)} unique URLs).")
    print(f"[*] Auditing URLs in parallel using {args.workers} threads...")

    # Audit links in parallel
    url_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_url = {executor.submit(auditor.check_link, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                res = future.result()
                url_results[url] = res
            except Exception as e:
                url_results[url] = {
                    "url": url,
                    "status": 0,
                    "msg": f"Verification error: {e}",
                    "redirect_url": None
                }

    # Analyze results
    ok_count = 0
    redirect_count = 0
    broken_count = 0

    print("\n--- Detailed Audit Results ---")
    
    # Sort occurrences by file path and line number
    url_occurrences.sort(key=lambda x: (x["file"], x["line"]))

    for occ in url_occurrences:
        url = occ["url"]
        res = url_results.get(url)
        
        status = res["status"]
        msg = res["msg"]
        redirect_url = res["redirect_url"]

        is_broken = status not in (200, 301, 302)
        is_redirect = redirect_url is not None

        if is_broken:
            broken_count += 1
            status_desc = f"BROKEN (Code {status}: {msg})"
            print(f"[!] {occ['file']}:{occ['line']} -> {url} is {status_desc}")
        elif is_redirect:
            redirect_count += 1
            print(f"[~] {occ['file']}:{occ['line']} -> {url} redirects to {redirect_url}")
        else:
            ok_count += 1
            if args.all_status:
                print(f"[+] {occ['file']}:{occ['line']} -> {url} is OK")

    print("\n--- Link Audit Summary ---")
    print(f"Total URL occurrences checked: {len(url_occurrences)}")
    print(f"Unique URLs:                  {len(unique_urls)}")
    print(f"Reachable (OK):               {ok_count}")
    print(f"Redirected:                   {redirect_count}")
    print(f"Broken/Unreachable:           {broken_count}")
    print("--------------------------")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exited by user.")
        sys.exit(0)
