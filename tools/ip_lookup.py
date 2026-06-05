#!/usr/bin/env python3
"""
IP Lookup Tool

Looks up geographical and network details for a given IP address (or the current machine's public IP).
Uses the free public service ip-api.com.

Usage:
    python tools/ip_lookup.py [ip_address]
"""

import argparse
import json
import sys
import urllib.request

def get_ip_info(ip=""):
    url = f"http://ip-api.com/json/{ip}"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print(f"Error fetching IP information: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="IP Lookup Tool - Geolocation and ISP information lookup")
    parser.add_argument('ip', nargs='?', default="", help='IP address to look up (default: your public IP)')
    args = parser.parse_args()

    print("Fetching information...")
    info = get_ip_info(args.ip)
    
    if not info:
        return 1

    if info.get('status') == 'fail':
        print(f"Failed to look up IP: {info.get('message', 'Unknown error')}")
        return 1

    print("\n" + "=" * 40)
    print(" IP LOOKUP DETAILS")
    print("=" * 40)
    print(f"IP Address:   {info.get('query')}")
    print(f"Country:      {info.get('country')} ({info.get('countryCode')})")
    print(f"Region/State: {info.get('regionName')} ({info.get('region')})")
    print(f"City:         {info.get('city')}")
    print(f"Zip/Postal:   {info.get('zip')}")
    print(f"Latitude:     {info.get('lat')}")
    print(f"Longitude:    {info.get('lon')}")
    print(f"Timezone:     {info.get('timezone')}")
    print(f"ISP:          {info.get('isp')}")
    print(f"Organization: {info.get('org')}")
    print(f"AS / Network: {info.get('as')}")
    print("=" * 40)

    return 0

if __name__ == "__main__":
    sys.exit(main())
