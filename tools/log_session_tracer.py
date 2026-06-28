#!/usr/bin/env python3
"""
Log Session Tracer

Traces specific session IDs, IP addresses, user IDs, or request IDs across one or more log files.
Extracts matching entries, auto-detects timestamps to sort them chronologically, and provides
context windowing (lines before and after matches).

Usage:
    python tools/log_session_tracer.py -i app.log -t "session_id_123"
    python tools/log_session_tracer.py -i logs/*.log -t "192.168.1.100" -B 2 -A 2
    cat app.log | python tools/log_session_tracer.py -t "req-987" --json
"""

import argparse
from datetime import datetime
import glob
import json
import os
import re
import sys

# Common timestamp regular expressions and parsing formats
TIMESTAMP_PATTERNS = [
    # ISO 8601 / RFC 3339: 2026-06-28T14:45:36.123Z or 2026-06-28 14:45:36,123
    (re.compile(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'), 
     lambda s: datetime.fromisoformat(s.replace('Z', '+00:00').replace(',', '.').replace(' ', 'T'))),
     
    # Apache/Nginx: 28/Jun/2026:14:45:36 +0530
    (re.compile(r'\[\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\]'),
     lambda s: datetime.strptime(s.strip('[]'), '%d/%b/%Y:%H:%M:%S %z')),
     
    # Syslog: Jun 28 14:45:36 (using current year since syslog usually doesn't have year)
    (re.compile(r'\b[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b'),
     lambda s: datetime.strptime(f"{datetime.now().year} {s}", '%Y %b %d %H:%M:%S')),
     
    # Simple timestamp: YYYY-MM-DD HH:MM:SS
    (re.compile(r'\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\b'),
     lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S')),
]

def extract_timestamp(log_line):
    """
    Attempts to extract and parse a datetime object from a log line.
    Returns (datetime_obj, raw_timestamp_str) or (None, None).
    """
    for pattern, parser in TIMESTAMP_PATTERNS:
        match = pattern.search(log_line)
        if match:
            raw_str = match.group(0)
            try:
                dt = parser(raw_str)
                return dt, raw_str
            except Exception:
                pass
    return None, None

def trace_session(log_sources, tracer_tokens, use_regex=False, before_context=0, after_context=0):
    """
    Scans log sources and returns a list of traces.
    Traces contain: {file, line_num, content, timestamp, dt}
    """
    compiled_tokens = []
    if use_regex:
        for t in tracer_tokens:
            try:
                compiled_tokens.append(re.compile(t))
            except re.error as e:
                print(f"[ERROR] Invalid regex token '{t}': {e}", file=sys.stderr)
                sys.exit(1)

    matched_events = []
    
    for source_name, lines in log_sources.items():
        total_lines = len(lines)
        for idx, line in enumerate(lines):
            # Check for token match
            matched = False
            if use_regex:
                for r in compiled_tokens:
                    if r.search(line):
                        matched = True
                        break
            else:
                for t in tracer_tokens:
                    if t in line:
                        matched = True
                        break
            
            if matched:
                # Extract context window
                start = max(0, idx - before_context)
                end = min(total_lines, idx + after_context + 1)
                
                context_lines = []
                for context_idx in range(start, end):
                    context_line = lines[context_idx].rstrip('\r\n')
                    is_target = (context_idx == idx)
                    context_lines.append({
                        "line_num": context_idx + 1,
                        "content": context_line,
                        "is_target": is_target
                    })
                
                dt, raw_ts = extract_timestamp(line)
                
                matched_events.append({
                    "file": source_name,
                    "line_num": idx + 1,
                    "content": line.rstrip('\r\n'),
                    "timestamp": raw_ts,
                    "dt": dt or datetime.min, # Fallback to min datetime for sorting if no ts found
                    "context": context_lines
                })
                
    # Sort chronologically by detected datetime, then by file and line number
    matched_events.sort(key=lambda e: (e["dt"], e["file"], e["line_num"]))
    return matched_events

def main():
    parser = argparse.ArgumentParser(
        description="Log Session Tracer - Trace specific sessions, request IDs, or IPs chronologically across log files."
    )
    parser.add_argument(
        '-i', '--input',
        nargs='*',
        help='Input log file paths. Supports glob patterns (e.g. "logs/*.log"). If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-t', '--token',
        required=True,
        nargs='+',
        help='One or more search tokens (e.g., session IDs, IP addresses, request IDs) to trace.'
    )
    parser.add_argument(
        '-r', '--regex',
        action='store_true',
        help='Treat search tokens as regular expressions.'
    )
    parser.add_argument(
        '-B', '--before-context',
        type=int,
        default=0,
        help='Print NUM lines of leading context before each matching line.'
    )
    parser.add_argument(
        '-A', '--after-context',
        type=int,
        default=0,
        help='Print NUM lines of trailing context after each matching line.'
    )
    parser.add_argument(
        '-C', '--context',
        type=int,
        default=0,
        help='Print NUM lines of context before and after each matching line. Overrides -B and -A.'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in structured JSON format.'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for log files (default: utf-8)'
    )

    args = parser.parse_args()

    # Determine context window sizes
    before = args.context if args.context > 0 else args.before_context
    after = args.context if args.context > 0 else args.after_context

    log_sources = {}

    # Load inputs
    if args.input:
        expanded_paths = []
        for pattern in args.input:
            matches = glob.glob(pattern)
            if matches:
                expanded_paths.extend(matches)
            else:
                # If glob doesn't match anything, add original pattern so it fails gracefully later
                expanded_paths.append(pattern)
                
        for path in expanded_paths:
            if not os.path.exists(path):
                print(f"[WARNING] File '{path}' does not exist, skipping.", file=sys.stderr)
                continue
            try:
                with open(path, 'r', encoding=args.encoding, errors='replace') as f:
                    log_sources[os.path.basename(path)] = f.readlines()
            except Exception as e:
                print(f"[ERROR] Failed to read log file '{path}': {e}", file=sys.stderr)
                return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for log input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            log_sources["stdin"] = sys.stdin.readlines()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not log_sources:
        print("[ERROR] No valid log sources loaded.", file=sys.stderr)
        return 1

    # Perform trace
    events = trace_session(
        log_sources, 
        args.token, 
        use_regex=args.regex, 
        before_context=before, 
        after_context=after
    )

    if args.json:
        # Output structured JSON (excluding the datetime object which is not JSON serializable)
        json_events = []
        for e in events:
            je = e.copy()
            del je["dt"]
            json_events.append(je)
        print(json.dumps(json_events, indent=2))
    else:
        # Text output formatting
        if not events:
            print(f"No log entries found tracing token(s): {', '.join(args.token)}")
            return 0
            
        print(f"=== TRACE REPORT FOR TOKEN(S): {', '.join(args.token)} ({len(events)} matches, sorted chronologically) ===")
        print("=" * 100)
        
        for idx, event in enumerate(events):
            source_info = f"[{event['file']}:{event['line_num']}]"
            ts_info = f" ({event['timestamp']})" if event['timestamp'] else ""
            print(f"\nMatch #{idx+1} {source_info}{ts_info}:")
            print("-" * 80)
            
            # Print context lines
            for ctx in event["context"]:
                marker = ">>> " if ctx["is_target"] else "    "
                print(f"{marker}{ctx['line_num']:04d}: {ctx['content']}")
            print("-" * 80)
            
        print("\n=== END OF TRACE ===")

    return 0

if __name__ == '__main__':
    sys.exit(main())
