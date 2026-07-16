#!/usr/bin/env python3
"""
Web Application Path Fuzzer & Security Directory Brute-Forcer
=============================================================
A multithreaded command-line scanner to fuzz web applications for hidden files,
directories, and sensitive endpoints. Features wildcard/soft-404 detection,
status code filtering, rate limiting, and an embedded security wordlist
targeting configuration leaks (.git, .env, backups), APIs, and admin panels.

Author: Antigravity
License: MIT
"""

import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Embedded common directory/file endpoints for immediate fuzzing
EMBEDDED_WORDLIST = [
    # Config / Environment leaks
    ".git/HEAD",
    ".git/config",
    ".env",
    "web.config",
    "config.json",
    "config.yml",
    "config.php",
    "wp-config.php",
    "secrets.yml",
    "settings.py",
    # Backups & DB dumps
    "backup.zip",
    "backup.tar.gz",
    "backup.sql",
    "db.sql",
    "dump.sql",
    "database.sql",
    "site.zip",
    "archived.zip",
    # Admin & Portals
    "admin/",
    "administrator/",
    "wp-admin/",
    "login/",
    "cpanel/",
    "dashboard/",
    "portal/",
    "console/",
    # API & Docs
    "api/",
    "api/v1/",
    "api/v2/",
    "swagger.json",
    "swagger-ui.html",
    "openapi.yaml",
    "openapi.json",
    "graphql",
    "graphiql",
    # Dev & Diagnostics
    "phpinfo.php",
    "info.php",
    "elmah.axd",
    "metrics",
    "healthz",
    "status",
    "test/",
    "dev/",
    "readme.html",
    "LICENSE.txt",
    "robots.txt"
]

class WebFuzzer:
    def __init__(self, base_url, wordlist=None, threads=10, show_status=None, delay=0.0):
        self.base_url = base_url.rstrip('/')
        self.threads = threads
        self.delay = delay
        self.show_status = show_status if show_status else [200, 204, 301, 302, 307, 401, 403]
        
        # Wordlist loading
        self.words = self._load_wordlist(wordlist)
        
        # Wildcard detection settings
        self.wildcard_responses = {}
        self.wildcard_detected = False

    def _load_wordlist(self, filepath):
        if filepath:
            if not os.path.exists(filepath):
                print(f"{RED}Error: Wordlist file '{filepath}' not found. Using embedded list.{RESET}")
                return EMBEDDED_WORDLIST
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return EMBEDDED_WORDLIST

    def check_url(self, path):
        """Sends an HTTP request to check path availability."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        
        # Add basic headers to simulate standard browser requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PE-Scanner/1.0',
            'Accept': '*/*'
        }
        
        req = urllib.request.Request(url, headers=headers, method='GET')
        
        if self.delay > 0.0:
            time.sleep(self.delay)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                length = len(response.read())
                # Handle redirects (urllib follows redirects automatically, check response URL)
                final_url = response.url
                redirected = final_url != url
                return status, length, url, redirected, final_url
        except urllib.error.HTTPError as e:
            # e.code holds HTTP error codes (e.g. 403, 500)
            return e.code, 0, url, False, ""
        except urllib.error.URLError as e:
            return -1, 0, url, False, ""
        except Exception:
            return -2, 0, url, False, ""

    def detect_wildcard(self):
        """Detects wildcard behavior where the server responds with 200/302 for non-existent paths."""
        test_path = "fuzz_wildcard_detect_test_" + str(int(time.time()))
        status, length, _, _, _ = self.check_url(test_path)
        
        if status in [200, 301, 302, 307]:
            self.wildcard_detected = True
            self.wildcard_responses[status] = length
            print(f"{YELLOW}Warning: Wildcard / Soft-404 redirection detected on random endpoint!{RESET}")
            print(f"Server returned status {status} (size: {length} bytes) for non-existent '{test_path}'")
            print("Scanner will auto-filter responses matching this criteria.\n")

    def run_fuzz(self):
        print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
        print(f"{BOLD}{GREEN}                   WEB PATH FUZZER & DIR BRUTE-FORCER                 {RESET}")
        print(f"{BOLD}{BLUE}======================================================================{RESET}\n")
        print(f"{BOLD}Target URL:{RESET}     {self.base_url}")
        print(f"{BOLD}Wordlist Size:{RESET}  {len(self.words)} paths")
        print(f"{BOLD}Threads:{RESET}        {self.threads}")
        print(f"{BOLD}Delay:{RESET}          {self.delay}s")
        print(f"{BOLD}Filters:{RESET}        Showing statuses: {', '.join(map(str, self.show_status))}\n")

        print("Calibrating server for wildcard redirection...")
        self.detect_wildcard()
        
        print(f"{BOLD}Starting fuzzing pipeline...{RESET}")
        results = []
        
        # Setup multithreaded pool
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            future_to_path = {executor.submit(self.check_url, path): path for path in self.words}
            
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    status, size, url, redirected, final_url = future.result()
                    
                    if status in [-1, -2]:
                        continue # connection/DNS errors
                        
                    # Filtering criteria (status code show filter + wildcard/soft-404 filter)
                    if status in self.show_status:
                        if self.wildcard_detected and status in self.wildcard_responses:
                            # If size is exactly or very close to wildcard response, skip it
                            if abs(size - self.wildcard_responses[status]) < 50:
                                continue
                                
                        # Log finding
                        color = GREEN if status == 200 else (BLUE if status in [301,302,307] else (YELLOW if status in [401,403] else RED))
                        redirect_info = f" -> {final_url}" if redirected else ""
                        print(f"  [{color}{status}{RESET}] {url:<50} ({size} bytes){redirect_info}")
                        results.append({
                            'path': path,
                            'status': status,
                            'size': size,
                            'url': url,
                            'redirected': redirected,
                            'final_url': final_url
                        })
                except Exception as e:
                    print(f"Exception during path check '{path}': {e}", file=sys.stderr)

        print(f"\n{BOLD}{GREEN}Fuzzing completed successfully. Found {len(results)} active paths.{RESET}")
        print(f"{BOLD}{BLUE}======================================================================{RESET}\n")
        return results

def main():
    parser = argparse.ArgumentParser(
        description="Web Application Path Fuzzer - Multi-threaded web path directory brute-forcing tool."
    )
    parser.add_argument("-u", "--url", required=True, help="Target URL (e.g. http://127.0.0.1:8000).")
    parser.add_argument("-w", "--wordlist", help="Path to custom wordlist file. If omitted, uses embedded list.")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent threads (default 10).")
    parser.add_argument("-s", "--status", default="200,204,301,302,307,401,403", help="Comma-separated status codes to show.")
    parser.add_argument("-d", "--delay", type=float, default=0.0, help="Optional delay (in seconds) between requests.")
    parser.add_argument("-o", "--output", help="Write findings to output file in JSON format.")

    args = parser.parse_args()

    # Parse status codes
    try:
        status_list = [int(code.strip()) for code in args.status.split(',')]
    except ValueError:
        print("Error: Status codes must be a comma-separated list of integers.", file=sys.stderr)
        sys.exit(1)

    fuzzer = WebFuzzer(
        base_url=args.url,
        wordlist=args.wordlist,
        threads=args.threads,
        show_status=status_list,
        delay=args.delay
    )
    
    try:
        findings = fuzzer.run_fuzz()
    except Exception as e:
        print(f"{RED}Fuzzing failed: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(findings, f, indent=4)
            print(f"Saved findings to '{args.output}'.")
        except Exception as e:
            print(f"{RED}Failed to write output to file: {e}{RESET}", file=sys.stderr)

if __name__ == "__main__":
    main()
