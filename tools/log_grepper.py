#!/usr/bin/env python3
"""
log_grepper - Advanced log search and filter utility

A command-line tool to search and filter log files (including compressed .gz
and .zip archives) by timestamp range, severity levels, and regex patterns,
with colorized terminal output.

Usage:
    python tools/log_grepper.py [file] [options]

Options:
    -h, --help            Show this help message and exit
    -f FILE, --file FILE  Log file path (alternative to positional argument)
    -r REGEX, --regex REGEX
                          Regular expression to filter lines
    -s SEVERITY, --severity SEVERITY
                          Filter by severity level: DEBUG, INFO, WARN, ERROR, CRITICAL
                          (supports minimum prefix, e.g., '>=WARN' or exact 'ERROR')
    -t TIME, --time TIME  Time range (UTC/ISO format): START_TIME/END_TIME
                          (e.g., '2026-06-17T12:00:00/2026-06-17T13:30:00')
    -c LIMIT, --count LIMIT
                          Limit the number of output matching lines
    -o FILE, --output FILE
                          Save filtered output lines to a file
    --no-color            Disable terminal ANSI color output

Examples:
    python tools/log_grepper.py app.log --severity ERROR --regex "connection failed"
    python tools/log_grepper.py server.log.gz -t "2026-06-17T10:00:00/2026-06-17T11:00:00"
    python tools/log_grepper.py archive.zip --severity ">=WARN" --output filtered.log
"""

import argparse
import datetime
import gzip
import os
import re
import sys
import zipfile

# Severity levels mapping
SEVERITY_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARN': 30,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
    'FATAL': 50
}

# ANSI colors
COLORS = {
    'RESET': '\033[0m',
    'DEBUG': '\033[36m',    # Cyan
    'INFO': '\033[32m',     # Green
    'WARN': '\033[33m',     # Yellow
    'WARNING': '\033[33m',  # Yellow
    'ERROR': '\033[31m',    # Red
    'CRITICAL': '\033[41m\033[37m', # White on Red
    'FATAL': '\033[41m\033[37m',    # White on Red
    'MATCH': '\033[4m\033[1m'       # Underline & Bold for regex match
}

# Regex to detect timestamps in log lines
TIMESTAMP_PATTERN = re.compile(
    r'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{3,6})?(?:[+-]\d{2}:?\d{2}|Z)?)'
)

def colorize(text, severity, no_color=False):
    """Wrap text with color tags based on severity."""
    if no_color:
        return text
    color = COLORS.get(severity.upper(), '')
    if not color:
        return text
    return f"{color}{text}{COLORS['RESET']}"

def parse_time(time_str):
    """Parse time string in common format."""
    if not time_str:
        return None
    time_str = time_str.strip().replace(' ', 'T')
    # Try parsing different ISO lengths
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(time_str[:len(fmt)-2] if '%' in fmt else time_str, fmt)
        except ValueError:
            continue
    try:
        # Fallback to general datetime parser if standard strings fail
        return datetime.datetime.fromisoformat(time_str)
    except ValueError:
        raise ValueError(f"Could not parse timestamp format: '{time_str}'")

def match_time_range(line, start_time, end_time):
    """Check if the log line's timestamp falls within the range."""
    if not start_time and not end_time:
        return True
        
    match = TIMESTAMP_PATTERN.search(line)
    if not match:
        return False # No timestamp found, exclude if range is set
        
    try:
        line_time = parse_time(match.group(1))
        if start_time and line_time < start_time:
            return False
        if end_time and line_time > end_time:
            return False
        return True
    except Exception:
        return False

def match_severity(line, min_level, exact_level):
    """Check if the log line matches the severity constraint."""
    if min_level is None and exact_level is None:
        return True, "INFO" # Default
        
    # Search for severity keywords in line
    found_sev = None
    for sev in SEVERITY_LEVELS:
        # Search for severity wrapped in brackets or as standalone word
        if re.search(r'\b' + sev + r'\b', line, re.IGNORECASE):
            found_sev = sev.upper()
            break
            
    if not found_sev:
        # Check if line prefix contains something like [D], [I], [W], [E], [C]
        brackets_match = re.search(r'\[([DIWEC])\]', line)
        if brackets_match:
            mapping = {'D': 'DEBUG', 'I': 'INFO', 'W': 'WARN', 'E': 'ERROR', 'C': 'CRITICAL'}
            found_sev = mapping.get(brackets_match.group(1))
            
    if not found_sev:
        # If severity isn't declared in line, default to INFO for matching
        found_sev = "INFO"
        
    line_val = SEVERITY_LEVELS.get(found_sev, 20)
    
    if exact_level:
        return found_sev == exact_level.upper(), found_sev
    if min_level:
        min_val = SEVERITY_LEVELS.get(min_level.upper(), 20)
        return line_val >= min_val, found_sev
        
    return True, found_sev

