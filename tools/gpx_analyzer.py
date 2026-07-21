#!/usr/bin/env python3
"""
gpx_analyzer - Parse and analyze GPX tracks

A utility to parse GPX (GPS Exchange Format) files, extract path coordinates,
timestamps, and elevation data. It computes metrics such as total distance,
time, speed, elevation gain/loss, and prints a summary or renders a simple
terminal-based elevation profile chart.

Usage:
    python tools/gpx_analyzer.py [file] [options]

Options:
    -h, --help            Show this help message and exit
    -f FILE, --file FILE  GPX file path (alternative to positional argument)
    -c, --chart           Generate an ASCII elevation profile chart in the terminal
    -e FILE, --export FILE
                          Export parsed track points as a JSON file
    -i, --imperial        Use imperial units (miles, feet, mph) instead of metric (km, meters, km/h)
    --speed-threshold THRESHOLD
                          Threshold speed in km/h to count as moving (default: 0.8)

Example:
    python tools/gpx_analyzer.py my_ride.gpx
    python tools/gpx_analyzer.py my_hike.gpx --chart --imperial
"""

import argparse
import datetime
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in meters."""
    R = 6371000.0  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def parse_iso_time(time_str):
    """Parse ISO 8601 timestamp to datetime object."""
    if not time_str:
        return None
    # Strip Z or offset for simple parsing
    time_str = time_str.replace('Z', '')
    if '.' in time_str:
        time_str = time_str.split('.')[0] # Strip milliseconds
    try:
        return datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def parse_gpx(file_path):
    """Parse GPX file and extract trackpoints list."""
    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"
        
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as pe:
        return None, f"XML Parse Error: {pe}"
    except Exception as e:
        return None, f"Error reading file: {e}"
        
    # GPX namespaces handling
    ns = ""
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'
        
    trackpoints = []
    
    # Traverse through trk -> trkseg -> trkpt
    for trk in root.findall(f'.//{ns}trk'):
        for trkseg in trk.findall(f'.//{ns}trkseg'):
            for trkpt in trkseg.findall(f'.//{ns}trkpt'):
                lat = float(trkpt.attrib.get('lat', 0.0))
                lon = float(trkpt.attrib.get('lon', 0.0))
                
                ele_node = trkpt.find(f'{ns}ele')
                ele = float(ele_node.text) if ele_node is not None and ele_node.text else None
                
                time_node = trkpt.find(f'{ns}time')
                time_val = parse_iso_time(time_node.text) if time_node is not None and time_node.text else None
                
                trackpoints.append({
                    "lat": lat,
                    "lon": lon,
                    "ele": ele,
                    "time": time_val
                })
                
    if not trackpoints:
        # Try finding waypoint (wpt) or route points (rtept) as fallback
        for wpt in root.findall(f'.//{ns}wpt'):
            lat = float(wpt.attrib.get('lat', 0.0))
            lon = float(wpt.attrib.get('lon', 0.0))
            ele_node = wpt.find(f'{ns}ele')
            ele = float(ele_node.text) if ele_node is not None and ele_node.text else None
            time_node = wpt.find(f'{ns}time')
            time_val = parse_iso_time(time_node.text) if time_node is not None and time_node.text else None
            trackpoints.append({"lat": lat, "lon": lon, "ele": ele, "time": time_val})
            
    return trackpoints, None

def analyze_track(points, moving_speed_threshold_kmh=0.8):
    """Analyze track points and return metrics dictionary."""
    total_dist = 0.0
    total_time = 0.0
    moving_time = 0.0
    moving_dist = 0.0
    ascent = 0.0
    descent = 0.0
    elevations = [p["ele"] for p in points if p["ele"] is not None]
    
    speeds = []
    
    for i in range(1, len(points)):
        p1 = points[i-1]
        p2 = points[i]
        
        # Distance (meters)
        d = haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        total_dist += d
        
        # Elevation differences
        if p1["ele"] is not None and p2["ele"] is not None:
            diff = p2["ele"] - p1["ele"]
            if diff > 0:
                ascent += diff
            else:
                descent += abs(diff)
                
        # Time and speed
        if p1["time"] and p2["time"]:
            dt = (p2["time"] - p1["time"]).total_seconds()
            if dt > 0:
                total_time += dt
                speed = d / dt  # m/s
                speed_kmh = speed * 3.6
                speeds.append(speed_kmh)
                
                if speed_kmh >= moving_speed_threshold_kmh:
                    moving_time += dt
                    moving_dist += d
                    
    max_speed = max(speeds) if speeds else 0.0
    avg_speed = (total_dist / total_time) * 3.6 if total_time > 0 else 0.0
    avg_moving_speed = (moving_dist / moving_time) * 3.6 if moving_time > 0 else 0.0
    
    min_ele = min(elevations) if elevations else None
    max_ele = max(elevations) if elevations else None
    
    return {
        "total_distance_m": total_dist,
        "total_time_s": total_time,
        "moving_time_s": moving_time,
        "moving_distance_m": moving_dist,
        "total_ascent_m": ascent,
        "total_descent_m": descent,
        "min_elevation_m": min_ele,
        "max_elevation_m": max_ele,
        "avg_speed_kmh": avg_speed,
        "avg_moving_speed_kmh": avg_moving_speed,
        "max_speed_kmh": max_speed,
        "point_count": len(points)
    }

def print_elevation_chart(points, width=60, height=12):
    """Print an ASCII elevation chart in the terminal."""
    elevations = [p["ele"] for p in points if p["ele"] is not None]
    if len(elevations) < 5:
        print("Not enough elevation data points to draw a chart.")
        return
        
    min_ele = min(elevations)
    max_ele = max(elevations)
    ele_range = max_ele - min_ele
    if ele_range == 0:
        ele_range = 1.0
        
    # Resample elevations to match width
    chunk_size = len(elevations) / width
    resampled = []
    for i in range(width):
        idx_start = int(i * chunk_size)
        idx_end = max(idx_start + 1, int((i + 1) * chunk_size))
        chunk = elevations[idx_start:idx_end]
        resampled.append(sum(chunk) / len(chunk) if chunk else min_ele)
        
    # Render chart grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    
    for x, ele in enumerate(resampled):
        # Calculate Y coordinate (0 is bottom, height-1 is top)
        norm = (ele - min_ele) / ele_range
        y = int(norm * (height - 1))
        
        # Fill grid from bottom up to y
        for row in range(height):
            if row <= y:
                # Use solid blocks for the plot
                grid[row][x] = "#"
                
    # Print grid (reversed to show top at top)
    for r in range(height - 1, -1, -1):
        # Y axis label
        if r == height - 1:
            label = f"{max_ele:>6.1f}m -|"
        elif r == 0:
            label = f"{min_ele:>6.1f}m -|"
        else:
            label = "       |"
        print(label + "".join(grid[r]))
        
    # X axis line
    print("        +" + "-" * width)
    print("         " + "Start" + " " * (width - 10) + "Finish")

def main():
    parser = argparse.ArgumentParser(
        description="Analyze GPX files, calculate path metrics and display elevation profiles."
    )
    parser.add_argument('file', nargs='?', help='GPX file path to analyze')
    parser.add_argument('-f', '--file-opt', dest='file_opt', help='GPX file path (alternative to positional argument)')
    parser.add_argument('-c', '--chart', action='store_true', help='Display ASCII elevation profile chart')
    parser.add_argument('-e', '--export', help='Export points data as JSON format')
    parser.add_argument('-i', '--imperial', action='store_true', help='Use imperial units (miles, feet, mph)')
    parser.add_argument('--speed-threshold', type=float, default=0.8,
                        help='Threshold speed in km/h to consider moving (default: 0.8)')
    
    args = parser.parse_args()
    
    file_path = args.file or args.file_opt
    if not file_path:
        parser.print_help()
        return 1
        
    points, err = parse_gpx(file_path)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
        
    if not points:
        print("Error: No coordinates or track points found in file.", file=sys.stderr)
        return 1
        
    stats = analyze_track(points, args.speed_threshold)
    
    # Unit conversions
    is_imp = args.imperial
    dist_unit = "mi" if is_imp else "km"
    ele_unit = "ft" if is_imp else "m"
    speed_unit = "mph" if is_imp else "km/h"
    
    # Distance conversion
    dist_val = stats["total_distance_m"] / 1609.344 if is_imp else stats["total_distance_m"] / 1000.0
    mov_dist_val = stats["moving_distance_m"] / 1609.344 if is_imp else stats["moving_distance_m"] / 1000.0
    
    # Elevation conversion (meters to feet if imperial)
    ele_conv = lambda m: m * 3.28084 if m is not None and is_imp else m
    ascent = ele_conv(stats["total_ascent_m"])
    descent = ele_conv(stats["total_descent_m"])
    min_ele = ele_conv(stats["min_elevation_m"])
    max_ele = ele_conv(stats["max_elevation_m"])
    
    # Speed conversion
    speed_conv = lambda kmh: kmh / 1.609344 if is_imp else kmh
    avg_speed = speed_conv(stats["avg_speed_kmh"])
    avg_moving_speed = speed_conv(stats["avg_moving_speed_kmh"])
    max_speed = speed_conv(stats["max_speed_kmh"])
    
    # Format time
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"
        
    total_time_str = format_time(stats["total_time_s"])
    moving_time_str = format_time(stats["moving_time_s"])
    
    print("=========================================================")
    print(f" GPX Track Analysis: {os.path.basename(file_path)}")
    print("=========================================================")
    print(f"  Trackpoints Count : {stats['point_count']}")
    print(f"  Total Distance    : {dist_val:.2f} {dist_unit}")
    print(f"  Moving Distance   : {mov_dist_val:.2f} {dist_unit}")
    print(f"  Total Duration    : {total_time_str}")
    print(f"  Moving Duration   : {moving_time_str}")
    print(f"  Average Speed     : {avg_speed:.2f} {speed_unit}")
    print(f"  Avg Moving Speed  : {avg_moving_speed:.2f} {speed_unit}")
    print(f"  Max Speed         : {max_speed:.2f} {speed_unit}")
    
    if min_ele is not None:
        print(f"  Total Ascent      : {ascent:.1f} {ele_unit}")
        print(f"  Total Descent     : {descent:.1f} {ele_unit}")
        print(f"  Min Elevation     : {min_ele:.1f} {ele_unit}")
        print(f"  Max Elevation     : {max_ele:.1f} {ele_unit}")
    else:
        print("  Elevation data    : Not available in this GPX file")
    print("=========================================================")
    
    if args.chart and min_ele is not None:
        print("\nElevation Profile Chart:")
        print_elevation_chart(points)
        print("=========================================================")
        
    if args.export:
        serializable_points = []
        for p in points:
            serializable_points.append({
                "lat": p["lat"],
                "lon": p["lon"],
                "ele": p["ele"],
                "time": p["time"].isoformat() if p["time"] else None
            })
            
        export_data = {
            "metadata": {
                "file": file_path,
                "analyzed_at": datetime.datetime.now().isoformat(),
            },
            "summary_stats": stats,
            "trackpoints": serializable_points
        }
        
        try:
            write_mode = 'w'
            with open(args.export, write_mode, encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
            print(f"\nSuccessfully exported route details to {args.export}")
        except Exception as e:
            print(f"\nError exporting to file: {e}", file=sys.stderr)
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
