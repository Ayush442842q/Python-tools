#!/usr/bin/env python3
"""
HTTP HSTS Preload & Security Header Checker

Audits domain or URL HTTP Strict Transport Security (HSTS) headers, evaluates
max-age, includeSubDomains, and preload directives, checks HTTPS redirection,
and verifies certificate readiness for HSTS Preload List submission.

Usage:
    python tools/http_hsts_preload_checker.py example.com
    python tools/http_hsts_preload_checker.py https://api.github.com --json
    python tools/http_hsts_preload_checker.py github.com --verbose
"""

import sys
import os
import ssl
import json
import socket
import argparse
from typing import Dict, Any, List, Tuple
import urllib.request
import urllib.error
from urllib.parse import urlparse

# ANSI terminal styling
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def is_color_enabled() -> bool:
    return sys.stdout.isatty() and os.name != 'nt' or os.getenv('COLORTERM') is not None or os.name == 'nt'


def colorize(text: str, color_code: str) -> str:
    if is_color_enabled():
        return f"{color_code}{text}{COLOR_RESET}"
    return text


def parse_hsts_header(header_value: str) -> Dict[str, Any]:
    """Parse HSTS Strict-Transport-Security header into directives."""
    directives = {}
    if not header_value:
        return directives

    parts = header_value.split(";")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            directives[key.strip().lower()] = val.strip().strip('"\'')
        else:
            directives[part.lower()] = True
    return directives


def check_https_redirect(domain: str) -> Tuple[bool, str, str]:
    """Check if http://domain redirects to https://."""
    http_url = f"http://{domain}"
    try:
        req = urllib.request.Request(http_url, headers={"User-Agent": "HSTS-Preload-Checker/1.0"})
        # Custom redirect handler to inspect location
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirectHandler)
        try:
            res = opener.open(req, timeout=8)
            return False, f"HTTP did not redirect (status code {res.status})", http_url
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                location = e.headers.get("Location", "")
                if location.startswith("https://"):
                    return True, f"Redirects ({e.code}) to {location}", location
                else:
                    return False, f"Redirects ({e.code}) to non-HTTPS URL: {location}", location
            return False, f"HTTP returned status {e.code}", http_url
    except Exception as ex:
        return False, f"HTTP connection error: {str(ex)}", http_url


