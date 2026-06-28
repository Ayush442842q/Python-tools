#!/usr/bin/env python3
"""
Subdomain Takeover Vulnerability Scanner
Scans subdomains for dangling CNAME records that point to unclaimed third-party
hosting providers (GitHub Pages, AWS S3, Heroku, Shopify, etc.).
"""

import sys
import re
import urllib.request
import urllib.error
import socket
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Optional

# ANSI Colors
COLORS = {
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "RESET": "\033[0m"
}

# Vulnerable service fingerprints (CNAME patterns and HTTP body signatures)
SIGNATURES = [
    {
        "name": "GitHub Pages",
        "cnames": ["github.io", "github.map.fastly.net"],
        "fingerprints": ["There isn't a GitHub Pages site here", "For root-level custom domains", "404 Not Found"]
    },
    {
        "name": "Amazon S3",
        "cnames": ["amazonaws.com", "s3.amazonaws.com", "s3-website"],
        "fingerprints": ["The specified bucket does not exist", "NoSuchBucket", "InvalidBucketName"]
    },
    {
        "name": "Heroku",
        "cnames": ["herokudns.com", "herokuapp.com", "herokucdn.com"],
        "fingerprints": ["No such app", "herokucdn.com/error-pages/no-such-app.html", "item-not-found"]
    },
    {
        "name": "Shopify",
        "cnames": ["myshopify.com", "shops.myshopify.com"],
        "fingerprints": ["Sorry, this shop is currently unavailable", "Only one step left", "custom_domain_needs_redirect"]
    },
    {
        "name": "Zendesk",
        "cnames": ["zendesk.com"],
        "fingerprints": ["Help Center Closed", "No such help center", "this help center does not exist"]
    },
    {
        "name": "Surge.sh",
        "cnames": ["surge.sh"],
        "fingerprints": ["project not found", "Surge: page not found"]
    },
    {
        "name": "Ghost.io",
        "cnames": ["ghost.io"],
        "fingerprints": ["The thing you were looking for is no longer here", "Ghost - Site unavailable"]
    },
    {
        "name": "Tumblr",
        "cnames": ["tumblr.com"],
        "fingerprints": ["Whatever you were looking for doesn't exist", "Here is where it would be"]
    },
    {
        "name": "Cargo Collective",
        "cnames": ["cargocollective.com", "cargo.site"],
        "fingerprints": ["404 Not Found", "If you are the owner of this project"]
    },
    {
        "name": "Bitbucket",
        "cnames": ["bitbucket.io"],
        "fingerprints": ["Repository not found", "404 - Page not found"]
    }
]

def query_cname_nslookup(subdomain: str) -> Optional[str]:
    """Fallback method using system nslookup to find CNAME even if it doesn't resolve (NXDOMAIN)."""
    try:
        # Run nslookup
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        cmd = ["nslookup", "-querytype=CNAME", subdomain]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, startupinfo=startupinfo)
        
        # Parse output for canonical name / aliases
        # Windows: "Aliases:  target.com" or "canonical name = target.com"
        # Linux: "subdomain.com canonical name = target.com."
        output = result.stdout
        match = re.search(r"canonical name\s*=\s*([^\s\n]+)", output, re.IGNORECASE)
        if match:
            return match.group(1).rstrip(".")
            
        match_alias = re.search(r"Aliases:\s*([^\s\n]+)", output, re.IGNORECASE)
        if match_alias:
            return match_alias.group(1).rstrip(".")
            
    except Exception:
        pass
    return None

def get_cname(subdomain: str) -> Optional[str]:
    """Retrieve CNAME for a given subdomain using socket resolution first, falling back to nslookup."""
    try:
        # Attempt standard resolution
        name, _, _ = socket.gethostbyname_ex(subdomain)
        if name != subdomain:
            return name
    except socket.gaierror:
        # If it failed to resolve, it might be a dangling CNAME (NXDOMAIN on target). Use nslookup.
        return query_cname_nslookup(subdomain)
    except Exception:
        pass
    return None

