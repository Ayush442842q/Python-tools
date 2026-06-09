#!/usr/bin/env python3
"""
User-Agent Parser

Parses browser User-Agent strings to detect Operating System, Browser, Engine, and Device Type.

Usage:
    python tools/user_agent_parser.py "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
"""

import argparse
import re
import sys

def parse_ua(ua):
    # Default values
    os_name = "Unknown OS"
    browser = "Unknown Browser"
    browser_ver = "Unknown Version"
    device = "Desktop"

    # Detect OS
    if "Windows NT 10.0" in ua:
        os_name = "Windows 10 / 11"
    elif "Windows NT 6.3" in ua:
        os_name = "Windows 8.1"
    elif "Windows NT 6.2" in ua:
        os_name = "Windows 8"
    elif "Windows NT 6.1" in ua:
        os_name = "Windows 7"
    elif "Android" in ua:
        os_name = "Android"
        device = "Mobile"
        match = re.search(r'Android\s+([0-9\.]+)', ua)
        if match:
            os_name = f"Android {match.group(1)}"
    elif "iPhone" in ua or "iPad" in ua:
        device = "Mobile" if "iPhone" in ua else "Tablet"
        match = re.search(r'OS\s+([0-9_]+)', ua)
        ver = match.group(1).replace('_', '.') if match else ""
        os_name = f"iOS {ver}".strip()
    elif "Macintosh" in ua or "Mac OS X" in ua:
        os_name = "macOS"
        match = re.search(r'Mac OS X\s+([0-9_]+)', ua)
        if match:
            os_name = f"macOS {match.group(1).replace('_', '.')}"
    elif "Linux" in ua:
        os_name = "Linux"

    # Detect Browser and Version
    if "Edg/" in ua:
        browser = "Microsoft Edge"
        match = re.search(r'Edg/([0-9\.]+)', ua)
        browser_ver = match.group(1) if match else ""
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
        match = re.search(r'(?:OPR|Opera)/([0-9\.]+)', ua)
        browser_ver = match.group(1) if match else ""
    elif "Chrome/" in ua:
        browser = "Google Chrome"
        match = re.search(r'Chrome/([0-9\.]+)', ua)
        browser_ver = match.group(1) if match else ""
    elif "Firefox/" in ua:
        browser = "Mozilla Firefox"
        match = re.search(r'Firefox/([0-9\.]+)', ua)
        browser_ver = match.group(1) if match else ""
    elif "Safari/" in ua and "Version/" in ua:
        browser = "Apple Safari"
        match = re.search(r'Version/([0-9\.]+)', ua)
        browser_ver = match.group(1) if match else ""

    # Bot / Crawler detection
    if any(bot in ua.lower() for bot in ["bot", "spider", "crawler", "googlebot"]):
        device = "Bot / Crawler"

    return {
        "os": os_name,
        "browser": browser,
        "version": browser_ver,
        "device": device
    }

def main():
    parser = argparse.ArgumentParser(description="User-Agent Parser - Parse client user agent strings")
    parser.add_argument('user_agent', help='The User-Agent string to parse')
    args = parser.parse_args()

    result = parse_ua(args.user_agent)

    print("\n" + "=" * 40)
    print(" USER-AGENT ANALYSIS")
    print("=" * 40)
    print(f"OS:             {result['os']}")
    print(f"Browser:        {result['browser']}")
    print(f"Version:        {result['version']}")
    print(f"Device Type:    {result['device']}")
    print("=" * 40)

    return 0

if __name__ == "__main__":
    sys.exit(main())
