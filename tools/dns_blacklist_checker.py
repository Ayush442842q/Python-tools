#!/usr/bin/env python3
"""
DNS Blacklist (DNSBL) Checker - Query multiple spam and reputation blocklists for an IP or domain.
"""

import sys
import socket
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

# A list of reputable DNSBL lists to query
# Format: (dnsbl_domain, name, type)
DNSBL_LISTS = [
    ('zen.spamhaus.org', 'Spamhaus ZEN', 'Combined Blocklist'),
    ('bl.spamcop.net', 'Spamcop', 'Spam report-based'),
    ('dnsbl.sorbs.net', 'SORBS (General)', 'Combined list'),
    ('spam.dnsbl.sorbs.net', 'SORBS Spam', 'Spam hosts'),
    ('b.barracudacentral.org', 'Barracuda BRBL', 'Spam hosts'),
    ('db.wpbl.info', 'WPBL', 'Spam / Bad reputation'),
    ('all.s5h.net', 'S5H All', 'Spam & Malicious hosts'),
    ('psbl.surriel.com', 'Passive Spam Blocklist', 'Spam hosts'),
    ('spam.rbl.msrbl.net', 'MSRBL Spam', 'Spam hosts'),
    ('bl.uribl.com', 'URIBL', 'Spam / Bad domain reputation'),
    ('blackholes.five-ten-sg.com', 'Five-Ten-SG', 'Spam / Bad reputation'),
    ('dnsbl-1.uceprotect.net', 'UCEPROTECT Level 1', 'Single IP abusers'),
]

def reverse_ipv4(ip):
    """Reverse octets of an IPv4 address. e.g. 1.2.3.4 -> 4.3.2.1"""
    parts = ip.split('.')
    return '.'.join(reversed(parts))

def reverse_ipv6(ip):
    """Reverse hex nibbles of an IPv6 address for DNSBL query."""
    # First resolve/standardize the IPv6 to full 32-character representation
    # using socket.getaddrinfo
    try:
        addrinfo = socket.getaddrinfo(ip, None, socket.AF_INET6, socket.SOCK_RAW, socket.AI_NUMERICHOST)
        # Get binary structure
        binary_ip = addrinfo[0][4][0]
    except Exception as e:
        return None
        
    # Convert binary to hex representation
    hex_str = ''.join(f'{b:02x}' for b in binary_ip)
    # Reverse the character order and join with dots
    return '.'.join(reversed(hex_str))

def check_dnsbl(target_ip, is_ipv6, dnsbl_host):
    """Query a single DNSBL server for target IP."""
    dnsbl_domain, name, desc = dnsbl_host
    
    if is_ipv6:
        rev_ip = reverse_ipv6(target_ip)
    else:
        rev_ip = reverse_ipv4(target_ip)
        
    if not rev_ip:
        return dnsbl_domain, name, False, "Invalid IP reversal", ""
        
    query = f"{rev_ip}.{dnsbl_domain}"
    
    try:
        # Perform DNS lookup for A record
        answers = socket.getaddrinfo(query, None, socket.AF_INET, socket.SOCK_RAW)
        results = [addr[4][0] for addr in answers]
        
        # Interpret returning address (typically 127.0.0.X)
        details = []
        for res in results:
            if res.startswith('127.'):
                # Interpret return codes (Spamhaus, Sorbs, UceProtect, etc.)
                if dnsbl_domain == 'zen.spamhaus.org':
                    codes = {
                        '2': 'SBL (Direct spam source)',
                        '3': 'SBL CSS (CSS spam emission)',
                        '4': 'XBL (CBL/exploits/proxies)',
                        '9': 'SBL (SBL Advisory)',
                        '10': 'PBL (ISP dynamic IP ranges)',
                        '11': 'PBL (ISP static IP ranges)'
                    }
                    last_octet = res.split('.')[-1]
                    details.append(codes.get(last_octet, f"Unknown code {last_octet}"))
                elif 'uceprotect' in dnsbl_domain:
                    details.append("UCEPROTECT Listed")
                else:
                    details.append(f"Listed ({res})")
            else:
                details.append(f"Resolved to {res}")
                
        return dnsbl_domain, name, True, ", ".join(details), desc
    except socket.gaierror:
        # Host name not found (IP is NOT listed)
        return dnsbl_domain, name, False, "Not Listed", desc
    except Exception as e:
        return dnsbl_domain, name, None, f"Query error: {e}", desc

