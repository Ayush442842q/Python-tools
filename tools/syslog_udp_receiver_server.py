#!/usr/bin/env python3
"""
Syslog UDP Receiver & Log Parser Server
---------------------------------------
Lightweight UDP Syslog server and log packet analyzer (RFC 3164 / RFC 5424 format).
Parses facility, severity level, timestamp, hostname/app name, and message payload.
Provides colored terminal output, filtering by severity level, and log file logging.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import socket
import json
import time
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

FACILITIES = [
    "kernel", "user", "mail", "daemon", "auth", "syslog", "lpr", "news",
    "uucp", "cron", "authpriv", "ftp", "ntp", "security", "console", "solaris-cron",
    "local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7"
]

SEVERITIES = [
    "EMERGENCY", "ALERT", "CRITICAL", "ERROR", "WARNING", "NOTICE", "INFORMATIONAL", "DEBUG"
]

SEVERITY_COLORS = {
    "EMERGENCY": RED + BOLD,
    "ALERT": RED + BOLD,
    "CRITICAL": RED,
    "ERROR": RED,
    "WARNING": YELLOW,
    "NOTICE": CYAN,
    "INFORMATIONAL": GREEN,
    "DEBUG": RESET,
}


def parse_syslog_message(data: str) -> Dict[str, Any]:
    """
    Parses a Syslog message string.
    Decodes <PRIVALUE> into Facility and Severity.
    """
    prival = 13  # Default user.notice (13)
    msg = data

    pri_match = re.match(r'^<(\d{1,3})>(.*)', data, re.DOTALL)
    if pri_match:
        prival = int(pri_match.group(1))
        msg = pri_match.group(2)

    facility_id = prival >> 3
    severity_id = prival & 7

    facility = FACILITIES[facility_id] if facility_id < len(FACILITIES) else f"custom({facility_id})"
    severity = SEVERITIES[severity_id] if severity_id < len(SEVERITIES) else f"level({severity_id})"

    # Check for header fields (RFC 3164 timestamp & host)
    header_pattern = r'^([A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+([^\s]+)\s+(.*)$'
    match = re.match(header_pattern, msg)

    if match:
        timestamp_str = match.group(1)
        hostname = match.group(2)
        content = match.group(3)
    else:
        timestamp_str = datetime.now().strftime("%b %d %H:%M:%S")
        hostname = "localhost"
        content = msg

    return {
        "priority_val": prival,
        "facility": facility,
        "severity": severity,
        "severity_id": severity_id,
        "timestamp": timestamp_str,
        "hostname": hostname,
        "message": content.strip(),
    }


def format_log_entry(entry: Dict[str, Any]) -> str:
    """Format syslog entry with ANSI color coding for terminal view."""
    color = SEVERITY_COLORS.get(entry["severity"], RESET)
    return (
        f"{CYAN}[{entry['timestamp']}]{RESET} "
        f"{BOLD}{entry['hostname']}{RESET} "
        f"{color}[{entry['facility'].upper()}:{entry['severity']}]{RESET} "
        f"{entry['message']}"
    )


def run_demo():
    """Run interactive demonstration with simulated Syslog packets."""
    demo_packets = [
        "<34>Oct 11 22:14:15 srv-web-01 nginx: [error] 1024#0: *12 open() /var/www/html/favicon.ico failed",
        "<86>Oct 11 22:14:18 auth-master-01 sshd[4821]: Failed password for invalid user admin from 192.168.1.150 port 52210 ssh2",
        "<13>Oct 11 22:14:20 app-node-02 user: [info] Background worker completed job #8841 successfully in 142ms",
        "<19>Oct 11 22:14:22 db-primary-01 postgres[2104]: [warning] Connection pool usage reached 85% capacity",
        "<11>Oct 11 22:14:25 core-router-01 kernel: Out of memory: Kill process 994 (python) score 850 or sacrifice child",
    ]

    print(f"{BOLD}{CYAN}=== Syslog UDP Receiver & Log Parser Server Demo ==={RESET}\n")
    print(f"{BOLD}Simulating incoming Syslog UDP packets...{RESET}\n")

    for raw in demo_packets:
        parsed = parse_syslog_message(raw)
        print(format_log_entry(parsed))

    print(f"\n{BOLD}{YELLOW}--- Parsed JSON Object Example ---{RESET}")
    print(json.dumps(parse_syslog_message(demo_packets[0]), indent=2))


def start_syslog_server(host: str, port: int, min_severity_id: int = 7, log_file: Optional[str] = None):
    """Binds UDP socket and listens for syslog messages."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
        print(f"{GREEN}Syslog UDP server listening on {host}:{port} ...{RESET}")
        print(f"Press Ctrl+C to terminate.")
    except Exception as e:
        print(f"Error binding socket to {host}:{port}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            msg_str = data.decode("utf-8", errors="replace")
            parsed = parse_syslog_message(msg_str)

            if parsed["severity_id"] <= min_severity_id:
                print(format_log_entry(parsed))

                if log_file:
                    try:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(parsed) + "\n")
                    except Exception as e:
                        print(f"Error writing to log file: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping Syslog server.{RESET}")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="UDP Syslog receiver server and parser utility (RFC 3164 / RFC 5424)."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind UDP server (default: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=5140, help="UDP port to listen on (default: 5140)")
    parser.add_argument(
        "-l", "--log-file", help="Path to write incoming logs as JSON lines"
    )
    parser.add_argument(
        "--min-severity",
        choices=SEVERITIES,
        default="DEBUG",
        help="Filter logs up to specified severity level (default: DEBUG)",
    )
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    min_sev_idx = SEVERITIES.index(args.min_severity.upper())
    start_syslog_server(args.host, args.port, min_severity_id=min_sev_idx, log_file=args.log_file)


if __name__ == "__main__":
    main()
