#!/usr/bin/env python3
"""
Sitemap XML Link Auditor
Fetches or reads a sitemap.xml file, extracts all URLs (recursively handling sitemap indices),
and performs concurrent audits to check HTTP status, response times, redirects, and broken links.
"""

import argparse
import csv
import os
import queue
import ssl
import sys
import threading
import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPSHandler

# ANSI Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
END = "\033[0m"

def log_info(msg):
    print(f"{BLUE}[INFO]{END} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{END} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{END} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{END} {msg}", file=sys.stderr)

class RedirectHandler(HTTPSHandler):
    """Custom handler to prevent automatic redirect following, allowing us to inspect redirect codes."""
    def http_error_301(self, req, fp, code, msg, headers): return fp
    def http_error_302(self, req, fp, code, msg, headers): return fp
    def http_error_303(self, req, fp, code, msg, headers): return fp
    def http_error_307(self, req, fp, code, msg, headers): return fp
    def http_error_308(self, req, fp, code, msg, headers): return fp

def fetch_content(source):
    """Fetches text content from a URL or reads from a local path."""
    if source.startswith(("http://", "https://")):
        try:
            req = Request(
                source, 
                headers={"User-Agent": "Mozilla/5.0 (SitemapAuditor/1.0; Python-urllib)"}
            )
            # Ignore SSL verification errors if needed
            context = ssl._create_unverified_context()
            with build_opener(HTTPSHandler(context=context)).open(req, timeout=15) as res:
                return res.read()
        except Exception as e:
            log_error(f"Failed to fetch remote sitemap {source}: {e}")
            return None
    else:
        if os.path.exists(source):
            try:
                with open(source, "rb") as f:
                    return f.read()
            except Exception as e:
                log_error(f"Failed to read local file {source}: {e}")
                return None
        else:
            log_error(f"Local file does not exist: {source}")
            return None

def extract_urls_from_sitemap(xml_content, recursive_urls):
    """Parses XML and returns list of URLs or nested sitemap locations."""
    if not xml_content:
        return [], []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        log_error(f"XML Parsing Error: {e}")
        return [], []

    # Namespace handling
    # Sitemaps usually have namespace {http://www.sitemaps.org/schemas/sitemap/0.9}
    # We will search both namespaced and non-namespaced tags
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    urls = []
    nested_sitemaps = []

    # 1. Check if it's a sitemapindex
    if root.tag == f"{ns}sitemapindex":
        for sitemap in root.findall(f"{ns}sitemap"):
            loc = sitemap.find(f"{ns}loc")
            if loc is not None and loc.text:
                nested_sitemaps.append(loc.text.strip())
                
    # 2. Check if it's a standard urlset
    elif root.tag == f"{ns}urlset":
        for url_node in root.findall(f"{ns}url"):
            loc = url_node.find(f"{ns}loc")
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    else:
        # Fallback to wildcard search if format is unusual
        for loc in root.findall(".//loc"):
            if loc.text:
                urls.append(loc.text.strip())

    return urls, nested_sitemaps

def get_all_sitemap_urls(start_source):
    """Recursively traverses sitemap indices to extract all unique URLs."""
    visited_sitemaps = set()
    to_visit = [start_source]
    all_urls = set()

    log_info(f"Extracting URLs from sitemap starting at: {start_source}")

    while to_visit:
        current = to_visit.pop(0)
        if current in visited_sitemaps:
            continue
        visited_sitemaps.add(current)

        content = fetch_content(current)
        if not content:
            continue

        urls, nested = extract_urls_from_sitemap(content, visited_sitemaps)
        
        # Add normal URLs
        for url in urls:
            all_urls.add(url)
            
        # Add nested sitemaps to queue
        for ns in nested:
            if ns not in visited_sitemaps:
                to_visit.append(ns)
                
    log_success(f"Extracted {len(all_urls)} unique URLs from {len(visited_sitemaps)} sitemaps.")
    return list(all_urls)

def audit_worker(url_queue, results, lock, timeout_secs, user_agent):
    """Thread worker that audits URLs from the queue."""
    # Create custom opener to intercept redirects instead of following them
    context = ssl._create_unverified_context()
    opener = build_opener(RedirectHandler(context=context))

    while True:
        try:
            url = url_queue.get_nowait()
        except queue.Empty:
            break

        start_time = time.time()
        status_code = -1
        error_msg = ""
        latency = 0.0
        redirect_target = ""

        try:
            req = Request(url, headers={"User-Agent": user_agent})
            with opener.open(req, timeout=timeout_secs) as res:
                status_code = res.getcode()
                latency = time.time() - start_time
                if status_code in (301, 302, 303, 307, 308):
                    redirect_target = res.headers.get("Location", "")
        except HTTPError as e:
            status_code = e.code
            latency = time.time() - start_time
        except URLError as e:
            status_code = 0
            error_msg = str(e.reason)
            latency = time.time() - start_time
        except Exception as e:
            status_code = -2
            error_msg = str(e)
            latency = time.time() - start_time

        result = {
            "url": url,
            "status": status_code,
            "latency": latency,
            "redirect_target": redirect_target,
            "error_msg": error_msg
        }

        with lock:
            results.append(result)
            
        url_queue.task_done()