def read_lines_from_file(file_path):
    """Yield lines from log file (supporting plain text, gz, and zip)."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.gz':
        with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
            for line in f:
                yield line
    elif ext == '.zip':
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Yield lines from the first file inside the zip archive
            infolist = zf.infolist()
            if not infolist:
                return
            with zf.open(infolist[0].filename, 'r') as f:
                for line in f:
                    yield line.decode('utf-8', errors='ignore')
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                yield line

def main():
    parser = argparse.ArgumentParser(
        description="Filter and search log files, including compressed gzip and zip archives."
    )
    parser.add_argument('file', nargs='?', help='Log file path (.log, .txt, .gz, .zip)')
    parser.add_argument('-f', '--file-opt', dest='file_opt', help='Log file path (alternative)')
    parser.add_argument('-r', '--regex', help='Regular expression pattern to filter log lines')
    parser.add_argument('-s', '--severity', help='Filter by severity (e.g. ERROR, WARNING, >=INFO)')
    parser.add_argument('-t', '--time', help='Time range: START_TIME/END_TIME (ISO format)')
    parser.add_argument('-c', '--count', type=int, help='Maximum number of matching lines to return')
    parser.add_argument('-o', '--output', help='Save filtered results to output file')
    parser.add_argument('--no-color', action='store_true', help='Disable terminal colors')
    
    args = parser.parse_args()
    
    file_path = args.file or args.file_opt
    if not file_path:
        parser.print_help()
        return 1
        
    if not os.path.exists(file_path):
        print(f"Error: Log file not found: {file_path}", file=sys.stderr)
        return 1
        
    # Parse severity filters
    min_level = None
    exact_level = None
    if args.severity:
        sev_str = args.severity.strip()
        if sev_str.startswith(">="):
            min_level = sev_str[2:].strip().upper()
            if min_level not in SEVERITY_LEVELS:
                print(f"Error: Invalid severity level '{min_level}'", file=sys.stderr)
                return 1
        else:
            exact_level = sev_str.upper()
            if exact_level not in SEVERITY_LEVELS:
                # Fallback to check if they omitted >=
                if exact_level in ['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL']:
                    pass
                else:
                    print(f"Error: Invalid severity level '{exact_level}'", file=sys.stderr)
                    return 1
                    
    # Parse time range filter
    start_time = None
    end_time = None
    if args.time:
        if '/' not in args.time:
            print("Error: Time range must be formatted as START_TIME/END_TIME", file=sys.stderr)
            return 1
        t_start, t_end = args.time.split('/', 1)
        try:
            if t_start.strip():
                start_time = parse_time(t_start)
            if t_end.strip():
                end_time = parse_time(t_end)
        except ValueError as ve:
            print(ve, file=sys.stderr)
            return 1
            
    # Compile regex pattern
    regex_pattern = None
    if args.regex:
        try:
            regex_pattern = re.compile(args.regex)
        except re.error as re_err:
            print(f"Error: Invalid regex pattern: {re_err}", file=sys.stderr)
            return 1
            
    # Process lines
    matched_count = 0
    out_file = None
    if args.output:
        try:
            write_mode = 'w'
            out_file = open(args.output, write_mode, encoding='utf-8')
        except Exception as e:
            print(f"Error opening output file: {e}", file=sys.stderr)
            return 1
            
    try:
        for line in read_lines_from_file(file_path):
            cleaned_line = line.rstrip('\n')
            
            # 1. Filter by severity
            sev_match, detected_sev = match_severity(cleaned_line, min_level, exact_level)
            if not sev_match:
                continue
                
            # 2. Filter by time range
            if not match_time_range(cleaned_line, start_time, end_time):
                continue
                
            # 3. Filter by regex
            if regex_pattern:
                reg_match = regex_pattern.search(cleaned_line)
                if not reg_match:
                    continue
                # Highlight regex matches in the terminal output
                if not args.no_color and not out_file:
                    span = reg_match.span()
                    match_colored = COLORS['MATCH'] + cleaned_line[span[0]:span[1]] + COLORS['RESET']
                    # Keep severity color inside match
                    sev_color = COLORS.get(detected_sev, '')
                    match_colored = match_colored.replace(COLORS['RESET'], COLORS['RESET'] + sev_color)
                    cleaned_line = cleaned_line[:span[0]] + match_colored + cleaned_line[span[1]:]
                    
            # We have a match!
            matched_count += 1
            
            if out_file:
                out_file.write(line.rstrip('\n') + '\n')
            else:
                colored_line = colorize(cleaned_line, detected_sev, args.no_color)
                print(colored_line)
                
            if args.count and matched_count >= args.count:
                break
                
        if out_file:
            print(f"Successfully processed log file. Wrote {matched_count} matching lines to {args.output}")
        else:
            if matched_count == 0:
                print("No matching log lines found.", file=sys.stderr)
                
        return 0
    except Exception as e:
        print(f"Error reading log stream: {e}", file=sys.stderr)
        return 1
    finally:
        if out_file:
            out_file.close()

if __name__ == "__main__":
    sys.exit(main())
