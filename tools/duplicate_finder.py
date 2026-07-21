#!/usr/bin/env python3
"""
Duplicate File Finder - Find duplicate files in a directory tree.

This script scans directories and finds files with identical content
using file hashing to identify duplicates.
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List, Tuple


def get_file_hash(filepath: Path, block_size: int = 65536) -> str:
    """
    Calculate MD5 hash of a file.
    
    Args:
        filepath: Path to the file
        block_size: Size of blocks to read at a time
        
    Returns:
        Hexadecimal hash string
    """
    file_hash = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                file_hash.update(block)
    except (IOError, OSError):
        return ""
    return file_hash.hexdigest()


def find_duplicates(directory: Path, min_size: int = 0) -> Dict[str, List[Path]]:
    """
    Find duplicate files in a directory.
    
    Args:
        directory: Directory to scan
        min_size: Minimum file size to consider (in bytes)
        
    Returns:
        Dictionary mapping hash to list of file paths with that hash
    """
    # First group by file size (quick filter)
    size_map: Dict[int, List[Path]] = {}
    
    for file_path in directory.rglob('*'):
        if file_path.is_file() and not file_path.is_symlink():
            try:
                file_size = file_path.stat().st_size
                if file_size >= min_size:
                    if file_size not in size_map:
                        size_map[file_size] = []
                    size_map[file_size].append(file_path)
            except (IOError, OSError):
                continue
    
    # Then check hashes for files with same size
    duplicates: Dict[str, List[Path]] = {}
    
    for size, files in size_map.items():
        if len(files) < 2:
            continue  # No duplicates possible
            
        # Group by hash for this size
        hash_map: Dict[str, List[Path]] = {}
        for file_path in files:
            file_hash = get_file_hash(file_path)
            if file_hash:  # Skip if hash failed
                if file_hash not in hash_map:
                    hash_map[file_hash] = []
                hash_map[file_hash].append(file_path)
        
        # Add to duplicates if more than one file has same hash
        for file_hash, file_list in hash_map.items():
            if len(file_list) > 1:
                duplicates[file_hash] = file_list
    
    return duplicates


def format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"


def main():
    """Main entry point for the duplicate file finder."""
    parser = argparse.ArgumentParser(
        description="Find duplicate files in a directory tree",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/directory
  %(prog)s ~/Documents --min-size 1MB
  %(prog)s /var/log --delete-duplicates
        """
    )
    
    parser.add_argument(
        'directory',
        type=str,
        help='Directory to scan for duplicates'
    )
    
    parser.add_argument(
        '--min-size',
        type=str,
        default='0',
        help='Minimum file size to consider (e.g., 1K, 1M, 1G) (default: 0)'
    )
    
    parser.add_argument(
        '--delete-duplicates',
        action='store_true',
        help='Delete duplicate files (keeps first one)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Parse min-size
    size_units = {'B': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    min_size_str = args.min_size.upper()
    min_size = 0
    
    if min_size_str[-1] in size_units:
        try:
            num = float(min_size_str[:-1])
            unit = min_size_str[-1]
            min_size = int(num * size_units[unit])
        except ValueError:
            pass
    else:
        try:
            min_size = int(min_size_str)
        except ValueError:
            min_size = 0
    
    directory = Path(args.directory).expanduser().resolve()
    
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Scanning for duplicates in: {directory}")
    if min_size > 0:
        print(f"Minimum file size: {format_size(min_size)}")
    print("-" * 50)
    
    duplicates = find_duplicates(directory, min_size)
    
    if not duplicates:
        print("No duplicate files found.")
        return
    
    total_duplicates = sum(len(files) - 1 for files in duplicates.values())
    total_wasted = sum(
        (len(files) - 1) * files[0].stat().st_size 
        for files in duplicates.values()
    )
    
    print(f"Found {len(duplicates)} groups of duplicate files")
    print(f"Total duplicate files: {total_duplicates}")
    print(f"Space wasted: {format_size(total_wasted)}")
    print("-" * 50)
    
    for i, (file_hash, files) in enumerate(duplicates.items(), 1):
        file_size = files[0].stat().st_size
        print(f"\nGroup {i} (Size: {format_size(file_size)}, Hash: {file_hash[:8]}...):")
        
        for j, file_path in enumerate(files):
            try:
                mtime = file_path.stat().st_mtime
                from datetime import datetime
                mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            except (IOError, OSError):
                mod_time = "unknown"
                
            marker = " (KEEP)" if j == 0 else ""
            print(f"  {j+1}. {file_path}")
            print(f"     Modified: {mod_time}")
            
            if args.delete_duplicates and j > 0:  # Don't delete the first one
                if args.dry_run:
                    print(f"     [DRY RUN] Would delete: {file_path}")
                else:
                    try:
                        file_path.unlink()
                        print(f"     [DELETED] {file_path}")
                    except (IOError, OSError) as e:
                        print(f"     [ERROR] Could not delete: {e}")
    
    if args.delete_duplicates and not args.dry_run:
        print("\n" + "="*50)
        print("Duplicate file cleanup completed!")
    elif args.delete_duplicates and args.dry_run:
        print("\n" + "="*50)
        print("This was a dry run. To actually delete duplicates, run without --dry-run")


if __name__ == '__main__':
    main()