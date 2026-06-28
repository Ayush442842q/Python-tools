#!/usr/bin/env python3
"""
Binary Search Log Slicer
------------------------
A high-performance log-slicing utility designed to extract log entries within
a specific timeframe from huge, chronologically ordered log files (e.g., gigabytes)
using binary search instead of scanning the file line-by-line.

Dependencies:
    - python 3.6+

Usage:
    python tools/log_slicer_by_time.py <log_file> --start "2026-06-28 12:00:00" --end "2026-06-28 13:00:00"
"""

import os
import sys
import re
import argparse
from datetime import datetime
from typing import Optional, Tuple, List

# Common log timestamp regexes and their corresponding datetime format strings
TIMESTAMP_PATTERNS = [
    # ISO 8601 / RFC 3339: 2026-06-28T14:40:36.123Z or 2026-06-28 14:40:36,123
    (re.compile(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?'), 
     lambda s: datetime.fromisoformat(s.replace('Z', '+00:00').replace(',', '.').replace(' ', 'T')[:19])),
     
    # Apache Common/Combined Log Format: [28/Jun/2026:14:40:36 +0530]
    (re.compile(r'\[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}) [+-]\d{4}\]'),
     lambda s: datetime.strptime(s, '%d/%b/%Y:%H:%M:%S')),
     
    # Syslog standard: Jun 28 14:40:36
    (re.compile(r'^([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'),
     lambda s: datetime.strptime(s, '%b %d %H:%M:%S').replace(year=datetime.now().year)),
     
    # Simple Date Time: 2026/06/28 14:40:36
    (re.compile(r'^(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})'),
     lambda s: datetime.strptime(s, '%Y/%m/%d %H:%M:%S')),
]

def extract_timestamp(line: str, custom_regex: Optional[re.Pattern] = None, custom_format: Optional[str] = None) -> Optional[datetime]:
    """Extract and parse timestamp from a log line."""
    if not line.strip():
        return None
        
    # Custom format support
    if custom_regex and custom_format:
        match = custom_regex.search(line)
        if match:
            try:
                return datetime.strptime(match.group(1) if match.groups() else match.group(0), custom_format)
            except ValueError:
                return None
        return None
        
    # Standard format matching
    for pattern, parser in TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if match:
            try:
                raw_ts = match.group(1) if pattern.groups else match.group(0)
                # Clean up brackets for Apache logs if present
                raw_ts = raw_ts.strip('[]')
                return parser(raw_ts)
            except (ValueError, IndexError):
                continue
                
    return None

def find_next_line(f, pos: int) -> Tuple[int, str]:
    """Seek to pos, read until a newline to align, then read and return the next line along with its byte start offset."""
    if pos == 0:
        f.seek(0)
        line = f.readline()
        return 0, line
        
    # Seek to character before pos to see if it's already a newline
    f.seek(pos - 1)
    char = f.read(1)
    
    # If the character is not a newline, read until the end of this line
    if char != '\n':
        f.readline()
        
    line_start = f.tell()
    line = f.readline()
    return line_start, line

def binary_search_log(file_path: str, target_time: datetime, custom_regex: Optional[re.Pattern] = None, custom_format: Optional[str] = None) -> int:
    """
    Search the log file using binary search to find the byte offset of the
    first line with a timestamp >= target_time.
    Returns the file byte offset.
    """
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        low = 0
        high = file_size
        best_offset = file_size
        
        while low <= high:
            mid = (low + high) // 2
            line_start, line = find_next_line(f, mid)
            
            if not line:
                # We hit EOF, search in lower half
                high = mid - 1
                continue
                
            ts = extract_timestamp(line, custom_regex, custom_format)
            
            # If we can't parse a timestamp, we might be in the middle of a multiline log or header.
            # Try to read a few more lines to find a valid timestamp.
            max_attempts = 10
            while ts is None and max_attempts > 0:
                line_start = f.tell()
                line = f.readline()
                if not line:
                    break
                ts = extract_timestamp(line, custom_regex, custom_format)
                max_attempts -= 1
                
            if ts is None:
                # Still no timestamp, fall back to searching lower half
                high = mid - 1
                continue
                
            if ts >= target_time:
                best_offset = line_start
                # Search lower half to find the first occurrence
                high = mid - 1
            else:
                # Search upper half
                low = f.tell()
                
        return best_offset

def slice_log(file_path: str, start_time: Optional[datetime], end_time: Optional[datetime], 
              custom_regex: Optional[re.Pattern] = None, custom_format: Optional[str] = None,
              output_path: Optional[str] = None) -> int:
    """Slice log file and write matching lines to standard output or a file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Log file not found: {file_path}")
        
    start_offset = 0
    if start_time:
        start_offset = binary_search_log(file_path, start_time, custom_regex, custom_format)
        
    lines_written = 0
    out_stream = open(output_path, 'w', encoding='utf-8') if output_path else sys.stdout
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(start_offset)
            
            # Keep reading until we pass the end_time
            while True:
                line = f.readline()
                if not line:
                    break
                    
                # Extract timestamp (for end_time check)
                if end_time:
                    ts = extract_timestamp(line, custom_regex, custom_format)
                    if ts and ts > end_time:
                        # Found line past the end window
                        break
                        
                out_stream.write(line)
                lines_written += 1
    finally:
        if output_path:
            out_stream.close()
            
    return lines_written

def main():
    parser = argparse.ArgumentParser(
        description="Binary Search Log Slicer: Slices giant log files by date/time using high-speed binary search."
    )
    parser.add_argument("log_file", help="Path to the log file")
    parser.add_argument("-s", "--start", help="Start date/time (e.g. '2026-06-28 12:00:00' or ISO format)")
    parser.add_argument("-e", "--end", help="End date/time (e.g. '2026-06-28 13:00:00' or ISO format)")
    parser.add_argument("-o", "--output", help="Write sliced log output to file instead of stdout")
    parser.add_argument("--regex", help="Custom regex pattern to capture timestamp (must group the timestamp substring)")
    parser.add_argument("--format", help="Custom strptime format string for parsing the captured timestamp")
    
    args = parser.parse_args()
    
    # Parse dates
    start_dt = None
    if args.start:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                start_dt = datetime.strptime(args.start, fmt)
                break
            except ValueError:
                continue
        if start_dt is None:
            try:
                start_dt = datetime.fromisoformat(args.start)
            except ValueError:
                print(f"Error: Could not parse start timestamp '{args.start}'. Try 'YYYY-MM-DD HH:MM:SS'.", file=sys.stderr)
                sys.exit(1)
                
    end_dt = None
    if args.end:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                end_dt = datetime.strptime(args.end, fmt)
                break
            except ValueError:
                continue
        if end_dt is None:
            try:
                end_dt = datetime.fromisoformat(args.end)
            except ValueError:
                print(f"Error: Could not parse end timestamp '{args.end}'. Try 'YYYY-MM-DD HH:MM:SS'.", file=sys.stderr)
                sys.exit(1)
                
    custom_regex = re.compile(args.regex) if args.regex else None
    
    if (args.regex and not args.format) or (args.format and not args.regex):
        print("Error: Both --regex and --format must be provided together for custom parsing.", file=sys.stderr)
        sys.exit(1)
        
    try:
        lines_count = slice_log(
            args.log_file, 
            start_dt, 
            end_dt, 
            custom_regex, 
            args.format, 
            args.output
        )
        if args.output:
            print(f"Successfully sliced {lines_count} lines into '{args.output}'.")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
