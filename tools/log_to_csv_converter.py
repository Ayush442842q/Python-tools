#!/usr/bin/env python3
"""
Log-to-CSV Converter
A standalone utility that auto-detects raw log format schemas (CLF, Combined, Syslog, custom)
and converts log files recursively or individually into clean, structured CSV or JSON outputs.
"""

import argparse
import csv
import gzip
import json
import os
import re
import sys

# Built-in standard regex patterns for common logs
PATTERNS = {
    "Nginx/Apache Combined": {
        "regex": re.compile(
            r'^(?P<ip>\S+)\s+(?P<ident>\S+)\s+(?P<authuser>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+'
            r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+(?P<status>\d{3})\s+'
            r'(?P<bytes>\S+)\s+"(?P<referrer>[^"]*)"\s+"(?P<useragent>[^"]*)"'
        ),
        "headers": ["ip", "ident", "authuser", "timestamp", "method", "path", "protocol", "status", "bytes", "referrer", "useragent"]
    },
    "Nginx/Apache Common (CLF)": {
        "regex": re.compile(
            r'^(?P<ip>\S+)\s+(?P<ident>\S+)\s+(?P<authuser>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+'
            r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)'
        ),
        "headers": ["ip", "ident", "authuser", "timestamp", "method", "path", "protocol", "status", "bytes"]
    },
    "RFC 3164 Syslog": {
        "regex": re.compile(
            r'^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<process>[^:\[]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.*)$'
        ),
        "headers": ["timestamp", "host", "process", "pid", "message"]
    },
    "RFC 5424 Syslog": {
        "regex": re.compile(
            r'^<(?P<pri>\d+)>(?P<version>\d+)\s+(?P<timestamp>\S+)\s+(?P<host>\S+)\s+(?P<appname>\S+)\s+(?P<procid>\S+)\s+(?P<msgid>\S+)\s+(?P<structured_data>\[[^\]]+\]|-)\s+(?P<message>.*)$'
        ),
        "headers": ["pri", "version", "timestamp", "host", "appname", "procid", "msgid", "structured_data", "message"]
    },
    "Log4j/Logback Standard": {
        "regex": re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d{3})\s+\[(?P<thread>[^\]]+)\]\s+(?P<level>[A-Z]+)\s+(?P<logger>\S+)\s+-\s+(?P<message>.*)$'
        ),
        "headers": ["timestamp", "thread", "level", "logger", "message"]
    },
    "Simple Log Pattern": {
        "regex": re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(?P<level>[A-Z]+)\]\s+(?P<message>.*)$'
        ),
        "headers": ["timestamp", "level", "message"]
    }
}


def open_log_file(filepath):
    """Opens plain text or gzipped log files transparently."""
    if filepath.endswith('.gz'):
        return gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
    return open(filepath, 'r', encoding='utf-8', errors='ignore')


