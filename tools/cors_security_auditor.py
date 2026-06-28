#!/usr/bin/env python3
"""
CORS Security Auditor
Scans HTTP/REST API endpoints for CORS (Cross-Origin Resource Sharing) misconfigurations
and vulnerabilities.
Vulnerability checks performed:
1. Reflected Origin (Access-Control-Allow-Origin matches custom/arbitrary origin)
2. Reflected Origin with Credentials Allowed (High Risk)
3. Null Origin Trust (Access-Control-Allow-Origin: null)
4. Weak Subdomain Match validation (e.g. eviltarget.com or target.com.evil.com allowed)
5. Insecure HTTP Origin allowed on HTTPS site
6. Wildcard Origin (*) with Credentials allowed
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_BOLD = "\033[1m"

def print_banner():
    print(f"{CLR_BOLD}{CLR_CYAN}")
    print(" ┌────────────────────────────────────────────────────────┐")
    print(" │                 CORS Security Auditor                  │")
    print(" │      Analyze and detect CORS API vulnerabilities       │")
    print(" └────────────────────────────────────────────────────────┘")
    print(CLR_RESET)

def send_request(url, origin, method="GET", extra_headers=None):
    """Sends HTTP request and returns headers, status, and error info."""
    headers = {
        "User-Agent": "Mozilla/5.0 (CORS Security Auditor)",
    }
    if origin:
        headers["Origin"] = origin
    if extra_headers:
        for k, v in extra_headers.items():
            headers[k] = v

    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.headers, None
    except urllib.error.HTTPError as e:
        # Many servers return CORS headers even on 4xx/5xx responses
        return e.code, e.headers, f"HTTP Error {e.code}"
    except Exception as e:
        return 0, {}, str(e)

def analyze_cors(url, method="GET", extra_headers=None):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    scheme = parsed_url.scheme
    
    # Define test origins
    test_origins = {
        "control": None,
        "arbitrary_evil": "https://evil.com",
        "null_origin": "null",
        "subdomain_suffix": f"https://{domain}.evil.com",
        "prefixed_subdomain": f"https://evil{domain}",
    }
    
    # If the site is HTTPS, test if it trusts HTTP origin
    if scheme == "https":
        test_origins["insecure_http"] = f"http://{domain}"

    results = {}
    
    print(f"Auditing endpoint: {CLR_BOLD}{url}{CLR_RESET} [Method: {method}]")
    print("Running CORS origin reflection tests...")
    
    for test_name, origin in test_origins.items():
        status, headers, error = send_request(url, origin, method, extra_headers)
        if error and status == 0:
            print(f"  ❌ Error connecting for origin {origin}: {error}")
            continue
        
        # Extract CORS headers (case-insensitive)
        acao = None
        acac = None
        acam = None
        acah = None
        vary = None
        
        for k, v in headers.items():
            k_lower = k.lower()
            if k_lower == "access-control-allow-origin":
                acao = v
            elif k_lower == "access-control-allow-credentials":
                acac = v.lower()
            elif k_lower == "access-control-allow-methods":
                acam = v
            elif k_lower == "access-control-allow-headers":
                acah = v
            elif k_lower == "vary":
                vary = v
                
        results[test_name] = {
            "origin": origin,
            "status": status,
            "acao": acao,
            "acac": acac,
            "vary": vary
        }
        
    evaluate_vulnerabilities(results, test_origins, scheme)

def evaluate_vulnerabilities(results, test_origins, scheme):
    vulnerabilities = []
    
    # Check 1: Arbitrary Evil Origin Reflection
    arb = results.get("arbitrary_evil")
    if arb and arb["acao"] == "https://evil.com":
        risk = "HIGH" if arb["acac"] == "true" else "LOW"
        desc = ("The server reflects arbitrary origins ('https://evil.com') in Access-Control-Allow-Origin."
                + (" Combined with allowed credentials, this is a CRITICAL vulnerability that lets any website access authenticated user data." if risk == "HIGH" else " Without credentials allowed, the risk is reduced but still violates standard practices."))
        vulnerabilities.append({
            "name": "Reflected Origin (Arbitrary Website Trust)",
            "risk": risk,
            "details": f"Origin: https://evil.com  ->  ACAO: {arb['acao']} | Credentials: {arb['acac'] or 'false'}",
            "description": desc
        })

    # Check 2: Null Origin Trust
    nul = results.get("null_origin")
    if nul and nul["acao"] == "null":
        risk = "HIGH" if nul["acac"] == "true" else "MEDIUM"
        desc = ("The server trusts the 'null' origin. This allows malicious iframe-sandboxed pages or local HTML files "
                "to perform cross-origin requests.")
        vulnerabilities.append({
            "name": "Null Origin Trusted",
            "risk": risk,
            "details": f"Origin: null  ->  ACAO: null | Credentials: {nul['acac'] or 'false'}",
            "description": desc
        })

    # Check 3: Weak Subdomain Validation (Suffix Match)
    suff = results.get("subdomain_suffix")
    if suff and suff["acao"] == test_origins["subdomain_suffix"]:
        risk = "HIGH" if suff["acac"] == "true" else "MEDIUM"
        desc = ("The server validates the target domain weakly (regex suffix check failed). Allowing '.evil.com' suffix "
                "allows attackers to register domains ending in your domain to steal data.")
        vulnerabilities.append({
            "name": "Weak Domain Validation (Suffix Match)",
            "risk": risk,
            "details": f"Origin: {test_origins['subdomain_suffix']}  ->  ACAO: reflected",
            "description": desc
        })

    # Check 4: Weak Subdomain Validation (Prefix Match)
    pref = results.get("prefixed_subdomain")
    if pref and pref["acao"] == test_origins["prefixed_subdomain"]:
        risk = "HIGH" if pref["acac"] == "true" else "MEDIUM"
        desc = ("The server validates domain weakly (regex prefix check failed). Allowing prepended domain variations "
                "allows attackers to buy domains like 'eviltarget.com' to bypass CORS.")
        vulnerabilities.append({
            "name": "Weak Domain Validation (Prefix Match)",
            "risk": risk,
            "details": f"Origin: {test_origins['prefixed_subdomain']}  ->  ACAO: reflected",
            "description": desc
        })

    # Check 5: Insecure HTTP Origin Allowed
    insec = results.get("insecure_http")
    if insec and insec["acao"] == test_origins.get("insecure_http"):
        risk = "MEDIUM" if insec["acac"] == "true" else "LOW"
        desc = "The HTTPS API allows requests from insecure HTTP origins, exposing the connection to MitM (Man-in-the-Middle) hijack attacks."
        vulnerabilities.append({
            "name": "Insecure HTTP Origin Allowed",
            "risk": risk,
            "details": f"Origin: {test_origins['insecure_http']}  ->  ACAO: reflected",
            "description": desc
        })

    # Check 6: Wildcard with credentials
    control = results.get("control")
    # Also check if wildcards are returned for any test
    for k, v in results.items():
        if v["acao"] == "*" and v["acac"] == "true":
            vulnerabilities.append({
                "name": "Wildcard Origin (*) with Credentials Enabled",
                "risk": "MEDIUM",
                "details": "ACAO: * | Credentials: true",
                "description": "Standard browsers block wildcard headers when credentials are allowed, but this configuration is invalid and shows weak security designs."
            })
            break

    # Output Results
    print("\n" + "=" * 80)
    print(f"🔬 {CLR_BOLD}CORS AUDIT RESULTS SUMMARY{CLR_RESET}")
    print("=" * 80)
    
    if not vulnerabilities:
        print(f"🎉 {CLR_GREEN}{CLR_BOLD}No CORS vulnerabilities detected!{CLR_RESET}")
        print("The API behaves securely and does not reflect untrusted origins.")
        
        # Show control CORS headers
        ctrl = results.get("control") or list(results.values())[0]
        print(f"Control headers returned:")
        print(f"  Access-Control-Allow-Origin: {ctrl.get('acao') or 'Not Set'}")
        print(f"  Access-Control-Allow-Credentials: {ctrl.get('acac') or 'Not Set'}")
        print(f"  Vary: {ctrl.get('vary') or 'Not Set'}")
    else:
        for v in vulnerabilities:
            color = CLR_RED if v["risk"] == "HIGH" else (CLR_YELLOW if v["risk"] == "MEDIUM" else CLR_BLUE)
            print(f"[{color}{CLR_BOLD}{v['risk']}{CLR_RESET}] {CLR_BOLD}{v['name']}{CLR_RESET}")
            print(f"   Details    : {v['details']}")
            print(f"   Description: {v['description']}")
            print("-" * 80)
            
    print("=" * 80 + "\n")

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="CORS Security Auditor - Audits HTTP API endpoints for CORS misconfigurations")
    parser.add_argument("url", help="API URL to check (e.g. 'https://api.example.com/v1/user')")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST", "OPTIONS", "PUT", "DELETE"], help="HTTP Method (default: GET)")
    parser.add_argument("-d", "--data", help="JSON string data to send in the request body")
    parser.add_argument("-H", "--header", action="append", help="Extra request headers (Format: 'Name: Value')")
    
    args = parser.parse_args()
    
    extra_headers = {}
    if args.header:
        for h in args.header:
            if ":" not in h:
                print(f"Error: Invalid header format '{h}'. Must be 'Name: Value'.", file=sys.stderr)
                return 1
            k, v = h.split(":", 1)
            extra_headers[k.strip()] = v.strip()
            
    if args.data:
        extra_headers["Content-Type"] = "application/json"
        
    analyze_cors(args.url, args.method, extra_headers)
    return 0

if __name__ == "__main__":
    sys.exit(main())
