#!/usr/bin/env python3
"""
Log Merger - Chronologically merges multiple log files using a low-memory generator-based merge sort.
Identifies common timestamp formats, maintains multiline log blocks (like stack traces) together,
and supports time range filtering.
"""

import argparse
import datetime
import heapq
import os
import re
import sys

# Common timestamp regular expressions
TIMESTAMP_PATTERNS = [
    # ISO 8601 / RFC 3339: 2026-06-17T22:04:07 or 2026-06-17 22:04:07.123
    (re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'), '%Y-%m-%d %H:%M:%S'),
    # Apache Log format: 17/Jun/2026:22:04:07 +0530
    (re.compile(r'^\[?(\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\]?'), '%d/%b/%Y:%H:%M:%S %z'),
    # Syslog format: Jun 17 22:04:07
    (re.compile(r'^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'), '%b %d %H:%M:%S'),
]

MONTHS = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
          'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

def parse_timestamp(ts_str):
    """Parses a timestamp string into a datetime object, fallback to naive parsing if timezone is complex."""
    # Strip brackets/quotes if present
    ts_str = ts_str.strip('[]"')
    
    # Try ISO-like formats
    if '-' in ts_str[:10]:
        # Clean up timezone or T/space
        cleaned = ts_str.replace('T', ' ')
        if 'Z' in cleaned:
            cleaned = cleaned.replace('Z', '')
        # Chop subseconds if any (only keep up to seconds for simpler parsing)
        if '.' in cleaned:
            cleaned = cleaned.split('.')[0]
        # Chop timezone offset if present (+05:30)
        cleaned = re.split(r' [+-]\d{2}:?\d{2}', cleaned)[0]
        try:
            return datetime.datetime.strptime(cleaned[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

    # Try Apache format
    if '/' in ts_str:
        try:
            # Drop timezone offset for simple comparison
            parts = ts_str.split(' ')
            dt_part = parts[0]
            return datetime.datetime.strptime(dt_part, '%d/%b/%Y:%H:%M:%S')
        except ValueError:
            pass

    # Try Syslog format (needs current year inference)
    if len(ts_str.split()) >= 3:
        try:
            parts = ts_str.split()
            month_str, day_str, time_str = parts[0], parts[1], parts[2]
            month = MONTHS.get(month_str, 1)
            day = int(day_str)
            h, m, s = map(int, time_str.split(':'))
            current_year = datetime.datetime.now().year
            return datetime.datetime(current_year, month, day, h, m, s)
        except (ValueError, IndexError):
            pass

    # Absolute fallback: epoch datetime
    return datetime.datetime.min

def extract_timestamp(line):
    """Scans the start of the line for a known timestamp pattern."""
    for pattern, _ in TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if match:
            ts_str = match.group(1)
            return parse_timestamp(ts_str), ts_str
    return None, None

class LogEntry:
    """Represents a single log entry, potentially spanning multiple lines."""
    def __init__(self, timestamp, lines, file_index, file_name):
        self.timestamp = timestamp
        self.lines = lines
        self.file_index = file_index
        self.file_name = file_name

    def __lt__(self, other):
        # Comparison logic for heapq: sorts by timestamp
        return self.timestamp < other.timestamp

def stream_log_file(file_path, file_index):
    """Generates LogEntry objects from a log file, keeping multiline entries grouped."""
    file_name = os.path.basename(file_path)
    current_ts = datetime.datetime.min
    current_lines = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                ts, _ = extract_timestamp(line)
                if ts:
                    if current_lines:
                        yield LogEntry(current_ts, current_lines, file_index, file_name)
                    current_ts = ts
                    current_lines = [line]
                else:
                    if not current_lines:
                        # Lead line without timestamp
                        current_ts = datetime.datetime.min
                    current_lines.append(line)
                    
            if current_lines:
                yield LogEntry(current_ts, current_lines, file_index, file_name)
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

def merge_logs(file_paths, output_file=None, start_time=None, end_time=None, show_source=False):
    """Merges files chronologically and writes to output or stdout."""
    streams = [stream_log_file(path, idx) for idx, path in enumerate(file_paths)]
    
    # Heap-based merge
    merged_stream = heapq.merge(*streams)
    
    out = open(output_file, 'w', encoding='utf-8') if output_file else sys.stdout
    
    try:
        for entry in merged_stream:
            # Date filtering
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
                
            for line in entry.lines:
                if show_source:
                    out.write(f"[{entry.file_name}] {line}")
                else:
                    out.write(line)
    finally:
        if output_file:
            out.close()

def main():
    parser = argparse.ArgumentParser(description="Chronologically merge multiple log files.")
    parser.add_argument("files", nargs="+", help="Log files to merge")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    parser.add_argument("-s", "--start", help="Filter: Only logs from this time onwards (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("-e", "--end", help="Filter: Only logs up to this time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--source", action="store_true", help="Prefix each merged line with its source file name")
    
    args = parser.parse_args()
    
    # Validate files
    valid_files = []
    for file_path in args.files:
        if os.path.exists(file_path):
            valid_files.append(file_path)
        else:
            print(f"Warning: File not found: {file_path}", file=sys.stderr)
            
    if not valid_files:
        print("Error: No valid log files provided.", file=sys.stderr)
        sys.exit(1)
        
    # Parse filter dates
    start_dt = None
    end_dt = None
    try:
        if args.start:
            start_dt = datetime.datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S')
        if args.end:
            end_dt = datetime.datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        print(f"Error parsing date filter: {e}. Use format YYYY-MM-DD HH:MM:SS", file=sys.stderr)
        sys.exit(1)
        
    merge_logs(valid_files, args.output, start_dt, end_dt, args.source)
    if args.output:
        print(f"Successfully merged {len(valid_files)} files into {args.output}")

if __name__ == "__main__":
    main()
