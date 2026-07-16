#!/usr/bin/env python3
"""
Apache HTTPD Log Analyzer & Auditor

A standalone terminal log analysis utility.
Parses Apache HTTPD Access Logs (Combined or Common format) line-by-line.
Provides:
1. Traffic statistics: hits, total bandwidth, status code percentages.
2. Analytics: top client IP hosts, top requested URL paths, user-agents.
3. Security auditor: flags directory traversal, SQL injection, XSS, and
   sensitive path scans (.env, .git, config files).

Usage:
    python apache_log_analyzer.py access.log
"""

import sys
import os
import argparse
import re
from collections import Counter

# Compiled regex for Apache Combined Log format:
# %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"
APACHE_COMBINED_REGEX = re.compile(
    r'^([^\s]+) ([^\s]+) ([^\s]+) \[(.*?)\] "(.*?)" (\d{3}) ([0-9\-]+)(?: "(.*?)" "(.*?)")?$'
)

# Security signatures to detect scanner activity or attack payloads
SECURITY_SIGNATURES = [
    (re.compile(r'(?:\.\.\/|\.\.\\|%2e%2e%2f|%2e%2e%255c)', re.I), "Directory Traversal"),
    (re.compile(r'(?:UNION\s+SELECT|UNION\s+ALL\s+SELECT|SELECT\s+.*?\s+FROM|OR\s+\d+=\d+)', re.I), "SQL Injection"),
    (re.compile(r'(?:<script|%3cscript|javascript:|onload=)', re.I), "Cross-Site Scripting (XSS)"),
    (re.compile(r'(?:\.env|\.git/config|wp-config\.php|config\.php|config\.json|setup\.php)', re.I), "Sensitive File Leakage Access"),
    (re.compile(r'(?:/bin/sh|/bin/bash|cmd\.exe|/etc/passwd)', re.I), "Remote Command Exec / Local File Inclusion")
]

def parse_request(request_str):
    """Splits request string e.g. 'GET /index.html HTTP/1.1' into components."""
    parts = request_str.split(' ')
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], parts[1], "HTTP/0.9"
    return "UNKNOWN", request_str, "UNKNOWN"

def format_bytes(size_bytes):
    """Formats bytes size into human-readable data representation."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def analyze_log(filepath):
    """Parses access log line-by-line and generates reports."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        return False

    total_lines = 0
    parsed_lines = 0
    total_bytes = 0
    
    ips = Counter()
    paths = Counter()
    statuses = Counter()
    methods = Counter()
    user_agents = Counter()
    
    security_alerts = []

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
            line = line.strip()
            if not line:
                continue
                
            match = APACHE_COMBINED_REGEX.match(line)
            if not match:
                continue
                
            parsed_lines += 1
            ip, ident, user, timestamp, request, status, size_str, referer, ua = match.groups()
            
            # 1. Parse Status and Size
            status = int(status)
            statuses[status] += 1
            
            size = 0
            if size_str != '-':
                size = int(size_str)
                total_bytes += size
                
            ips[ip] += 1
            
            # 2. Parse Request Method and Path
            method, path, protocol = parse_request(request)
            methods[method] += 1
            paths[path] += 1
            
            if ua:
                user_agents[ua] += 1
                
            # 3. Security Auditing
            # Audit the path, query string, and entire request line
            for pattern, threat_type in SECURITY_SIGNATURES:
                if pattern.search(request):
                    security_alerts.append({
                        'ip': ip,
                        'time': timestamp,
                        'threat': threat_type,
                        'payload': request,
                        'status': status
                    })
                    break

    print("Apache HTTPD Log Analyzer & Auditor")
    print("=" * 70)
    print(f"Log File Path    : {filepath}")
    print(f"Total Lines      : {total_lines}")
    print(f"Parsed Log Lines : {parsed_lines}")
    print(f"Parsed Success % : {(parsed_lines/total_lines)*100:.2f}%" if total_lines > 0 else "0.00%")
    print(f"Total Bandwidth  : {format_bytes(total_bytes)}")
    print("=" * 70)

    if parsed_lines == 0:
        print("No valid log lines matched the Apache Combined/Common regex format.")
        return True

    # Print Methods
    print("\n[HTTP Methods]")
    print("-" * 70)
    for method, count in methods.most_common(5):
        print(f"  {method:<10} : {count:8d} ({(count/parsed_lines)*100:5.2f}%)")

    # Print Status Codes
    print("\n[Response Status Codes]")
    print("-" * 70)
    for status, count in sorted(statuses.items()):
        status_desc = "OK" if status < 300 else "Redirect" if status < 400 else "Client Error" if status < 500 else "Server Error"
        print(f"  {status:<10d} ({status_desc:<12}) : {count:8d} ({(count/parsed_lines)*100:5.2f}%)")

    # Print Top IPs
    print("\n[Top 10 Client IP Hosts]")
    print("-" * 70)
    for ip, count in ips.most_common(10):
        print(f"  {ip:<25} : {count:8d} ({(count/parsed_lines)*100:5.2f}%)")

    # Print Top Paths
    print("\n[Top 10 Requested Paths]")
    print("-" * 70)
    for path, count in paths.most_common(10):
        # Shorten path if too long
        display_path = path if len(path) < 50 else path[:47] + "..."
        print(f"  {display_path:<50} : {count:8d}")

    # Print Security Alerts
    print("\n[Security Auditor Alerts]")
    print("=" * 70)
    if security_alerts:
        try:
            print(f"\033[91m⚠️  WARNING: Detected {len(security_alerts)} potential security scanner attacks!\033[0m")
        except UnicodeEncodeError:
            print(f"\033[91m[!] WARNING: Detected {len(security_alerts)} potential security scanner attacks!\033[0m")
        print("-" * 70)
        # Print top 15 alerts
        for idx, alert in enumerate(security_alerts[:15], 1):
            print(f" #{idx:<2d} [{alert['threat']}] from {alert['ip']} at {alert['time']}")
            print(f"     Payload: {alert['payload']}")
            print(f"     Status : {alert['status']}")
            print()
        if len(security_alerts) > 15:
            print(f"  ... and {len(security_alerts) - 15} more security warnings.")
    else:
        try:
            print("\033[92m✓ No suspicious access payloads or scanner signatures identified.\033[0m")
        except UnicodeEncodeError:
            print("\033[92m[ok] No suspicious access payloads or scanner signatures identified.\033[0m")
    print("=" * 70)

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Natively inspects Apache HTTPD logs and audits suspicious access payloads.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "log_file",
        help="Path to the Apache HTTPD access log file."
    )
    
    args = parser.parse_args()
    
    success = analyze_log(args.log_file)
    if not success:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
