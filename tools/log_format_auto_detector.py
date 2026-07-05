#!/usr/bin/env python3
"""
Log Format Auto-Detector & Parser Generator

Scans log files, auto-detects line structures (Common Log Format, Combined Log Format,
Syslog, JSON, Key-Value pairs, ISO8601/RFC2822 timestamps, bracketed logs), infers
named regular expressions, and generates executable Python parsing scripts.

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional


TIMESTAMP_PATTERNS = [
    (r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?', 'iso8601', 'timestamp'),
    (r'\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}', 'http_clf', 'timestamp'),
    (r'[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', 'syslog_rfc3164', 'timestamp'),
    (r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', 'standard_date_time', 'timestamp'),
]

IP_PATTERN = (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'ip_address', 'client_ip')
LOG_LEVEL_PATTERN = (r'\b(?:DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b', 'log_level', 'log_level')
HTTP_METHOD_PATTERN = (r'\b(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b', 'http_method', 'method')
HTTP_STATUS_PATTERN = (r'\b[1-5]\d{2}\b', 'http_status', 'status_code')


def detect_json_log(lines: List[str]) -> bool:
    valid_json_count = 0
    for line in lines[:10]:
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                json.loads(line)
                valid_json_count += 1
            except Exception:
                pass
    return valid_json_count >= max(1, min(len(lines), 3))


def detect_kv_log(lines: List[str]) -> bool:
    kv_count = 0
    kv_regex = re.compile(r'\b[a-zA-Z0-9_\.]+=("[^"]*"|\S+)')
    for line in lines[:10]:
        matches = kv_regex.findall(line)
        if len(matches) >= 2:
            kv_count += 1
    return kv_count >= max(1, min(len(lines), 3))


def infer_regex_pattern(sample_lines: List[str]) -> Tuple[str, List[str], Dict[str, str]]:
    if not sample_lines:
        return r'.*', [], {}

    # Check JSON first
    if detect_json_log(sample_lines):
        return r'^\{.*\}$', ['json_data'], {'format': 'JSON'}

    # Use first non-empty sample line as baseline structure template
    sample = ""
    for line in sample_lines:
        if line.strip():
            sample = line.strip()
            break

    if not sample:
        return r'.*', [], {}

    pattern_parts = []
    field_names = []
    field_types = {}
    idx = 0
    length = len(sample)

    token_regex = re.compile(
        r'(' + TIMESTAMP_PATTERNS[0][0] + r'|' + TIMESTAMP_PATTERNS[1][0] + r'|' +
        TIMESTAMP_PATTERNS[2][0] + r'|' + IP_PATTERN[0] + r'|' + LOG_LEVEL_PATTERN[0] + r')'
    )

    pos = 0
    while pos < length:
        match = token_regex.search(sample, pos)
        if not match:
            # Escape remaining literal text
            remaining = sample[pos:]
            pattern_parts.append(re.escape(remaining))
            break

        start, end = match.span()
        if start > pos:
            literal = sample[pos:start]
            pattern_parts.append(re.escape(literal))

        matched_text = match.group(0)
        field_name = f"field_{len(field_names)+1}"
        field_pat = re.escape(matched_text)

        # Classify token
        for ts_pat, ts_name, default_field in TIMESTAMP_PATTERNS:
            if re.fullmatch(ts_pat, matched_text):
                field_name = default_field if default_field not in field_names else f"{default_field}_{len(field_names)}"
                field_pat = ts_pat
                field_types[field_name] = ts_name
                break
        else:
            if re.fullmatch(IP_PATTERN[0], matched_text):
                field_name = "client_ip" if "client_ip" not in field_names else f"ip_{len(field_names)}"
                field_pat = IP_PATTERN[0]
                field_types[field_name] = "IPv4"
            elif re.fullmatch(LOG_LEVEL_PATTERN[0], matched_text):
                field_name = "level"
                field_pat = LOG_LEVEL_PATTERN[0]
                field_types[field_name] = "log_level"

        pattern_parts.append(f"(?P<{field_name}>{field_pat})")
        field_names.append(field_name)
        pos = end

    # Fallback if pattern matched no tokens
    if not field_names:
        full_pattern = r'^(?P<log_message>.*)$'
        field_names = ['log_message']
    else:
        full_pattern = "^" + "".join(pattern_parts) + "$"

    return full_pattern, field_names, field_types


def generate_python_code(regex_pattern: str, is_json: bool, log_filename: str) -> str:
    if is_json:
        return f'''# Auto-generated Log Parser Script for {log_filename}
import json
import sys

def parse_log_line(line):
    line = line.strip()
    if not line:
        return None
    return json.loads(line)

def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "{log_filename}"
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            parsed = parse_log_line(line)
            if parsed:
                print(f"Line {{idx}}: {{parsed}}")

if __name__ == "__main__":
    main()
'''
    else:
        return f'''# Auto-generated Log Parser Script for {log_filename}
import re
import sys
import json

LOG_REGEX = re.compile(r"""{regex_pattern}""")

def parse_log_line(line):
    line = line.strip()
    match = LOG_REGEX.match(line)
    if match:
        return match.groupdict()
    return None

def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "{log_filename}"
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            parsed = parse_log_line(line)
            if parsed:
                print(f"Line {{idx}}: {{json.dumps(parsed)}}")
            else:
                print(f"Line {{idx}} [FAILED MATCH]: {{line.strip()}}")

if __name__ == "__main__":
    main()
'''


def main():
    parser = argparse.ArgumentParser(
        description="Auto-detect log formats, infer named regex capture groups, and generate Python parser scripts."
    )
    parser.add_argument("file", help="Path to sample log file")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of sample lines to analyze (default: 50)")
    parser.add_argument("--export-python", help="Export auto-generated Python parser script to file path")
    parser.add_argument("--json", action="store_true", help="Output detection results as JSON")

    args = parser.parse_args()
    log_path = Path(args.file)

    if not log_path.exists():
        print(f"Error: File '{log_path}' not found.", file=sys.stderr)
        sys.exit(1)

    lines = []
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                lines.append(line.rstrip("\r\n"))
                if len(lines) >= args.sample_size:
                    break

    if not lines:
        print("Log file is empty.", file=sys.stderr)
        sys.exit(1)

    is_json = detect_json_log(lines)
    is_kv = detect_kv_log(lines) if not is_json else False

    regex_pattern, fields, field_types = infer_regex_pattern(lines)

    # Test regex matching rate on sample lines
    matched_count = 0
    compiled_re = None
    if not is_json:
        try:
            compiled_re = re.compile(regex_pattern)
            for line in lines:
                if compiled_re.match(line):
                    matched_count += 1
        except Exception:
            pass
    else:
        matched_count = len(lines)

    match_rate = (matched_count / len(lines)) * 100.0 if lines else 0.0

    detected_format = "JSON Structured Log" if is_json else ("Key-Value Pair Log" if is_kv else "Delimited/Pattern Log")

    results = {
        "file_name": log_path.name,
        "sample_lines_tested": len(lines),
        "detected_format": detected_format,
        "regex_pattern": regex_pattern,
        "match_success_rate": f"{match_rate:.1f}%",
        "extracted_fields": fields,
        "field_types": field_types
    }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"=== Log Format Auto-Detection Report ===")
        print(f"Target File     : {log_path.name}")
        print(f"Detected Format : {detected_format}")
        print(f"Match Precision : {match_rate:.1f}% ({matched_count}/{len(lines)} lines)")
        print(f"Extracted Fields: {', '.join(fields) if fields else 'None'}")
        print(f"\nInferred Named Regex Pattern:\n  {regex_pattern}\n")

        print("Sample Extracted Record:")
        if is_json:
            try:
                print(json.dumps(json.loads(lines[0]), indent=2))
            except Exception:
                print(lines[0])
        elif compiled_re:
            m = compiled_re.match(lines[0])
            if m:
                print(json.dumps(m.groupdict(), indent=2))
            else:
                print("  (Line 1 did not match regex pattern)")

    if args.export_python:
        py_code = generate_python_code(regex_pattern, is_json, log_path.name)
        out_path = Path(args.export_python)
        out_path.write_text(py_code, encoding="utf-8")
        print(f"\nPython parser script successfully written to '{out_path}'.")


if __name__ == "__main__":
    main()
