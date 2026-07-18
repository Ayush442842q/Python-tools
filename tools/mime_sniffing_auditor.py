#!/usr/bin/env python3
"""
HTTP MIME Sniffing & Security Headers Auditor

A standalone utility to probe web applications for missing security headers
and MIME-type sniffing vulnerabilities.
1. Connects to target URLs using Python's built-in `urllib.request`.
2. Inspects response headers for:
   - X-Content-Type-Options: nosniff (Prevent MIME sniffing)
   - Content-Security-Policy (Mitigate XSS/injection)
   - X-Frame-Options (Clickjacking)
   - Strict-Transport-Security (HSTS)
   - Referrer-Policy
3. Body signature matching: reads the prefix of the payload bytes to verify
   if it matches the server-declared Content-Type (detecting file upload scripting bypasses).
4. Generates a security scorecard with grades.

Usage:
    python mime_sniffing_auditor.py https://example.com
"""

import sys
import os
import argparse
import urllib.request
import urllib.error
import re

# File signature magic bytes
SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'%PDF-': 'application/pdf',
    b'PK\x03\x04': 'application/zip',
}

# String prefixes indicating text/html or scripts
HTML_PREFIXES = [
    re.compile(b'^\\s*<!doctype\\s+html', re.IGNORECASE),
    re.compile(b'^\\s*<html', re.IGNORECASE),
    re.compile(b'^\\s*<script', re.IGNORECASE),
    re.compile(b'^\\s*<head', re.IGNORECASE),
    re.compile(b'^\\s*<body', re.IGNORECASE),
    re.compile(b'^\\s*<svg', re.IGNORECASE)
]

def sniff_mime_type(body_prefix):
    """Attempts to match magic bytes or text patterns to identify actual mime type."""
    # Check binary magic signatures
    for sig, mime in SIGNATURES.items():
        if body_prefix.startswith(sig):
            return mime
            
    # Check text/HTML tags
    for pattern in HTML_PREFIXES:
        if pattern.match(body_prefix):
            return 'text/html'
            
    return None

def analyze_headers(headers):
    """Audits HTTP headers for security posture, returns scores and comments."""
    score = 100
    findings = []
    
    # 1. X-Content-Type-Options
    x_cto = headers.get('X-Content-Type-Options', '').lower()
    if 'nosniff' not in x_cto:
        score -= 30
        findings.append(("\033[91m[-] Missing X-Content-Type-Options: nosniff\033[0m", 
                         "Allows browsers to sniff mime types. HTML/JS payloads hidden in files (like PNGs) could be executed."))
    else:
        findings.append(("\033[92m[✓] X-Content-Type-Options: nosniff is set\033[0m", "MIME type sniffing is securely disabled."))
        
    # 2. Content-Security-Policy
    csp = headers.get('Content-Security-Policy', '')
    if not csp:
        score -= 25
        findings.append(("\033[91m[-] Missing Content-Security-Policy (CSP)\033[0m", 
                         "Leaves application vulnerable to Cross-Site Scripting (XSS) and data injection attacks."))
    else:
        findings.append(("\033[92m[✓] Content-Security-Policy is present\033[0m", "CSP helps restrict resource loads and execution."))
        
    # 3. X-Frame-Options
    xfo = headers.get('X-Frame-Options', '').lower()
    frame_ancestors = 'frame-ancestors' in csp.lower()
    if not xfo and not frame_ancestors:
        score -= 15
        findings.append(("\033[91m[-] Missing clickjacking protection\033[0m", 
                         "Neither X-Frame-Options nor CSP frame-ancestors is configured. Site can be embedded in iframes."))
    else:
        findings.append(("\033[92m[✓] Clickjacking protection is active\033[0m", "Site embedding in iframes is restricted."))
        
    # 4. Strict-Transport-Security (HSTS)
    hsts = headers.get('Strict-Transport-Security', '')
    if not hsts:
        score -= 15
        findings.append(("\033[93m[!] Missing Strict-Transport-Security (HSTS)\033[0m", 
                         "Connection can be downgraded to HTTP via SSL strip MITM attacks."))
    else:
        findings.append(("\033[92m[✓] Strict-Transport-Security (HSTS) is active\033[0m", "Forces HTTPS connections securely."))
        
    # 5. Referrer-Policy
    ref = headers.get('Referrer-Policy', '')
    if not ref:
        score -= 15
        findings.append(("\033[93m[!] Missing Referrer-Policy\033[0m", 
                         "Leaking sensitive path routing details to external link destinations."))
    else:
        findings.append(("\033[92m[✓] Referrer-Policy is present\033[0m", "Controls referral source details leaked."))
        
    return max(0, score), findings

