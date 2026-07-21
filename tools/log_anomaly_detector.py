#!/usr/bin/env python3
"""
Log Anomaly Detector - Scans logs for security threat patterns (SQL Injection,
XSS, Path Traversal, Command Injection, vulnerability scanner user agents)
and volumetric anomalies (request spikes, high 4xx/5xx error rates per IP).
"""

import argparse
from collections import defaultdict
import os
import re
import sys

# Security threat signatures
THREAT_SIGNATURES = {
    "SQL Injection": re.compile(
        r"(?:union\s+all\s+select|select\s+.*\s+from|concat\s*\(|group_concat|order\s+by|\'\s*or\s*\'?\d+\'?\s*=\s*\'?\d+|\'\s*or\s*\'?.*\'?\s*=\s*\'?.*|\b(select|union|insert|update|delete|drop)\b)", 
        re.IGNORECASE
    ),
    "Cross-Site Scripting (XSS)": re.compile(
        r"(?:<script|script>|javascript:|onerror\s*=|onload\s*=|alert\s*\(|confirm\s*\(|<img\s+src\b|document\.cookie)", 
        re.IGNORECASE
    ),
    "Path Traversal": re.compile(
        r"(?:\.\.\/\.\.|(?:\.\.\/)+etc\/passwd|(?:\.\.\\)+windows\\win\.ini|(?:\.\.\/)+etc\/hosts|\bboot\.ini\b)", 
        re.IGNORECASE
    ),
    "Command Injection / RFI": re.compile(
        r"(?:\b(?:wget|curl|cmd\.exe|powershell|bin\/sh|bin\/bash)\b|\b(?:http|https|ftp):\/\/\S+\.(?:php|txt|sh|pl)\b)", 
        re.IGNORECASE
    ),
    "Scanner User-Agent": re.compile(
        r"(?:sqlmap|nikto|nmap|acunetix|w3af|gobuster|dirbuster|nessus|masscan|hydra|zgrab)", 
        re.IGNORECASE
    )
}

# General regex to extract basic log components (IP, Timestamp, Method, URL/Resource, Status Code, User-Agent)
# Handles Common Log Format (CLF) and Combined Log Format
LOG_PATTERN = re.compile(
    r'(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'              # IP Address
    r'\s+-\s+-\s+\['                                          # Separator and brackets
    r'(?P<timestamp>[^\]]+)\]'                                # Timestamp
    r'\s+"(?P<method>[A-Z]+)\s+(?P<url>[^\s"]+)[^"]*"'        # Method and URL
    r'\s+(?P<status>\d{3})'                                   # HTTP Status code
    r'\s+(?P<bytes>\d+|-)'                                    # Bytes sent
    r'(?:\s+"(?P<referrer>[^"]*)"\s+"(?P<user_agent>[^"]*)")?' # Referrer & User-Agent
)


def analyze_log_line(line, line_num):
    """Parses a log line and checks for signature-based security anomalies."""
    match = LOG_PATTERN.search(line)
    if not match:
        # Fallback raw line search for threats if not matching standard format
        for threat_type, regex in THREAT_SIGNATURES.items():
            if regex.search(line):
                return {
                    "line_num": line_num,
                    "ip": "Unknown IP",
                    "timestamp": "Unknown Time",
                    "url": "Raw Line Match",
                    "threat": threat_type,
                    "evidence": line.strip()[:100]
                }
        return None

    data = match.groupdict()
    ip = data.get("ip")
    timestamp = data.get("timestamp")
    url = data.get("url", "")
    user_agent = data.get("user_agent", "")
    status = data.get("status")

    # Check request URL/parameters for threats
    for threat_type, regex in THREAT_SIGNATURES.items():
        # Scanners are typically checked in User-Agent, others in URL/payload
        if threat_type == "Scanner User-Agent":
            if user_agent and regex.search(user_agent):
                return {
                    "line_num": line_num,
                    "ip": ip,
                    "timestamp": timestamp,
                    "url": url,
                    "threat": threat_type,
                    "evidence": f"UA: {user_agent}"
                }
        else:
            if regex.search(url):
                return {
                    "line_num": line_num,
                    "ip": ip,
                    "timestamp": timestamp,
                    "url": url,
                    "threat": threat_type,
                    "evidence": url[:120]
                }

    return {
        "line_num": line_num,
        "ip": ip,
        "timestamp": timestamp,
        "url": url,
        "status": int(status) if status else 0,
        "threat": None
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scan web/application logs to detect security anomalies."
    )
    parser.add_argument("log_file", help="Path to the log file to analyze.")
    parser.add_argument(
        "-e", "--errors-limit", 
        type=int, 
        default=20, 
        help="Error count limit from a single IP to flag as anomaly (default: 20)."
    )
    parser.add_argument(
        "-r", "--requests-limit", 
        type=int, 
        default=100, 
        help="Total requests limit from a single IP to flag as anomaly (default: 100)."
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Show detailed parsing info."
    )

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: Log file '{args.log_file}' not found.", file=sys.stderr)
        return 1

    threats_detected = []
    ip_request_counts = defaultdict(int)
    ip_error_counts = defaultdict(int)
    total_parsed = 0

    try:
        with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                res = analyze_log_line(line, idx)
                if not res:
                    continue
                
                total_parsed += 1
                ip = res.get("ip")
                
                # Increment request counter
                if ip and ip != "Unknown IP":
                    ip_request_counts[ip] += 1
                
                # Check signature threat
                if res.get("threat"):
                    threats_detected.append(res)
                
                # Check status codes for 4xx/5xx errors
                status = res.get("status", 0)
                if 400 <= status < 600:
                    if ip and ip != "Unknown IP":
                        ip_error_counts[ip] += 1
                        
    except Exception as e:
        print(f"Error reading log file: {e}", file=sys.stderr)
        return 1

    # Print Report
    print("=" * 60)
    print(" LOG ANOMALY DETECTOR REPORT")
    print("=" * 60)
    print(f"File scanned:  {args.log_file}")
    print(f"Total lines:   {total_parsed}")
    print(f"Threat events: {len(threats_detected)}")
    print("=" * 60)

    # 1. Signature threats
    if threats_detected:
        print("\n[+] Signature Threat Events Found:")
        for idx, threat in enumerate(threats_detected, 1):
            print(f"  {idx}. Line {threat['line_num']}: [{threat['threat']}] from {threat['ip']} at {threat['timestamp']}")
            print(f"     Evidence: {threat['evidence']}")
    else:
        print("\n[+] No signature-based threat events detected.")

    # 2. Volumetric anomalies (High requests)
    volume_anomalies = {ip: count for ip, count in ip_request_counts.items() if count >= args.requests_limit}
    if volume_anomalies:
        print(f"\n[+] High-volume IP Anomalies (>= {args.requests_limit} requests):")
        for ip, count in sorted(volume_anomalies.items(), key=lambda x: x[1], reverse=True):
            print(f"  * IP: {ip:<15} - Total Requests: {count}")
    
    # 3. High error rate anomalies
    error_anomalies = {ip: count for ip, count in ip_error_counts.items() if count >= args.errors_limit}
    if error_anomalies:
        print(f"\n[+] High Error Rate IP Anomalies (>= {args.errors_limit} 4xx/5xx errors):")
        for ip, count in sorted(error_anomalies.items(), key=lambda x: x[1], reverse=True):
            print(f"  * IP: {ip:<15} - Error Requests: {count}")

    # Return exit code: 1 if any signature threat or volumetric anomaly is found, 0 otherwise
    if threats_detected or volume_anomalies or error_anomalies:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
