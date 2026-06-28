#!/usr/bin/env python3
"""
Content Security Policy (CSP) Generator & Validator - Audit HTML files or URLs to generate and validate CSP configurations.

This tool extracts resource domains from HTML files or URLs and constructs a secure CSP,
or validates existing CSP strings for security risks (e.g. unsafe-inline, wildcards, missing base-uri).
"""

import os
import re
import sys
import argparse
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser

# ANSI colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

# Directives mapping
DIRECTIVES = {
    "default-src": set(),
    "script-src": set(),
    "style-src": set(),
    "img-src": set(),
    "font-src": set(),
    "connect-src": set(),
    "frame-src": set(),
    "media-src": set(),
    "object-src": set(),
    "base-uri": set(),
    "form-action": set()
}

class ResourceExtractor(HTMLParser):
    def __init__(self, base_url=""):
        super().__init__()
        self.base_url = base_url
        self.found_inline_script = False
        self.found_inline_style = False

    def get_domain(self, url):
        if not url:
            return None
        # Clean data URIs, inline scripts, etc.
        url_lower = url.lower().strip()
        if url_lower.startswith("data:"):
            return "data:"
        if url_lower.startswith("blob:"):
            return "blob:"
        if url_lower.startswith("javascript:") or url_lower.startswith("mailto:") or url_lower.startswith("#"):
            return None
            
        parsed = urlparse(url)
        if not parsed.netloc:
            # If relative, it resolves to self
            return "'self'"
            
        # Standardize domain (keep scheme only if it's https/wss)
        scheme_prefix = ""
        if parsed.scheme in ("https", "wss"):
            scheme_prefix = f"{parsed.scheme}://"
        return f"{scheme_prefix}{parsed.netloc}"

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        
        if tag == "script":
            src = attr_dict.get("src")
            if src:
                dom = self.get_domain(src)
                if dom: DIRECTIVES["script-src"].add(dom)
            else:
                self.found_inline_script = True
                
        elif tag == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href")
            if href:
                dom = self.get_domain(href)
                if not dom:
                    return
                if "stylesheet" in rel:
                    DIRECTIVES["style-src"].add(dom)
                elif "icon" in rel or "shortcut" in rel:
                    DIRECTIVES["img-src"].add(dom)
                elif "preload" in rel or "prefetch" in rel:
                    as_type = attr_dict.get("as", "").lower()
                    if as_type == "script": DIRECTIVES["script-src"].add(dom)
                    elif as_type == "style": DIRECTIVES["style-src"].add(dom)
                    elif as_type == "font": DIRECTIVES["font-src"].add(dom)
                    elif as_type == "image": DIRECTIVES["img-src"].add(dom)
                    
        elif tag in ("style", "img", "iframe", "frame", "audio", "video", "source", "object", "embed", "form"):
            src_attr = "href" if tag == "style" else ("action" if tag == "form" else "src")
            val = attr_dict.get(src_attr)
            if val:
                dom = self.get_domain(val)
                if not dom:
                    return
                if tag == "img": DIRECTIVES["img-src"].add(dom)
                elif tag in ("iframe", "frame"): DIRECTIVES["frame-src"].add(dom)
                elif tag in ("audio", "video", "source"): DIRECTIVES["media-src"].add(dom)
                elif tag in ("object", "embed"): DIRECTIVES["object-src"].add(dom)
                elif tag == "form": DIRECTIVES["form-action"].add(dom)
            elif tag == "style":
                self.found_inline_style = True

