#!/usr/bin/env python3
"""
user_agent_analyzer - User-Agent string analyzer and web log parser

Parses User-Agent strings to identify browser, operating system, device type,
and crawler/bot identity. Can analyze individual strings, process files,
or extract and aggregate user-agent statistics from server access logs (Apache/Nginx).

Usage:
    # Analyze a single user agent string
    python tools/user_agent_analyzer.py --ua "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."

    # Parse and aggregate statistics from Nginx/Apache log file
    python tools/user_agent_analyzer.py log access.log
"""

import argparse
import collections
import json
import re
import sys


def parse_user_agent(ua_string):
    """
    Parses a single User-Agent string.
    Returns a dictionary of extracted properties.
    """
    if not ua_string:
        return {
            "browser": "Unknown", "browser_version": "Unknown",
            "os": "Unknown", "os_version": "Unknown",
            "device": "Unknown", "is_bot": False, "bot_name": None
        }

    ua_lower = ua_string.lower()

    # 1. Identify Bots / Crawlers
    is_bot = False
    bot_name = None
    bot_patterns = [
        ("googlebot", "Googlebot"),
        ("bingbot", "Bingbot"),
        ("yandexbot", "YandexBot"),
        ("baiduspider", "Baiduspider"),
        ("duckduckbot", "DuckDuckBot"),
        ("applebot", "Applebot"),
        ("slurp", "Yahoo! Slurp"),
        ("facebookexternalhit", "Facebook Bot"),
        ("twitterbot", "Twitter Bot"),
        ("ia_archiver", "Alexa Crawler"),
        ("facebot", "Facebook Bot"),
        ("crawl", "Generic Crawler"),
        ("spider", "Generic Crawler"),
        ("bot", "Generic Bot"),
        ("curl", "Curl Command Line"),
        ("wget", "Wget Command Line"),
        ("python-requests", "Python Requests Library"),
        ("http-client", "Generic HTTP Client")
    ]
    for pattern, name in bot_patterns:
        if pattern in ua_lower:
            is_bot = True
            bot_name = name
            break

    # 2. Identify Operating System
    os_name = "Unknown"
    os_version = "Unknown"

    if "windows nt 10.0" in ua_lower:
        os_name, os_version = "Windows", "10/11"
    elif "windows nt 6.3" in ua_lower:
        os_name, os_version = "Windows", "8.1"
    elif "windows nt 6.2" in ua_lower:
        os_name, os_version = "Windows", "8"
    elif "windows nt 6.1" in ua_lower:
        os_name, os_version = "Windows", "7"
    elif "windows nt 6.0" in ua_lower:
        os_name, os_version = "Windows", "Vista"
    elif "windows nt 5.1" in ua_lower:
        os_name, os_version = "Windows", "XP"
    elif "windows" in ua_lower:
        os_name = "Windows"
    elif "macintosh" in ua_lower or "mac os x" in ua_lower:
        os_name = "macOS"
        ver_match = re.search(r"mac os x (\d+[\._]\d+[\._]?\d*)", ua_lower)
        if ver_match:
            os_version = ver_match.group(1).replace("_", ".")
    elif "android" in ua_lower:
        os_name = "Android"
        ver_match = re.search(r"android (\d+[\.\d]*)", ua_lower)
        if ver_match:
            os_version = ver_match.group(1)
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        os_name = "iOS"
        ver_match = re.search(r"os (\d+[\._]\d+[\._]?\d*) like mac os x", ua_lower)
        if ver_match:
            os_version = ver_match.group(1).replace("_", ".")
    elif "linux" in ua_lower:
        os_name = "Linux"
        if "ubuntu" in ua_lower:
            os_name = "Ubuntu Linux"
        elif "debian" in ua_lower:
            os_name = "Debian Linux"
        elif "fedora" in ua_lower:
            os_name = "Fedora Linux"
        elif "centos" in ua_lower:
            os_name = "CentOS Linux"
    elif "crkey" in ua_lower or "chromecast" in ua_lower:
        os_name = "Chromecast"
    elif "cros" in ua_lower:
        os_name = "ChromeOS"

    # 3. Identify Device Type
    if is_bot:
        device_type = "Bot"
    elif "ipad" in ua_lower or ("android" in ua_lower and "mobile" not in ua_lower):
        device_type = "Tablet"
    elif "iphone" in ua_lower or "mobile" in ua_lower or "phone" in ua_lower:
        device_type = "Mobile"
    elif "macintosh" in ua_lower or "windows nt" in ua_lower or ("linux" in ua_lower and "android" not in ua_lower):
        device_type = "Desktop"
    else:
        device_type = "Unknown"

    # 4. Identify Browser Name & Version
    browser_name = "Unknown"
    browser_version = "Unknown"

    if is_bot:
        browser_name = bot_name or "Bot"
    # Special browsers first (Opera, Edge) to prevent general matches (Chrome, Safari)
    elif "edg/" in ua_lower or "edge/" in ua_lower:
        browser_name = "Microsoft Edge"
        match = re.search(r"(?:edg|edge)/(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser_name = "Opera"
        match = re.search(r"(?:opr|version)/(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)
    elif "firefox/" in ua_lower or "fxios/" in ua_lower:
        browser_name = "Mozilla Firefox"
        match = re.search(r"(?:firefox|fxios)/(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)
    elif "chrome/" in ua_lower or "crios/" in ua_lower:
        browser_name = "Google Chrome"
        match = re.search(r"(?:chrome|crios)/(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)
    elif "safari/" in ua_lower and "version/" in ua_lower:
        browser_name = "Apple Safari"
        match = re.search(r"version/(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)
    elif "msie" in ua_lower or "trident/" in ua_lower:
        browser_name = "Internet Explorer"
        match = re.search(r"(?:msie\s|rv:)(\d+[\.\d]*)", ua_lower)
        if match:
            browser_version = match.group(1)

    return {
        "browser": browser_name,
        "browser_version": browser_version,
        "os": os_name,
        "os_version": os_version,
        "device": device_type,
        "is_bot": is_bot,
        "bot_name": bot_name
    }


def parse_log_line(line):
    """
    Parses an Nginx/Apache Combined Log Format line to extract the user agent string.
    Combined format: IP IDENT USER [DATE] "REQ" STATUS BYTES "REFERER" "USER_AGENT"
    """
    # Matches the user agent string, which is typically the last quoted field in the log line
    pattern = re.compile(r'^.*? "(?:[^"\\]|\\.)*" \d+ \d+ "(?:[^"\\]|\\.)*" "(.*?)"\s*$')
    match = pattern.match(line)
    if match:
        return match.group(1)
    
    # Fallback: find all strings enclosed in quotes and take the last one
    quotes = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
    if len(quotes) >= 2:
        return quotes[-1]
    return None


def analyze_log_file(log_path):
    """Parses a log file, aggregates UA data, and displays statistics."""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error opening log file '{log_path}': {e}", file=sys.stderr)
        return 1

    total_lines = len(lines)
    parsed_count = 0
    
    browsers = collections.Counter()
    oses = collections.Counter()
    devices = collections.Counter()
    bots = collections.Counter()
    bot_count = 0
    human_count = 0

    for line in lines:
        ua_string = parse_log_line(line)
        if ua_string:
            parsed_count += 1
            info = parse_user_agent(ua_string)
            
            if info["is_bot"]:
                bot_count += 1
                bots[info["browser"]] += 1
            else:
                human_count += 1
                browsers[info["browser"]] += 1
                oses[info["os"]] += 1
                
            devices[info["device"]] += 1

    if parsed_count == 0:
        print("Could not extract any User-Agent strings from the log file. Is it in Combined Log format?")
        return 1

    print("=" * 60)
    print(f" LOG ANALYSIS REPORT: {log_path}")
    print("=" * 60)
    print(f"Total Log Lines Analyzed: {total_lines}")
    print(f"Successfully Extracted:  {parsed_count} ({parsed_count/total_lines*100:.1f}%)")
    print("-" * 60)
    
    print("\n[Device Distribution]")
    for dev, count in devices.most_common():
        pct = (count / parsed_count) * 100
        print(f"  {dev:<12} : {count:>6} ({pct:.1f}%)")

    print(f"\n[Traffic Split: Bot vs Human]")
    bot_pct = (bot_count / parsed_count) * 100
    human_pct = (human_count / parsed_count) * 100
    print(f"  Human / Browser Traffic : {human_count:>6} ({human_pct:.1f}%)")
    print(f"  Bot / Crawler Traffic   : {bot_count:>6} ({bot_pct:.1f}%)")

    if browsers:
        print("\n[Top Browsers (Human Traffic)]")
        for br, count in browsers.most_common(5):
            pct = (count / max(1, human_count)) * 100
            print(f"  {br:<18} : {count:>6} ({pct:.1f}%)")

    if oses:
        print("\n[Top Operating Systems (Human Traffic)]")
        for os_val, count in oses.most_common(5):
            pct = (count / max(1, human_count)) * 100
            print(f"  {os_val:<18} : {count:>6} ({pct:.1f}%)")

    if bots:
        print("\n[Top Bots/Crawlers Identified]")
        for bot, count in bots.most_common(5):
            pct = (count / max(1, bot_count)) * 100
            print(f"  {bot:<18} : {count:>6} ({pct:.1f}%)")
            
    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Standalone User-Agent Analyzer and Server Log Parser"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Subcommand (leave empty for single UA parse)")
    
    # Log parser subcommand
    log_parser = subparsers.add_parser("log", help="Analyze Nginx or Apache access log file")
    log_parser.add_argument("file", help="Path to access log file")
    
    # Direct single UA parsing
    parser.add_argument("--ua", help="A single User-Agent string to parse")
    parser.add_argument("--json", action="store_true", help="Output single UA parse results as JSON")

    args = parser.parse_args()

    if args.command == "log":
        return analyze_log_file(args.file)
    elif args.ua:
        info = parse_user_agent(args.ua)
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print("-" * 50)
            print("USER-AGENT ANALYSIS")
            print("-" * 50)
            print(f"Device Category : {info['device']}")
            print(f"Operating System: {info['os']} (Version: {info['os_version']})")
            print(f"Browser / Client: {info['browser']} (Version: {info['browser_version']})")
            print(f"Is Bot/Crawler  : {info['is_bot']}")
            if info['is_bot']:
                print(f"Bot Name        : {info['bot_name']}")
            print("-" * 50)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
