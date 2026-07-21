#!/usr/bin/env python3
"""
Archive Searcher - Search for text patterns inside ZIP and TAR archives without extracting

This tool scans through compressed archives (.zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2)
and searches for a query (plain text or regular expression) within all text files in the archive.

Usage:
    python tools/archive_searcher.py ARCHIVE_PATH "SEARCH_QUERY" [options]

Options:
    -r, --regex          Treat query as a regular expression
    -i, --ignore-case    Perform case-insensitive search
    -n, --line-number    Show line numbers of matches
    -l, --files-only     Only list names of files with matches
    --exclude PATTERN    Glob patterns to exclude from search (e.g. "*.png")
    -h, --help           Show this help message and exit

Example:
    python tools/archive_searcher.py logs.zip "ERROR" -n -i
"""

import argparse
import fnmatch
import os
import re
import sys
import tarfile
import zipfile
from typing import List, Pattern, Union, Iterator, Tuple


def is_binary(data: bytes) -> bool:
    """Detect if byte data is binary (contains null bytes or high ratio of non-ascii)."""
    if not data:
        return False
    # If it contains a null byte, it's very likely binary
    if b'\x00' in data:
        return True
    
    # Check proportion of text characters
    text_chars = bytearray(range(32, 127)) + b'\n\r\t\b'
    non_text = sum(1 for byte in data if byte not in text_chars)
    return (non_text / len(data)) > 0.30


def search_content(content_str: str, query_pattern: Pattern, filename: str, args: argparse.Namespace) -> int:
    """Search for matches in a text content string and print them."""
    lines = content_str.splitlines()
    matches_count = 0

    for i, line in enumerate(lines, start=1):
        if query_pattern.search(line):
            matches_count += 1
            if args.files_only:
                print(filename)
                return 1
            
            prefix = f"{filename}:"
            if args.line_number:
                prefix += f"{i}:"
                
            print(f"{prefix} {line}")
            
    return matches_count


def process_zip(archive_path: str, query_pattern: Pattern, args: argparse.Namespace) -> int:
    """Search inside a ZIP archive."""
    total_matches = 0
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            for info in zip_ref.infolist():
                # Skip directories
                if info.is_dir():
                    continue
                
                # Check exclusion patterns
                if args.exclude and any(fnmatch.fnmatch(info.filename, p) for p in args.exclude):
                    continue

                # Read file contents
                try:
                    with zip_ref.open(info) as f:
                        raw_data = f.read(8192)  # Read chunk to check if binary
                        if is_binary(raw_data):
                            continue
                        
                        # Read rest of data if any
                        raw_data += f.read()
                        
                    content = raw_data.decode('utf-8', errors='replace')
                    matches = search_content(content, query_pattern, info.filename, args)
                    total_matches += matches
                    
                    if matches > 0 and args.files_only:
                        continue
                except Exception as e:
                    print(f"Warning: Failed to read {info.filename}: {e}", file=sys.stderr)
    except zipfile.BadZipFile:
        print(f"Error: Invalid or corrupted ZIP file '{archive_path}'", file=sys.stderr)
        return -1
    return total_matches


def process_tar(archive_path: str, query_pattern: Pattern, args: argparse.Namespace) -> int:
    """Search inside a TAR archive."""
    total_matches = 0
    mode = 'r:*'  # Auto-detect compression (gzip, bz2, xz, plain)
    try:
        with tarfile.open(archive_path, mode) as tar_ref:
            for member in tar_ref.getmembers():
                # Only process regular files
                if not member.isfile():
                    continue

                # Check exclusion patterns
                if args.exclude and any(fnmatch.fnmatch(member.name, p) for p in args.exclude):
                    continue

                try:
                    f = tar_ref.extractfile(member)
                    if f is None:
                        continue
                    
                    raw_data = f.read(8192)  # Read header chunk
                    if is_binary(raw_data):
                        continue
                    
                    raw_data += f.read()
                    content = raw_data.decode('utf-8', errors='replace')
                    matches = search_content(content, query_pattern, member.name, args)
                    total_matches += matches
                    
                    if matches > 0 and args.files_only:
                        continue
                except Exception as e:
                    print(f"Warning: Failed to read {member.name}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error opening TAR file '{archive_path}': {e}", file=sys.stderr)
        return -1
    return total_matches


def main():
    parser = argparse.ArgumentParser(description="Search for text inside archives (zip, tar, tgz, tbz2).")
    parser.add_argument("archive", help="Path to the archive file")
    parser.add_argument("query", help="Text or regular expression to search for")
    parser.add_argument("-r", "--regex", action="store_true", help="Interpret query as a regular expression")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Perform case-insensitive search")
    parser.add_argument("-n", "--line-number", action="store_true", help="Show line numbers of matches")
    parser.add_argument("-l", "--files-only", action="store_true", help="Only list filenames containing matches")
    parser.add_argument("--exclude", action="append", help="Exclude files matching glob pattern (can be repeated)")

    args = parser.parse_args()

    if not os.path.exists(args.archive):
        print(f"Error: Archive file not found: {args.archive}", file=sys.stderr)
        return 1

    # Compile the query regex
    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        if args.regex:
            query_pattern = re.compile(args.query, flags)
        else:
            query_pattern = re.compile(re.escape(args.query), flags)
    except re.error as e:
        print(f"Error: Invalid regular expression pattern: {e}", file=sys.stderr)
        return 1

    # Identify archive format
    archive_lower = args.archive.lower()
    is_zip = zipfile.is_zipfile(args.archive) or archive_lower.endswith('.zip')
    is_tar = tarfile.is_tarfile(args.archive) or any(
        archive_lower.endswith(ext) for ext in ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz']
    )

    if is_zip:
        matches = process_zip(args.archive, query_pattern, args)
    elif is_tar:
        matches = process_tar(args.archive, query_pattern, args)
    else:
        print("Error: Unsupported archive format. Must be a ZIP or TAR archive.", file=sys.stderr)
        return 1

    if matches < 0:
        return 1
    
    return 0 if matches > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
