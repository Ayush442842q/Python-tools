#!/usr/bin/env python3
"""
Log Visualizer

Parse and analyze log files (JSON-Lines, CSV, or standard text logs),
aggregate metrics (by level, hour, or service), and display a beautiful
text-based histogram and summary report in the terminal.

Usage:
    python tools/log_visualizer.py <log_file> [options]

Requirements:
    - Python 3.6+
"""

import sys
import os
import re
import argparse
import json
import csv
from datetime import datetime
from collections import Counter

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

LEVEL_COLORS = {
    "DEBUG": BLUE,
    "INFO": GREEN,
    "WARN": YELLOW,
    "WARNING": YELLOW,
    "ERROR": RED,
    "CRITICAL": MAGENTA,
    "UNKNOWN": CYAN
}

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def generate_histogram(counter, max_width=40, use_color=True):
    """Generate a horizontal text-based histogram from a Counter object."""
    if not counter:
        return ""
    
    max_val = max(counter.values())
    sorted_items = sorted(counter.items(), key=lambda x: x[0])
    
    lines = []
    for label, val in sorted_items:
        bar_len = int(round(max_width * val / max_val)) if max_val > 0 else 0
        bar = "█" * bar_len + "░" * (max_width - bar_len)
        color = LEVEL_COLORS.get(str(label).upper(), RESET) if use_color else ""
        lines.append(f"  {label:<12} [{color}{bar}{RESET if use_color else ''}] {val:5d}")
    return "\n".join(lines)

def detect_level(text):
    """Heuristic to detect log levels in raw text."""
    text_upper = text.upper()
    for lvl in ["CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"]:
        if lvl in text_upper:
            return lvl
    return "UNKNOWN"

def parse_log_line(line, line_num):
    """Attempt to parse a log line as JSON, CSV, or plain text."""
    line_stripped = line.strip()
    if not line_stripped:
        return None

    # 1. Try parsing as JSON
    try:
        data = json.loads(line_stripped)
        if isinstance(data, dict):
            # Try to identify level
            level = "UNKNOWN"
            for k in ["level", "loglevel", "severity", "status", "type"]:
                if k in data:
                    level = str(data[k]).upper()
                    break
            if level == "UNKNOWN":
                # Fallback to checking full JSON string
                level = detect_level(line)

            # Try to identify timestamp
            timestamp = None
            for k in ["time", "timestamp", "date", "@timestamp"]:
                if k in data:
                    timestamp = str(data[k])
                    break

            # Try to identify message
            message = ""
            for k in ["msg", "message", "text", "description"]:
                if k in data:
                    message = str(data[k])
                    break
            
            return {"level": level, "timestamp": timestamp, "message": message}
    except json.JSONDecodeError:
        pass

    # 2. Fall back to plain text regex-based scanning
    # Common log formats often include timestamps and log levels in brackets/uppercase
    level = detect_level(line)
    
    # Try extracting timestamp: e.g., 2026-06-17 10:00:00 or [17/Jun/2026:10:00:00]
    time_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', line)
    timestamp = time_match.group(1) if time_match else None
    
    return {"level": level, "timestamp": timestamp, "message": line_stripped}

def analyze_log_file(file_path):
    """Read and analyze the log file."""
    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"
    
    level_counter = Counter()
    hour_counter = Counter()
    total_lines = 0
    errors_list = []

    try:
        # Check if it looks like a CSV file (based on extension)
        is_csv = file_path.lower().endswith('.csv')
        
        if is_csv:
            with open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    total_lines += 1
                    # Try to find level, timestamp, message in CSV columns
                    level = "UNKNOWN"
                    for k in row.keys():
                        if k and k.lower() in ["level", "loglevel", "severity", "status"]:
                            level = str(row[k]).upper()
                            break
                    if level == "UNKNOWN":
                        level = detect_level(str(row))

                    timestamp = None
                    for k in row.keys():
                        if k and k.lower() in ["time", "timestamp", "date"]:
                            timestamp = str(row[k])
                            break
                    
                    level_counter[level] += 1
                    
                    # Parse hour from timestamp if possible
                    if timestamp:
                        hour_match = re.search(r'(\d{2}):\d{2}:', timestamp)
                        if hour_match:
                            hour_counter[f"{hour_match.group(1)}:00"] += 1

                    if level in ["ERROR", "CRITICAL"]:
                        msg = row.get("message") or row.get("msg") or str(row)
                        errors_list.append(msg[:100])
        else:
            # Parse line by line (Text/JSON-Lines)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    parsed = parse_log_line(line, line_num)
                    if not parsed:
                        continue
                    
                    total_lines += 1
                    lvl = parsed["level"]
                    level_counter[lvl] += 1
                    
                    # Parse hour from timestamp
                    ts = parsed["timestamp"]
                    if ts:
                        hour_match = re.search(r'(\d{2}):\d{2}:', ts)
                        if hour_match:
                            hour_counter[f"{hour_match.group(1)}:00"] += 1
                            
                    if lvl in ["ERROR", "CRITICAL"]:
                        errors_list.append(parsed["message"][:100])
                        
        return {
            "total_lines": total_lines,
            "levels": level_counter,
            "hours": hour_counter,
            "errors": errors_list[:10]  # Keep top 10 error lines
        }, None
    except Exception as e:
        return None, f"Error processing file: {e}"

def main():
    parser = argparse.ArgumentParser(
        description="Analyze log files and visualize metrics in the console.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the log file (txt, log, jsonl, csv)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")
    parser.add_argument("-w", "--width", type=int, default=40, help="Max width of histogram bars (default: 40)")
    parser.add_argument("-e", "--errors", action="store_true", help="Print recent error message snippets")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    print(f"Analyzing log file: {args.file} ...")
    stats, err = analyze_log_file(args.file)
    
    if err:
        print_colored(f"Error: {err}", RED, use_color)
        return 1

    if stats["total_lines"] == 0:
        print_colored("No log lines parsed. The file might be empty or in an unrecognized format.", YELLOW, use_color)
        return 0

    print_colored(f"\n{BOLD}=== LOG ANALYSIS REPORT ==={RESET}", BOLD if use_color else "", use_color)
    print(f"Total Log Lines Processed: {stats['total_lines']}")
    print()

    # 1. Log Levels Breakdown
    print_colored(f"{BOLD}Log Level Distribution:{RESET}", BOLD if use_color else "", use_color)
    print(generate_histogram(stats["levels"], max_width=args.width, use_color=use_color))
    print()

    # 2. Hourly Distribution
    if stats["hours"]:
        print_colored(f"{BOLD}Hourly Log Frequency:{RESET}", BOLD if use_color else "", use_color)
        print(generate_histogram(stats["hours"], max_width=args.width, use_color=False))
        print()

    # 3. Print Error details
    if args.errors or stats["levels"]["ERROR"] > 0 or stats["levels"]["CRITICAL"] > 0:
        err_count = stats["levels"]["ERROR"] + stats["levels"]["CRITICAL"]
        if err_count > 0:
            print_colored(f"{BOLD}Recent Errors/Critical Events (Top {len(stats['errors'])} shown):{RESET}", RED, use_color)
            for idx, err_msg in enumerate(stats["errors"], 1):
                print(f"  {idx}. {err_msg.strip()}")
            print()
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
