#!/usr/bin/env python3
"""
DNS Zone File Generator
-----------------------
Generates standardized RFC 1035 BIND zone files from a simple, structured JSON config.
Provides automatic SOA serial number calculation (YYYYMMDDNN) with daily increment logic,
column alignment, and key semantic checks (e.g. validating CNAME conflicts, MX priority format,
and IP address validity).

Author: Antigravity
License: MIT
"""

import os
import re
import sys
import json
import socket
import argparse
from datetime import datetime

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_SOA = {
    "mname": "ns1.example.com.",
    "rname": "admin.example.com.",
    "refresh": 86400,
    "retry": 7200,
    "expire": 3600000,
    "minimum": 172800
}

def is_valid_ipv4(ip):
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except socket.error:
        return False

def is_valid_ipv6(ip):
    try:
        socket.inet_pton(socket.AF_INET6, ip)
        return True
    except socket.error:
        return False

def get_current_date_serial():
    """Generates a default serial matching YYYYMMDD01."""
    today_str = datetime.now().strftime("%Y%m%d")
    return int(today_str + "01")

def increment_serial(old_serial):
    """Increments existing serial YYYYMMDDNN. If date is today, increment NN, else update date to today."""
    today_str = datetime.now().strftime("%Y%m%d")
    old_serial_str = str(old_serial)
    
    if len(old_serial_str) != 10:
        return get_current_date_serial()
        
    old_date = old_serial_str[:8]
    old_seq = int(old_serial_str[8:])
    
    if old_date == today_str:
        new_seq = min(99, old_seq + 1)
        return int(today_str + f"{new_seq:02d}")
    else:
        return get_current_date_serial()

