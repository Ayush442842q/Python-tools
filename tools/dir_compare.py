#!/usr/bin/env python3
"""
Directory Compare - Compare two directories recursively for differences

This tool scans two directories, compares their contents recursively, and reports:
  - Files unique to Directory A
  - Files unique to Directory B
  - Files present in both but modified (differing in size or SHA256 checksum)
  - Files present in both that are identical

Usage:
    python tools/dir_compare.py DIR_A DIR_B [--quick] [--report REPORT_FILE]

Example:
    python tools/dir_compare.py project_v1 project_v2 --report diff_report.txt
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, Set, Tuple, List


def get_file_hash(filepath: Path) -> str:
    """Computes SHA256 checksum of a file in binary chunks."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256.update(byte_block)
        return sha256.hexdigest()
    except Exception as e:
        return f"ERROR:{e}"


def scan_directory(base_dir: Path) -> Dict[str, Tuple[int, float]]:
    """Scans directory and returns relative_path -> (size, mtime)."""
    files_info = {}
    base_dir_resolved = base_dir.resolve()
    
    for root, _, files in os.walk(base_dir_resolved):
        for file in files:
            full_path = Path(root) / file
            try:
                rel_path = full_path.relative_to(base_dir_resolved).as_posix()
                stat = full_path.stat()
                files_info[rel_path] = (stat.st_size, stat.st_mtime)
            except Exception:
                # Ignore files that cannot be read/statted
                continue
    return files_info


def compare_directories(
    dir_a: Path, 
    dir_b: Path, 
    quick: bool = False
) -> Tuple[List[str], List[str], List[Tuple[str, str]], List[str]]:
    """Compares files in both directories. Returns (only_a, only_b, modified, identical)."""
    files_a = scan_directory(dir_a)
    files_b = scan_directory(dir_b)

    only_a: List[str] = []
    only_b: List[str] = []
    modified: List[Tuple[str, str]] = [] # list of (rel_path, reason)
    identical: List[str] = []

    # Get absolute paths to calculate hashes
    dir_a_resolved = dir_a.resolve()
    dir_b_resolved = dir_b.resolve()

    all_rel_paths = set(files_a.keys()).union(set(files_b.keys()))

    for rel_path in sorted(all_rel_paths):
        in_a = rel_path in files_a
        in_b = rel_path in files_b

        if in_a and not in_b:
            only_a.append(rel_path)
        elif in_b and not in_a:
            only_b.append(rel_path)
        else:
            # Present in both
            size_a, mtime_a = files_a[rel_path]
            size_b, mtime_b = files_b[rel_path]
            
            # Fast check
            if size_a != size_b:
                modified.append((rel_path, f"Size difference ({size_a} vs {size_b} bytes)"))
                continue
            
            if quick:
                # Check modification time
                if abs(mtime_a - mtime_b) > 0.01:
                    modified.append((rel_path, f"Timestamp difference"))
                else:
                    identical.append(rel_path)
            else:
                # Content hash check
                hash_a = get_file_hash(dir_a_resolved / rel_path)
                hash_b = get_file_hash(dir_b_resolved / rel_path)
                
                if hash_a.startswith("ERROR:") or hash_b.startswith("ERROR:"):
                    modified.append((rel_path, f"Read error during comparison"))
                elif hash_a != hash_b:
                    modified.append((rel_path, "Content difference (hash mismatch)"))
                else:
                    identical.append(rel_path)

    return only_a, only_b, modified, identical


