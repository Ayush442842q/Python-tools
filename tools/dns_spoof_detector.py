#!/usr/bin/env python3
"""
DNS Spoofing & Hijacking Detector - Zero-dependency security diagnostics
Detects if local DNS resolutions are spoofed, hijacked, or redirected (common in
captive portals, ISP ad-injection, DNS filtering, or MITM attacks).
It compares local UDP DNS resolutions with secure, encrypted DNS-over-HTTPS (DoH)
queries to Cloudflare and Google, checking for discrepancies and private IP routing.
"""

import argparse
import json
import socket
import sys
import urllib.request
from typing import Dict, List, Set, Tuple

# Default secure target domains to check
DEFAULT_DOMAINS = [
    "google.com",
    "github.com",
    "amazon.com",
    "facebook.com",
    "wikipedia.org",
    "microsoft.com",
    "apple.com",
    "cloudflare.com"
]

# DoH Endpoints (JSON APIs)
CLOUDFLARE_DOH = "https://cloudflare-dns.com/dns-query"
GOOGLE_DOH = "https://dns.google/resolve"

def query_doh_cloudflare(domain: str) -> List[str]:
    """Query Cloudflare DoH API for A records of the domain."""
    url = f"{CLOUDFLARE_DOH}?name={domain}&type=A"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            ips = []
            if "Answer" in data:
                for ans in data["Answer"]:
                    if ans.get("type") == 1:  # Type 1 is A record
                        ips.append(ans["data"])
            return ips
    except Exception:
        return []

def query_doh_google(domain: str) -> List[str]:
    """Query Google DoH API for A records of the domain."""
    url = f"{GOOGLE_DOH}?name={domain}&type=A"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            ips = []
            if "Answer" in data:
                for ans in data["Answer"]:
                    if ans.get("type") == 1:  # Type 1 is A record
                        ips.append(ans["data"])
            return ips
    except Exception:
        return []

def resolve_local(domain: str) -> List[str]:
    """Resolve A records using the local system DNS resolver."""
    try:
        # Get all socket addresses for port 80 (HTTP) on the domain
        addr_infos = socket.getaddrinfo(domain, 80, proto=socket.IPPROTO_TCP)
        # Extract IP addresses (index 4 of addr_info is the socket address tuple, index 0 is IP)
        ips = list(set(info[4][0] for info in addr_infos if ":" not in info[4][0])) # Filter IPv4 only
        return ips
    except Exception:
        return []

def is_private_ip(ip: str) -> bool:
    """Check if an IP address belongs to RFC 1918 private ranges."""
    try:
        parts = [int(p) for p in ip.split('.')]
        if len(parts) != 4:
            return False
            
        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 127.0.0.0/8 (Loopback)
        if parts[0] == 127:
            return True
        # 169.254.0.0/16 (Link-local)
        if parts[0] == 169 and parts[1] == 254:
            return True
            
        return False
    except Exception:
        return False

def verify_cdn_overlap(local_ips: List[str], secure_ips: List[str]) -> bool:
    """
    Check if local IPs and secure IPs share reverse DNS domain networks
    to account for CDNs (like Cloudflare/Akamai/AWS) using dynamic public IPs.
    """
    local_set = set(local_ips)
    secure_set = set(secure_ips)
    
    # Direct intersection
    if local_set.intersection(secure_set):
        return True
        
    # Check reverse domains for matching domains
    def get_hostnames(ips: List[str]) -> Set[str]:
        hostnames = set()
        for ip in ips:
            try:
                name, _, _ = socket.gethostbyaddr(ip)
                # Keep main domains (e.g. 1e100.net, cloudflare.com, akamaitechnologies.com)
                parts = name.split('.')
                if len(parts) >= 2:
                    hostnames.add(".".join(parts[-2:]))
            except Exception:
                pass
        return hostnames
        
    local_hosts = get_hostnames(local_ips)
    secure_hosts = get_hostnames(secure_ips)
    
    if local_hosts.intersection(secure_hosts):
        return True
        
    return False

