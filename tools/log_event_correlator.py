#!/usr/bin/env python3
"""
Log Event Correlator & Chronological Timeline Builder
Normalizes timestamps across different log files, filters by a correlation key,
and outputs a unified chronological timeline with latency tracking.
"""

import sys
import os
import re
import argparse
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Color utilities for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"

# Common log patterns
PATTERNS = {
    "nginx": re.compile(
        r'^(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d+) (?P<bytes>\d+|-)'
    ),
    "app_iso": re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+\[(?P<level>\w+)\]\s+(?P<message>.*)$'
    ),
    "syslog": re.compile(
        r'^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<process>[^:\[]+)(?:\[(?P<pid>\d+)\])?:?\s+(?P<message>.*)$'
    )
}

# Timestamp parsing formats
TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%d/%b/%Y:%H:%M:%S %z",
    "%b %d %H:%M:%S"  # Syslog style, needs current year injection
]

def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Try to parse a timestamp string using multiple formats."""
    # Strip excess space
    ts_str = ts_str.strip()
    
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(ts_str, fmt)
            # Handle syslog missing year (default to current year)
            if fmt == "%b %d %H:%M:%S":
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
            
    # Try regex cleaning for ISO-8601 sub-second differences
    try:
        # e.g. "2026-07-02 22:03:21,123" -> replace comma with dot
        ts_cleaned = ts_str.replace(",", ".")
        # Remove trailing offset colon if present for Python < 3.7 (e.g. +05:30 -> +0530)
        if len(ts_cleaned) > 6 and ts_cleaned[-3] == ":" and (ts_cleaned[-6] in "+-"):
            ts_cleaned = ts_cleaned[:-3] + ts_cleaned[-2:]
            
        for fmt in TIME_FORMATS:
            try:
                return datetime.strptime(ts_cleaned, fmt)
            except ValueError:
                continue
    except Exception:
        pass
        
    return None

def extract_fields(line: str) -> Dict[str, str]:
    """Attempt to extract standard fields from a log line using predefined patterns."""
    for name, pattern in PATTERNS.items():
        match = pattern.match(line)
        if match:
            data = match.groupdict()
            data["_format"] = name
            return data
            
    # Fallback parser: search for any ISO-8601-like timestamp in the first 50 chars
    iso_match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?', line[:50])
    if iso_match:
        return {"timestamp": iso_match.group(0), "message": line[iso_match.end():].strip(), "_format": "fallback_iso"}
        
    return {"timestamp": "", "message": line, "_format": "raw"}

def process_file(filepath: str, key_re: Optional[re.Pattern]) -> List[Dict[str, Any]]:
    """Read a log file, extract entries, filter by key, and parse timestamps."""
    entries = []
    filename = os.path.basename(filepath)
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                # Filter by key first if specified to save resources
                if key_re and not key_re.search(line):
                    continue
                    
                fields = extract_fields(line.strip())
                ts_str = fields.get("timestamp", "")
                dt = parse_timestamp(ts_str) if ts_str else None
                
                # If timestamp parsing fails but we matched the key, use line number or print warning
                message = fields.get("message", line.strip())
                if fields.get("_format") == "nginx":
                    message = f"{fields.get('ip')} - {fields.get('request')} -> {fields.get('status')}"
                elif fields.get("_format") == "syslog":
                    message = f"[{fields.get('process')}] {fields.get('message')}"
                    
                entries.append({
                    "filename": filename,
                    "line_no": line_no,
                    "timestamp": dt,
                    "timestamp_raw": ts_str,
                    "message": message,
                    "raw": line.strip()
                })
    except Exception as e:
        print(f"\033[31mError reading {filepath}: {e}\033[0m", file=sys.stderr)
        
    return entries

def main():
    parser = argparse.ArgumentParser(
        description="Log Event Correlator - Build a chronological timeline from multiple log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python log_event_correlator.py -k "192.168.1.50" nginx_access.log syslog app_debug.log
  python log_event_correlator.py -k "user_id_102" app.log db.log -w 10
  python log_event_correlator.py -k "ERR_CONN_TIMEOUT" auth.log --raw
        """
    )
    parser.add_argument("-k", "--key", type=str, required=True, help="Correlation key (e.g. IP address, session ID, UUID)")
    parser.add_argument("files", nargs="+", help="List of log files to correlate and merge")
    parser.add_argument("-w", "--window", type=float, help="Time window (in seconds) to separate transaction sequences visually")
    parser.add_argument("--raw", action="store_true", help="Display raw log lines instead of parsed/summarized messages")
    
    args = parser.parse_args()
    
    # Compile key regex
    try:
        key_re = re.compile(re.escape(args.key), re.IGNORECASE)
    except Exception as e:
        print(f"Invalid correlation key: {e}", file=sys.stderr)
        sys.exit(1)
        
    all_entries = []
    
    # Process each log file
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"\033[31mFile not found: {filepath}\033[0m", file=sys.stderr)
            continue
        entries = process_file(filepath, key_re)
        all_entries.extend(entries)
        
    if not all_entries:
        print(f"No events found matching key: '{args.key}'")
        return
        
    # Sort entries by timestamp. If timestamp is missing, place at the end
    # Sort stable by original line order
    all_entries.sort(key=lambda x: (x["timestamp"] or datetime.max, x["filename"], x["line_no"]))
    
    # Visual colors list for files
    file_colors = [CYAN, GREEN, YELLOW, MAGENTA, BOLD]
    file_color_map: Dict[str, str] = {}
    for idx, f in enumerate(set(e["filename"] for e in all_entries)):
        file_color_map[f] = file_colors[idx % len(file_colors)]
        
    print_colored(f"Correlating events for key: '{args.key}' ({len(all_entries)} matches found)\n", BOLD)
    print(f"{'Timestamp':<26} | {'Source File':<20} | {'Latency':<9} | Message")
    print("-" * 100)
    
    last_dt = None
    for entry in all_entries:
        dt = entry["timestamp"]
        ts_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if dt else entry["timestamp_raw"] or "No Timestamp"
        
        # Calculate latency / delta
        latency_str = ""
        if last_dt and dt:
            delta = (dt - last_dt).total_seconds()
            if args.window and delta > args.window:
                # Print window boundary separator
                print("-" * 100)
                print_colored(f"{' '*29}=== TIME GAP DETECTED: {delta:.2f} seconds ==={' '*20}", YELLOW)
                print("-" * 100)
            
            if delta < 0.001:
                latency_str = "0.0s"
            elif delta < 1.0:
                latency_str = f"+{delta*1000:.0f}ms"
            else:
                latency_str = f"+{delta:.2f}s"
                
        last_dt = dt or last_dt
        
        filename = entry["filename"]
        color = file_color_map[filename]
        msg = entry["raw"] if args.raw else entry["message"]
        
        # Print row
        file_part = f"{filename}:{entry['line_no']}"
        print(f"{ts_display:<26} | {color}{file_part:<20}{RESET} | {YELLOW}{latency_str:<9}{RESET} | {msg}")
        
if __name__ == "__main__":
    main()
