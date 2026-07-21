#!/usr/bin/env python3
"""
Regex Extractor
Scans files and directories for common patterns (emails, URLs, IPs, phone numbers, dates, UUIDs)
and custom regular expressions, exporting findings to CSV, JSON, or text reports.
"""

import argparse
import csv
import json
import os
import re
import sys

# Standard regular expression patterns
PATTERNS = {
    "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "url": r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/[^\s"\']*)?',
    "ipv4": r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
    "ipv6": r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
    "phone": r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
    "date": r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b',
    "uuid": r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
}

def extract_patterns(file_path, compiled_patterns):
    """
    Extracts all occurrences of patterns in the file.
    Returns a dict mapping pattern_name to list of dicts with match details.
    """
    matches = {name: [] for name in compiled_patterns}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                for name, regex in compiled_patterns.items():
                    for match in regex.finditer(line):
                        match_text = match.group(0).strip()
                        if match_text:
                            matches[name].append({
                                "line": line_num,
                                "match": match_text
                            })
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
    return matches

def main():
    parser = argparse.ArgumentParser(
        description="Extract pattern matches (emails, URLs, IPs, etc.) from files or directories."
    )
    parser.add_argument('path', help='File or directory path to scan')
    parser.add_argument('-p', '--types', nargs='+', choices=list(PATTERNS.keys()) + ['all'], default=['all'],
                        help='Types of patterns to extract (default: all)')
    parser.add_argument('-c', '--custom', help='Custom regex pattern to extract')
    parser.add_argument('-cn', '--custom-name', default='custom', help='Name for custom pattern (default: custom)')
    parser.add_argument('-f', '--format', choices=['text', 'json', 'csv'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('-o', '--output', help='Save output to specified file path')
    parser.add_argument('-r', '--recursive', action='store_true', help='Scan directories recursively')
    parser.add_argument('-u', '--unique', action='store_true', help='Only return unique values per file/type')
    parser.add_argument('-e', '--exclude', nargs='+', help='Glob/string patterns of files to exclude')

    args = parser.parse_args()

    # Determine types of patterns to compile
    types = args.types
    if 'all' in types:
        types = list(PATTERNS.keys())

    compiled_patterns = {}
    for t in types:
        compiled_patterns[t] = re.compile(PATTERNS[t])

    if args.custom:
        try:
            compiled_patterns[args.custom_name] = re.compile(args.custom)
        except re.error as e:
            print(f"Error compiling custom regex: {e}", file=sys.stderr)
            return 1

    # Gather files to scan
    files_to_scan = []
    if os.path.isfile(args.path):
        files_to_scan.append(args.path)
    elif os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            for file in files:
                full_path = os.path.join(root, file)
                
                # Check exclusions
                should_exclude = False
                if args.exclude:
                    for excl in args.exclude:
                        if excl in full_path or re.search(excl.replace('*', '.*'), full_path):
                            should_exclude = True
                            break
                
                if not should_exclude:
                    files_to_scan.append(full_path)
            
            if not args.recursive:
                break
    else:
        print(f"Error: Path '{args.path}' does not exist.", file=sys.stderr)
        return 1

    # Scan files
    results = {}
    for file_path in files_to_scan:
        file_matches = extract_patterns(file_path, compiled_patterns)
        
        # Clean results (remove empty matches)
        cleaned_matches = {}
        for name, items in file_matches.items():
            if items:
                if args.unique:
                    # Filter for unique match texts
                    seen = set()
                    unique_items = []
                    for item in items:
                        if item["match"] not in seen:
                            seen.add(item["match"])
                            unique_items.append(item)
                    items = unique_items
                cleaned_matches[name] = items
        
        if cleaned_matches:
            # Store with relative path if possible for cleaner output
            rel_path = os.path.relpath(file_path, start=os.path.dirname(args.path) or '.')
            results[rel_path] = cleaned_matches

    # Format output
    out_content = ""
    if args.format == 'json':
        out_content = json.dumps(results, indent=2)
    elif args.format == 'csv':
        import io
        csv_out = io.StringIO()
        writer = csv.writer(csv_out)
        writer.writerow(["File", "PatternType", "Line", "MatchValue"])
        for file_path, patterns in results.items():
            for name, items in patterns.items():
                for item in items:
                    writer.writerow([file_path, name, item["line"], item["match"]])
        out_content = csv_out.getvalue()
        csv_out.close()
    else:
        # Standard text format
        lines = []
        for file_path, patterns in results.items():
            lines.append(f"=== File: {file_path} ===")
            for name, items in patterns.items():
                lines.append(f"  [{name.upper()}] ({len(items)} matches):")
                for item in items:
                    lines.append(f"    Line {item['line']}: {item['match']}")
            lines.append("")
        out_content = "\n".join(lines)

    # Output content
    if args.output:
        try:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(out_content + ('\n' if args.format != 'csv' else ''))
            print(f"Successfully exported data to {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            return 1
    else:
        print(out_content)

    return 0

if __name__ == '__main__':
    sys.exit(main())
