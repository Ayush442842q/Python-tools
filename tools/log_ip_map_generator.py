#!/usr/bin/env python3
"""
Log IP Geolocation Map Generator

A standalone utility to scan server log files (e.g. Nginx, Apache, custom CSVs),
extract public IP addresses, geolocate them (using a free API with local caching
to prevent rate limits), and generate an interactive Leaflet.js HTML map with 
density/hit-count markers.

Usage:
    python log_ip_map_generator.py access.log -o map.html
"""

import os
import sys
import argparse
import re
import json
import urllib.request
import urllib.parse
import time
from collections import Counter

# Regex for IPv4 addresses
IP_REGEX = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')

# Cache filename to preserve lookups and prevent API rate-limiting
CACHE_FILE = "ip_geo_cache.json"

def is_public_ip(ip):
    """Filter out private, local loopback, and multicast IP ranges."""
    parts = list(map(int, ip.split('.')))
    
    # Loopback (127.0.0.0/8)
    if parts[0] == 127:
        return False
    # Private Class A (10.0.0.0/8)
    if parts[0] == 10:
        return False
    # Private Class B (172.16.0.0/12)
    if parts[0] == 172 and (16 <= parts[1] <= 31):
        return False
    # Private Class C (192.168.0.0/16)
    if parts[0] == 192 and parts[1] == 168:
        return False
    # Link-local (169.254.0.0/16)
    if parts[0] == 169 and parts[1] == 254:
        return False
    # Multicast / Broadcast
    if parts[0] >= 224:
        return False
        
    return True


def load_cache():
    """Loads geolocated IP cache from local JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    """Saves geolocated IP cache to local JSON file."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save IP cache: {e}", file=sys.stderr)


def geolocate_ip(ip):
    """Queries free ip-api.com service for latitude/longitude, city, and country."""
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,city,lat,lon,isp"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('status') == 'success':
                return {
                    'lat': data.get('lat'),
                    'lon': data.get('lon'),
                    'city': data.get('city', 'Unknown City'),
                    'country': data.get('country', 'Unknown Country'),
                    'isp': data.get('isp', 'Unknown ISP')
                }
    except Exception as e:
        print(f"Warning: Failed to geolocate {ip}: {e}", file=sys.stderr)
    return None


def generate_map_html(locations, output_path):
    """Generates a standalone interactive Leaflet.js HTML map with marker data."""
    
    # Prepare JavaScript array of marker coordinates and popups
    markers_js = []
    for info in locations:
        ip = info['ip']
        lat = info['lat']
        lon = info['lon']
        city = info['city']
        country = info['country']
        isp = info['isp']
        count = info['count']
        
        # Determine radius sizing based on hit count
        radius = min(30, max(6, count * 2))
        
        popup_text = f"<strong>IP:</strong> {ip}<br>" \
                     f"<strong>Location:</strong> {city}, {country}<br>" \
                     f"<strong>ISP:</strong> {isp}<br>" \
                     f"<strong>Hits:</strong> {count}"
                     
        # Escape single quotes in popup
        popup_text_esc = popup_text.replace("'", "\\'")
        
        markers_js.append(
            f"L.circleMarker([{lat}, {lon}], {{"
            f"  radius: {radius},"
            f"  fillColor: '#ff7800',"
            f"  color: '#000',"
            f"  weight: 1,"
            f"  opacity: 1,"
            f"  fillOpacity: 0.8"
            f"}}).addTo(map).bindPopup('{popup_text_esc}');"
        )

    leaflet_markers = "\n        ".join(markers_js)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Log Traffic Geolocation Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
    <style>
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        #map {{
            width: 100%;
            height: calc(100vh - 60px);
        }}
        .header {{
            height: 60px;
            background: #1a1a1a;
            color: #ffffff;
            display: flex;
            align-items: center;
            padding: 0 20px;
            box-sizing: border-box;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }}
        .header h1 {{
            margin: 0;
            font-size: 1.2rem;
            font-weight: 500;
        }}
        .header .summary {{
            margin-left: auto;
            font-size: 0.9rem;
            color: #aaaaaa;
        }}
    </style>
</head>
<body>

    <div class="header">
        <h1>Log IP Geolocation Map</h1>
        <div class="summary">Total Markers: {len(locations)}</div>
    </div>

    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script>
        // Initialize the map, centered globally
        var map = L.map('map').setView([20, 0], 2);

        // Load OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
        }}).addTo(map);

        // Plot geolocated IP locations
        {leaflet_markers}
    </script>
</body>
</html>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser(
        description="Scan access logs, extract and geolocate IP addresses, and generate an interactive Leaflet map."
    )
    parser.add_argument("log_file", help="Path to input log file (e.g. access.log)")
    parser.add_argument(
        "-o", "--output", 
        default="ip_map.html", 
        help="Path to save the generated map HTML file (defaults to 'ip_map.html')"
    )
    parser.add_argument(
        "--api-delay", 
        type=float, 
        default=1.0, 
        help="Delay in seconds between API requests to respect endpoint rate-limiting (default: 1.0s)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: Log file '{args.log_file}' does not exist.", file=sys.stderr)
        return 1

    print(f"Scanning log file '{args.log_file}'...")
    
    # 1. Parse and collect IPs
    ip_counter = Counter()
    try:
        with open(args.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                ips = IP_REGEX.findall(line)
                for ip in ips:
                    if is_public_ip(ip):
                        ip_counter[ip] += 1
    except Exception as e:
        print(f"Error reading log file: {e}", file=sys.stderr)
        return 1

    total_ips = len(ip_counter)
    print(f"Found {total_ips} unique public IP addresses.")

    if total_ips == 0:
        print("No public IP addresses found in the log file.")
        return 0

    # 2. Geolocate IPs (using cache first)
    cache = load_cache()
    resolved_locations = []
    
    needs_save = False
    new_lookups = 0

    print("Resolving geolocations (using local cache if available)...")
    for i, (ip, count) in enumerate(ip_counter.most_common(), 1):
        if ip in cache:
            # Check cached structure contains lat/lon
            geo_info = cache[ip]
            if geo_info and 'lat' in geo_info and 'lon' in geo_info:
                geo_info['count'] = count
                geo_info['ip'] = ip
                resolved_locations.append(geo_info)
                continue

        # Not in cache, lookup
        print(f"  [{i}/{total_ips}] Looking up: {ip}...")
        geo_info = geolocate_ip(ip)
        
        if geo_info:
            cache[ip] = geo_info
            needs_save = True
            new_lookups += 1
            
            geo_info['count'] = count
            geo_info['ip'] = ip
            resolved_locations.append(geo_info)
            
            # Rate limit politeness
            time.sleep(args.api_delay)
        else:
            # Flag failed lookup in cache with null so we don't retry immediately next run
            cache[ip] = None
            needs_save = True
            time.sleep(args.api_delay)

    # Save cache if additions made
    if needs_save:
        save_cache(cache)
        print(f"Cached {new_lookups} new IP geolocations locally.")

    print(f"Successfully geolocated {len(resolved_locations)}/{total_ips} IPs.")

    if not resolved_locations:
        print("Error: Could not resolve any IP addresses to coordinates. No map generated.", file=sys.stderr)
        return 1

    # 3. Generate HTML Map
    try:
        generate_map_html(resolved_locations, args.output)
        print(f"Interactive map successfully generated and saved to '{args.output}'")
        return 0
    except Exception as e:
        print(f"Error generating HTML map: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