def main():
    parser = argparse.ArgumentParser(
        description="DNS Blacklist (DNSBL) Checker - Query multiple blocklists for reputation and spam indicators."
    )
    parser.add_argument('target', help="IP address or Domain name to check.")
    parser.add_argument('--workers', type=int, default=10, help="Number of concurrent query worker threads.")
    
    args = parser.parse_args()
    
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    target = args.target
    is_ip = False
    is_ipv6 = False
    
    # 1. Determine if input is IP or Domain
    try:
        socket.inet_pton(socket.AF_INET, target)
        is_ip = True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, target)
            is_ip = True
            is_ipv6 = True
        except socket.error:
            is_ip = False
            
    resolved_ip = target
    
    if not is_ip:
        print(f"Resolving domain '{target}'...")
        try:
            # Resolve domain
            addrinfo = socket.getaddrinfo(target, None)
            # Find IPv4 if possible, otherwise IPv6
            ipv4_candidates = [addr[4][0] for addr in addrinfo if addr[0] == socket.AF_INET]
            ipv6_candidates = [addr[4][0] for addr in addrinfo if addr[0] == socket.AF_INET6]
            
            if ipv4_candidates:
                resolved_ip = ipv4_candidates[0]
                is_ipv6 = False
            elif ipv6_candidates:
                resolved_ip = ipv6_candidates[0]
                is_ipv6 = True
            else:
                print(f"{c_red}Could not resolve domain '{target}' to any IP address.{c_reset}", file=sys.stderr)
                sys.exit(1)
            print(f"Resolved to IP: {c_bold}{resolved_ip}{c_reset}")
        except socket.gaierror as e:
            print(f"{c_red}Resolution failed: {e}{c_reset}", file=sys.stderr)
            sys.exit(1)
            
    print("\n" + "=" * 60)
    print(f"Checking reputation for: {c_blue}{resolved_ip}{c_reset}")
    print(f"Using {len(DNSBL_LISTS)} DNSBL lists (Concurrency: {args.workers} workers)")
    print("=" * 60)
    
    listed_count = 0
    error_count = 0
    clean_count = 0
    
    # Run requests concurrently using thread pool
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_dnsbl, resolved_ip, is_ipv6, dnsbl): dnsbl for dnsbl in DNSBL_LISTS}
        
        for future in as_completed(futures):
            dnsbl = futures[future]
            try:
                domain, name, listed, details, desc = future.result()
                if listed is True:
                    print(f"[{c_red}LISTED{c_reset}] {c_bold}{name:<22}{c_reset} ({domain}): {details} -- {desc}")
                    listed_count += 1
                elif listed is False:
                    # Clean
                    clean_count += 1
                else:
                    # Error
                    print(f"[{c_yellow}ERROR {c_reset}] {name:<22} ({domain}): {details}")
                    error_count += 1
            except Exception as exc:
                print(f"Failed querying {dnsbl[1]}: {exc}", file=sys.stderr)
                error_count += 1
                
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  - Total lists queried: {len(DNSBL_LISTS)}")
    print(f"  - {c_green if listed_count == 0 else c_red}Blacklisted on:      {listed_count} lists{c_reset}")
    print(f"  - Clean on:            {clean_count} lists")
    if error_count > 0:
        print(f"  - Queries failed:      {error_count}")
        
    if listed_count > 0:
        print(f"\n{c_red}WARNING: This IP/Domain has a poor email/network sender reputation.{c_reset}")
    else:
        print(f"\n{c_green}SUCCESS: IP/Domain is clean across all checked blacklists.{c_reset}")

if __name__ == '__main__':
    main()