def check_ssl_certificate(hostname: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Verify SSL certificate validity and return details."""
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, 443), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in cert.get('subject', []))
                issuer = dict(x[0] for x in cert.get('issuer', []))
                common_name = subject.get('commonName', 'Unknown')
                issuer_name = issuer.get('organizationName', issuer.get('commonName', 'Unknown'))
                not_after = cert.get('notAfter', 'Unknown')
                return True, "Valid SSL/TLS certificate", {
                    "commonName": common_name,
                    "issuer": issuer_name,
                    "expires": not_after
                }
    except Exception as ex:
        return False, f"SSL Certificate check failed: {str(ex)}", {}


def fetch_hsts_header(target_url: str) -> Tuple[int, Dict[str, str], str]:
    """Fetch headers for HTTPS target URL."""
    req = urllib.request.Request(target_url, headers={"User-Agent": "HSTS-Preload-Checker/1.0"})
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            headers = dict(response.info())
            return response.status, headers, ""
    except urllib.error.HTTPError as e:
        headers = dict(e.headers)
        return e.code, headers, f"HTTP status {e.code}"
    except Exception as ex:
        return 0, {}, str(ex)


def evaluate_hsts_preload_eligibility(
    domain: str,
    hsts_header: str,
    directives: Dict[str, Any],
    redirects_to_https: bool,
    valid_cert: bool
) -> Dict[str, Any]:
    """Evaluate requirements against Chromium/HSTS Preload List criteria."""
    checks = []
    eligible = True

    # 1. Valid SSL cert
    checks.append({
        "requirement": "Valid SSL/TLS Certificate",
        "passed": valid_cert,
        "detail": "Domain presents a valid trusted SSL certificate" if valid_cert else "SSL certificate invalid or connection failed"
    })
    if not valid_cert:
        eligible = False

    # 2. Redirect HTTP to HTTPS
    checks.append({
        "requirement": "HTTP to HTTPS Redirection",
        "passed": redirects_to_https,
        "detail": "http:// redirects to https://" if redirects_to_https else "HTTP root does not redirect to HTTPS"
    })
    if not redirects_to_https:
        eligible = False

    # 3. HSTS Header Presence
    has_header = bool(hsts_header)
    checks.append({
        "requirement": "Strict-Transport-Security Header Present",
        "passed": has_header,
        "detail": f"Header found: '{hsts_header}'" if has_header else "No Strict-Transport-Security header present"
    })
    if not has_header:
        eligible = False

    # 4. max-age requirement (minimum 31536000 seconds = 1 year)
    max_age_val = 0
    if "max-age" in directives:
        try:
            max_age_val = int(directives["max-age"])
        except ValueError:
            max_age_val = 0

    min_required_max_age = 31536000
    passed_max_age = max_age_val >= min_required_max_age
    checks.append({
        "requirement": "HSTS max-age >= 31,536,000 seconds (1 year)",
        "passed": passed_max_age,
        "detail": f"max-age={max_age_val} seconds ({max_age_val / 86400:.1f} days)" if has_header else "Missing max-age"
    })
    if not passed_max_age:
        eligible = False

    # 5. includeSubDomains directive
    has_subdomains = directives.get("includesubdomains") is True
    checks.append({
        "requirement": "includeSubDomains Directive Present",
        "passed": has_subdomains,
        "detail": "includeSubDomains enabled" if has_subdomains else "includeSubDomains directive missing"
    })
    if not has_subdomains:
        eligible = False

    # 6. preload directive
    has_preload = directives.get("preload") is True
    checks.append({
        "requirement": "preload Directive Present",
        "passed": has_preload,
        "detail": "preload directive present" if has_preload else "preload directive missing"
    })
    if not has_preload:
        eligible = False

    return {
        "eligible": eligible,
        "checks": checks
    }


def analyze_domain(target: str, verbose: bool = False) -> Dict[str, Any]:
    # Normalize input to domain name and https URL
    if not target.startswith("http://") and not target.startswith("https://"):
        domain = target.split("/")[0]
        https_url = f"https://{domain}"
    else:
        parsed = urlparse(target)
        domain = parsed.netloc or parsed.path.split("/")[0]
        https_url = f"https://{domain}"

    # Perform audits
    redirects_to_https, redirect_msg, redirect_url = check_https_redirect(domain)
    valid_cert, cert_msg, cert_info = check_ssl_certificate(domain)
    status_code, headers, fetch_err = fetch_hsts_header(https_url)

    # Search case-insensitively for Strict-Transport-Security
    hsts_header = ""
    for k, v in headers.items():
        if k.lower() == "strict-transport-security":
            hsts_header = v
            break

    directives = parse_hsts_header(hsts_header)
    evaluation = evaluate_hsts_preload_eligibility(
        domain, hsts_header, directives, redirects_to_https, valid_cert
    )

    return {
        "domain": domain,
        "https_url": https_url,
        "http_redirect": {
            "success": redirects_to_https,
            "message": redirect_msg,
            "target": redirect_url
        },
        "ssl_certificate": {
            "valid": valid_cert,
            "message": cert_msg,
            "info": cert_info
        },
        "http_response": {
            "status_code": status_code,
            "hsts_raw_header": hsts_header,
            "directives": directives,
            "error": fetch_err
        },
        "preload_evaluation": evaluation
    }


def print_report(results: Dict[str, Any], verbose: bool = False):
    print("=" * 68)
    print(colorize(f"  HSTS & Preload Audit Report: {results['domain']}", COLOR_BOLD + COLOR_HEADER))
    print("=" * 68)

    # SSL Certificate
    cert = results["ssl_certificate"]
    cert_status = colorize("[PASS]", COLOR_GREEN) if cert["valid"] else colorize("[FAIL]", COLOR_RED)
    print(f"\n{cert_status} SSL/TLS Certificate:")
    print(f"  Details: {cert['message']}")
    if cert["info"]:
        print(f"  Issuer: {cert['info'].get('issuer')} | Expires: {cert['info'].get('expires')}")

    # HTTP Redirect
    redir = results["http_redirect"]
    redir_status = colorize("[PASS]", COLOR_GREEN) if redir["success"] else colorize("[WARN]", COLOR_YELLOW)
    print(f"\n{redir_status} HTTP -> HTTPS Redirection:")
    print(f"  Details: {redir['message']}")

    # HSTS Header
    resp = results["http_response"]
    hsts_header = resp["hsts_raw_header"]
    print(f"\n[{colorize('HEADER', COLOR_CYAN)}] Strict-Transport-Security Header:")
    if hsts_header:
        print(f"  Raw: {colorize(hsts_header, COLOR_BOLD)}")
        print("  Parsed Directives:")
        for d, v in resp["directives"].items():
            val_str = f" = {v}" if isinstance(v, str) else ""
            print(f"    - {colorize(d, COLOR_CYAN)}{val_str}")
    else:
        print(f"  {colorize('No HSTS header detected!', COLOR_RED)}")

    # Preload Eligibility Evaluation
    eval_data = results["preload_evaluation"]
    is_eligible = eval_data["eligible"]
    print("\n" + "-" * 68)
    print(colorize("  Chromium HSTS Preload List Eligibility Requirements:", COLOR_BOLD))
    print("-" * 68)

    for chk in eval_data["checks"]:
        symbol = colorize("✓ PASS", COLOR_GREEN) if chk["passed"] else colorize("✗ FAIL", COLOR_RED)
        print(f"  [{symbol}] {chk['requirement']}")
        if verbose or not chk["passed"]:
            print(f"         └─ {chk['detail']}")

    print("\n" + "=" * 68)
    if is_eligible:
        print(colorize("  >>> ELIGIBLE FOR HSTS PRELOAD LIST <<<", COLOR_BOLD + COLOR_GREEN))
        print("  You can submit this domain at: https://hstspreload.org")
    else:
        print(colorize("  >>> NOT CURRENTLY ELIGIBLE FOR HSTS PRELOAD <<<", COLOR_BOLD + COLOR_RED))
        print("  Address the failed checks above before submitting to hstspreload.org.")
    print("=" * 68 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Audit HTTP Strict-Transport-Security (HSTS) headers and HSTS Preload list readiness for a domain."
    )
    parser.add_argument("target", help="Domain name or URL to check (e.g. example.com or https://example.com)")
    parser.add_argument("--json", action="store_true", help="Output audit results in JSON format")
    parser.add_argument("-v", "--verbose", action="store_true", help="Display verbose diagnostic output")

    args = parser.parse_args()

    results = analyze_domain(args.target, verbose=args.verbose)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, verbose=args.verbose)

    sys.exit(0 if results["preload_evaluation"]["eligible"] else 1)


if __name__ == "__main__":
    main()
