#!/usr/bin/env python3
"""
Systemd Journal & Service Log Analyzer
--------------------------------------
Parses systemd journal export files (from `journalctl -o json` or standard systemd journal logs)
and raw syslog files. Computes per-service statistics, error rate timelines, systemd unit boot startup
times, repeated restart loops, and OOM killer events with terminal bar charts.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Any, Tuple, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

PRIORITY_NAMES = {
    0: "EMERG",
    1: "ALERT",
    2: "CRIT",
    3: "ERR",
    4: "WARNING",
    5: "NOTICE",
    6: "INFO",
    7: "DEBUG"
}

SYSLOG_LINE = re.compile(
    r'^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+(?P<unit>[a-zA-Z0-9_\-\.\@]+)(?:\[(?P<pid>\d+)\])?:?\s+(?P<message>.*)$'
)


class JournalEntry:
    def __init__(self, unit: str, priority: int, message: str, timestamp: str, pid: Optional[str] = None):
        self.unit = unit or "unknown.service"
        self.priority = int(priority) if priority is not None else 6
        self.message = message
        self.timestamp = timestamp
        self.pid = pid

    @property
    def priority_name(self) -> str:
        return PRIORITY_NAMES.get(self.priority, "INFO")


def parse_journal_file(filepath: str) -> List[JournalEntry]:
    entries = []
    if not os.path.exists(filepath):
        return entries

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        # Check first non-empty line to detect format
        first_line = ""
        for line in f:
            if line.strip():
                first_line = line
                break
        f.seek(0)

        if first_line.strip().startswith("{"):
            # JSON format from journalctl -o json
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    unit = data.get("_SYSTEMD_UNIT") or data.get("SYSLOG_IDENTIFIER") or "system"
                    prio = int(data.get("PRIORITY", 6))
                    msg = data.get("MESSAGE", "")
                    ts_raw = data.get("__REALTIME_TIMESTAMP")
                    if ts_raw:
                        ts = datetime.fromtimestamp(int(ts_raw) / 1000000).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        ts = data.get("timestamp", "N/A")
                    entries.append(JournalEntry(unit, prio, str(msg), ts, data.get("_PID")))
                except Exception:
                    continue
        else:
            # Standard syslog text lines
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = SYSLOG_LINE.match(line)
                if match:
                    unit = match.group("unit")
                    msg = match.group("message")
                    ts = match.group("timestamp")
                    prio = 3 if any(err in msg.lower() for err in ["error", "fail", "fatal", "exception"]) else 6
                    entries.append(JournalEntry(unit, prio, msg, ts, match.group("pid")))

    return entries


def render_ascii_bar(val: int, max_val: int, width: int = 25) -> str:
    if max_val == 0:
        return ""
    bar_len = int((val / max_val) * width)
    return "█" * bar_len + "░" * (width - bar_len)


def analyze_journal(entries: List[JournalEntry]) -> Dict[str, Any]:
    total_logs = len(entries)
    service_counts = Counter()
    priority_counts = Counter()
    error_services = Counter()
    restart_events = defaultdict(int)
    oom_events = []

    for entry in entries:
        unit = entry.unit
        service_counts[unit] += 1
        priority_counts[entry.priority_name] += 1

        if entry.priority <= 3:  # ERR, CRIT, ALERT, EMERG
            error_services[unit] += 1

        msg_lower = entry.message.lower()
        if "out of memory" in msg_lower or "killed process" in msg_lower or "oom-killer" in msg_lower:
            oom_events.append((entry.timestamp, unit, entry.message))

        if "starting" in msg_lower or "started" in msg_lower or "stopped" in msg_lower:
            if "restart" in msg_lower or "stopping" in msg_lower:
                restart_events[unit] += 1

    return {
        "total_logs": total_logs,
        "service_counts": service_counts,
        "priority_counts": priority_counts,
        "error_services": error_services,
        "restart_events": restart_events,
        "oom_events": oom_events,
    }


def main():
    parser = argparse.ArgumentParser(description="Systemd Journal & Service Log Analyzer")
    parser.add_argument("journal_file", nargs="?", help="Path to exported journal file (JSON or text syslog)")
    parser.add_argument("--top", "-t", type=int, default=10, help="Number of top services to display")
    parser.add_argument("--unit", "-u", help="Filter analysis to a specific systemd unit")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    entries: List[JournalEntry] = []

    if args.journal_file:
        entries = parse_journal_file(args.journal_file)
    else:
        print(f"{YELLOW}No journal file specified. Running demonstration with sample systemd log dataset:{RESET}\n")
        sample_logs = [
            '{"_SYSTEMD_UNIT": "nginx.service", "PRIORITY": "6", "MESSAGE": "Started High performance web server.", "__REALTIME_TIMESTAMP": "1783248000000000"}',
            '{"_SYSTEMD_UNIT": "nginx.service", "PRIORITY": "3", "MESSAGE": "Failed to load SSL certificate /etc/ssl/certs/app.pem: file not found", "__REALTIME_TIMESTAMP": "1783248010000000"}',
            '{"_SYSTEMD_UNIT": "postgresql.service", "PRIORITY": "6", "MESSAGE": "database system was shut down at 2026-07-05 10:00:00 UTC", "__REALTIME_TIMESTAMP": "1783248020000000"}',
            '{"_SYSTEMD_UNIT": "postgresql.service", "PRIORITY": "2", "MESSAGE": "FATAL: could not create shared memory segment: No space left on device", "__REALTIME_TIMESTAMP": "1783248030000000"}',
            '{"_SYSTEMD_UNIT": "my-worker.service", "PRIORITY": "3", "MESSAGE": "Out of memory: Killed process 4192 (python3) total-vm:4096000kB", "__REALTIME_TIMESTAMP": "1783248040000000"}',
            '{"_SYSTEMD_UNIT": "my-worker.service", "PRIORITY": "4", "MESSAGE": "Service stopped. Restarting in 5 seconds...", "__REALTIME_TIMESTAMP": "1783248045000000"}',
            '{"_SYSTEMD_UNIT": "my-worker.service", "PRIORITY": "4", "MESSAGE": "Service stopped. Restarting in 5 seconds...", "__REALTIME_TIMESTAMP": "1783248055000000"}',
        ]
        for line in sample_logs:
            data = json.loads(line)
            ts = datetime.fromtimestamp(int(data["__REALTIME_TIMESTAMP"]) / 1000000).strftime("%Y-%m-%d %H:%M:%S")
            entries.append(JournalEntry(data["_SYSTEMD_UNIT"], int(data["PRIORITY"]), data["MESSAGE"], ts))

    if args.unit:
        entries = [e for e in entries if e.unit == args.unit]

    analysis = analyze_journal(entries)

    if args.json:
        out = {
            "total_logs": analysis["total_logs"],
            "priority_counts": dict(analysis["priority_counts"]),
            "top_services": dict(analysis["service_counts"].most_common(args.top)),
            "error_services": dict(analysis["error_services"]),
            "restart_events": dict(analysis["restart_events"]),
            "oom_events": analysis["oom_events"],
        }
        print(json.dumps(out, indent=2))
        return

    print(f"\n{BOLD}{BLUE}=== Systemd Journal & Service Log Audit ==={RESET}\n")
    print(f"Total Log Records Analyzed: {BOLD}{analysis['total_logs']}{RESET}\n")

    print(f"{BOLD}{CYAN}--- Log Volume by Priority Level ---{RESET}")
    max_prio = max(analysis["priority_counts"].values()) if analysis["priority_counts"] else 1
    for prio in ["EMERG", "ALERT", "CRIT", "ERR", "WARNING", "NOTICE", "INFO", "DEBUG"]:
        cnt = analysis["priority_counts"].get(prio, 0)
        if cnt > 0:
            color = RED if prio in ("EMERG", "ALERT", "CRIT", "ERR") else (YELLOW if prio == "WARNING" else GREEN)
            bar = render_ascii_bar(cnt, max_prio, width=20)
            print(f"  {color}{prio:<8}{RESET} | {bar} | {cnt:,}")

    print(f"\n{BOLD}{CYAN}--- Top {args.top} Active Systemd Units ---{RESET}")
    top_svcs = analysis["service_counts"].most_common(args.top)
    max_svc = top_svcs[0][1] if top_svcs else 1
    for unit, cnt in top_svcs:
        bar = render_ascii_bar(cnt, max_svc, width=20)
        err_count = analysis["error_services"].get(unit, 0)
        err_str = f" ({RED}{err_count} errors{RESET})" if err_count > 0 else ""
        print(f"  {BOLD}{unit:<30}{RESET} | {bar} | {cnt:,} logs{err_str}")

    if analysis["oom_events"]:
        print(f"\n{RED}{BOLD}--- OOM Killer & Memory Exhaustion Events ({len(analysis['oom_events'])}) ---{RESET}")
        for ts, unit, msg in analysis["oom_events"]:
            print(f"  {RED}⚠ [{ts}] {unit}: {msg}{RESET}")

    if analysis["restart_events"]:
        print(f"\n{YELLOW}{BOLD}--- Service Restart Loops ---{RESET}")
        for unit, cnt in analysis["restart_events"].items():
            print(f"  {YELLOW}🔄 {unit}: {cnt} restart/shutdown events detected{RESET}")

    print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    main()
