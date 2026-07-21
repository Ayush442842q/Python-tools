#!/usr/bin/env python3
"""
IP Geolocation Finder - Find geographical information for an IP address or domain

This utility resolves domain names (if provided) and queries public geocoding services
to fetch location details including city, region, country, coordinates, timezone, and ISP.

Usage:
    python tools/ip_geolocation_finder.py [IP_OR_DOMAIN] [--output OUTPUT_FILE]

Example:
    python tools/ip_geolocation_finder.py google.com
    python tools/ip_geolocation_finder.py 8.8.8.8 --output tools/google_dns_geo.json
"""

import argparse
import json
import socket
import sys
import urllib.request
from typing import Dict, Any, Optional

def resolve_host(target: str) -> Optional[str]:
    """Resolve a domain name to an IP address. Return the IP or None if it fails."""
    try:
        # Check if it's already an IP address
        socket.inet_aton(target)
        return target
    except socket.error:
        try:
            # Resolve domain
            return socket.gethostbyname(target)
        except socket.gaierror as e:
            print(f"Error: Unable to resolve domain '{target}': {e}", file=sys.stderr)
            return None

def fetch_geolocation(ip: str) -> Optional[Dict[str, Any]]:
    """Fetch geocoding data from ip-api.com for the target IP address."""
    url = f"http://ip-api.com/json/{ip}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 IP-Geolocation-Finder/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "success":
                return data
            else:
                print(f"Error: API returned status '{data.get('status')}' - {data.get('message')}", file=sys.stderr)
                return None
    except Exception as e:
        print(f"Error: Failed to fetch data from API: {e}", file=sys.stderr)
        return None

def display_geolocation_report(data: Dict[str, Any]):
    """Print the geolocation details in a clean, human-readable report."""
    print("=" * 60)
    print(f"IP Geolocation Report for: {data.get('query')}")
    print("=" * 60)
    
    fields = [
        ("Country", f"{data.get('country')} ({data.get('countryCode')})"),
        ("Region/State", f"{data.get('regionName')} ({data.get('region')})"),
        ("City", data.get("city")),
        ("ZIP / Postal Code", data.get("zip")),
        ("Latitude / Longitude", f"{data.get('lat')}, {data.get('lon')}"),
        ("Timezone", data.get("timezone")),
        ("Internet Service Provider", data.get("isp")),
        ("Organization", data.get("org")),
        ("AS Number / Name", data.get("as")),
    ]
    
    label_width = 25
    for label, val in fields:
        val_str = str(val) if val else "Unknown"
        print(f"{label:<{label_width}}: {val_str}")
        
    print("=" * 60)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find geographic details of an IP address or domain name."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="",
        help="Target IP address or domain (default: your public IP)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save the JSON output data to a file"
    )
    
    args = parser.parse_args()
    target = args.target.strip()
    
    # If no target specified, query default public IP
    if not target:
        print("No target specified. Fetching geolocation for your public IP...")
        resolved_ip = ""
    else:
        resolved_ip = resolve_host(target)
        if not resolved_ip:
            return 1
            
    print(f"Querying geolocation details...")
    geo_data = fetch_geolocation(resolved_ip)
    if not geo_data:
        return 1
        
    display_geolocation_report(geo_data)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(geo_data, f, indent=4)
            print(f"Data saved to: {args.output}")
        except Exception as e:
            print(f"Error: Failed to write output file: {e}", file=sys.stderr)
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