def extract_serial_from_zone(filepath):
    """Attempts to find the serial number in an existing zone file."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Find SOA block and match the first number after MNAME/RNAME (within parenthesis)
        # Typically formatted as serial ; Serial
        # Using regex to look for a 10-digit number followed by a comment containing 'serial'
        match = re.search(r'(\d{10})\s*;?\s*[Ss]erial', content)
        if match:
            return int(match.group(1))
            
        # Fallback: Look for the first 10-digit number in the SOA section
        soa_match = re.search(r'\b(SOA)\b.*?\(.*?\b(\d{10})\b', content, re.DOTALL | re.IGNORECASE)
        if soa_match:
            return int(soa_match.group(2))
    except Exception:
        pass
    return None

def validate_dns_records(origin, records_dict):
    """Performs validation checks on inputs and outputs errors/warnings."""
    errors = []
    warnings = []
    
    for name, records in records_dict.items():
        has_cname = False
        has_other = False
        
        for r in records:
            rtype = r.get("type", "").upper()
            rval = r.get("value", "").strip()
            
            if rtype == "CNAME":
                has_cname = True
            else:
                has_other = True
                
            # Type specific checks
            if rtype == "A":
                if not is_valid_ipv4(rval):
                    errors.append(f"[{name}] Invalid IPv4 address for A record: '{rval}'")
            elif rtype == "AAAA":
                if not is_valid_ipv6(rval):
                    errors.append(f"[{name}] Invalid IPv6 address for AAAA record: '{rval}'")
            elif rtype == "MX":
                parts = rval.split(None, 1)
                if len(parts) != 2 or not parts[0].isdigit():
                    errors.append(f"[{name}] MX record value must start with integer priority (e.g. '10 mail.example.com.'): Got '{rval}'")
            elif rtype in ["NS", "CNAME"]:
                if not rval.endswith("."):
                    warnings.append(f"[{name}] Hostname in {rtype} record '{rval}' does not end with a trailing dot. This might resolve as sub-domain of origin.")
                    
        # RFC 1034 section 3.6.2: CNAME cannot co-exist with other record types for the same name
        if has_cname and has_other:
            errors.append(f"[{name}] Semantic Error: CNAME record cannot co-exist with other record types on the same node (RFC 1034).")
            
    return errors, warnings

def build_zone_file(config, serial):
    """Assembles records into a formatted string."""
    origin = config.get("origin", "example.com.")
    if not origin.endswith("."):
        origin += "."
        
    ttl = config.get("ttl", 3600)
    soa_cfg = config.get("soa", DEFAULT_SOA)
    
    lines = []
    lines.append(f"$ORIGIN {origin}")
    lines.append(f"$TTL {ttl}")
    lines.append("")
    
    # SOA block
    mname = soa_cfg.get("mname", DEFAULT_SOA["mname"])
    rname = soa_cfg.get("rname", DEFAULT_SOA["rname"])
    refresh = soa_cfg.get("refresh", DEFAULT_SOA["refresh"])
    retry = soa_cfg.get("retry", DEFAULT_SOA["retry"])
    expire = soa_cfg.get("expire", DEFAULT_SOA["expire"])
    minimum = soa_cfg.get("minimum", DEFAULT_SOA["minimum"])
    
    lines.append(f"@\tIN\tSOA\t{mname} {rname} (")
    lines.append(f"\t\t\t\t{serial:010d}\t; Serial")
    lines.append(f"\t\t\t\t{refresh:<8d}\t; Refresh")
    lines.append(f"\t\t\t\t{retry:<8d}\t; Retry")
    lines.append(f"\t\t\t\t{expire:<8d}\t; Expire")
    lines.append(f"\t\t\t\t{minimum:<8d}\t; Minimum TTL")
    lines.append("\t\t\t\t)")
    lines.append("")
    
    # Resource records
    records_dict = config.get("records", {})
    # Sort keys for consistent output order, keeping '@' at top
    keys = sorted(records_dict.keys(), key=lambda x: "" if x == "@" else x)
    
    for name in keys:
        for r in records_dict[name]:
            rtype = r.get("type", "").upper()
            rval = r.get("value", "").strip()
            rclass = r.get("class", "IN").upper()
            rttl = r.get("ttl", "")
            
            ttl_str = f"{rttl}\t" if rttl else ""
            lines.append(f"{name:<16}\t{ttl_str}{rclass}\t{rtype:<6}\t{rval}")
            
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(
        description="Generates RFC 1035 compliant BIND DNS zone files from structured JSON configs.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("config", help="Path to JSON configuration file.")
    parser.add_argument("-o", "--output", help="Path to save the generated zone file.")
    parser.add_argument("--serial", type=int, help="Override automatically generated serial number.")
    parser.add_argument("--increment", action="store_true", help="Increment serial from existing output file if it exists.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        print(f"{RED}Error: Config file '{args.config}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"{RED}Error parsing JSON config: {e}{RESET}", file=sys.stderr)
        sys.exit(1)
        
    origin = config.get("origin", "")
    records = config.get("records", {})
    
    if not origin:
        print(f"{RED}Error: Config must contain an 'origin' domain.{RESET}", file=sys.stderr)
        sys.exit(1)
        
    # Validate records
    errors, warnings = validate_dns_records(origin, records)
    
    if warnings:
        for w in warnings:
            print(f"{YELLOW}Warning: {w}{RESET}", file=sys.stderr)
            
    if errors:
        print(f"{RED}Validation Errors found. Generation aborted:{RESET}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
        
    # Calculate Serial
    serial = args.serial
    if not serial:
        old_serial = None
        if args.increment and args.output:
            old_serial = extract_serial_from_zone(args.output)
            
        if old_serial:
            serial = increment_serial(old_serial)
            print(f"[*] Incremented serial from existing file: {old_serial} -> {serial}")
        else:
            serial = get_current_date_serial()
            print(f"[*] Generated default date-based serial: {serial}")
            
    # Build content
    zone_content = build_zone_file(config, serial)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(zone_content)
            print(f"{GREEN}[+] Successfully wrote zone file to: {args.output}{RESET}")
        except Exception as e:
            print(f"{RED}Error writing output file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n--- GENERATED ZONE FILE ---")
        print(zone_content)
        print("---------------------------")

if __name__ == "__main__":
    main()
