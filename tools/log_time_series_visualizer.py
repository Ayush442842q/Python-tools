#!/usr/bin/env python3
"""
Log Time-Series Event Visualizer

A CLI tool to parse any text log file, auto-detect log timestamp formats, 
aggregate events over custom time buckets (seconds, minutes, hours, days, etc.), 
and render a beautiful ASCII/Unicode line or bar chart in the terminal.

Usage:
    python tools/log_time_series_visualizer.py -l app.log
    python tools/log_time_series_visualizer.py -l server.log -i minute -q "ERROR"
    python tools/log_time_series_visualizer.py -l access.log -t line -w 50
"""

import argparse
import datetime
import os
import re
import sys
from typing import Dict, List, Tuple, Any, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GRAY = "\033[90m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# List of regexes and corresponding datetime parser patterns
TIMESTAMP_FORMATS = [
    # ISO 8601: 2026-06-29T14:16:08.123Z or 2026-06-29 14:16:08,123
    (re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), 
     lambda s: datetime.datetime.fromisoformat(s.replace("Z", "+00:00").replace(",", ".").split()[0].split(".")[0])),
    
    # Common Apache/Nginx format: 29/Jun/2026:14:16:08 +0530
    (re.compile(r"\b\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}\b"), 
     lambda s: datetime.datetime.strptime(s, "%d/%b/%Y:%H:%M:%S")),
     
    # Syslog format: Jun 29 14:16:08 (assumes current year if missing)
    (re.compile(r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"), 
     lambda s: datetime.datetime.strptime(s, "%b %d %H:%M:%S").replace(year=datetime.datetime.now().year)),
     
    # Simple Date: 2026/06/29 14:16:08
    (re.compile(r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}"), 
     lambda s: datetime.datetime.strptime(s, "%Y/%m/%d %H:%M:%S")),
     
    # Epoch timestamp: 1782739281 or 1782739281.391
    (re.compile(r"\b\d{10}(?:\.\d+)?\b"), 
     lambda s: datetime.datetime.fromtimestamp(float(s)))
]

def detect_and_parse_timestamp(line: str, custom_regex: Optional[re.Pattern] = None) -> Optional[datetime.datetime]:
    """Tries to extract and parse a timestamp from a log line."""
    if custom_regex:
        match = custom_regex.search(line)
        if match:
            try:
                # Try fromisoformat as fallback, or custom logic
                return datetime.datetime.fromisoformat(match.group(0))
            except ValueError:
                pass
        return None
        
    for regex, parser in TIMESTAMP_FORMATS:
        match = regex.search(line)
        if match:
            try:
                return parser(match.group(0))
            except Exception:
                continue
    return None