def get_grade(score):
    """Maps score out of 100 to standard letter grade."""
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 60: return 'D'
    return 'F'

def audit_url(url, user_agent="Mozilla/5.0 (MIME Auditor)"):
    """Fetches URL response, extracts headers and body prefix, and audits them."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': user_agent}
    )
    
    print(f"Connecting to target: {url} ...")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as response:
            headers = dict(response.info())
            body_prefix = response.read(512)
            actual_url = response.geturl()
    except urllib.error.HTTPError as e:
        headers = dict(e.info())
        body_prefix = e.read(512)
        actual_url = url
    except Exception as e:
        return None, f"Failed connecting to endpoint: {e}"

    # Extract declared Content-Type header
    declared_ct = headers.get('Content-Type', '').split(';')[0].strip().lower()
    
    # 1. Analyze Header Security
    score, findings = analyze_headers(headers)
    
    # 2. Analyze MIME Sniffing safety mismatch
    mime_mismatch_warning = None
    sniffed_type = sniff_mime_type(body_prefix)
    
    nosniff_present = 'nosniff' in headers.get('X-Content-Type-Options', '').lower()
    
    if sniffed_type and declared_ct:
        # Check if actual bytes mismatch declared type
        if sniffed_type != declared_ct:
            # If server declared it is image/png but bytes are HTML
            if sniffed_type == 'text/html' and declared_ct != 'text/html':
                if not nosniff_present:
                    mime_mismatch_warning = (
                        f"\033[91m[-] CRITICAL: MIME Mismatch Vulnerability!\033[0m\n"
                        f"    Declared Type: {declared_ct}\n"
                        f"    Sniffed Type : {sniffed_type}\n"
                        f"    Impact       : Lacks 'nosniff' protection. Browsers will execute HTML/JS hidden in this file."
                    )
                else:
                    mime_mismatch_warning = (
                        f"\033[93m[!] Alert: MIME Mismatch Detected (mitigated by nosniff)\033[0m\n"
                        f"    Declared Type: {declared_ct}\n"
                        f"    Sniffed Type : {sniffed_type}\n"
                        f"    Note         : Browser execution is blocked because 'X-Content-Type-Options: nosniff' is set."
                    )

    return {
        'url': actual_url,
        'declared_ct': declared_ct,
        'score': score,
        'grade': get_grade(score),
        'findings': findings,
        'mismatch': mime_mismatch_warning
    }, None

def main():
    parser = argparse.ArgumentParser(
        description="Verify web endpoint security headers and identify MIME-type execution risks.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="Target URL to audit (e.g. https://example.com).")
    args = parser.parse_args()

    target_url = args.url
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    res, err = audit_url(target_url)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("\nHTTP MIME Sniffing & Header Security Audit Report")
    print("=" * 75)
    print(f"Target URL   : {res['url']}")
    print(f"Content-Type : {res['declared_ct'] if res['declared_ct'] else 'N/A'}")
    print(f"Safety Score : {res['score']}/100")
    print(f"Grade Rank   : {res['grade']}")
    print("=" * 75)

    print("\n[Header Findings]")
    print("-" * 75)
    for title, desc in res['findings']:
        print(f"  {title}")
        print(f"    └── {desc}")
        print()

    if res['mismatch']:
        print("-" * 75)
        print("[MIME Verification]")
        print(res['mismatch'])
        print()

    print("=" * 75)
    return 0

if __name__ == "__main__":
    sys.exit(main())