def run_auditor(urls, thread_count=10, timeout_secs=10, user_agent="SitemapAuditor/1.0"):
    """Starts the thread pool to audit all URLs."""
    url_queue = queue.Queue()
    for url in urls:
        url_queue.put(url)

    results = []
    lock = threading.Lock()
    threads = []

    log_info(f"Auditing {len(urls)} URLs using {thread_count} concurrent threads...")
    start_time = time.time()

    for _ in range(thread_count):
        t = threading.Thread(
            target=audit_worker, 
            args=(url_queue, results, lock, timeout_secs, user_agent)
        )
        t.daemon = True
        t.start()
        threads.append(t)

    # Monitor progress in the main thread
    while not url_queue.empty():
        done = len(results)
        pct = (done / len(urls)) * 100
        # Print inline progress bar
        sys.stdout.write(f"\rProgress: [{done}/{len(urls)}] {pct:.1f}% complete")
        sys.stdout.flush()
        time.sleep(0.5)

    # Wait for all threads to join
    for t in threads:
        t.join()

    # Clear progress line
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()

    total_time = time.time() - start_time
    log_success(f"Audit completed in {total_time:.2f} seconds.")
    return results

def output_results(results, latency_threshold, csv_path=None):
    """Analyzes audit results, prints CLI summary, and optionally writes to CSV."""
    success_count = 0
    redirect_count = 0
    broken_count = 0
    error_count = 0
    slow_count = 0
    
    broken_links = []
    redirects = []
    slow_links = []
    failures = []

    for r in results:
        status = r["status"]
        lat = r["latency"]
        
        if 200 <= status < 300:
            success_count += 1
            if lat > latency_threshold:
                slow_count += 1
                slow_links.append((r["url"], lat))
        elif 300 <= status < 400:
            redirect_count += 1
            redirects.append((r["url"], status, r["redirect_target"]))
        elif 400 <= status < 600:
            broken_count += 1
            broken_links.append((r["url"], status))
        else:
            error_count += 1
            failures.append((r["url"], r["error_msg"]))

    print(f"\n{BOLD}{CYAN}=== Sitemap Audit Results Summary ==={END}\n")
    print(f"{BOLD}Total URLs Checked:{END}  {len(results)}")
    print(f"  - {GREEN}Success (2xx):{END}    {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"  - {YELLOW}Redirects (3xx):{END}  {redirect_count} ({redirect_count/len(results)*100:.1f}%)")
    print(f"  - {RED}Broken (4xx/5xx):{END} {broken_count} ({broken_count/len(results)*100:.1f}%)")
    print(f"  - {RED}Failures/Errors:{END}  {error_count} ({error_count/len(results)*100:.1f}%)")
    print(f"  - {YELLOW}Slow Links:{END}       {slow_count} (> {latency_threshold}s)")

    # Detail Lists
    if broken_links:
        print(f"\n{BOLD}{RED}--- Broken Links (4xx/5xx) ---{END}")
        for url, code in broken_links[:10]:
            print(f"  - Code {code}: {url}")
        if len(broken_links) > 10:
            print(f"  ... and {len(broken_links)-10} more.")

    if failures:
        print(f"\n{BOLD}{RED}--- Network Failures (DNS/Connection/SSL) ---{END}")
        for url, msg in failures[:10]:
            print(f"  - Error: {msg} on {url}")
        if len(failures) > 10:
            print(f"  ... and {len(failures)-10} more.")

    if redirects:
        print(f"\n{BOLD}{YELLOW}--- Redirect Links ---{END}")
        for url, code, target in redirects[:5]:
            print(f"  - Code {code}: {url} -> {target}")
        if len(redirects) > 5:
            print(f"  ... and {len(redirects)-5} more.")

    if slow_links:
        print(f"\n{BOLD}{YELLOW}--- Slow Links (> {latency_threshold}s) ---{END}")
        for url, lat in sorted(slow_links, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - Latency {lat:.2f}s: {url}")
        if len(slow_links) > 5:
            print(f"  ... and {len(slow_links)-5} more.")

    # Write to CSV
    if csv_path:
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["URL", "Status Code", "Latency (s)", "Redirect Target", "Network Error Message"])
                for r in results:
                    writer.writerow([r["url"], r["status"], f"{r['latency']:.4f}", r["redirect_target"], r["error_msg"]])
            log_success(f"Detailed audit results exported to CSV: {csv_path}")
        except Exception as e:
            log_error(f"Failed to export CSV: {e}")

    print()

def main():
    parser = argparse.ArgumentParser(
        description="Sitemap XML Link Auditor. Extracts and validates all URLs concurrently."
    )
    parser.add_argument("sitemap_source", help="URL or local file path to sitemap.xml")
    parser.add_argument("-t", "--threads", type=int, default=10,
                        help="Number of concurrent threads (default: 10)")
    parser.add_argument("-w", "--timeout", type=int, default=10,
                        help="HTTP timeout limit in seconds (default: 10)")
    parser.add_argument("-l", "--latency", type=float, default=1.5,
                        help="Slow-response alert threshold in seconds (default: 1.5)")
    parser.add_argument("-c", "--csv", help="Optional path to export audit results as CSV")
    parser.add_argument("-u", "--user-agent", default="SitemapAuditor/1.0",
                        help="HTTP User-Agent header (default: SitemapAuditor/1.0)")

    args = parser.parse_args()

    if sys.platform == "win32":
        os.system("")

    urls = get_all_sitemap_urls(args.sitemap_source)
    if not urls:
        log_error("No URLs found to audit. Exiting.")
        sys.exit(1)

    results = run_auditor(
        urls, 
        thread_count=args.threads, 
        timeout_secs=args.timeout, 
        user_agent=args.user_agent
    )
    output_results(results, latency_threshold=args.latency, csv_path=args.csv)

if __name__ == "__main__":
    main()
