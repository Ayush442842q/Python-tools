#!/usr/bin/env python3
"""Photo GPS Map Generator

Scans directories for images, extracts GPS EXIF tags (using Pillow or a custom raw
binary parser as fallback), and generates an interactive, styled LeafletJS HTML map
showing where the photos were taken. Requires no external dependencies by default.
"""

import argparse
import os
from pathlib import Path
import struct
import sys
from typing import List, Dict, Any, Tuple, Optional

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

# Try importing Pillow. If not present, we fall back to raw binary parsing.
PILLOW_AVAILABLE = False
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_AVAILABLE = True
except ImportError:
    pass


def parse_rational(data: bytes, is_big: bool, offset: int) -> float:
    """Parse a single TIFF rational number (numerator/denominator)."""
    fmt = ">II" if is_big else "<II"
    num, den = struct.unpack_from(fmt, data, offset)
    return float(num) / float(den) if den != 0 else 0.0


def extract_gps_binary(filepath: Path) -> Optional[Tuple[float, float]]:
    """Extract GPS coordinates using custom raw JPEG binary EXIF parsing.
    
    Acts as a zero-dependency fallback when Pillow is not installed.
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read(1024 * 128)  # Read first 128KB which contains EXIF APP1
            
        if not data.startswith(b"\xff\xd8"):
            return None  # Not a JPEG file
            
        # Search for APP1 Marker (\xff\xe1)
        idx = 2
        app1_offset = -1
        while idx < len(data) - 4:
            marker, size = struct.unpack_from(">HH", data, idx)
            if marker == 0xffe1:
                app1_offset = idx
                break
            if (marker & 0xff00) != 0xff00:
                break  # Not a valid marker sequence
            idx += size + 2

        if app1_offset == -1:
            return None

        # Exif Header starts after size (2 bytes)
        exif_idx = app1_offset + 4
        if data[exif_idx:exif_idx + 6] != b"Exif\x00\x00":
            return None

        tiff_offset = exif_idx + 6
        tiff_data = data[tiff_offset:]
        
        # Byte order: II (Little Endian) or MM (Big Endian)
        byte_order = tiff_data[:2]
        is_big = (byte_order == b"MM")
        
        # Verify TIFF Magic (0x002A)
        magic_fmt = ">H" if is_big else "<H"
        magic = struct.unpack_from(magic_fmt, tiff_data, 2)[0]
        if magic != 42:
            return None

        # Offset to first IFD
        offset_fmt = ">I" if is_big else "<I"
        ifd_offset = struct.unpack_from(offset_fmt, tiff_data, 4)[0]
        
        # Read IFD Fields
        num_fields_fmt = ">H" if is_big else "<H"
        num_fields = struct.unpack_from(num_fields_fmt, tiff_data, ifd_offset)[0]
        
        gps_ifd_offset = -1
        field_offset = ifd_offset + 2
        for _ in range(num_fields):
            tag = struct.unpack_from(magic_fmt, tiff_data, field_offset)[0]
            # Tag 0x8825 is GPSInfo
            if tag == 0x8825:
                gps_ifd_offset = struct.unpack_from(offset_fmt, tiff_data, field_offset + 8)[0]
                break
            field_offset += 12

        if gps_ifd_offset == -1:
            return None

        # Read GPS IFD Fields
        num_gps_fields = struct.unpack_from(num_fields_fmt, tiff_data, gps_ifd_offset)[0]
        gps_field_offset = gps_ifd_offset + 2

        lat_ref = ""
        lon_ref = ""
        lat_raw = None
        lon_raw = None

        for _ in range(num_gps_fields):
            tag = struct.unpack_from(magic_fmt, tiff_data, gps_field_offset)[0]
            val_offset = struct.unpack_from(offset_fmt, tiff_data, gps_field_offset + 8)[0]

            if tag == 1:  # GPSLatitudeRef
                lat_ref = chr(tiff_data[gps_field_offset + 8])
            elif tag == 2:  # GPSLatitude
                lat_raw = [
                    parse_rational(tiff_data, is_big, val_offset),
                    parse_rational(tiff_data, is_big, val_offset + 8),
                    parse_rational(tiff_data, is_big, val_offset + 16)
                ]
            elif tag == 3:  # GPSLongitudeRef
                lon_ref = chr(tiff_data[gps_field_offset + 8])
            elif tag == 4:  # GPSLongitude
                lon_raw = [
                    parse_rational(tiff_data, is_big, val_offset),
                    parse_rational(tiff_data, is_big, val_offset + 8),
                    parse_rational(tiff_data, is_big, val_offset + 16)
                ]
            gps_field_offset += 12

        if not lat_raw or not lon_raw:
            return None

        # Convert rationals to decimal
        lat = lat_raw[0] + lat_raw[1] / 60.0 + lat_raw[2] / 3600.0
        lon = lon_raw[0] + lon_raw[1] / 60.0 + lon_raw[2] / 3600.0

        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon

        return lat, lon

    except Exception:
        return None


def extract_gps_pillow(filepath: Path) -> Optional[Tuple[float, float]]:
    """Extract GPS coordinates using Pillow library."""
    try:
        with Image.open(filepath) as img:
            exif = img._getexif()
            if not exif:
                return None
            
            gps_info = {}
            for tag, val in exif.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    for t in val:
                        sub_decoded = GPSTAGS.get(t, t)
                        gps_info[sub_decoded] = val[t]
            
            if not gps_info:
                return None
            
            # Helper to convert degrees, minutes, seconds to decimal
            def to_decimal(coords, ref):
                # Pillow might return tuples of (num, den) or float or Degrees/Minutes/Seconds objects
                def val(x):
                    if isinstance(x, tuple):
                        return float(x[0]) / float(x[1]) if x[1] != 0 else 0.0
                    return float(x)

                d = val(coords[0])
                m = val(coords[1])
                s = val(coords[2])
                
                decimal = d + m / 60.0 + s / 3600.0
                if ref in ["S", "W"]:
                    decimal = -decimal
                return decimal

            lat = to_decimal(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
            lon = to_decimal(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
            return lat, lon

    except Exception:
        return None


def get_photo_gps(filepath: Path) -> Optional[Tuple[float, float]]:
    if PILLOW_AVAILABLE:
        coords = extract_gps_pillow(filepath)
        if coords:
            return coords
    # Fallback to binary parsing
    return extract_gps_binary(filepath)


def generate_map_html(photos_data: List[Dict[str, Any]], output_file: Path):
    markers_js = []
    
    for photo in photos_data:
        # Convert path to forward slashes for cross-platform browser support
        rel_path = photo["rel_path"].replace("\\", "/")
        name = photo["name"]
        lat = photo["lat"]
        lon = photo["lon"]
        
        marker_code = f"""
        L.marker([{lat}, {lon}])
            .addTo(map)
            .bindPopup(`
                <div style="font-family: sans-serif; text-align: center;">
                    <h4 style="margin: 5px 0;">{name}</h4>
                    <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Lat: {lat:.6f}, Lon: {lon:.6f}</p>
                    <img src="{rel_path}" style="max-width: 180px; max-height: 120px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);" />
                </div>
            `);
        """
        markers_js.append(marker_code)

    # Use coordinates of first photo to center map, or default to 0,0
    center_lat, center_lon = (0.0, 0.0)
    center_zoom = 2
    if photos_data:
        center_lat = photos_data[0]["lat"]
        center_lon = photos_data[0]["lon"]
        center_zoom = 12

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Geo-Location Map</title>
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
        }}
        #map {{
            height: calc(100% - 60px);
            width: 100%;
        }}
        .header {{
            height: 60px;
            background-color: #1e293b;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            box-sizing: border-box;
            border-bottom: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 18px;
            color: #38bdf8;
        }}
        .header .stats {{
            font-size: 13px;
            color: #94a3b8;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Photo GPS Location Map</h1>
        <div class="stats">Found <strong>{len(photos_data)}</strong> geotagged photos</div>
    </div>
    
    <div id="map"></div>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script>
        // Initialize Map
        const map = L.map('map').setView([{center_lat}, {center_lon}], {center_zoom});

        // Add OpenStreetMap Tile Layer (Sleek CartoDB Dark Matter)
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }}).addTo(map);

        // Add Markers
        {"".join(markers_js)}
    </script>
</body>
</html>
    """
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser(
        description="Extract GPS metadata from photos and generate an interactive LeafletJS map."
    )
    parser.add_argument("directory", help="Directory containing photos to scan")
    parser.add_argument("--output", default="photo_map.html", help="Path to save the generated HTML map file")
    args = parser.parse_args()

    scan_dir = Path(args.directory)
    if not scan_dir.exists():
        print(f"{COLOR_RED}Error: Directory '{args.directory}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{COLOR_BOLD}Scanning directory '{scan_dir}' for photos...{COLOR_RESET}")
    if PILLOW_AVAILABLE:
        print(f"{COLOR_BLUE}Info: Pillow metadata engine loaded successfully.{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}Warning: Pillow not found. Falling back to native JPEG binary GPS extractor.{COLOR_RESET}")

    photo_extensions = {".jpg", ".jpeg"}
    photos_data = []

    # Recursively scan for JPG files
    for filepath in scan_dir.rglob("*"):
        if filepath.suffix.lower() in photo_extensions:
            gps = get_photo_gps(filepath)
            if gps:
                lat, lon = gps
                # Get path relative to the directory containing the HTML map output file
                output_parent = Path(args.output).parent.resolve()
                try:
                    rel_path = os.path.relpath(filepath, output_parent)
                except ValueError:
                    rel_path = str(filepath) # Absolute fallback
                    
                photos_data.append({
                    "name": filepath.name,
                    "rel_path": rel_path,
                    "lat": lat,
                    "lon": lon
                })

    if not photos_data:
        print(f"{COLOR_YELLOW}No geotagged photos found in the specified directory.{COLOR_RESET}")
        sys.exit(0)

    print(f"\nFound {COLOR_GREEN}{len(photos_data)}{COLOR_RESET} photos with GPS coordinates:")
    for p in photos_data[:10]:
        print(f" - {p['name']}: ({p['lat']:.6f}, {p['lon']:.6f}) -> {p['rel_path']}")
    if len(photos_data) > 10:
        print(f" ... and {len(photos_data) - 10} more.")

    output_path = Path(args.output)
    try:
        generate_map_html(photos_data, output_path)
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}Success: Map file generated successfully at '{output_path}'!{COLOR_RESET}")
        print("Open the HTML file in any browser to view the interactive map.")
    except Exception as e:
        print(f"{COLOR_RED}Error writing map file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
