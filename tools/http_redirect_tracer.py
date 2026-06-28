#!/usr/bin/env python3
"""
HTTP Redirect Tracer - Trace the redirect path (3xx) of a URL and analyze each hop.

This tool takes a URL and traces its redirection chain, showing intermediate URLs,
HTTP status codes, response times, set cookies, and HTTP security headers. It can
detect redirection loops and identify open redirect vulnerabilities.

Usage:
    python tools/http_redirect_tracer.py URL [--max-redirects N] [--user-agent UA]
"""

import argparse
import http.client
import os
import sys
import time
import urllib.parse
import urllib.request


def init_colors():
    if sys.stdout.isatty() and os.name == 'nt':
        os.system('')
    use_color = sys.stdout.isatty()
    return {
        "green": "\033[92m" if use_color else "",
        "red": "\033[91m" if use_color else "",
        "yellow": "\033[93m" if use_color else "",
        "blue": "\033[94m" if use_color else "",
        "cyan": "\033[96m" if use_color else "",
        "bold": "\033[1m" if use_color else "",
        "reset": "\033[0m" if use_color else ""
    }


COLORS = init_colors()


class RedirectException(Exception):
    """Custom exception raised to halt automatic redirects and inspect details."""
    def __init__(self, code, new_url, headers):
        self.code = code
        self.new_url = new_url
        self.headers = headers


class HTTPNoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """A redirect handler that raises an exception rather than following the redirect."""
    def http_error_301(self, req, fp, code, msg, hdrs):
        raise RedirectException(code, hdrs.get('Location'), hdrs)
        
    def http_error_302(self, req, fp, code, msg, hdrs):
        raise RedirectException(code, hdrs.get('Location'), hdrs)
        
    def http_error_303(self, req, fp, code, msg, hdrs):
        raise RedirectException(code, hdrs.get('Location'), hdrs)
        
    def http_error_307(self, req, fp, code, msg, hdrs):
        raise RedirectException(code, hdrs.get('Location'), hdrs)
        
    def http_error_308(self, req, fp, code, msg, hdrs):
        raise RedirectException(code, hdrs.get('Location'), hdrs)


def format_bytes(size):
    """Format bytes to human readable format."""
    if size is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def trace_url(start_url, max_redirects=10, user_agent=None):
    """Traces the redirection hops of a URL."""
    current_url = start_url
    hops = []
    visited = set()
    
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HTTPRedirectTracer/1.0"
    ua = user_agent or default_ua
    
    # Configure custom opener
    opener = urllib.request.build_opener(HTTPNoRedirectHandler())
    opener.addheaders = [('User-Agent', ua)]
    
    print(f"\n{COLORS['bold']}{COLORS['cyan']}Tracing redirects for: {start_url}{COLORS['reset']}\n")
    
    hop_num = 1
    while hop_num <= max_redirects:
        # Detect loop
        if current_url in visited:
            print(f"{COLORS['red']}[!] REDIRECT LOOP DETECTED on URL: {current_url}{COLORS['reset']}")
            break
        visited.add(current_url)
        
        parsed = urllib.parse.urlparse(current_url)
        if not parsed.scheme or not parsed.netloc:
            print(f"{COLORS['red']}[!] Invalid URL: {current_url}{COLORS['reset']}")
            break
            
        req = urllib.request.Request(current_url)
        
        start_time = time.perf_counter()
        try:
            # We open the URL. If it redirects, our custom handler raises RedirectException.
            # Otherwise it succeeds as normal.
            response = opener.open(req, timeout=10)
            elapsed = (time.perf_counter() - start_time) * 1000
            
            # Successful end of redirection chain (200 OK, 404, etc.)
            code = response.status
            headers = response.info()
            
            hop_info = {
                "hop": hop_num,
                "url": current_url,
                "code": code,
                "msg": response.reason,
                "elapsed": elapsed,
                "headers": headers,
                "cookies": headers.get_all('Set-Cookie', []),
                "size": len(response.read())
            }
            hops.append(hop_info)
            print_hop(hop_info)
            break
            
        except RedirectException as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            
            # Resolve relative URLs
            next_url = e.new_url
            if not urllib.parse.urlparse(next_url).netloc:
                next_url = urllib.parse.urljoin(current_url, next_url)
                
            hop_info = {
                "hop": hop_num,
                "url": current_url,
                "code": e.code,
                "msg": "Redirect",
                "elapsed": elapsed,
                "headers": e.headers,
                "cookies": e.headers.get_all('Set-Cookie', []),
                "next_url": next_url,
                "size": None
            }
            hops.append(hop_info)
            print_hop(hop_info)
            
            current_url = next_url
            hop_num += 1
            
        except urllib.error.HTTPError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            hop_info = {
                "hop": hop_num,
                "url": current_url,
                "code": e.code,
                "msg": e.reason,
                "elapsed": elapsed,
                "headers": e.headers,
                "cookies": e.headers.get_all('Set-Cookie', []),
                "size": None
            }
            hops.append(hop_info)
            print_hop(hop_info)
            break
            
        except Exception as e:
            print(f"{COLORS['red']}[!] Connection failed: {e}{COLORS['reset']}")
            break
            
    else:
        print(f"{COLORS['yellow']}[!] Reached maximum redirect limit of {max_redirects} hops.{COLORS['reset']}")

    display_summary(hops)


