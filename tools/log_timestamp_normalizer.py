#!/usr/bin/env python3
"""
Log Timestamp Normalizer - Parse, shift timezone, and normalize various log timestamp formats.
"""

import argparse
import sys
import re
from datetime import datetime, timezone, timedelta
import glob
import os

# Common log timestamp formats and their regex patterns
DATETIME_PATTERNS = [
    # ISO-8601 / RFC-3339: 2026-06-29T14:30:00.123456+05:30 or 2026-06-29 14:30:00,123Z
    (re.compile(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'), 
     lambda m: parse_iso8601(m.group(0))),
    
    # Apache Log format: [29/Jun/2026:14:30:00 +0530]
    (re.compile(r'\[\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\]'), 
     lambda m: datetime.strptime(m.group(0)[1:-1], "%d/%b/%Y:%H:%M:%S %z")),
    
    # Syslog format: Jun 29 14:30:00 (no year, uses current year)
    (re.compile(r'\b[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b'), 
     lambda m: parse_syslog(m.group(0))),
    
    # Unix epoch (seconds/milliseconds): 1772274600 or 1772274600123
    (re.compile(r'\b\d{10}(?:\.\d{1,6})?\b'), 
     lambda m: datetime.fromtimestamp(float(m.group(0)), tz=timezone.utc)),
]

def parse_iso8601(ts_str):
    # Normalize separator
    ts_str = ts_str.replace(' ', 'T')
    # Replace comma milliseconds separator to dot
    ts_str = ts_str.replace(',', '.')
    
    # Python 3.7+ supports fromisoformat, but to support older versions and timezones with ':' we clean it up
    # Remove colon in timezone offset if present (e.g. +05:30 -> +0530)
    if (ts_str.endswith('Z')):
        ts_str = ts_str[:-1] + '+0000'
    else:
        # Check if there is offset at the end like +05:30
        match = re.search(r'([+-]\d{2}):(\d{2})$', ts_str)
        if match:
            ts_str = ts_str[:-6] + match.group(1) + match.group(2)
            
    # Try parsing varying subsecond lengths
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Could not parse ISO-8601: {ts_str}")

def parse_syslog(ts_str):
    # Syslog doesn't contain a year. We assume current year.
    current_year = datetime.now().year
    dt = datetime.strptime(f"{current_year} {ts_str}", "%Y %b %d %H:%M:%S")
    # Syslog is usually local time or UTC. We assume UTC here unless configured otherwise.
    return dt.replace(tzinfo=timezone.utc)

def normalize_line(line, target_format, tz_offset=None):
    """Scan line for timestamps, normalize them, and return updated line"""
    normalized_line = line
    parsed_dt = None
    matched_span = None

    for pattern, parse_fn in DATETIME_PATTERNS:
        match = pattern.search(line)
        if match:
            try:
                dt = parse_fn(match)
                # Shift timezone if needed
                if tz_offset is not None:
                    # tz_offset is in hours
                    dt = dt.astimezone(timezone(timedelta(hours=tz_offset)))
                
                # Format to target
                formatted_ts = dt.strftime(target_format)
                
                # Replace the original timestamp match
                start, end = match.span()
                normalized_line = line[:start] + formatted_ts + line[end:]
                parsed_dt = dt
                matched_span = (start, start + len(formatted_ts))
                break
            except Exception:
                continue
                
    return normalized_line, parsed_dt

def main():
    parser = argparse.ArgumentParser(
        description="Log Timestamp Normalizer - Standardize and merge log files with varying timestamp formats."
    )
    parser.add_argument("files", nargs="+", help="Log files to parse (supports glob patterns)")
    parser.add_argument(
        "-f", "--format", default="%Y-%m-%dT%H:%M:%S.%f%z", 
        help="Target datetime strftime format (default: ISO-8601 with milliseconds and timezone)"
    )
    parser.add_argument(
        "--tz", type=float, help="Timezone shift offset in hours (e.g. 5.5 for IST, 0 for UTC)"
    )
    parser.add_argument(
        "-o", "--output", help="Output file path (default: write to stdout)"
    )
    parser.add_argument(
        "--sort", action="store_true", help="Chronologically sort and merge log lines across all files"
    )
    args = parser.parse_args()

    # Expand glob patterns
    log_files = []
    for file_pattern in args.files:
        expanded = glob.glob(file_pattern)
        if expanded:
            log_files.extend(expanded)
        else:
            print(f"Warning: File pattern '{file_pattern}' did not match any files.", file=sys.stderr)

    if not log_files:
        print("Error: No input files found.", file=sys.stderr)
        sys.exit(1)

    all_log_entries = []

    for file_path in log_files:
        if not os.path.isfile(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    norm_line, dt = normalize_line(line, args.format, args.tz)
                    if args.sort:
                        # If sorting, keep track of date time and original index
                        # Use line index as tie-breaker
                        sort_key = dt or datetime.min.replace(tzinfo=timezone.utc)
                        all_log_entries.append((sort_key, norm_line))
                    else:
                        if args.output:
                            all_log_entries.append((None, norm_line))
                        else:
                            sys.stdout.write(norm_line)
        except Exception as e:
            print(f"Error reading file '{file_path}': {e}", file=sys.stderr)

    if args.sort:
        # Sort log lines by timestamp
        all_log_entries.sort(key=lambda x: x[0])

    if args.output or args.sort:
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as out_f:
                    for _, line in all_log_entries:
                        out_f.write(line)
                print(f"Normalized logs successfully written to '{args.output}'.")
            except Exception as e:
                print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
        else:
            for _, line in all_log_entries:
                sys.stdout.write(line)

if __name__ == "__main__":
    main()