def validate_csp(csp_str):
    """Validate a CSP policy and return diagnostic results."""
    issues = []
    # Parse directives
    parts = [p.strip() for p in csp_str.split(";") if p.strip()]
    parsed_csp = {}
    for part in parts:
        tokens = part.split()
        if not tokens:
            continue
        directive = tokens[0].lower()
        sources = tokens[1:]
        parsed_csp[directive] = sources

    # Check 1: Missing default-src
    if "default-src" not in parsed_csp:
        issues.append({
            "severity": "CRITICAL",
            "message": "Missing 'default-src' fallback directive.",
            "remediation": "Add 'default-src \'self\'' as a safe default fallback."
        })

    # Check 2: Unsafe scripts/styles
    if "script-src" in parsed_csp:
        sources = parsed_csp["script-src"]
        if "'unsafe-inline'" in sources:
            issues.append({
                "severity": "HIGH",
                "message": "'script-src' allows 'unsafe-inline'. Allows Cross-Site Scripting (XSS).",
                "remediation": "Remove 'unsafe-inline' and use CSP nonces, hashes, or move inline JS to external scripts."
            })
        if "'unsafe-eval'" in sources:
            issues.append({
                "severity": "MEDIUM",
                "message": "'script-src' allows 'unsafe-eval' (eval(), setTimeout strings, etc.).",
                "remediation": "Refactor JS code to avoid dynamic evaluation libraries."
            })
        if "*" in sources:
            issues.append({
                "severity": "HIGH",
                "message": "'script-src' permits scripts from any host (*).",
                "remediation": "Limit sources to explicit domains or 'self'."
            })
    else:
        # Falls back to default-src
        pass

    # Check 3: Missing base-uri
    if "base-uri" not in parsed_csp:
        issues.append({
            "severity": "MEDIUM",
            "message": "Missing 'base-uri' directive. Vulnerable to <base> tag hijacking.",
            "remediation": "Restrict base injection using: base-uri 'self'"
        })

    # Check 4: Missing object-src
    if "object-src" not in parsed_csp:
        issues.append({
            "severity": "HIGH",
            "message": "Missing 'object-src' directive. Flash/Java plugin execution allowed.",
            "remediation": "Disable plugins using: object-src 'none'"
        })
    elif "'none'" not in parsed_csp["object-src"] and "*" in parsed_csp["object-src"]:
        issues.append({
            "severity": "HIGH",
            "message": "'object-src' allows wildcard (*).",
            "remediation": "Set object-src 'none' to block flash/object exploits."
        })

    # Check 5: Plain HTTP schemes in directives
    for directive, sources in parsed_csp.items():
        for src in sources:
            if src.startswith("http://"):
                issues.append({
                    "severity": "LOW",
                    "message": f"Directive '{directive}' allows insecure HTTP origin: {src}.",
                    "remediation": "Upgrade resources to HTTPS."
                })

    return issues

