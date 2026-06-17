#!/usr/bin/env python3
"""
HTTP Security Headers Checker

Fetch the HTTP headers of a given URL and analyze their security posture.
Reports missing, misconfigured, or recommended security headers.

Usage:
    python tools/http_headers_checker.py <url> [options]

Requirements:
    - Python 3.6+
"""

import sys
import os
import argparse
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError
import ssl

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

SECURITY_HEADERS = {
    "Strict-Transport-Security": {
        "description": "Enforces HTTPS connections to protect against man-in-the-middle attacks.",
        "severity": "High"
    },
    "Content-Security-Policy": {
        "description": "Restricts resources (such as JavaScript, CSS, Images) that the browser is allowed to load.",
        "severity": "High"
    },
    "X-Frame-Options": {
        "description": "Prevents clickjacking attacks by controlling whether the page can be rendered in a frame/iframe.",
        "severity": "Medium"
    },
    "X-Content-Type-Options": {
        "description": "Prevents the browser from MIME-sniffing the response away from the declared content-type.",
        "severity": "Low"
    },
    "Referrer-Policy": {
        "description": "Controls how much referrer information is passed along with requests.",
        "severity": "Low"
    },
    "Permissions-Policy": {
        "description": "Allows a site to control which browser features (like camera, microphone, geolocation) can be used.",
        "severity": "Low"
    }
}

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def check_headers(url, user_agent, insecure):
    """Fetch URL and check for security headers."""
    # Ensure scheme is present
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urllib.parse.urlparse(url)

    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HTTP Security Headers Checker/1.0"
    }
    
    # Configure SSL context
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            resp_headers = response.info()
            status_code = response.getcode()
            final_url = response.geturl()
            return status_code, resp_headers, final_url, None
    except HTTPError as e:
        # Some servers return 403 or 401 but still serve headers we can analyze
        return e.code, e.headers, url, None
    except URLError as e:
        return None, None, url, f"URL Error: {e.reason}"
    except Exception as e:
        return None, None, url, f"Failed to connect: {e}"

def main():
    parser = argparse.ArgumentParser(
        description="Analyze HTTP security headers of a website.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="Target URL (e.g., example.com or https://example.com)")
    parser.add_argument("-k", "--insecure", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("-a", "--user-agent", help="Custom User-Agent string")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")
    parser.add_argument("-d", "--details", action="store_true", help="Show descriptions and recommendations")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    print(f"Connecting to {args.url}...")
    status, headers, final_url, err = check_headers(args.url, args.user_agent, args.insecure)
    
    if err:
        print_colored(f"Error: {err}", RED, use_color)
        return 1

    print_colored(f"\nTarget URL: {args.url}", BOLD if use_color else "", use_color)
    print(f"Resolved URL: {final_url}")
    print(f"HTTP Status: {status}\n")

    # Group headers
    found_security_headers = {}
    missing_security_headers = {}
    other_headers = {}

    # Standardize header keys to lower case for easy case-insensitive matching
    headers_lower = {k.lower(): (k, v) for k, v in headers.items()}

    for sec_header, info in SECURITY_HEADERS.items():
        sec_header_lower = sec_header.lower()
        if sec_header_lower in headers_lower:
            original_key, val = headers_lower[sec_header_lower]
            found_security_headers[original_key] = val
        else:
            missing_security_headers[sec_header] = info

    for k, v in headers.items():
        if k.lower() not in [sh.lower() for sh in SECURITY_HEADERS.keys()]:
            other_headers[k] = v

    # Print Found Security Headers
    print_colored(f"--- SECURITY HEADERS FOUND ({len(found_security_headers)}/{len(SECURITY_HEADERS)}) ---", GREEN, use_color)
    for k, v in sorted(found_security_headers.items()):
        print_colored(f" [✓] {k}: {v}", GREEN, use_color)
    print()

    # Print Missing Security Headers
    print_colored(f"--- MISSING SECURITY HEADERS ({len(missing_security_headers)}) ---", RED if missing_security_headers else GREEN, use_color)
    for k, info in sorted(missing_security_headers.items()):
        sev_color = RED if info["severity"] == "High" else YELLOW
        print_colored(f" [✗] {k} (Severity: {info['severity']})", sev_color, use_color)
        if args.details:
            print(f"     Description: {info['description']}")
    print()

    # Print Summary score
    score = int((len(found_security_headers) / len(SECURITY_HEADERS)) * 100)
    score_color = RED if score < 40 else (YELLOW if score < 75 else GREEN)
    print_colored(f"Security Header Grade Score: {score}/100", score_color, use_color)
    print()

    # Print Server Information & Other Headers
    print_colored("--- OTHER HEADERS ---", BLUE, use_color)
    interesting_others = ["Server", "X-Powered-By", "Content-Type", "Cache-Control", "Content-Encoding"]
    for k, v in sorted(other_headers.items()):
        if k in interesting_others or args.details:
            print(f"     {k}: {v}")
    if not args.details:
        print("     (Run with --details or -d to show all remaining HTTP headers)")
    
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
