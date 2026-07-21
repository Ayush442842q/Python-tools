#!/usr/bin/env python3
"""
DNS Propagation Checker - Query multiple DNS providers for domain records

This utility checks how a domain's DNS records are resolved across different public
DNS networks (Cloudflare, Google, Quad9, DNS.SB) using their DNS-over-HTTPS (DoH) APIs.

Usage:
    python tools/dns_propagation_checker.py <domain> [--type RECORD_TYPE]

Example:
    python tools/dns_propagation_checker.py google.com --type A
    python tools/dns_propagation_checker.py github.com --type CNAME
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from typing import Dict, List, Optional

# Public DoH API endpoints
DNS_PROVIDERS = {
    "Cloudflare": "https://cloudflare-dns.com/dns-query",
    "Google": "https://dns.google/resolve",
    "Quad9": "https://dns.quad9.net:5053/dns-query",
}

# Mapping of record type names to standard integers
RECORD_TYPES = {
    "A": 1,
    "AAAA": 28,
    "CNAME": 5,
    "MX": 15,
    "TXT": 16,
    "NS": 2,
    "SOA": 6,
}

def query_doh_google_style(url: str, domain: str, rtype: str) -> List[str]:
    """Query a DoH endpoint that supports Google-style JSON format."""
    params = {
        "name": domain,
        "type": rtype,
    }
    query_string = urllib.parse.urlencode(params)
    req_url = f"{url}?{query_string}"
    
    req = urllib.request.Request(
        req_url,
        headers={"Accept": "application/dns-json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            answers = data.get("Answer", [])
            results = []
            for ans in answers:
                # Type might match what we asked for
                data_val = ans.get("data", "")
                results.append(data_val)
            return results if results else ["No records found"]
    except Exception as e:
        return [f"Error: {e}"]

def check_dns_propagation(domain: str, rtype: str) -> Dict[str, List[str]]:
    """Query all configured DNS providers for the domain and record type."""
    propagation_results = {}
    for provider, api_url in DNS_PROVIDERS.items():
        propagation_results[provider] = query_doh_google_style(api_url, domain, rtype)
    return propagation_results

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check DNS record propagation across multiple public DNS providers."
    )
    parser.add_argument("domain", help="The domain name to check (e.g., example.com)")
    parser.add_argument(
        "--type", "-t",
        default="A",
        choices=list(RECORD_TYPES.keys()),
        help="DNS record type to query (default: A)"
    )
    
    args = parser.parse_args()
    domain = args.domain.strip()
    rtype = args.type.upper()
    
    print("=" * 60)
    print(f"Checking DNS Propagation for: {domain} ({rtype})")
    print("=" * 60)
    
    results = check_dns_propagation(domain, rtype)
    
    # Print results in a clean table format
    provider_width = 15
    print(f"{'DNS Provider':<{provider_width}} | {'Resolved Records'}")
    print("-" * 60)
    
    for provider, records in results.items():
        records_str = ", ".join(records)
        print(f"{provider:<{provider_width}} | {records_str}")
        
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