def get_bucket_key(dt: datetime.datetime, interval: str) -> datetime.datetime:
    """Rounds a datetime object down to the start of the specified interval bucket."""
    if interval == 'second':
        return dt.replace(microsecond=0)
    elif interval == 'minute':
        return dt.replace(second=0, microsecond=0)
    elif interval == 'hour':
        return dt.replace(minute=0, second=0, microsecond=0)
    elif interval == 'day':
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == 'week':
        # Align to Monday of that week
        monday = dt - datetime.timedelta(days=dt.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == 'month':
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt

def generate_buckets(start_dt: datetime.datetime, end_dt: datetime.datetime, interval: str) -> List[datetime.datetime]:
    """Generates all interval bucket datetimes between start and end inclusive."""
    delta = None
    if interval == 'second':
        delta = datetime.timedelta(seconds=1)
    elif interval == 'minute':
        delta = datetime.timedelta(minutes=1)
    elif interval == 'hour':
        delta = datetime.timedelta(hours=1)
    elif interval == 'day':
        delta = datetime.timedelta(days=1)
    elif interval == 'week':
        delta = datetime.timedelta(weeks=1)
    elif interval == 'month':
        # Custom step for months
        buckets = []
        curr = start_dt
        while curr <= end_dt:
            buckets.append(curr)
            # Add ~30 days, then round back to day=1
            curr = (curr + datetime.timedelta(days=32)).replace(day=1)
        return buckets
        
    buckets = []
    curr = start_dt
    while curr <= end_dt:
        buckets.append(curr)
        curr += delta
    return buckets

def draw_chart(buckets: List[datetime.datetime], counts: Dict[datetime.datetime, int], chart_type: str, width: int, interval: str) -> None:
    """Renders the ASCII/Unicode time-series chart."""
    if not counts:
        print("No events to plot.")
        return
        
    max_val = max(counts.values())
    if max_val == 0:
        max_val = 1
        
    # Format string for bucket timestamps
    fmt = "%Y-%m-%d %H:%M:%S"
    if interval == 'day' or interval == 'week':
        fmt = "%Y-%m-%d"
    elif interval == 'month':
        fmt = "%Y-%m"
    elif interval == 'hour':
        fmt = "%Y-%m-%d %H:00"
    elif interval == 'minute':
        fmt = "%m-%d %H:%M"

    print(color_text(f"\nTime-Series Distribution ({interval} intervals)", COLOR_BOLD))
    print(color_text("=" * (width + 25), COLOR_GRAY))

    for b in buckets:
        cnt = counts.get(b, 0)
        label = b.strftime(fmt)
        
        # Calculate bar length
        bar_len = int((cnt / max_val) * width)
        
        if chart_type == 'bar':
            bar = "█" * bar_len
            if bar_len == 0 and cnt > 0:
                bar = "▏"
        else: # line chart
            bar = " " * (bar_len - 1) + "●" if bar_len > 0 else "·"
            
        color = COLOR_GREEN
        if cnt > (max_val * 0.8):
            color = COLOR_RED
        elif cnt > (max_val * 0.4):
            color = COLOR_YELLOW
            
        count_str = f"({cnt})"
        print(f"{color_text(label, COLOR_CYAN)} │ {color_text(bar, color):<{width}} {color_text(count_str, COLOR_BOLD)}")
        
    print(color_text("=" * (width + 25), COLOR_GRAY))
    print(f"Peak events in single interval: {color_text(str(max_val), COLOR_RED)}")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate log files by timestamp and draw time-series frequency charts in terminal."
    )
    parser.add_argument("-l", "--log", required=True, help="Path to the log file to analyze")
    parser.add_argument("-i", "--interval", choices=["second", "minute", "hour", "day", "week", "month"], default="hour",
                        help="Time interval bucket (default: hour)")
    parser.add_argument("-q", "--query", help="Filter log lines by keyword/substring search pattern")
    parser.add_argument("-t", "--type", choices=["bar", "line"], default="bar", help="Chart visual type (default: bar)")
    parser.add_argument("-w", "--width", type=int, default=60, help="Chart width in characters (default: 60)")
    parser.add_argument("-r", "--regex", help="Custom regex pattern to locate timestamps in log lines")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.log):
        print(color_text(f"Error: Log file '{args.log}' not found.", COLOR_RED), file=sys.stderr)
        return 1
        
    custom_re = None
    if args.regex:
        try:
            custom_re = re.compile(args.regex)
        except re.error as e:
            print(color_text(f"Error compiling custom regex: {e}", COLOR_RED), file=sys.stderr)
            return 1

    counts = {}
    parsed_count = 0
    skipped_count = 0
    query_filtered_count = 0
    
    times = []
    
    print(color_text(f"[*] Reading log file: {args.log}...", COLOR_YELLOW))
    
    with open(args.log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            # Query filter
            if args.query and args.query not in line:
                query_filtered_count += 1
                continue
                
            dt = detect_and_parse_timestamp(line, custom_re)
            if dt:
                parsed_count += 1
                times.append(dt)
            else:
                skipped_count += 1

    if not times:
        print(color_text("Error: Could not find or parse any timestamps. Check log format or use --regex.", COLOR_RED), file=sys.stderr)
        if query_filtered_count > 0:
            print(color_text(f"Note: Query '{args.query}' filtered out {query_filtered_count} lines. Try broadening your query.", COLOR_CYAN))
        return 1

    # Sort times and define limits
    times.sort()
    start_dt = get_bucket_key(times[0], args.interval)
    end_dt = get_bucket_key(times[-1], args.interval)
    
    # Generate all buckets in range to handle zero counts
    buckets = generate_buckets(start_dt, end_dt, args.interval)
    
    # Too many buckets check (limit to 100 to prevent terminal flooding)
    if len(buckets) > 100:
        print(color_text(f"[!] Warning: Bucketing yields {len(buckets)} intervals (max display is 100).", COLOR_YELLOW))
        print(color_text("[*] Scaling interval up automatically to keep chart readable...", COLOR_CYAN))
        
        # Scale up
        current_idx = ["second", "minute", "hour", "day", "week", "month"].index(args.interval)
        while len(buckets) > 100 and current_idx < 5:
            current_idx += 1
            args.interval = ["second", "minute", "hour", "day", "week", "month"][current_idx]
            start_dt = get_bucket_key(times[0], args.interval)
            end_dt = get_bucket_key(times[-1], args.interval)
            buckets = generate_buckets(start_dt, end_dt, args.interval)
            
        print(color_text(f"[+] New interval selected: {args.interval} ({len(buckets)} buckets)", COLOR_GREEN))

    # Initialize buckets count
    counts = {b: 0 for b in buckets}
    for dt in times:
        b_key = get_bucket_key(dt, args.interval)
        if b_key in counts:
            counts[b_key] += 1
            
    # Display Stats
    print("\n" + color_text("=== Parsing Statistics ===", COLOR_BOLD))
    print(f"Total lines parsed successfully:   {color_text(str(parsed_count), COLOR_GREEN)}")
    if skipped_count > 0:
        print(f"Lines with unparsed timestamps:  {color_text(str(skipped_count), COLOR_YELLOW)}")
    if args.query:
        print(f"Lines filtered out by query:     {query_filtered_count}")
    print(f"Start Timestamp:                 {times[0]}")
    print(f"End Timestamp:                   {times[-1]}")
    print(f"Duration:                        {times[-1] - times[0]}")
    
    draw_chart(buckets, counts, args.type, args.width, args.interval)
    return 0

if __name__ == "__main__":
    sys.exit(main())
