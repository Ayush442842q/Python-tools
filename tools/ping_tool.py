#!/usr/bin/env python3
"""
ping_tool - Simple wrapper around system ping to test connectivity

Usage:
    python tools/ping_tool.py HOST

Example:
    python tools/ping_tool.py google.com
"""

import argparse, subprocess, sys

def main():
    parser = argparse.ArgumentParser(description="Ping a host and show result")
    parser.add_argument('host', help='hostname or IP to ping')
    parser.add_argument('-c', '--count', type=int, default=4, help='Number of packets')
    args = parser.parse_args()
    try:
        result = subprocess.run(['ping', '-c', str(args.count), args.host], capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr.strip()}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
