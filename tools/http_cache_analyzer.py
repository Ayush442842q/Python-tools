#!/usr/bin/env python3
"""
HTTP Cache Analyzer
Requests a URL and analyzes its HTTP response headers (Cache-Control, Expires, ETag,
Last-Modified, Vary, etc.) to evaluate CDN/browser caching behavior, compute TTLs,
and audit compression configurations.
"""

import argparse
import datetime
import email.utils
import sys
import urllib.request
from typing import Dict, List, Optional, Tuple


class CacheControlParser:
    """Parses and holds HTTP Cache-Control directives."""

    def __init__(self, header_value: Optional[str]):
        self.directives: Dict[str, Optional[str]] = {}
        if not header_value:
            return

        # Split directives by comma
        parts = header_value.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, val = part.split("=", 1)
                self.directives[key.strip().lower()] = val.strip().strip('"')
            else:
                self.directives[part.lower()] = None

    def has(self, directive: str) -> bool:
        return directive.lower() in self.directives

    def get(self, directive: str) -> Optional[str]:
        return self.directives.get(directive.lower())


def parse_http_date(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parses standard HTTP dates (RFC 1123 / RFC 822) to datetime objects."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        # Convert to naive datetime in UTC for simple arithmetic
        return parsed.replace(tzinfo=None)
    except Exception:
        return None


def format_ttl(seconds: float) -> str:
    """Formats a duration in seconds to a human-readable string."""
    if seconds <= 0:
        return "Expired / Immediate Revalidation"
    if seconds < 60:
        return f"{int(seconds)} second(s)"
    if seconds < 3600:
        return f"{int(seconds // 60)} minute(s) {int(seconds % 60)} second(s)"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hour(s) {int((seconds % 3600) // 60)} minute(s)"
    return f"{int(seconds // 86400)} day(s) {int((seconds % 86400) // 3600)} hour(s)"


def analyze_cache(url: str, user_agent: str, method: str) -> Dict:
    """Performs HTTP request and performs caching analysis on response headers."""
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate, br",  # Check compression capability
        },
    )

    try:
        start_time = datetime.datetime.now()
        with urllib.request.urlopen(req, timeout=10) as response:
            latency = (datetime.datetime.now() - start_time).total_seconds()
            headers = {k.lower(): v for k, v in response.getheaders()}
            status = response.status
    except urllib.error.HTTPError as e:
        latency = 0
        headers = {k.lower(): v for k, v in e.headers.items()}
        status = e.code
    except Exception as e:
        print(f"Error requesting URL: {e}", file=sys.stderr)
        sys.exit(1)

    cc_header = headers.get("cache-control")
    cc = CacheControlParser(cc_header)
    
    expires_header = headers.get("expires")
    expires_date = parse_http_date(expires_header)
    
    date_header = headers.get("date")
    response_date = parse_http_date(date_header) or datetime.datetime.utcnow()
    
    last_mod_header = headers.get("last-modified")
    last_mod_date = parse_http_date(last_mod_header)

    analysis = {
        "status": status,
        "latency_ms": int(latency * 1000),
        "headers": headers,
        "cacheability": "Unknown",
        "ttl_seconds": 0.0,
        "ttl_source": "None",
        "validation_supported": False,
        "recommendations": [],
        "warnings": [],
    }

    # 1. Determine Cacheability
    if cc.has("no-store"):
        analysis["cacheability"] = "No-Store (Do Not Cache)"
        analysis["ttl_seconds"] = 0.0
        analysis["ttl_source"] = "Cache-Control: no-store"
    elif cc.has("no-cache"):
        analysis["cacheability"] = "No-Cache (Must Revalidate Every Time)"
        analysis["ttl_seconds"] = 0.0
        analysis["ttl_source"] = "Cache-Control: no-cache"
    elif cc.has("private"):
        analysis["cacheability"] = "Private (Browser Only, No CDNs/Proxies)"
    elif cc.has("public") or cc_header:
        analysis["cacheability"] = "Public (Browser, CDNs, and Proxies)"
    else:
        # Default behavior in absence of headers
        analysis["cacheability"] = "Implicit/Heuristic (Undefined)"

    # 2. Compute TTL (Max Age)
    ttl_computed = False
    if not cc.has("no-store") and not cc.has("no-cache"):
        # Check s-maxage first (for shared caches / CDNs)
        if cc.has("s-maxage"):
            try:
                analysis["ttl_seconds"] = float(cc.get("s-maxage") or 0)
                analysis["ttl_source"] = "Cache-Control: s-maxage"
                ttl_computed = True
            except ValueError:
                pass
        # Check max-age next
        if not ttl_computed and cc.has("max-age"):
            try:
                analysis["ttl_seconds"] = float(cc.get("max-age") or 0)
                analysis["ttl_source"] = "Cache-Control: max-age"
                ttl_computed = True
            except ValueError:
                pass
        # Check Expires header next
        if not ttl_computed and expires_date:
            time_diff = (expires_date - response_date).total_seconds()
            analysis["ttl_seconds"] = max(0.0, time_diff)
            analysis["ttl_source"] = "Expires header"
            ttl_computed = True
        
        # Check Heuristic caching if nothing specified
        if not ttl_computed:
            if last_mod_date:
                # Heuristic: 10% of time since Last-Modified (RFC 7234)
                age = (response_date - last_mod_date).total_seconds()
                heuristic_ttl = max(0.0, age * 0.1)
                analysis["ttl_seconds"] = heuristic_ttl
                analysis["ttl_source"] = "Heuristic (10% of age since Last-Modified)"
                analysis["recommendations"].append(
                    "Heuristic caching is active. Explicitly set Cache-Control: max-age to prevent ambiguous client behavior."
                )
            else:
                analysis["ttl_seconds"] = 0.0
                analysis["ttl_source"] = "None (No caching rules found)"
                analysis["warnings"].append(
                    "No cache lifetime is defined. Clients may cache this unpredictably or not at all."
                )

    # 3. Check Validation Support
    etag = headers.get("etag")
    last_mod = headers.get("last-modified")
    if etag or last_mod:
        analysis["validation_supported"] = True
    else:
        analysis["warnings"].append(
            "Neither ETag nor Last-Modified header is present. Clients cannot perform conditional requests, forcing full downloads."
        )

    # 4. Compression check
    content_enc = headers.get("content-encoding")
    if content_enc:
        analysis["compression"] = content_enc
    else:
        # Check if content type is textual/compressible
        content_type = headers.get("content-type", "")
        compressible_types = ["text/", "javascript", "json", "xml", "svg"]
        is_compressible = any(t in content_type for t in compressible_types)
        if is_compressible:
            analysis["warnings"].append(
                "Resource content type is text-based but content-encoding is missing. Enable gzip/brotli compression on your server."
            )
        analysis["compression"] = "None"

    # 5. Vary header audits
    vary = headers.get("vary")
    if vary:
        vary_parts = [v.strip().lower() for v in vary.split(",")]
        if "user-agent" in vary_parts:
            analysis["recommendations"].append(
                "Vary header includes 'User-Agent'. This degrades CDN caching efficiency. Consider caching by device type or stripping it."
            )
        if "*" in vary_parts:
            analysis["warnings"].append(
                "Vary header is set to '*'. This prevents caching of this resource on most CDNs and downstream proxies."
            )

    # 6. Sanity checks / Conflict Warnings
    if cc.has("no-store") and (cc.has("max-age") or expires_header):
        analysis["warnings"].append(
            "Conflict: 'no-store' is specified alongside cache validity times ('max-age' or 'Expires'). 'no-store' will take precedence."
        )
    if cc.has("no-cache") and cc.has("no-store"):
        analysis["recommendations"].append(
            "Note: Both 'no-cache' and 'no-store' are set. 'no-store' is stronger, meaning the response will not be written to disk."
        )
    
    return analysis


def print_report(url: str, data: Dict):
    """Renders the diagnostic cache report to stdout."""
    # Color settings if terminal
    is_tty = sys.stdout.isatty()
    c_green = "\033[92m" if is_tty else ""
    c_yellow = "\033[93m" if is_tty else ""
    c_red = "\033[91m" if is_tty else ""
    c_cyan = "\033[96m" if is_tty else ""
    c_bold = "\033[1m" if is_tty else ""
    c_reset = "\033[0m" if is_tty else ""

    print(f"\n{c_bold}HTTP Cache Analysis Report{c_reset}")
    print("=" * 80)
    print(f"{c_bold}Target URL:{c_reset} {url}")
    print(f"{c_bold}HTTP Status:{c_reset} {data['status']}")
    print(f"{c_bold}Response Latency:{c_reset} {data['latency_ms']} ms")
    print(f"{c_bold}Compression Status:{c_reset} {c_cyan}{data['compression']}{c_reset}")
    print("-" * 80)

    # Cache Policy
    print(f"{c_bold}Cacheability:{c_reset} {c_cyan}{data['cacheability']}{c_reset}")
    ttl_sec = data["ttl_seconds"]
    if ttl_sec > 0:
        ttl_color = c_green if ttl_sec > 3600 else c_yellow
        print(f"{c_bold}Computed Lifespan (TTL):{c_reset} {ttl_color}{format_ttl(ttl_sec)}{c_reset} ({int(ttl_sec)} seconds)")
        print(f"{c_bold}TTL Determined By:{c_reset} {data['ttl_source']}")
    else:
        print(f"{c_bold}Computed Lifespan (TTL):{c_reset} {c_red}No Cache / Immediate Revalidation{c_reset}")
        print(f"{c_bold}TTL Determined By:{c_reset} {data['ttl_source']}")

    print(f"{c_bold}Conditional Request Support (Validation):{c_reset} " + 
          (f"{c_green}Yes{c_reset}" if data["validation_supported"] else f"{c_red}No{c_reset}"))

    # Key headers
    print("-" * 80)
    print(f"{c_bold}Relevant Response Headers:{c_reset}")
    key_headers = ["cache-control", "expires", "etag", "last-modified", "vary", "pragma", "age", "content-encoding", "server"]
    for kh in key_headers:
        val = data["headers"].get(kh)
        if val:
            print(f"  {c_cyan}{kh.capitalize()}:{c_reset} {val}")
        else:
            print(f"  {kh.capitalize()}: (Not Present)")

    # Warnings
    if data["warnings"]:
        print("-" * 80)
        print(f"{c_red}{c_bold}Warnings / Configuration Issues ({len(data['warnings'])}):{c_reset}")
        for warning in data["warnings"]:
            print(f"  [!] {warning}")

    # Recommendations
    if data["recommendations"]:
        print("-" * 80)
        print(f"{c_yellow}{c_bold}Best Practice Recommendations ({len(data['recommendations'])}):{c_reset}")
        for rec in data["recommendations"]:
            print(f"  [*] {rec}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze HTTP response caching headers and server performance optimizations."
    )
    parser.add_argument("url", help="HTTP or HTTPS URL to analyze")
    parser.add_argument("-a", "--user-agent", default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) HTTP Cache Analyzer/1.0",
                        help="Specify a custom User-Agent header")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "HEAD"],
                        help="HTTP method to use (default: GET)")

    args = parser.parse_args()

    url = args.url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        analysis_data = analyze_cache(url, args.user_agent, args.method)
        print_report(url, analysis_data)
    except Exception as e:
        print(f"Failed to analyze URL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
