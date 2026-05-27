#!/usr/bin/env python3
"""
Disk Usage Analyzer - Analyze disk space usage.

This script analyzes directory sizes and shows what's taking up space.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import humanize


def get_directory_size(path: Path) -> int:
    """
    Get the size of a directory in bytes.
    
    Args:
        path: Path to directory
        
    Returns:
        Size in bytes
    """
    total_size = 0
    try:
        for item in path.rglob('*'):
            if item.is_file() and not item.is_symlink():
                try:
                    total_size += item.stat().st_size
                except (IOError, OSError):
                    pass
    except (IOError, OSError, PermissionError):
        pass
    return total_size


def analyze_directory(
    directory: Path, 
    min_size: int = 0,
    depth: int = 1,
    show_files: bool = False
) -> List[Tuple[Path, int]]:
    """
    Analyze directory usage.
    
    Args:
        directory: Directory to analyze
        min_size: Minimum size to show (bytes)
        depth: How deep to recurse (0 = only this directory)
        show_files: Whether to show individual files
        
    Returns:
        List of (path, size) tuples sorted by size descending
    """
    results = []
    
    def scan_dir(current_path: Path, current_depth: int):
        try:
            # Get size of this directory
            dir_size = get_directory_size(current_path)
            
            if dir_size >= min_size:
                results.append((current_path, dir_size))
            
            # Recurse if we haven't reached max depth
            if current_depth < depth or depth == -1:
                for item in current_path.iterdir():
                    if item.is_dir() and not item.is_symlink():
                        # Skip hidden directories
                        if not item.name.startswith('.'):
                            scan_dir(item, current_depth + 1)
                        
                    elif show_files and item.is_file() and not item.is_symlink():
                        try:
                            file_size = item.stat().st_size
                            if file_size >= min_size:
                                results.append((item, file_size))
                        except (IOError, OSError):
                            pass
        except (IOError, OSError, PermissionError):
            pass
    
    scan_dir(directory, 0)
    # Sort by size descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def main():
    """Main entry point for the disk usage analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyze disk space usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /home/user
  %(prog)s . --depth 2
  %(prog)s /var/log --min-size 10M
  %(prog)s ~ --show-files --depth 3
        """
    )
    
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to analyze (default: current directory)'
    )
    
    parser.add_argument(
        '--min-size',
        type=str,
        default='0',
        help='Minimum size to show (e.g., 1K, 1M, 1G) (default: 0)'
    )
    
    parser.add_argument(
        '--depth',
        type=int,
        default=1,
        help='Directory depth to analyze (default: 1, -1 for unlimited)'
    )
    
    parser.add_argument(
        '--show-files',
        action='store_true',
        help='Show individual files in addition to directories'
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=20,
        help='Number of results to show (default: 20)'
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
    
    print(f"Analyzing disk usage in: {directory}")
    print(f"Minimum size: {humanize.naturalsize(min_size)}")
    print(f"Depth: {'unlimited' if args.depth == -1 else args.depth}")
    print("-" * 60)
    
    results = analyze_directory(
        directory=directory,
        min_size=min_size,
        depth=args.depth,
        show_files=args.show_files
    )
    
    if not results:
        print("No files or directories found matching criteria.")
        return
    
    # Show results
    print(f"{'Size':>10} {'Path'}")
    print("-" * 60)
    
    for path, size in results[:args.count]:
        try:
            rel_path = path.relative_to(directory)
            display_path = str(rel_path) if str(rel_path) != '.' else '.'
        except ValueError:
            display_path = str(path)
        
        print(f"{humanize.naturalsize(size):>10} {display_path}")
    
    total_scanned = sum(size for _, size in results)
    print("-" * 60)
    print(f"Total scanned: {humanize.naturalsize(total_scanned)}")
    print(f"Shown: {len(results[:args.count])} of {len(results)} items")


if __name__ == '__main__':
    main()