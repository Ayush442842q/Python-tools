#!/usr/bin/env python3
"""
Log Pattern Extractor
A command-line tool that aggregates and clusters log lines into common templates
by masking dynamic variables (IPs, numbers, timestamps, UUIDs, hex values)
using standard regex rules, helping developers quickly identify major log categories.
"""

import argparse
import sys
import re
import os
from collections import Counter

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

def print_color(text, color):
    """Print text with ANSI color if supported."""
    print(f"{color}{text}{COLOR_RESET}")

# Precompiled regex patterns for substitution
REGEXES = [
    # URLs
    (re.compile(r"https?://[a-zA-Z0-9./?=&_%+-]+"), "<URL>"),
    # Email addresses
    (re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "<EMAIL>"),
    # IP Addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<IP>"),
    # UUIDs
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    # ISO Timestamps (e.g. 2026-06-28T14:04:16+05:30)
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"), "<TIMESTAMP>"),
    # Simple Time (e.g. 14:04:16)
    (re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b"), "<TIME>"),
    # Hexadecimal values
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<HEX>"),
    # Floats / Decimals
    (re.compile(r"\b\d+\.\d+\b"), "<FLOAT>"),
    # Integers
    (re.compile(r"\b\d+\b"), "<INT>"),
    # Paths (POSIX and Windows)
    (re.compile(r"(?:/[a-zA-Z0-9._-]+){2,}"), "<PATH>"),
    (re.compile(r"[a-zA-Z]:(?:\\[a-zA-Z0-9._-]+){2,}"), "<PATH>"),
]

# Common log severity keywords
SEVERITY_PATTERN = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b", re.IGNORECASE)

def mask_variables(line):
    """Mask dynamic values in a log line to generate a generic template."""
    masked = line
    for pattern, placeholder in REGEXES:
        masked = pattern.sub(placeholder, masked)
    
    # Strip excessive white spaces
    masked = re.sub(r"\s+", " ", masked).strip()
    return masked

def extract_severity(line):
    """Attempt to extract severity from a log line."""
    match = SEVERITY_PATTERN.search(line)
    if match:
        return match.group(1).upper()
    return "UNKNOWN"

def process_logs(log_stream, min_occurrences=1, group_by_severity=False):
    """Process lines from log stream and group them into templates."""
    templates = Counter()
    line_count = 0
    severity_counts = Counter()
    template_examples = {}

    for line in log_stream:
        line_count += 1
        line_str = line.strip()
        if not line_str:
            continue
            
        severity = extract_severity(line_str)
        severity_counts[severity] += 1

        template = mask_variables(line_str)
        
        # If grouping by severity, include severity prefix
        if group_by_severity:
            template = f"[{severity}] {template}"

        templates[template] += 1
        
        # Keep the first raw line matching this template as an example
        if template not in template_examples:
            template_examples[template] = line_str

    return line_count, templates, severity_counts, template_examples

def main():
    parser = argparse.ArgumentParser(
        description="Log Pattern Extractor - Aggregates log lines into template clusters.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", nargs="?", help="Log file path (reads from standard input if omitted)")
    parser.add_argument("-n", "--top", type=int, default=15, help="Show top N templates (default: 15)")
    parser.add_argument("-m", "--min", type=int, default=1, help="Filter out patterns with fewer than M occurrences")
    parser.add_argument("-s", "--severity", action="store_true", help="Group and tag templates by severity level")
    parser.add_argument("-e", "--examples", action="store_true", help="Print a raw log line example for each pattern")

    args = parser.parse_args()

    # Determine input source
    if args.file:
        if not os.path.exists(args.file):
            print_color(f"Error: Log file '{args.file}' does not exist.", COLOR_RED)
            return 1
        try:
            with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
                line_count, templates, severity_counts, examples = process_logs(f, args.min, args.severity)
        except Exception as e:
            print_color(f"Error reading file: {e}", COLOR_RED)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[*] Log Pattern Extractor: Reading from standard input (Ctrl+C/Ctrl+D to finish)...")
        line_count, templates, severity_counts, examples = process_logs(sys.stdin, args.min, args.severity)

    if line_count == 0:
        print_color("[-] No log lines processed.", COLOR_YELLOW)
        return 0

    print_color(f"\n[*] Extracted Log Patterns Summary:", COLOR_BOLD + COLOR_BLUE)
    print(f"Total Lines Processed: {line_count}")
    print(f"Unique Templates Found: {len(templates)}")
    
    # Severity breakdown
    if severity_counts:
        print("\nSeverity Breakdown:")
        for sev, count in severity_counts.items():
            pct = (count / line_count) * 100.0
            print(f"  - {sev:<10} : {count:<8} ({pct:.2f}%)")

    # Filter templates by min occurrences
    filtered_templates = {k: v for k, v in templates.items() if v >= args.min}
    sorted_templates = sorted(filtered_templates.items(), key=lambda x: x[1], reverse=True)

    print(f"\n[*] Top {args.top} Patterns (filtering out < {args.min} occurrences):")
    print(f"{COLOR_BOLD}{'RANK':<4} | {'COUNT':<8} | {'PERCENT':<8} | {'TEMPLATE PATTERN'}{COLOR_RESET}")
    print("-" * 100)

    for i, (template, count) in enumerate(sorted_templates[:args.top]):
        pct = (count / line_count) * 100.0
        rank = i + 1
        
        # Color rank based on count/frequency
        color = COLOR_RESET
        if pct > 20:
            color = COLOR_RED
        elif pct > 5:
            color = COLOR_YELLOW
        elif pct > 1:
            color = COLOR_GREEN
            
        print(f"{rank:<4} | {color}{count:<8}{COLOR_RESET} | {color}{pct:>7.2f}%{COLOR_RESET} | {template}")
        if args.examples:
            # Print example of raw log line matching this pattern
            print_color(f"       Example: {examples[template]}", COLOR_CYAN)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[-] Operation aborted by user.")
        sys.exit(1)