def detect_format(filepath, sample_lines=100):
    """Scans the first N lines of a file to check which pattern fits best."""
    try:
        with open_log_file(filepath) as f:
            lines = [f.readline() for _ in range(sample_lines)]
            lines = [l.strip() for l in lines if l.strip()]
    except Exception as e:
        print(f"Error reading sample lines from {filepath}: {e}", file=sys.stderr)
        return None, None

    if not lines:
        return None, None

    best_pattern_name = None
    best_match_count = 0

    for name, pattern_info in PATTERNS.items():
        rx = pattern_info["regex"]
        match_count = sum(1 for line in lines if rx.match(line))
        if match_count > best_match_count:
            best_match_count = match_count
            best_pattern_name = name

    # If at least 20% of lines matched, use it
    if best_match_count >= (len(lines) * 0.2):
        return best_pattern_name, PATTERNS[best_pattern_name]
    
    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Convert raw, unstructured log files into CSV or JSON files."
    )
    parser.add_argument("log_file", help="Path to the log file (supports plain text or .gz).")
    parser.add_argument("-o", "--output", help="Output file path. Defaults to same name with .csv extension.")
    parser.add_argument("-f", "--format", choices=list(PATTERNS.keys()), help="Explicitly set input log format.")
    parser.add_argument("-r", "--regex", help="Custom regex pattern with named groups for custom log styles.")
    parser.add_argument("--json", action="store_true", help="Output JSON format instead of CSV.")
    parser.add_argument("--delimiter", default=",", help="CSV field delimiter. Default: comma (,).")
    parser.add_argument("--skip-invalid", action="store_true", help="Silently discard lines that do not match the format schema.")

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: Log file '{args.log_file}' not found.", file=sys.stderr)
        return 1

    pattern_name = args.format
    pattern_info = None

    if args.regex:
        try:
            custom_rx = re.compile(args.regex)
            # Find group names from custom regex
            group_names = list(custom_rx.groupindex.keys())
            if not group_names:
                # If no named groups, use positional index headers
                group_names = [f"field_{i+1}" for i in range(custom_rx.groups)]
            pattern_info = {"regex": custom_rx, "headers": group_names}
            pattern_name = "Custom User Regex"
        except re.error as e:
            print(f"Error: Invalid custom regex pattern: {e}", file=sys.stderr)
            return 1
    elif args.format:
        pattern_info = PATTERNS[args.format]
    else:
        print("Attempting to auto-detect log schema format...")
        detected_name, detected_info = detect_format(args.log_file)
        if detected_name:
            pattern_name = detected_name
            pattern_info = detected_info
            print(f"Auto-detected format: [ {pattern_name} ]")
        else:
            print("Could not auto-detect log format. Please specify format manually with --format or --regex.", file=sys.stderr)
            return 1

    # Define output filename
    if not args.output:
        base, _ = os.path.splitext(args.log_file)
        ext = ".json" if args.json else ".csv"
        args.output = base + ext

    # Initialize counters
    matched_lines = 0
    skipped_lines = 0
    total_lines = 0

    rx = pattern_info["regex"]
    headers = pattern_info["headers"]

    # Write output
    try:
        with open_log_file(args.log_file) as infile:
            if args.json:
                out_file = open(args.output, 'w', encoding='utf-8')
                # We'll write JSON array
                out_file.write("[\n")
            else:
                out_file = open(args.output, 'w', encoding='utf-8', newline='')
                csv_writer = csv.writer(out_file, delimiter=args.delimiter)
                # Write header row
                header_row = headers.copy()
                if not args.skip_invalid:
                    header_row.append("unparsed_raw_line")
                csv_writer.writerow(header_row)

            first_json_item = True

            for line_idx, line in enumerate(infile, 1):
                total_lines = line_idx
                line_str = line.rstrip('\r\n')
                match = rx.match(line_str)

                if match:
                    matched_lines += 1
                    # Extract matched groups
                    data_dict = match.groupdict()
                    # Fallback for positional groups if named groups aren't fully matching headers
                    if not data_dict:
                        data_dict = {headers[i]: match.group(i+1) for i in range(min(len(headers), len(match.groups())))}

                    if args.json:
                        if not first_json_item:
                            out_file.write(",\n")
                        json.dump(data_dict, out_file, indent=2)
                        first_json_item = False
                    else:
                        row = [data_dict.get(h, "") for h in headers]
                        if not args.skip_invalid:
                            row.append("") # Empty raw line since it parsed successfully
                        csv_writer.writerow(row)
                else:
                    skipped_lines += 1
                    if not args.skip_invalid:
                        if args.json:
                            # Put raw line inside a JSON block
                            data_dict = {"unparsed_raw_line": line_str}
                            if not first_json_item:
                                out_file.write(",\n")
                            json.dump(data_dict, out_file, indent=2)
                            first_json_item = False
                        else:
                            row = [""] * len(headers)
                            row.append(line_str)
                            csv_writer.writerow(row)

            # Close files
            if args.json:
                out_file.write("\n]\n")
            out_file.close()

    except Exception as e:
        print(f"Error processing conversion: {e}", file=sys.stderr)
        return 1

    print(f"\nProcessing Complete:")
    print(f"  - Total processed lines: {total_lines}")
    print(f"  - Successfully matched/parsed: {matched_lines} ({matched_lines/total_lines*100:.1f}%)")
    print(f"  - Unparsed lines: {skipped_lines} ({skipped_lines/total_lines*100:.1f}%)")
    print(f"  - Structured data saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
