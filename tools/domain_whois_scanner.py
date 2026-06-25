#!/usr/bin/env python3
"""
Domain WHOIS Expiry Scanner

A pure Python standalone CLI tool to query domain registration records (WHOIS)
directly using TCP sockets (Port 43) and parse registrar, creation, and expiration dates.
It requires zero third-party packages.

Usage:
    python domain_whois_scanner.py google.com python.org
"""

import sys
import socket
import argparse
import re
from datetime import datetime
from typing import Dict, List, Optional

# Default WHOIS root server
IANA_WHOIS = "whois.iana.org"

# Regex patterns to extract metadata
PATTERNS = {
    "registrar": [
        re.compile(r"Registrar:\s*(.*)", re.IGNORECASE),
        re.compile(r"registrar name:\s*(.*)", re.IGNORECASE),
        re.compile(r"Sponsoring Registrar:\s*(.*)", re.IGNORECASE),
    ],
    "expiry_date": [
        re.compile(r"Registry Expiry Date:\s*(.*)", re.IGNORECASE),
        re.compile(r"Registrar Registration Expiration Date:\s*(.*)", re.IGNORECASE),
        re.compile(r"Expiration Date:\s*(.*)", re.IGNORECASE),
        re.compile(r"expires:\s*(.*)", re.IGNORECASE),
        re.compile(r"Record expires on:\s*(.*)", re.IGNORECASE),
    ],
    "creation_date": [
        re.compile(r"Creation Date:\s*(.*)", re.IGNORECASE),
        re.compile(r"Registered on:\s*(.*)", re.IGNORECASE),
        re.compile(r"Created on:\s*(.*)", re.IGNORECASE),
        re.compile(r"Registration Date:\s*(.*)", re.IGNORECASE),
    ],
    "name_servers": [
        re.compile(r"Name Server:\s*(.*)", re.IGNORECASE),
        re.compile(r"nserver:\s*(.*)", re.IGNORECASE),
    ]
}

def query_whois_raw(domain: str, server: str) -> str:
    """Connect to a WHOIS server on port 43 and retrieve domain info."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10.0)
        s.connect((server, 43))
        # Format query: some registries prefer just domain\r\n, others need prefixes
        query = f"{domain}\r\n"
        s.sendall(query.encode("utf-8"))
        
        response = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            response.append(data.decode("utf-8", errors="replace"))
        s.close()
        return "".join(response)
    except Exception as e:
        return f"Error querying WHOIS server {server}: {e}"

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various datetime string formats into datetime object."""
    date_str = date_str.strip().strip("Z").split()[0] # Clean up timezones/suffixes
    # Try different common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def scan_domain(domain: str) -> Dict:
    """Scan a domain using recursive WHOIS query logic starting at IANA."""
    result = {
        "domain": domain,
        "registrar": "Unknown",
        "creation_date": None,
        "expiry_date": None,
        "name_servers": [],
        "raw": "",
        "days_left": None
    }
    
    # Query IANA first to find the authoritative registry server
    iana_data = query_whois_raw(domain, IANA_WHOIS)
    if "Error" in iana_data:
        result["raw"] = iana_data
        return result
        
    # Search for refer/whois line in IANA response
    refer_match = re.search(r"refer:\s*([a-zA-Z0-9\.\-]+)", iana_data)
    whois_match = re.search(r"whois:\s*([a-zA-Z0-9\.\-]+)", iana_data)
    
    target_server = None
    if refer_match:
        target_server = refer_match.group(1).strip()
    elif whois_match:
        target_server = whois_match.group(1).strip()
        
    if not target_server:
        # Fallback to common TLD WHOIS server conventions if not found
        tld = domain.split(".")[-1]
        target_server = f"whois.nic.{tld}"
        
    # Now query the authoritative server
    whois_data = query_whois_raw(domain, target_server)
    if "Error" in whois_data:
        # Try fallback directly to whois.verisign-grs.com for .com/.net
        if domain.endswith((".com", ".net")):
            whois_data = query_whois_raw(domain, "whois.verisign-grs.com")
        else:
            result["raw"] = whois_data
            return result
            
    result["raw"] = whois_data
    
    # Parse registrar
    for pattern in PATTERNS["registrar"]:
        match = pattern.search(whois_data)
        if match:
            result["registrar"] = match.group(1).strip()
            break
            
    # Parse creation date
    for pattern in PATTERNS["creation_date"]:
        match = pattern.search(whois_data)
        if match:
            date_parsed = parse_date(match.group(1).strip())
            if date_parsed:
                result["creation_date"] = date_parsed
                break
                
    # Parse expiry date
    for pattern in PATTERNS["expiry_date"]:
        match = pattern.search(whois_data)
        if match:
            date_parsed = parse_date(match.group(1).strip())
            if date_parsed:
                result["expiry_date"] = date_parsed
                break
                
    # Calculate days left
    if result["expiry_date"]:
        delta = result["expiry_date"] - datetime.utcnow()
        result["days_left"] = delta.days
        
    # Parse name servers
    nservers = []
    for pattern in PATTERNS["name_servers"]:
        matches = pattern.finditer(whois_data)
        for m in matches:
            ns = m.group(1).strip().lower()
            if ns not in nservers:
                nservers.append(ns)
    result["name_servers"] = nservers
    
    return result

def main():
    parser = argparse.ArgumentParser(
        description="Domain WHOIS Expiry Scanner: Query domain details and check time until expiration.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "domains",
        nargs="+",
        help="One or more domain names to scan."
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Print full raw WHOIS output instead of summary report."
    )
    
    args = parser.parse_args()
    
    for domain in args.domains:
        print(f"\033[94m[+] Scanning WHOIS records for: {domain}...\033[0m")
        res = scan_domain(domain)
        
        if args.raw:
            print("\033[95m--- RAW WHOIS RECORD ---\033[0m")
            print(res["raw"])
            print("\033[95m------------------------\033[0m\n")
            continue
            
        if "Error" in res["raw"] and not res["expiry_date"]:
            print(f"\033[91mFailed to scan {domain}: {res['raw']}\033[0m\n")
            continue
            
        print(f"  \033[1mDomain Name:\033[0m   \033[96m{res['domain']}\033[0m")
        print(f"  \033[1mRegistrar:\033[0m     {res['registrar']}")
        
        c_date = res['creation_date'].strftime('%Y-%m-%d') if res['creation_date'] else 'Unknown'
        e_date = res['expiry_date'].strftime('%Y-%m-%d') if res['expiry_date'] else 'Unknown'
        print(f"  \033[1mCreated On:\033[0m    {c_date}")
        print(f"  \033[1mExpires On:\033[0m    {e_date}")
        
        if res["days_left"] is not None:
            days = res["days_left"]
            if days < 0:
                print(f"  \033[1mStatus:\033[0m        \033[91mEXPIRED ({abs(days)} days ago)\033[0m")
            elif days < 30:
                print(f"  \033[1mStatus:\033[0m        \033[91mCRITICAL ({days} days remaining)\033[0m")
            elif days < 90:
                print(f"  \033[1mStatus:\033[0m        \033[93mWARNING ({days} days remaining)\033[0m")
            else:
                print(f"  \033[1mStatus:\033[0m        \033[92mOK ({days} days remaining)\033[0m")
        else:
            print(f"  \033[1mStatus:\033[0m        Unknown")
            
        if res["name_servers"]:
            print(f"  \033[1mName Servers:\033[0m  {', '.join(res['name_servers'])}")
        print()

if __name__ == "__main__":
    main()
