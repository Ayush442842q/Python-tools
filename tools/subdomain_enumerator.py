#!/usr/bin/env python3
"""
Subdomain Enumerator - A fast DNS subdomain discovery utility

This tool scans a target domain to discover active subdomains by performing
concurrent DNS lookups using a common subdomains wordlist. It helps map
attack surfaces or identify dev/staging environments.

Usage:
    python tools/subdomain_enumerator.py TARGET_DOMAIN [options]

Options:
    -w, --wordlist FILE     Path to a custom wordlist file
    -t, --threads N         Number of concurrent threads (default: 20)
    -o, --output FILE       Save active subdomains to a text file
    -v, --verbose           Show detailed scanning attempts
    -h, --help              Show this help message and exit

Example:
    python tools/subdomain_enumerator.py example.com -t 30
"""

import argparse
import concurrent.futures
import os
import socket
import sys
from typing import List, Tuple, Optional

# A built-in list of common subdomains to use if no wordlist is provided
DEFAULT_SUBDOMAINS = [
    "www", "mail", "blog", "api", "dev", "stage", "staging", "ftp", "vpn",
    "dns", "secure", "webmail", "cloud", "admin", "test", "portal", "git",
    "gitlab", "github", "cpanel", "whm", "support", "help", "shop", "store",
    "app", "apps", "status", "monitor", "billing", "db", "database", "sql",
    "mysql", "jira", "wiki", "docs", "dev-api", "stage-api", "beta", "demo",
    "internal", "intranet", "corp", "assets", "static", "media", "images",
    "cdn", "ns1", "ns2", "ns3", "ns4", "mx", "mx1", "mx2", "smtp", "pop",
    "imap", "proxy", "gw", "gateway", "router", "fw", "firewall", "auth",
    "login", "sso", "identity", "oauth", "api-dev", "api-stage", "ops"
]


def resolve_subdomain(subdomain: str, domain: str) -> Tuple[str, Optional[str], List[str]]:
    """Resolves a subdomain to IP addresses. Returns (full_domain, primary_ip, all_ips)"""
    full_domain = f"{subdomain}.{domain}"
    try:
        # Get address info (resolves DNS)
        infos = socket.getaddrinfo(full_domain, None, proto=socket.IPPROTO_TCP)
        ips = list(set(info[4][0] for info in infos))
        primary_ip = ips[0] if ips else None
        return full_domain, primary_ip, ips
    except socket.gaierror:
        # Resolution failure, subdomain does not exist
        return full_domain, None, []
    except Exception:
        return full_domain, None, []


def check_wildcard(domain: str) -> Optional[List[str]]:
    """Checks if the domain has wildcard DNS records enabled."""
    # Resolve a random-looking subdomain that should not exist
    random_sub = "wildcard-check-9988776655"
    _, primary_ip, ips = resolve_subdomain(random_sub, domain)
    return ips if primary_ip else None


def main() -> int:
    parser = argparse.ArgumentParser(description="DNS Subdomain Enumeration Utility.")
    parser.add_argument("domain", help="Target domain (e.g., example.com)")
    parser.add_argument("-w", "--wordlist", help="Path to custom subdomains wordlist file")
    parser.add_argument("-t", "--threads", type=int, default=20, help="Number of concurrent resolver threads")
    parser.add_argument("-o", "--output", help="Path to output file to write discovered subdomains")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print resolution failures and details")
    
    args = parser.parse_args()
    
    target_domain = args.domain.strip().lower()
    # Remove protocol prefix if entered by mistake
    if target_domain.startswith("http://"):
        target_domain = target_domain[7:]
    elif target_domain.startswith("https://"):
        target_domain = target_domain[8:]
    if target_domain.startswith("www."):
        target_domain = target_domain[4:]
        
    print(f"Target Domain: {target_domain}")
    
    # Check for wildcards
    print("Checking for wildcard DNS records...")
    wildcard_ips = check_wildcard(target_domain)
    if wildcard_ips:
        print(f"[*] WARNING: Wildcard DNS detected! Non-existent subdomains resolve to: {', '.join(wildcard_ips)}")
        print("[*] Results may contain false positives.")
    else:
        print("[+] No wildcard DNS detected. Proceeding...")

    # Load subdomains wordlist
    subdomains = DEFAULT_SUBDOMAINS
    if args.wordlist:
        if not os.path.exists(args.wordlist):
            print(f"Error: Wordlist file '{args.wordlist}' not found.", file=sys.stderr)
            return 1
        try:
            with open(args.wordlist, "r", encoding="utf-8") as f:
                subdomains = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
            print(f"Loaded {len(subdomains)} subdomains from custom wordlist: {args.wordlist}")
        except Exception as e:
            print(f"Error reading wordlist: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Using built-in list of {len(subdomains)} common subdomains.")
        
    # Dedup and sort subdomains
    subdomains = sorted(list(set(subdomains)))
    
    active_subdomains = []
    print(f"Scanning subdomains using {args.threads} threads...")
    
    try:
        # Use ThreadPoolExecutor for concurrent DNS queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Map resolving task
            future_to_sub = {executor.submit(resolve_subdomain, sub, target_domain): sub for sub in subdomains}
            
            for future in concurrent.futures.as_completed(future_to_sub):
                sub = future_to_sub[future]
                try:
                    full_domain, primary_ip, ips = future.result()
                    if primary_ip:
                        # If wildcard DNS is enabled, check if resolved IPs match wildcard IPs
                        if wildcard_ips and set(ips) == set(wildcard_ips):
                            if args.verbose:
                                print(f"[-] Ignored (Wildcard Match): {full_domain} -> {', '.join(ips)}")
                            continue
                            
                        print(f"[+] Found: {full_domain} -> {', '.join(ips)}")
                        active_subdomains.append((full_domain, ips))
                    else:
                        if args.verbose:
                            print(f"[-] Failed: {sub}.{target_domain}")
                except Exception as exc:
                    if args.verbose:
                        print(f"[*] Exception resolving {sub}.{target_domain}: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nScan interrupted by user. Saving partial results...")
        
    print(f"\nScan completed. Discovered {len(active_subdomains)} active subdomains.")
    
    # Save output if specified
    if args.output and active_subdomains:
        try:
            write_mode = "w"
            with open(args.output, write_mode, encoding="utf-8") as f:
                for domain, ips in sorted(active_subdomains):
                    f.write(f"{domain}\t{','.join(ips)}\n")
            print(f"Results successfully written to: {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
