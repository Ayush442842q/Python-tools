#!/usr/bin/env python3
"""
Directory Syncer - A fast, lightweight one-way directory synchronization tool

This tool synchronizes a target destination directory to match a source directory
one-way. It detects modifications using file size, modification times, and MD5
checksum comparison, copying only new or changed files. Optionally, it can prune
(delete) files in the destination that no longer exist in the source.

Usage:
    python tools/directory_syncer.py SOURCE_DIR DEST_DIR [options]

Options:
    -d, --delete            Delete files in destination that aren't in source
    -c, --checksum          Verify file content changes using MD5 hashes (slower, but safer)
    -n, --dry-run           Show what would be copied or deleted without making changes
    -v, --verbose           Show detailed log of copied and deleted files
    -h, --help              Show this help message and exit

Example:
    python tools/directory_syncer.py /path/to/source /path/to/destination --delete --verbose
"""

import argparse
import hashlib
import os
import shutil
import sys
from typing import Dict, Set, Tuple


def calculate_md5(file_path: str) -> str:
    """Calculate the MD5 hash of a file."""
    hasher = hashlib.md5()
    try:
        # Read in binary mode
        read_mode = "r" + "b"
        with open(file_path, read_mode) as f:
            chunk = f.read(65536)
            while chunk:
                hasher.update(chunk)
                chunk = f.read(65536)
        return hasher.hexdigest()
    except Exception:
        return ""


def get_dir_state(dir_path: str, use_checksum: bool) -> Dict[str, Tuple[int, float, str]]:
    """
    Scans a directory tree and returns a map of:
    relative_path -> (size, mtime, md5_checksum)
    """
    state: Dict[str, Tuple[int, float, str]] = {}
    for root, _, files in os.walk(dir_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, dir_path)
            
            try:
                stat = os.stat(full_path)
                size = stat.st_size
                mtime = stat.st_mtime
                checksum = calculate_md5(full_path) if use_checksum else ""
                state[rel_path] = (size, mtime, checksum)
            except Exception:
                continue
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="One-way directory synchronization utility.")
    parser.add_argument("source", help="Source directory (master)")
    parser.add_argument("destination", help="Destination directory (replica)")
    parser.add_argument("-d", "--delete", action="store_true", help="Delete orphaned files in destination")
    parser.add_argument("-c", "--checksum", action="store_true", help="Compare file hashes (slower)")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    src_dir = os.path.abspath(args.source)
    dst_dir = os.path.abspath(args.destination)
    
    if not os.path.isdir(src_dir):
        print(f"Error: Source directory '{src_dir}' does not exist.", file=sys.stderr)
        return 1
        
    # In dry-run, we might simulate destination creation
    if not os.path.exists(dst_dir):
        if args.dry_run:
            print(f"[Dry-run] Would create destination directory: {dst_dir}")
        else:
            try:
                os.makedirs(dst_dir)
                if args.verbose:
                    print(f"Created destination directory: {dst_dir}")
            except Exception as e:
                print(f"Error creating destination directory: {e}", file=sys.stderr)
                return 1
                
    print(f"Scanning directories...")
    src_state = get_dir_state(src_dir, args.checksum)
    dst_state = get_dir_state(dst_dir, args.checksum)
    
    copied_count = 0
    deleted_count = 0
    skipped_count = 0
    
    # 1. Synchronize files from source to destination
    for rel_path, src_info in src_state.items():
        src_size, src_mtime, src_checksum = src_info
        dst_path = os.path.join(dst_dir, rel_path)
        
        need_copy = False
        reason = ""
        
        if rel_path not in dst_state:
            need_copy = True
            reason = "New file"
        else:
            dst_size, dst_mtime, dst_checksum = dst_state[rel_path]
            
            # Compare sizes
            if src_size != dst_size:
                need_copy = True
                reason = "Size changed"
            # Compare checksums if requested
            elif args.checksum and src_checksum != dst_checksum:
                need_copy = True
                reason = "Checksum mismatch"
            # Fallback to modification time (allow slight float inaccuracy of 0.01s)
            elif not args.checksum and abs(src_mtime - dst_mtime) > 0.01:
                # Only copy if source is newer (prevent older file overwrites)
                if src_mtime > dst_mtime:
                    need_copy = True
                    reason = "Source is newer"
                    
        if need_copy:
            if args.dry_run:
                print(f"[Dry-run] Would copy: {rel_path} ({reason})")
                copied_count += 1
            else:
                try:
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(os.path.join(src_dir, rel_path), dst_path)
                    copied_count += 1
                    if args.verbose:
                        print(f"Copied: {rel_path} ({reason})")
                except Exception as e:
                    print(f"Error copying {rel_path}: {e}", file=sys.stderr)
        else:
            skipped_count += 1
            
    # 2. Prune orphaned files in destination if --delete is set
    if args.delete:
        for rel_path in dst_state:
            if rel_path not in src_state:
                dst_path = os.path.join(dst_dir, rel_path)
                if args.dry_run:
                    print(f"[Dry-run] Would delete: {rel_path}")
                    deleted_count += 1
                else:
                    try:
                        os.remove(dst_path)
                        deleted_count += 1
                        if args.verbose:
                            print(f"Deleted: {rel_path}")
                    except Exception as e:
                        print(f"Error deleting {rel_path}: {e}", file=sys.stderr)
                        
        # Prune empty subdirectories in destination
        if not args.dry_run:
            for root, dirs, _ in os.walk(dst_dir, topdown=False):
                for d in dirs:
                    d_path = os.path.join(root, d)
                    try:
                        if not os.listdir(d_path):
                            os.rmdir(d_path)
                            if args.verbose:
                                print(f"Removed empty directory: {os.path.relpath(d_path, dst_dir)}")
                    except Exception:
                        pass
                        
    # Print summary
    mode_str = " (Dry-run)" if args.dry_run else ""
    print(f"\nSync Summary{mode_str}:")
    print(f"  Files Copied/Updated: {copied_count}")
    print(f"  Files Deleted:        {deleted_count if args.delete else 'N/A (delete not enabled)'}")
    print(f"  Files Unchanged:      {skipped_count}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