def audit_url(url):
    """Fetch URL and extract resource dependencies."""
    try:
        import requests
    except ImportError:
        print(f"{COLOR_RED}Error: 'requests' module is required to audit URLs. Run 'pip install requests'.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching URL: {COLOR_CYAN}{url}{COLOR_RESET}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"{COLOR_RED}Failed to fetch URL: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Check existing CSP
    csp_header = response.headers.get("Content-Security-Policy")
    if csp_header:
        print(f"\n{COLOR_GREEN}✓ Existing Content-Security-Policy Header Found:{COLOR_RESET}")
        print(f"  {csp_header}\n")
        issues = validate_csp(csp_header)
        print_audit_report(issues)
    else:
        print(f"\n{COLOR_YELLOW}⚠ No Content-Security-Policy Header found on server response.{COLOR_RESET}\n")

    # Generate CSP
    extractor = ResourceExtractor(base_url=url)
    extractor.feed(response.text)
    
    # Check CSS files for fonts
    # A simple regex scan for font-face url() in style tags or linked sheets can be done,
    # but here we'll dynamically check standard properties.
    return generate_csp_string(extractor)

def generate_csp_string(extractor):
    # Setup self fallback
    DIRECTIVES["default-src"].add("'self'")
    DIRECTIVES["base-uri"].add("'self'")
    DIRECTIVES["object-src"].add("'none'")

    # Inline flags
    if extractor.found_inline_script:
        DIRECTIVES["script-src"].add("'unsafe-inline'")
    if extractor.found_inline_style:
        DIRECTIVES["style-src"].add("'unsafe-inline'")

    # Fallbacks for empty script/style
    if not DIRECTIVES["script-src"]:
        DIRECTIVES["script-src"].add("'self'")
    else:
        DIRECTIVES["script-src"].add("'self'")
        
    if not DIRECTIVES["style-src"]:
        DIRECTIVES["style-src"].add("'self'")
    else:
        DIRECTIVES["style-src"].add("'self'")

    if not DIRECTIVES["img-src"]:
        DIRECTIVES["img-src"].add("'self'")
    else:
        DIRECTIVES["img-src"].add("'self'")

    csp_parts = []
    for k, v in DIRECTIVES.items():
        if v:
            # Sort with self and none first for readability
            v_list = list(v)
            sorted_v = []
            for item in ("'none'", "'self'", "'unsafe-inline'", "'unsafe-eval'", "data:", "blob:"):
                if item in v_list:
                    sorted_v.append(item)
                    v_list.remove(item)
            sorted_v.extend(sorted(v_list))
            csp_parts.append(f"{k} {' '.join(sorted_v)}")

    return "; ".join(csp_parts)

def audit_file(filepath):
    """Audit a local HTML file to generate CSP."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    extractor = ResourceExtractor()
    extractor.feed(content)
    return generate_csp_string(extractor)

def print_audit_report(issues):
    print(f"{COLOR_BOLD}=== CSP Security Audit Report ==={COLOR_RESET}")
    if not issues:
        print(f"{COLOR_GREEN}✓ CSP looks secure! No issues found.{COLOR_RESET}\n")
        return

    print(f"Found {len(issues)} security warning(s):\n")
    for iss in issues:
        sev_color = COLOR_RED if iss["severity"] in ("CRITICAL", "HIGH") else (COLOR_YELLOW if iss["severity"] == "MEDIUM" else COLOR_CYAN)
        print(f"  {sev_color}[{iss['severity']}]{COLOR_RESET} {iss['message']}")
        print(f"    Remediation: {COLOR_GREEN}{iss['remediation']}{COLOR_RESET}")
        print()

def main():
    parser = argparse.ArgumentParser(description="Content Security Policy (CSP) Generator and Security Validator.")
    parser.add_argument("target", nargs="?", help="URL or local path to HTML file to analyze and generate CSP for")
    parser.add_argument("-v", "--validate", help="Validate an existing CSP string")
    parser.add_argument("--meta", action="store_true", help="Generate output as HTML <meta> tag format")
    args = parser.parse_args()

    # Mode 1: Validate existing CSP string
    if args.validate:
        issues = validate_csp(args.validate)
        print_audit_report(issues)
        sys.exit(0)

    if not args.target:
        parser.print_help()
        sys.exit(0)

    # Mode 2: Audit URL or file
    is_url = urlparse(args.target).scheme in ("http", "https")
    if is_url:
        generated_csp = audit_url(args.target)
    else:
        generated_csp = audit_file(args.target)

    # Print results
    print(f"{COLOR_BOLD}=== Generated Content Security Policy ==={COLOR_RESET}\n")
    if args.meta:
        print(f'{COLOR_CYAN}<meta http-equiv="Content-Security-Policy" content="{generated_csp}">{COLOR_RESET}')
    else:
        print(f"{COLOR_CYAN}Content-Security-Policy: {generated_csp}{COLOR_RESET}")
    print()

    # Validate generated policy just to make sure
    gen_issues = validate_csp(generated_csp)
    if gen_issues:
        print(f"{COLOR_YELLOW}Note: The generated policy has some warnings based on inline codes found in your page:{COLOR_RESET}")
        for iss in gen_issues:
            if "unsafe-inline" in iss["message"]:
                print(f"  - {iss['message']}")
        print()

if __name__ == "__main__":
    main()
