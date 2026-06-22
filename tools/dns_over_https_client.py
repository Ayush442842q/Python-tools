#!/usr/bin/env python3
"""
DNS over HTTPS (DoH) Client - Query DNS records securely over encrypted HTTPS.

This tool resolves DNS records (A, AAAA, MX, TXT, CNAME, etc.) by querying
public DNS-over-HTTPS (DoH) API endpoints from Google or Cloudflare. It uses
only standard Python modules (urllib and json).
"""

import sys
import argparse
import urllib.request
import urllib.parse
import json

# DNS Record Type Mapping (integers to strings as standard)
# JSON API returns numeric types sometimes, or standard strings.
RECORD_TYPES = {
    1: 'A',
    2: 'NS',
    5: 'CNAME',
    6: 'SOA',
    12: 'PTR',
    15: 'MX',
    16: 'TXT',
    28: 'AAAA',
    33: 'SRV',
    257: 'CAA'
}

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'red': '\033[31m',
    'reset': '\033[0m'
}

def colorize(text, color):
    """Wrap text in ANSI color escape codes if output is a terminal"""
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def get_type_name(type_val):
    """Get name of DNS record type from type value."""
    if isinstance(type_val, int):
        return RECORD_TYPES.get(type_val, f"TYPE_{type_val}")
    return str(type_val).upper()

def query_doh(domain, record_type, provider='cloudflare'):
    """Query DoH endpoint for DNS records."""
    record_type = record_type.upper()
    
    if provider == 'cloudflare':
        url_base = "https://cloudflare-dns.com/dns-query"
    elif provider == 'google':
        url_base = "https://dns.google/resolve"
    else:
        print(colorize(f"Error: Unknown provider '{provider}'", 'red'), file=sys.stderr)
        return None

    params = {
        'name': domain,
        'type': record_type
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{url_base}?{query_string}"
    
    headers = {
        'Accept': 'application/dns-json'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except urllib.error.URLError as e:
        print(colorize(f"HTTP Connection Error: {e.reason}", 'red'), file=sys.stderr)
        return None
    except Exception as e:
        print(colorize(f"Error querying DNS: {e}", 'red'), file=sys.stderr)
        return None

def format_status(status_code):
    """Translate standard DNS return status code to text."""
    statuses = {
        0: "NOERROR (Success)",
        1: "FORMERR (Format Error)",
        2: "SERVFAIL (Server Failure)",
        3: "NXDOMAIN (Non-Existent Domain)",
        4: "NOTIMP (Not Implemented)",
        5: "REFUSED (Query Refused)"
    }
    return statuses.get(status_code, f"UNKNOWN_STATUS ({status_code})")

def display_results(result, provider):
    """Format and display DoH query results."""
    if not result:
        return False
        
    status = result.get('Status', -1)
    status_text = format_status(status)
    
    print(colorize(f"\n--- DoH Query Results (Provider: {provider.capitalize()}) ---", 'bold'))
    
    question = result.get('Question', [])
    if question:
        for q in question:
            q_name = q.get('name', 'N/A')
            q_type = get_type_name(q.get('type', 'N/A'))
            print(f"Querying: {colorize(q_name, 'cyan')} ({q_type})")
            
    print(f"Status: {colorize(status_text, 'green' if status == 0 else 'red')}")
    
    # Check flags
    tc = result.get('TC', False)  # Truncated
    rd = result.get('RD', False)  # Recursion Desired
    ra = result.get('RA', False)  # Recursion Available
    ad = result.get('AD', False)  # Authentic Data (DNSSEC validated)
    cd = result.get('CD', False)  # Checking Disabled
    
    flags = []
    if tc: flags.append("TC (Truncated)")
    if rd: flags.append("RD (Recursion Desired)")
    if ra: flags.append("RA (Recursion Available)")
    if ad: flags.append("AD (DNSSEC Authenticated)")
    if cd: flags.append("CD (Checking Disabled)")
    
    if flags:
        print(f"Flags: {', '.join(flags)}")
        
    answer = result.get('Answer', [])
    authority = result.get('Authority', [])
    
    if answer:
        print(colorize("\nAnswers:", 'green'))
        # Table headers
        print(f"{'Name':<35} {'Type':<6} {'TTL':<6} {'Data'}")
        print("-" * 75)
        for ans in answer:
            name = ans.get('name', '')
            atype = get_type_name(ans.get('type', ''))
            ttl = ans.get('TTL', '')
            data = ans.get('data', '')
            
            # Format clean strings
            print(f"{name:<35} {atype:<6} {ttl:<6} {colorize(data, 'yellow')}")
    else:
        print("\nNo answers returned.")
        
    if authority:
        print(colorize("\nAuthority Records:", 'green'))
        print(f"{'Name':<35} {'Type':<6} {'TTL':<6} {'Data'}")
        print("-" * 75)
        for auth in authority:
            name = auth.get('name', '')
            atype = get_type_name(auth.get('type', ''))
            ttl = auth.get('TTL', '')
            data = auth.get('data', '')
            print(f"{name:<35} {atype:<6} {ttl:<6} {data}")
            
    print()
    return status == 0

def main():
    parser = argparse.ArgumentParser(
        description="DNS over HTTPS (DoH) Client - Query DNS records securely over encrypted HTTPS.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("domain", help="The domain name to query (e.g. google.com).")
    parser.add_argument(
        "type", 
        nargs="?", 
        default="A", 
        help="DNS record type to look up. E.g. A, AAAA, MX, TXT, CNAME, NS. Default is A."
    )
    parser.add_argument(
        "-p", "--provider", 
        choices=['cloudflare', 'google'], 
        default='cloudflare',
        help="The DoH service provider to query (default: cloudflare)."
    )

    args = parser.parse_args()
    
    result = query_doh(args.domain, args.type, args.provider)
    success = display_results(result, args.provider)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
