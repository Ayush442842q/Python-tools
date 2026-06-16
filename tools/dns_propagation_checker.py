#!/usr/bin/env python3
"""
DNS Propagation Checker

Query multiple global DNS-over-HTTPS (DoH) providers in parallel to verify
if domain DNS records have propagated globally.
Supports record types: A, AAAA, CNAME, MX, TXT, NS.

Usage:
    python tools/dns_propagation_checker.py google.com
    python tools/dns_propagation_checker.py example.com -t MX
    python tools/dns_propagation_checker.py mydomain.com --json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"

# Global DoH Endpoints
DOH_PROVIDERS = {
    "Cloudflare (Global)": {
        "url": "https://cloudflare-dns.com/dns-query",
        "headers": {"Accept": "application/dns-json"},
        "format": "rfc8427"
    },
    "Google (Global)": {
        "url": "https://dns.google/resolve",
        "headers": {},
        "format": "google"
    },
    "Quad9 (Secure)": {
        "url": "https://dns.quad9.net/dns-query",
        "headers": {"Accept": "application/dns-json"},
        "format": "rfc8427"
    },
    "Alibaba (Asia)": {
        "url": "https://dns.alidns.com/resolve",
        "headers": {},
        "format": "google"
    },
    "AdGuard (Blocker)": {
        "url": "https://dns.adguard-dns.com/resolve",
        "headers": {},
        "format": "google"
    }
}

# DNS Response Codes (RCODE) mapping
RCODES = {
    0: "NOERROR",
    1: "FORMERR",
    2: "SERVFAIL",
    3: "NXDOMAIN",
    4: "NOTIMP",
    5: "REFUSED",
    6: "YXDOMAIN",
    7: "YXRRSET",
    8: "NXRRSET",
    9: "NOTAUTH",
    10: "NOTZONE"
}

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def query_doh(provider_name: str, domain: str, record_type: str, timeout: float = 4.0) -> Dict[str, Any]:
    """Queries a specific DoH provider for a domain and record type."""
    provider = DOH_PROVIDERS[provider_name]
    params = {"name": domain, "type": record_type}
    query_str = urllib.parse.urlencode(params)
    url = f"{provider['url']}?{query_str}"
    
    req = urllib.request.Request(url, headers=provider["headers"])
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return {"provider": provider_name, "error": f"HTTP {response.status}", "records": []}
            
            data = json.loads(response.read().decode('utf-8'))
            
            # Check response status code
            status_code = data.get("Status", 0)
            status_desc = RCODES.get(status_code, f"UNKNOWN({status_code})")
            
            records = []
            if "Answer" in data:
                for ans in data["Answer"]:
                    # Clean trailing dots in names if any
                    ans_data = ans.get("data", "")
                    if isinstance(ans_data, str) and ans_data.endswith(".") and len(ans_data) > 1:
                        ans_data = ans_data[:-1]
                    records.append(ans_data)
                    
            return {
                "provider": provider_name,
                "status": status_desc,
                "records": sorted(records),
                "error": None
            }
    except Exception as e:
        return {
            "provider": provider_name,
            "error": str(e),
            "records": []
        }

def run_propagation_check(domain: str, record_type: str) -> List[Dict[str, Any]]:
    """Runs DNS queries across all providers in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=len(DOH_PROVIDERS)) as executor:
        futures = {
            executor.submit(query_doh, name, domain, record_type): name 
            for name in DOH_PROVIDERS
        }
        for future in futures:
            results.append(future.result())
    return results

def print_table(domain: str, record_type: str, results: List[Dict[str, Any]]):
    """Prints results in a beautiful ASCII table."""
    print("\n" + color_text(f"DNS Propagation Report for: {domain} ({record_type} Records)", COLOR_BOLD))
    print(color_text("=" * 80, COLOR_DIM))
    
    # Header
    print(f"{color_text('DNS Provider', COLOR_BOLD):<25} | {color_text('Status', COLOR_BOLD):<10} | {color_text('Resolved Value(s)', COLOR_BOLD)}")
    print("-" * 80)
    
    # Rows
    for res in results:
        provider = res["provider"]
        if res["error"]:
            status = color_text("ERROR", COLOR_RED)
            resolved = color_text(res["error"], COLOR_RED)
        else:
            status_str = res["status"]
            if status_str == "NOERROR":
                status = color_text(status_str, COLOR_GREEN)
            else:
                status = color_text(status_str, COLOR_YELLOW)
                
            records = res["records"]
            if not records:
                resolved = color_text("(No records found)", COLOR_DIM)
            elif len(records) == 1:
                resolved = color_text(records[0], COLOR_BOLD)
            else:
                resolved = color_text(", ".join(records), COLOR_BOLD)
                
        print(f"{provider:<25} | {status:<10} | {resolved}")
        
    print(color_text("=" * 80, COLOR_DIM))
    
    # Check consistency
    valid_results = [r for r in results if not r["error"]]
    if len(valid_results) > 1:
        first_records = valid_results[0]["records"]
        consistent = all(r["records"] == first_records for r in valid_results)
        if consistent:
            print(color_text("[+] Propagation Status: CONSISTENT (All queried servers resolve identically)", COLOR_GREEN))
        else:
            print(color_text("[!] Propagation Status: INCONSISTENT (Resolvers show different record states)", COLOR_YELLOW))

def main():
    parser = argparse.ArgumentParser(
        description="DNS Propagation Checker: Check DNS propagation status globally using DoH endpoints.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("domain", help="The domain name to check (e.g. google.com)")
    parser.add_argument("-t", "--type", default="A", choices=["A", "AAAA", "CNAME", "MX", "TXT", "NS"],
                        help="DNS Record type (default: A)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    # Clean domain name
    domain = args.domain.strip()
    if not domain:
        print(color_text("[-] Invalid domain", COLOR_RED), file=sys.stderr)
        sys.exit(1)
        
    record_type = args.type.upper()
    
    if not args.json:
        print(f"Checking {record_type} records for {domain} across global resolvers...")
        
    results = run_propagation_check(domain, record_type)
    
    if args.json:
        print(json.dumps({
            "domain": domain,
            "record_type": record_type,
            "results": results
        }, indent=2))
    else:
        print_table(domain, record_type, results)

if __name__ == "__main__":
    main()