def format_bytes(size: int) -> str:
    """Formats bytes to human readable sizes."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}" if unit != 'B' else f"{size} B"
        size /= 1024.0
    return f"{size:.2f} PB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two directories recursively.")
    parser.add_argument("dir_a", help="Path to Directory A")
    parser.add_argument("dir_b", help="Path to Directory B")
    parser.add_argument("--quick", action="store_true", help="Perform quick check using size/timestamp instead of full SHA256 hashes")
    parser.add_argument("--report", help="Save detailed comparison report to a text file")
    
    args = parser.parse_args()

    path_a = Path(args.dir_a)
    path_b = Path(args.dir_b)

    if not path_a.is_dir():
        print(f"Error: Directory A '{args.dir_a}' does not exist or is not a directory.", file=sys.stderr)
        return 1
    if not path_b.is_dir():
        print(f"Error: Directory B '{args.dir_b}' does not exist or is not a directory.", file=sys.stderr)
        return 1

    print("=" * 60)
    print(f"Comparing Directories:")
    print(f"  A: {path_a.resolve()}")
    print(f"  B: {path_b.resolve()}")
    print(f"Method: {'Quick check (size/mtime)' if args.quick else 'Deep check (SHA-256 hash)'}")
    print("Scanning...")
    print("=" * 60)

    try:
        only_a, only_b, modified, identical = compare_directories(path_a, path_b, args.quick)
    except Exception as e:
        print(f"Error during comparison: {e}", file=sys.stderr)
        return 1

    # Print Summary Console Output
    print(f"Comparison Summary:")
    print(f"  Identical Files:         {len(identical)}")
    print(f"  Modified Files:          {len(modified)}")
    print(f"  Files only in A:         {len(only_a)}")
    print(f"  Files only in B:         {len(only_b)}")
    print("-" * 60)

    # Detailed report string building
    report_lines = []
    report_lines.append(f"Directory Comparison Report")
    report_lines.append(f"===========================")
    report_lines.append(f"Directory A: {path_a.resolve()}")
    report_lines.append(f"Directory B: {path_b.resolve()}")
    report_lines.append(f"Check Type:  {'Quick (size/mtime)' if args.quick else 'Deep (SHA256)'}")
    report_lines.append(f"\nSummary:")
    report_lines.append(f"  Identical: {len(identical)}")
    report_lines.append(f"  Modified:  {len(modified)}")
    report_lines.append(f"  Only in A: {len(only_a)}")
    report_lines.append(f"  Only in B: {len(only_b)}")

    if modified:
        report_lines.append(f"\nModified Files ({len(modified)}):")
        for rel_path, reason in modified:
            report_lines.append(f"  [MODIFIED] {rel_path} - {reason}")
            
    if only_a:
        report_lines.append(f"\nFiles Only in A ({len(only_a)}):")
        for rel_path in only_a:
            report_lines.append(f"  [ONLY A]   {rel_path}")
            
    if only_b:
        report_lines.append(f"\nFiles Only in B ({len(only_b)}):")
        for rel_path in only_b:
            report_lines.append(f"  [ONLY B]   {rel_path}")

    # Output detailed report to terminal if short enough and no file output specified
    total_diff = len(modified) + len(only_a) + len(only_b)
    if total_diff == 0:
        print("Directories are completely synchronized and identical.")
    else:
        if not args.report:
            # Print a brief preview of differences to stdout
            if modified:
                print("Modified Files:")
                for rel_path, reason in modified[:10]:
                    print(f"  * {rel_path} ({reason})")
                if len(modified) > 10:
                    print(f"  ... and {len(modified)-10} more modified files.")
            if only_a:
                print("\nFiles Only in A:")
                for rel_path in only_a[:10]:
                    print(f"  + {rel_path}")
                if len(only_a) > 10:
                    print(f"  ... and {len(only_a)-10} more files.")
            if only_b:
                print("\nFiles Only in B:")
                for rel_path in only_b[:10]:
                    print(f"  - {rel_path}")
                if len(only_b) > 10:
                    print(f"  ... and {len(only_b)-10} more files.")

    # Write report if requested
    if args.report:
        try:
            with open(args.report, 'w', encoding='utf-8') as f:
                f.write("\n".join(report_lines))
            print(f"\nDetailed report written to: {args.report}")
        except Exception as e:
            print(f"Error saving report file: {e}", file=sys.stderr)
            return 1
            
    print("=" * 60)
    return 0 if total_diff == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
