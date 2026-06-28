#!/usr/bin/env python3
"""
Log Rate Analyzer

A CLI tool that parses logs, identifies timestamps (supporting standard formats like
Apache log, ISO 8601, syslog, DB logs), aggregates entries over configurable time
intervals (seconds, minutes, hours, days), prints statistics, and visualizes log
rates using a dynamic ASCII bar chart.

Usage:
    python tools/log_rate_analyzer.py -f server.log -i 1h
    cat server.log | python tools/log_rate_analyzer.py -i 5m --chart-height 10
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import math
import os
import re
import sys
from typing import Dict, Any, List, Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Log level indicators to count
LEVEL_PATTERNS = {
    "DEBUG": re.compile(r"\b(DEBUG|DBG|TRACE)\b", re.IGNORECASE),
    "INFO": re.compile(r"\b(INFO|INF)\b", re.IGNORECASE),
    "WARNING": re.compile(r"\b(WARNING|WARN|WRN)\b", re.IGNORECASE),
    "ERROR": re.compile(r"\b(ERROR|ERR|FATAL|CRITICAL|CRT)\b", re.IGNORECASE)
}

# Timestamp regex patterns
TIMESTAMP_PATTERNS = [
    # ISO 8601 / RFC 3339: 2026-06-28T15:30:36+05:30 or 2026-06-28 15:30:36.123
    (re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?[Z\d:+-]*)"), 
     lambda m: parse_datetime(m, ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"])),
    
    # Apache Common Log: [28/Jun/2026:15:30:36 +0530]
    (re.compile(r"\[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}(?:\s+[+-]\d{4})?)\]"),
     lambda m: parse_datetime(m, ["%d/%b/%Y:%H:%M:%S"])),
    
    # Syslog: Jun 28 15:30:36 (assumes current year if missing)
    (re.compile(r"\b([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b"),
     lambda m: parse_syslog_datetime(m))
]

def parse_datetime(match_str: str, formats: List[str]) -> Optional[datetime]:
    # Clean string if there are offsets or subseconds for simplified parsing
    cleaned = match_str.split('.')[0].split('+')[0].split('-')[0].strip()
    if cleaned.endswith('Z'):
        cleaned = cleaned[:-1]
    
    # Special clean-up for Apache offset
    if ' ' in cleaned and (cleaned.split(' ')[-1].startswith('+') or cleaned.split(' ')[-1].startswith('-')):
        cleaned = cleaned.rsplit(' ', 1)[0]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None

def parse_syslog_datetime(match_str: str) -> Optional[datetime]:
    current_year = datetime.now().year
    try:
        # Standard syslog format doesn't have a year, prefixing current year
        cleaned = re.sub(r'\s+', ' ', match_str.strip())
        dt = datetime.strptime(f"{current_year} {cleaned}", "%Y %b %d %H:%M:%S")
        return dt
    except ValueError:
        return None

class LogRateAnalyzer:
    def __init__(self, interval_seconds: int = 60, max_chart_width: int = 50):
        self.interval_seconds = interval_seconds
        self.max_chart_width = max_chart_width
        self.total_lines = 0
        self.parsed_lines = 0
        self.timestamps: List[datetime] = []
        self.levels = Counter()

    def feed_line(self, line: str):
        self.total_lines += 1
        
        # Audit log level
        for level, pattern in LEVEL_PATTERNS.items():
            if pattern.search(line):
                self.levels[level] += 1
                break

        # Find timestamp
        for pattern, parser_func in TIMESTAMP_PATTERNS:
            match = pattern.search(line)
            if match:
                dt = parser_func(match.group(1))
                if dt:
                    self.timestamps.append(dt)
                    self.parsed_lines += 1
                    break

    def analyze(self) -> Dict[str, Any]:
        if not self.timestamps:
            return {}

        self.timestamps.sort()
        start_time = self.timestamps[0]
        end_time = self.timestamps[-1]
        duration_seconds = max(1.0, (end_time - start_time).total_seconds())

        # Bucket logs
        buckets = defaultdict(int)
        for ts in self.timestamps:
            offset = int((ts - start_time).total_seconds() / self.interval_seconds)
            buckets[offset] += 1

        # Fill in empty buckets
        max_bucket = int(duration_seconds / self.interval_seconds)
        for i in range(max_bucket + 1):
            if i not in buckets:
                buckets[i] = 0

        sorted_buckets = sorted(buckets.items())
        counts = [val for _, val in sorted_buckets]
        peak_rate = max(counts) if counts else 0
        avg_rate = len(self.timestamps) / (max_bucket + 1)

        return {
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "total_lines": self.total_lines,
            "parsed_lines": self.parsed_lines,
            "peak_rate": peak_rate,
            "avg_rate": avg_rate,
            "buckets": sorted_buckets,
            "levels": self.levels
        }

    def render_ascii_chart(self, analysis: Dict[str, Any], chart_height: int = 10) -> str:
        buckets = analysis.get("buckets", [])
        if not buckets:
            return "No bucket data to display."

        max_val = max(val for _, val in buckets)
        if max_val == 0:
            return "All buckets are empty."

        # Aggregate buckets if they exceed max_chart_width
        num_buckets = len(buckets)
        if num_buckets > self.max_chart_width:
            chunk_size = math.ceil(num_buckets / self.max_chart_width)
            aggregated = []
            for i in range(0, num_buckets, chunk_size):
                chunk = buckets[i : i + chunk_size]
                avg_time_idx = chunk[0][0]
                sum_val = sum(v for _, v in chunk)
                aggregated.append((avg_time_idx, sum_val))
            chart_buckets = aggregated
            max_val = max(val for _, val in chart_buckets)
        else:
            chart_buckets = buckets

        # Draw chart grid
        lines = []
        width = len(chart_buckets)

        for row in range(chart_height, 0, -1):
            threshold = (row / chart_height) * max_val
            line_parts = []
            for _, val in chart_buckets:
                if val >= threshold:
                    line_parts.append("█")
                elif val >= threshold - (max_val / (chart_height * 2)):
                    line_parts.append("▄")
                else:
                    line_parts.append(" ")
            
            y_label = f"{int(threshold):>6} | "
            lines.append(y_label + "".join(line_parts))

        # X-axis line
        lines.append("       +" + "-" * width)
        
        # X-axis Labels (Start and End times)
        start_str = analysis["start_time"].strftime("%H:%M:%S")
        end_str = analysis["end_time"].strftime("%H:%M:%S")
        
        spacing = width - len(start_str) - len(end_str)
        if spacing > 0:
            x_labels = "        " + start_str + " " * spacing + end_str
        else:
            x_labels = "        " + start_str + " ... " + end_str
        lines.append(x_labels)

        return "\n".join(lines)

def parse_interval(interval_str: str) -> int:
    """Parses interval string (e.g., '10s', '5m', '2h') into seconds."""
    match = re.match(r"^(\d+)([smhd])$", interval_str.lower())
    if not match:
        raise ValueError("Invalid interval format. Use e.g. 30s, 5m, 1h, 1d")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    return 60

def main():
    parser = argparse.ArgumentParser(description="Log Rate Analyzer & Visualizer")
    parser.add_argument("-f", "--file", help="Path to log file (reads from stdin if omitted)")
    parser.add_argument("-i", "--interval", default="1m", help="Time bucket interval (e.g., 10s, 1m, 1h, 1d) [default: 1m]")
    parser.add_argument("--chart-height", type=int, default=10, help="Height of ASCII bar chart in lines [default: 10]")
    parser.add_argument("--chart-width", type=int, default=60, help="Maximum width of ASCII bar chart [default: 60]")
    
    args = parser.parse_args()

    try:
        interval_secs = parse_interval(args.interval)
    except ValueError as e:
        print(color_text(str(e), COLOR_RED), file=sys.stderr)
        sys.exit(1)

    analyzer = LogRateAnalyzer(interval_seconds=interval_secs, max_chart_width=args.chart_width)

    # Read inputs
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    analyzer.feed_line(line)
        else:
            if sys.stdin.isatty():
                parser.print_help()
                sys.exit(0)
            for line in sys.stdin:
                analyzer.feed_line(line)
    except KeyboardInterrupt:
        print(color_text("\nAnalysis interrupted by user.", COLOR_YELLOW), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(color_text(f"Error reading logs: {e}", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    analysis = analyzer.analyze()
    if not analysis:
        print(color_text("Error: No valid timestamps found in the log data.", COLOR_RED))
        sys.exit(1)

    # Render results
    print(color_text(f"\n{COLOR_BOLD}=== Log Rate Analysis Results ==={COLOR_RESET}", COLOR_CYAN))
    print(f"Total Lines Scanned: {analysis['total_lines']}")
    print(f"Lines with Timestamps: {analysis['parsed_lines']} ({analysis['parsed_lines']/analysis['total_lines']*100:.1f}%)")
    print(f"Time Window: {analysis['start_time']} to {analysis['end_time']}")
    
    duration = analysis['duration_seconds']
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"Duration: {int(hours)}h {int(minutes)}m {int(seconds)}s")
    
    # Rates
    entries_per_sec = len(analyzer.timestamps) / duration
    print(f"Average Log Rate: {entries_per_sec:.2f} lines/sec (or {analysis['avg_rate']:.1f} lines per {args.interval} interval)")
    print(f"Peak Log Rate in interval: {analysis['peak_rate']} lines per {args.interval}")

    # Levels
    print(color_text(f"\n{COLOR_BOLD}=== Log Level Breakdown ==={COLOR_RESET}", COLOR_CYAN))
    levels = analysis["levels"]
    total_levels = sum(levels.values())
    for lvl in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        count = levels[lvl]
        pct = (count / total_levels * 100) if total_levels > 0 else 0.0
        color = COLOR_GREEN
        if lvl == "WARNING":
            color = COLOR_YELLOW
        elif lvl == "ERROR":
            color = COLOR_RED
        elif lvl == "DEBUG":
            color = COLOR_MAGENTA
        print(f"  {color_text(lvl:<8, color)}: {count:<8} ({pct:.1f}%)")

    # ASCII Chart
    print(color_text(f"\n{COLOR_BOLD}=== Log Rate Chart (Volume per {args.interval} interval) ==={COLOR_RESET}", COLOR_CYAN))
    print(analyzer.render_ascii_chart(analysis, chart_height=args.chart_height))
    print()

if __name__ == "__main__":
    main()