def check_http_fingerprint(url: str, fingerprints: List[str]) -> Tuple[bool, str]:
    """Send HTTP request to url and check if any signature fingerprints are in the response body."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SubdomainTakeoverScanner/1.0'}
        )
        # Use short timeouts to keep execution fast
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            for fp in fingerprints:
                if fp.lower() in html.lower():
                    return True, fp
    except urllib.error.HTTPError as e:
        # Check HTTP error body (e.g. 404 page often contains the fingerprint)
        try:
            html = e.read().decode('utf-8', errors='ignore')
            for fp in fingerprints:
                if fp.lower() in html.lower():
                    return True, fp
        except Exception:
            pass
    except Exception:
        pass
    return False, ""

def scan_subdomain(subdomain: str, verbose: bool) -> Dict[str, Any]:
    """Analyze a single subdomain for takeover vulnerability."""
    result = {
        "subdomain": subdomain,
        "cname": None,
        "vulnerable": False,
        "service": None,
        "confidence": "Low",
        "details": ""
    }
    
    cname = get_cname(subdomain)
    if not cname:
        if verbose:
            print(f"[{subdomain}] No CNAME record found.")
        return result
        
    result["cname"] = cname
    
    # Match CNAME against signatures
    matched_service = None
    for service in SIGNATURES:
        for pattern in service["cnames"]:
            if pattern in cname.lower():
                matched_service = service
                break
        if matched_service:
            break
            
    if not matched_service:
        if verbose:
            print(f"[{subdomain}] CNAME points to {cname} (no known signatures match).")
        return result
        
    result["service"] = matched_service["name"]
    
    # CNAME matches a vulnerable service! Check if target points to unclaimed resource.
    # 1. Check if the target CNAME resolved IP exists (is the domain resolving to anything?)
    dangling_dns = False
    try:
        socket.gethostbyname(cname)
    except socket.gaierror:
        # CNAME target fails to resolve, this is a dangling CNAME!
        dangling_dns = True
        
    # 2. Check HTTP responses for signature fingerprints
    vuln_found = False
    matched_fp = ""
    for proto in ["http://", "https://"]:
        is_vuln, fp = check_http_fingerprint(f"{proto}{subdomain}", matched_service["fingerprints"])
        if is_vuln:
            vuln_found = True
            matched_fp = fp
            break
            
    if vuln_found:
        result["vulnerable"] = True
        result["confidence"] = "High"
        result["details"] = f"HTTP signature matched: '{matched_fp}'"
    elif dangling_dns:
        result["vulnerable"] = True
        result["confidence"] = "Medium"
        result["details"] = f"CNAME '{cname}' does not resolve to any IP (dangling record)."
    else:
        result["details"] = f"CNAME points to {matched_service['name']}, but no active takeover signature was found."

    return result

def main():
    parser = argparse.ArgumentParser(
        description="Subdomain Takeover Vulnerability Scanner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/subdomain_takeover_scanner.py -s dev.example.com staging.example.com
  python tools/subdomain_takeover_scanner.py -f subdomains.txt -t 20
        """
    )
    parser.add_argument("-s", "--subdomains", nargs="+", help="Direct list of subdomains to scan")
    parser.add_argument("-f", "--file", help="Path to file containing subdomains (one per line)")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of concurrent scanner threads (default: 10)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose logs during scanning")

    args = parser.parse_args()

    subdomains_list = []
    
    # Load subdomains from file
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        subdomains_list.append(s)
        except Exception as e:
            print(f"Error loading subdomain file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)

    # Load direct subdomains
    if args.subdomains:
        subdomains_list.extend([s.strip() for s in args.subdomains if s.strip()])

    if not subdomains_list:
        print("Error: No subdomains specified. Use -s/--subdomains or -f/--file to specify targets.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # De-duplicate list
    subdomains_list = list(set(subdomains_list))

    print(f"\nStarting subdomain takeover scan on {len(subdomains_list)} targets using {args.threads} threads...\n")

    vulnerable_findings = []
    
    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Submit all jobs
            future_to_sub = {executor.submit(scan_subdomain, sub, args.verbose): sub for sub in subdomains_list}
            
            for future in as_completed(future_to_sub):
                sub = future_to_sub[future]
                try:
                    res = future.result()
                    if res["vulnerable"]:
                        vulnerable_findings.append(res)
                        conf_color = COLORS["RED"] if res["confidence"] == "High" else COLORS["YELLOW"]
                        print(f" {COLORS['RED']}[VULNERABLE]{COLORS['RESET']} {COLORS['BOLD']}{res['subdomain']}{COLORS['RESET']}")
                        print(f"   CNAME:      {res['cname']}")
                        print(f"   Service:    {res['service']}")
                        print(f"   Confidence: {conf_color}{res['confidence']}{COLORS['RESET']}")
                        print(f"   Details:    {res['details']}\n")
                    elif args.verbose and res["cname"]:
                        print(f" [SECURE] {res['subdomain']} -> CNAME: {res['cname']} ({res['details']})")
                except Exception as e:
                    print(f"Error scanning {sub}: {e}", file=sys.stderr)
                    
    except KeyboardInterrupt:
        print("\nScan aborted by user.")
        sys.exit(0)

    # Summary
    print(f"--- Scan Summary ---")
    print(f"Total scanned:      {len(subdomains_list)}")
    print(f"Vulnerable found:   {len(vulnerable_findings)}")
    
    if vulnerable_findings:
        print(f"\n{COLORS['RED']}{COLORS['BOLD']}WARNING: Found {len(vulnerable_findings)} potential subdomain takeovers!{COLORS['RESET']}")
        sys.exit(1)
    else:
        print(f"\n{COLORS['GREEN']}All clear! No subdomain takeover vulnerabilities detected.{COLORS['RESET']}")
        sys.exit(0)

if __name__ == "__main__":
    main()
