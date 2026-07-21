#!/usr/bin/env python3
"""
Duplicate File Linker - Scan for duplicate files and consolidate them using hard links, symlinks, or deletion.
"""

import os
import sys
import hashlib
import argparse
from collections import defaultdict
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def get_human_size(size_bytes):
    """Convert bytes to human-readable size string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_fast_hash(filepath):
    """Calculate hash of the first 1024 bytes of a file for quick comparison."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None

def get_full_hash(filepath):
    """Calculate SHA256 hash of the entire file."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None

def scan_for_duplicates(directory, min_size=0):
    """Find duplicates using hierarchical filtering: Size -> Quick Hash -> Full Hash."""
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    c_blue = get_color('blue')

    print(f"Scanning directory: {c_blue}{directory}{c_reset}")
    print("Step 1: Grouping files by size...")
    
    size_groups = defaultdict(list)
    file_count = 0
    
    for root, _, files in os.walk(directory):
        for name in files:
            filepath = os.path.join(root, name)
            try:
                # Resolve symlinks to avoid self-comparison
                if os.path.islink(filepath):
                    continue
                stat = os.stat(filepath)
                size = stat.st_size
                if size >= min_size:
                    size_groups[size].append(filepath)
                    file_count += 1
            except (OSError, PermissionError):
                continue

    print(f"  Processed {file_count} candidate files. Found {len([g for g in size_groups.values() if len(g) > 1])} size groups with potential duplicates.")

    # Filter out sizes with only 1 file
    potential_dup_sizes = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    
    print("Step 2: Performing quick partial hash comparison...")
    quick_hash_groups = defaultdict(list)
    for size, paths in potential_dup_sizes.items():
        for path in paths:
            h = get_fast_hash(path)
            if h:
                # Key is (size, fast_hash)
                quick_hash_groups[(size, h)].append(path)

    # Filter out quick hashes with only 1 file
    potential_dup_quick = {key: paths for key, paths in quick_hash_groups.items() if len(paths) > 1}

    print("Step 3: Verifying full hashes of candidates...")
    duplicates = defaultdict(list)
    for (size, _), paths in potential_dup_quick.items():
        for path in paths:
            h = get_full_hash(path)
            if h:
                # Key is (size, full_hash)
                duplicates[(size, h)].append(path)

    # Final cleanup: keep only groups with more than 1 duplicate
    final_duplicates = {key: paths for key, paths in duplicates.items() if len(paths) > 1}
    return final_duplicates

def consolidate_duplicates(duplicates_dict, mode, interactive=False, dry_run=False):
    """Consolidate duplicates using hard links, symlinks, or deletion."""
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    total_saved_space = 0
    group_idx = 1
    
    consolidated_count = 0
    errors_count = 0

    for (size, file_hash), paths in duplicates_dict.items():
        # Source/Original file is the first one in the list
        source = paths[0]
        dups = paths[1:]
        saved_for_group = size * len(dups)
        total_saved_space += saved_for_group

        print(f"\n[{group_idx}] Duplicate Group - Hash: {file_hash[:16]}... | Size: {get_human_size(size)}")
        print(f"  {c_green}[ORIGINAL]{c_reset} {source}")
        for d in dups:
            print(f"  {c_yellow}[DUPLICATE]{c_reset} {d}")

        group_idx += 1

        if dry_run:
            continue

        if interactive:
            confirm = input(f"Consolidate this group using {mode}? (y/N): ")
            if confirm.lower() != 'y':
                print("Skipped group.")
                continue

        for dup in dups:
            try:
                # Mode logic
                if mode == 'delete':
                    print(f"  Deleting {dup}...")
                    os.remove(dup)
                elif mode == 'hardlink':
                    # Check if hard link can be created.
                    # Hard links require removing the old file first.
                    temp_dup = dup + ".tmp_link"
                    os.rename(dup, temp_dup)
                    try:
                        os.link(source, dup)
                        os.remove(temp_dup)
                        print(f"  {c_green}[OK] Hardlinked{c_reset} {dup} -> {source}")
                        consolidated_count += 1
                    except Exception as link_err:
                        # Restore file if link fails (e.g. cross-volume link)
                        os.rename(temp_dup, dup)
                        raise link_err
                elif mode == 'symlink':
                    temp_dup = dup + ".tmp_link"
                    os.rename(dup, temp_dup)
                    try:
                        # Use absolute or relative pathing? Absolute is safer.
                        os.symlink(os.path.abspath(source), dup)
                        os.remove(temp_dup)
                        print(f"  {c_green}[OK] Symlinked{c_reset} {dup} -> {source}")
                        consolidated_count += 1
                    except Exception as sym_err:
                        os.rename(temp_dup, dup)
                        raise sym_err
            except Exception as e:
                print(f"  {c_red}[FAIL] Failed to process {dup}: {str(e)}{c_reset}")
                errors_count += 1

    print("\n" + "=" * 60)
    if dry_run:
        print(f"{c_bold}Dry Run Summary:{c_reset}")
        print(f"  Total duplicate groups found: {len(duplicates_dict)}")
        print(f"  Potential disk space savings: {c_green}{get_human_size(total_saved_space)}{c_reset}")
    else:
        print(f"{c_bold}Consolidation Summary:{c_reset}")
        print(f"  Action mode:         {mode}")
        print(f"  Successful links/dels: {consolidated_count}")
        print(f"  Failed operations:     {errors_count}")
        print(f"  Disk space reclaimed:  {c_green}{get_human_size(total_saved_space)}{c_reset}")

def main():
    parser = argparse.ArgumentParser(description="Duplicate File Linker - Safely find duplicate files and merge them via hard links or symlinks to reclaim disk space.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-m", "--mode", choices=['hardlink', 'symlink', 'delete'], default='hardlink',
                        help="Action to perform on duplicate files (default: hardlink)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Ask for confirmation before consolidating each group")
    parser.add_argument("-f", "--force", action="store_true", help="Run without dry-run (Caution: will modify files!)")
    parser.add_argument("-s", "--min-size", type=int, default=1, help="Minimum file size to evaluate in bytes (default: 1)")

    args = parser.parse_args()

    scan_dir = os.path.abspath(args.directory)
    if not os.path.isdir(scan_dir):
        print(f"{get_color('red')}Error: '{scan_dir}' is not a valid directory.{get_color('reset')}")
        sys.exit(1)

    duplicates = scan_for_duplicates(scan_dir, args.min_size)

    if not duplicates:
        print(f"\n{get_color('green')}No duplicate files found under these settings.{get_color('reset')}")
        return

    print(f"\nFound {get_color('bold')}{len(duplicates)}{get_color('reset')} duplicate groups.")

    dry_run = not args.force
    if dry_run:
        print(f"\n{get_color('yellow')}*** Running in DRY-RUN mode. No files will be modified. ***{get_color('reset')}")
        print("To apply changes, add the '--force' flag.")

    consolidate_duplicates(duplicates, args.mode, args.interactive, dry_run)

if __name__ == "__main__":
    main()