def audit_domain(domain: str) -> Dict[str, Any]:
    """Audit a single domain and compare local vs secure resolutions."""
    local_ips = resolve_local(domain)
    cf_ips = query_doh_cloudflare(domain)
    go_ips = query_doh_google(domain)
    
    # Combined secure set of IP addresses
    secure_ips = list(set(cf_ips + go_ips))
    
    status = "OK"
    details = "Resolution matches secure DoH queries."
    
    if not local_ips:
        status = "FAILED"
        details = "Local resolution failed (Offline or blocked)."
    elif not secure_ips:
        status = "UNKNOWN"
        details = "Secure DoH queries failed (Network error or DoH block)."
    else:
        # Check if local resolved to private IPs (typical captive portal redirection)
        if any(is_private_ip(ip) for ip in local_ips):
            status = "CAPTIVE_PORTAL"
            details = "Local DNS resolves to private RFC 1918 IP. Captive portal or filter redirection."
        else:
            # Check for CDN dynamic IP differences
            has_match = verify_cdn_overlap(local_ips, secure_ips)
            if not has_match:
                status = "HIJACKED"
                details = "IP mismatch. Local IPs do not match secure CDN/DoH resolutions."
                
    return {
        "domain": domain,
        "local_ips": local_ips,
        "cloudflare_ips": cf_ips,
        "google_ips": go_ips,
        "status": status,
        "details": details
    }

def main():
    parser = argparse.ArgumentParser(
        description="DNS Spoofing & Hijacking Detector - Zero-dependency security diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-d", "--domains",
        nargs="+",
        help="Custom list of domain names to audit (overrides defaults)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output report format (default: text)"
    )
    
    args = parser.parse_args()
    
    domains_to_check = args.domains if args.domains else DEFAULT_DOMAINS
    
    # Status formatting colors
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    if args.format == "text" and not sys.stdout.isatty():
        RED = YELLOW = GREEN = RESET = BOLD = ""
        
    if args.format == "text":
        print(f"\n{BOLD}DNS Spoofing & Hijacking Diagnostics{RESET}")
        print("=" * 80)
        print(f"{'Domain':<20} | {'Local IP(s)':<22} | {'DoH IP(s)':<22} | {'Status'}")
        print("=" * 80)
        
    results = []
    hijacks_found = 0
    portals_found = 0
    
    for domain in domains_to_check:
        res = audit_domain(domain)
        results.append(res)
        
        status = res["status"]
        if status == "HIJACKED":
            hijacks_found += 1
            status_fmt = f"{RED}{BOLD}HIJACKED{RESET}"
        elif status == "CAPTIVE_PORTAL":
            portals_found += 1
            status_fmt = f"{YELLOW}{BOLD}REDIRECTED{RESET}"
        elif status == "OK":
            status_fmt = f"{GREEN}OK{RESET}"
        else:
            status_fmt = f"{status}"
            
        local_str = ",".join(res["local_ips"][:2]) if res["local_ips"] else "None"
        doh_str = ",".join(res["cloudflare_ips"][:2]) if res["cloudflare_ips"] else "None"
        
        if args.format == "text":
            print(f"{domain:<20} | {local_str:<22} | {doh_str:<22} | {status_fmt}")
            
    if args.format == "json":
        print(json.dumps(results, indent=2))
        return
        
    print("=" * 80)
    print(f"Audit summary: {len(domains_to_check)} checked.")
    if hijacks_found > 0:
        print(f"\n{RED}{BOLD}WARNING: {hijacks_found} cases of potential DNS Hijacking or Spoofing detected!{RESET}")
        print("Local IP addresses do not align with verified public DNS-over-HTTPS CDN spaces.")
        sys.exit(2)
    elif portals_found > 0:
        print(f"\n{YELLOW}{BOLD}NOTE: {portals_found} domain(s) redirected to private networks.{RESET}")
        print("This is normal if you are behind a captive portal (public Wi-Fi registration) or a local corporate DNS filter.")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✔ All DNS resolutions matched secure servers. No spoofing detected.{RESET}\n")
        sys.exit(0)

if __name__ == '__main__':
    main()
