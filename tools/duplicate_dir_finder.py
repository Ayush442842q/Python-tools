#!/usr/bin/env python3
"""
Duplicate Directory Finder
--------------------------
Recursively scans a directory tree to find identical folders (directories
containing the exact same file contents and structures, even if named differently).

Useful for identifying duplicated vendor directories, cloned assets, or redundant
project backups. Provides file counts, disk space reclaim potential, and details.

Author: Antigravity
License: MIT
"""

import os
import sys
import hashlib
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Set


def get_file_hash(filepath: str, block_size: int = 65536) -> str:
    """Calculate SHA-256 hash of a single file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()
    except (IOError, OSError):
        # Return dummy hash on read failure (e.g., locked files or permissions)
        return "error"


def hash_dir_contents(dir_path: str, file_hashes: Dict[str, Tuple[str, int]], min_size: int = 0) -> Tuple[Optional[str], int, int]:
    """
    Computes a deterministic hash of a directory based on its files and layout.
    Returns: (dir_hash, total_size, total_files)
    """
    items_to_hash = []
    total_size = 0
    total_files = 0
    
    try:
        # Walk directories recursively to capture all files and relative paths
        for root, dirs, files in os.walk(dir_path):
            # Sort to ensure deterministic traversal order
            dirs.sort()
            files.sort()
            
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dir_path)
                
                # Check cache for file hash and size
                if full_path in file_hashes:
                    f_hash, size = file_hashes[full_path]
                else:
                    size = os.path.getsize(full_path)
                    f_hash = get_file_hash(full_path)
                    file_hashes[full_path] = (f_hash, size)
                    
                total_size += size
                total_files += 1
                items_to_hash.append((rel_path, f_hash, size))
    except (OSError, PermissionError) as e:
        print(f"Warning: Skipping directory {dir_path} due to error: {e}", file=sys.stderr)
        return None, 0, 0
        
    if not items_to_hash or total_size < min_size:
        return None, 0, 0
        
    # Sort items by relative path to ensure signature is independent of scanning order
    items_to_hash.sort()
    
    # Hash the aggregated file descriptions
    hasher = hashlib.sha256()
    for rel_path, f_hash, size in items_to_hash:
        hasher.update(rel_path.encode('utf-8'))
        hasher.update(f_hash.encode('utf-8'))
        hasher.update(str(size).encode('utf-8'))
        
    return hasher.hexdigest(), total_size, total_files


def find_duplicate_dirs(search_path: str, min_size: int = 0, ignore_empty: bool = True) -> Dict[str, List[Tuple[str, int, int]]]:
    """
    Scan directories recursively and group them by content signature.
    Returns: Dict mapping directory_signature -> List of (dir_path, size, file_count)
    """
    file_hashes: Dict[str, Tuple[str, int]] = {}
    dir_signatures = defaultdict(list)
    
    # Find all unique directory paths in tree
    all_dirs = []
    print("Collecting directory list...")
    for root, dirs, _ in os.walk(search_path):
        for d in dirs:
            all_dirs.append(os.path.join(root, d))
            
    total_dirs = len(all_dirs)
    print(f"Found {total_dirs} directories to analyze. Scanning signatures...")
    
    for idx, d_path in enumerate(all_dirs, 1):
        if idx % 100 == 0 or idx == total_dirs:
            # Simple CLI progress feedback
            sys.stdout.write(f"\rProgress: {idx}/{total_dirs} directories scanned...")
            sys.stdout.flush()
            
        d_hash, size, file_count = hash_dir_contents(d_path, file_hashes, min_size)
        if d_hash:
            if ignore_empty and file_count == 0:
                continue
            dir_signatures[d_hash].append((d_path, size, file_count))
            
    print("\nScan completed. Consolidating duplicate directories...")
    
    # Filter out entries that have only one directory (no duplicates)
    duplicates = {sig: paths for sig, paths in dir_signatures.items() if len(paths) > 1}
    return duplicates


def format_bytes(n: int) -> str:
    """Format bytes into human-readable representation."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PB"


def main():
    parser = argparse.ArgumentParser(
        description="Scan directory tree to find identical folders and potential reclaimed space."
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory to search (default: current)")
    parser.add_argument("--min-size", type=str, default="0",
                        help="Minimum directory size to match (e.g. 100KB, 5MB, 10GB). Default is 0.")
    parser.add_argument("--keep-empty", action="store_true", help="Include empty directories in results")
    parser.add_argument("--prune-script", help="Save a script containing recommended cleanup commands to file")

    args = parser.parse_args()

    # Parse human-readable min-size option
    min_size_bytes = 0
    size_match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)?$", args.min_size.upper().strip())
    if size_match:
        val = float(size_match.group(1))
        unit = size_match.group(2)
        multiplier = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4,
            None: 1
        }[unit]
        min_size_bytes = int(val * multiplier)
    else:
        print(f"Warning: Invalid --min-size format: '{args.min_size}'. Defaulting to 0.", file=sys.stderr)

    search_path = os.path.abspath(args.path)
    if not os.path.exists(search_path):
        print(f"Error: Path does not exist: {search_path}", file=sys.stderr)
        return 1

    duplicates = find_duplicate_dirs(search_path, min_size=min_size_bytes, ignore_empty=not args.keep_empty)

    if not duplicates:
        print("No duplicate directories found matching constraints.")
        return 0

    print(f"\nFound {len(duplicates)} sets of duplicate directories:")
    print("=" * 80)

    total_space_wasted = 0
    cleanup_actions = []

    # Sort groups by directory size (descending)
    sorted_groups = sorted(duplicates.items(), key=lambda x: x[1][0][1], reverse=True)

    for idx, (sig, dir_list) in enumerate(sorted_groups, 1):
        # Sort directories inside group by length of path (shortest path becomes the "original" master)
        sorted_dirs = sorted(dir_list, key=lambda x: len(x[0]))
        master_path, size, file_count = sorted_dirs[0]
        duplicates_only = sorted_dirs[1:]
        
        group_wasted = size * len(duplicates_only)
        total_space_wasted += group_wasted
        
        print(f"Set #{idx} | Size: {format_bytes(size)} | Files: {file_count} | Redundancy wasted: {format_bytes(group_wasted)}")
        print(f"  [ORIGINAL] {master_path}")
        for dup_path, _, _ in duplicates_only:
            print(f"  [DUPLICATE] {dup_path}")
            # Add prune shell command suggestion
            cleanup_actions.append((dup_path, master_path))
        print("-" * 80)

    print(f"Total potential reclaimed space: {ANSI.BOLD if IS_WINDOWS else ''}{format_bytes(total_space_wasted)}{ANSI.RESET if not IS_WINDOWS else ''}")

    if args.prune_script:
        try:
            with open(args.prune_script, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n# Recommended cleanup script for duplicate directories\n\n")
                for dup, master in cleanup_actions:
                    f.write(f"# Duplicate of: {master}\n")
                    f.write(f'# rm -rf "{dup}"\n\n')
            print(f"Recommended cleanup actions saved to {args.prune_script}")
        except Exception as e:
            print(f"Failed to save cleanup script: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