def print_hop(hop):
    """Pretty prints information about a single redirect hop."""
    code = hop['code']
    if 300 <= code < 400:
        color = COLORS['yellow']
    elif 200 <= code < 300:
        color = COLORS['green']
    else:
        color = COLORS['red']
        
    print(f" {COLORS['bold']}[Hop {hop['hop']}]{COLORS['reset']} {hop['url']}")
    print(f"   Status: {color}{code} {hop['msg']}{COLORS['reset']} | Duration: {COLORS['cyan']}{hop['elapsed']:.1f}ms{COLORS['reset']}")
    
    server = hop['headers'].get('Server', 'Unknown')
    print(f"   Server: {COLORS['bold']}{server}{COLORS['reset']}")
    
    if hop['cookies']:
        print(f"   Cookies set: {COLORS['green']}{len(hop['cookies'])} cookie(s){COLORS['reset']}")
        
    if 'next_url' in hop:
        print(f"   Redirects to: {COLORS['blue']}{hop['next_url']}{COLORS['reset']}\n")
    else:
        size_str = format_bytes(hop['size']) if hop['size'] is not None else "N/A"
        print(f"   Terminal page payload: {COLORS['bold']}{size_str}{COLORS['reset']}\n")


def display_summary(hops):
    """Displays a final summary of the redirect chain."""
    if not hops:
        return
        
    print(f"{COLORS['bold']}=== REDIRECT SUMMARY ==={COLORS['reset']}")
    print(f"Total Hops: {len(hops)}")
    
    # Check for security headers on the final hop
    final_hop = hops[-1]
    final_headers = final_hop['headers']
    
    # Common security headers
    security_headers = [
        'Strict-Transport-Security',
        'Content-Security-Policy',
        'X-Frame-Options',
        'X-Content-Type-Options',
        'Referrer-Policy'
    ]
    
    present = []
    missing = []
    
    for sh in security_headers:
        if sh in final_headers:
            present.append(sh)
        else:
            missing.append(sh)
            
    print(f"\nFinal Destination: {COLORS['green']}{COLORS['bold']}{final_hop['url']}{COLORS['reset']}")
    
    total_time = sum(h['elapsed'] for h in hops)
    print(f"Total Response Time: {COLORS['cyan']}{total_time:.1f} ms{COLORS['reset']}")
    
    print(f"\n{COLORS['bold']}Final Hop Security Headers:{COLORS['reset']}")
    for header in present:
        print(f"  [{COLORS['green']}✓{COLORS['reset']}] {header}: {final_headers[header][:50]}...")
    for header in missing:
        print(f"  [{COLORS['red']}✗{COLORS['reset']}] {header} is missing")

    # Check for potential open redirect (final URL matches domain parameters of initial, but target changed)
    # This is a basic heuristic check
    orig_parsed = urllib.parse.urlparse(hops[0]['url'])
    final_parsed = urllib.parse.urlparse(final_hop['url'])
    if orig_parsed.netloc and final_parsed.netloc and orig_parsed.netloc != final_parsed.netloc:
        # Check if original URL has parameters containing final URL domain
        query = orig_parsed.query
        params = urllib.parse.parse_qs(query)
        suspicious = False
        for k, vals in params.items():
            for v in vals:
                if final_parsed.netloc in v or (v.startswith('http') and urllib.parse.urlparse(v).netloc != orig_parsed.netloc):
                    suspicious = True
                    break
        if suspicious:
            print(f"\n{COLORS['bold']}{COLORS['red']}[!] WARNING: Potential Open Redirect Vulnerability detected!{COLORS['reset']}")
            print(f"    The target URL redirected to an external domain ({final_parsed.netloc})")
            print(f"    which was specified in the query parameters of the initial URL.")


def main():
    parser = argparse.ArgumentParser(description="HTTP Redirect Tracer")
    parser.add_argument("url", help="URL to trace (include http:// or https://)")
    parser.add_argument("-m", "--max-redirects", type=int, default=10, help="Maximum number of redirects to follow (default: 10)")
    parser.add_argument("-u", "--user-agent", help="Custom User-Agent string")
    
    args = parser.parse_args()
    url = args.url
    
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        
    try:
        trace_url(url, max_redirects=args.max_redirects, user_agent=args.user_agent)
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Trace interrupted by user.{COLORS['reset']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
