#!/usr/bin/env python3
"""Log Timestamp Gap Detector

Scans log files for timestamped entries, calculates time deltas between consecutive events,
detects unexpected silence gaps or execution freezes exceeding a specified threshold,
and outputs gap timelines with contextual log snippets.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

# Common timestamp regex formats
TIMESTAMP_PATTERNS = [
    # ISO 8601 / YYYY-MM-DD HH:MM:SS.fff or T
    (re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)"), "%Y-%m-%d %H:%M:%S"),
    # Standard log: YYYY/MM/DD HH:MM:SS
    (re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)"), "%Y/%m/%d %H:%M:%S"),
    # Syslog: MMM DD HH:MM:SS (e.g. Jul  6 04:00:12)
    (re.compile(r"([A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})"), "%b %d %H:%M:%S"),
]


class LogEntry:
    def __init__(self, line_num: int, timestamp: datetime.datetime, raw_line: str):
        self.line_num = line_num
        self.timestamp = timestamp
        self.raw_line = raw_line


class LogGap:
    def __init__(self, start_entry: LogEntry, end_entry: LogEntry, duration_seconds: float):
        self.start_entry = start_entry
        self.end_entry = end_entry
        self.duration_seconds = duration_seconds


def parse_timestamp(ts_str: str) -> Optional[datetime.datetime]:
    """Attempts to parse timestamp string into datetime object."""
    # Clean fractional seconds if needed
    clean_ts = ts_str.replace("T", " ")
    if "." in clean_ts:
        clean_ts = clean_ts.split(".")[0]

    for _, fmt in TIMESTAMP_PATTERNS:
        try:
            dt = datetime.datetime.strptime(clean_ts, fmt)
            # If syslog without year, assume current year
            if fmt == "%b %d %H:%M:%S" and dt.year == 1900:
                dt = dt.replace(year=datetime.datetime.now().year)
            return dt
        except ValueError:
            continue
    return None


def extract_log_entries(file_path: Path) -> List[LogEntry]:
    """Parses log file and extracts lines containing valid timestamps."""
    entries: List[LogEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                line_str = line.strip()
                if not line_str:
                    continue

                for pattern, _ in TIMESTAMP_PATTERNS:
                    match = pattern.search(line_str)
                    if match:
                        ts_val = match.group(1)
                        dt = parse_timestamp(ts_val)
                        if dt:
                            entries.append(LogEntry(idx, dt, line_str))
                            break
    except Exception as e:
        print(f"{COLOR_RED}Error reading file '{file_path}': {e}{COLOR_RESET}", file=sys.stderr)
    return entries


def detect_gaps(entries: List[LogEntry], min_gap_seconds: float) -> List[LogGap]:
    """Calculates time deltas between consecutive log entries and identifies gaps."""
    gaps: List[LogGap] = []
    if len(entries) < 2:
        return gaps

    for i in range(len(entries) - 1):
        prev = entries[i]
        curr = entries[i + 1]
        delta = (curr.timestamp - prev.timestamp).total_seconds()
        if delta >= min_gap_seconds:
            gaps.append(LogGap(prev, curr, delta))

    return gaps


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze log files to detect unexpected time gaps and execution delays."
    )
    parser.add_argument("log_file", help="Path to input log file.")
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=5.0,
        help="Minimum gap duration in seconds to trigger alert (default: 5.0).",
    )
    parser.add_argument(
        "-c",
        "--context",
        action="store_true",
        help="Display raw log lines before and after detected gaps.",
    )

    args = parser.parse_args()
    log_path = Path(args.log_file).resolve()

    if not log_path.is_file():
        print(f"{COLOR_RED}Error: Log file '{args.log_file}' not found.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    entries = extract_log_entries(log_path)

    if not entries:
        print(f"{COLOR_YELLOW}No timestamped log entries recognized in '{log_path.name}'.{COLOR_RESET}")
        return

    gaps = detect_gaps(entries, args.threshold)
    deltas = [
        (entries[i + 1].timestamp - entries[i].timestamp).total_seconds()
        for i in range(len(entries) - 1)
    ]
    positive_deltas = [d for d in deltas if d >= 0]

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Log Timestamp Gap Detection ==={COLOR_RESET}\n")
    print(f"File: {COLOR_BOLD}{log_path.name}{COLOR_RESET}")
    print(f"Total Timestamped Entries: {len(entries):,}")
    print(f"Time Range: {entries[0].timestamp} to {entries[-1].timestamp}")
    print(f"Gap Threshold: >={args.threshold:.1f} seconds")
    print(f"Gaps Detected: {len(gaps)}\n")

    if positive_deltas:
        avg_delta = sum(positive_deltas) / len(positive_deltas)
        max_delta = max(positive_deltas)
        print(f"{COLOR_BOLD}Time Delta Statistics:{COLOR_RESET}")
        print(f" * Average Delta Between Logs : {avg_delta:.2f}s")
        print(f" * Maximum Time Gap          : {max_delta:.2f}s\n")

    if not gaps:
        print(f"{COLOR_GREEN}No log gaps exceeding threshold ({args.threshold}s) were found!{COLOR_RESET}\n")
        return

    print(f"{COLOR_BOLD}Detected Silence Gaps:{COLOR_RESET}")
    for idx, gap in enumerate(gaps, start=1):
        start_ts = gap.start_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        end_ts = gap.end_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f" {idx:2d}. [{COLOR_RED}{gap.duration_seconds:6.1f}s gap{COLOR_RESET}] "
            f"Line {gap.start_entry.line_num} ({start_ts}) ➜ Line {gap.end_entry.line_num} ({end_ts})"
        )
        if args.context:
            print(f"     {COLOR_GREY}Before (L{gap.start_entry.line_num}): {gap.start_entry.raw_line[:80]}{COLOR_RESET}")
            print(f"     {COLOR_GREY}After  (L{gap.end_entry.line_num}): {gap.end_entry.raw_line[:80]}{COLOR_RESET}")

    print()


if __name__ == "__main__":
    main()
