#!/usr/bin/env python3
"""
Directory Tree Printer - Print directory structures in tree format.

This script prints directory structures similar to the 'tree' command.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Set


def print_tree(
    directory: Path,
    prefix: str = '',
    is_last: bool = True,
    max_depth: int = -1,
    current_depth: int = 0,
    show_files: bool = True,
    dirs_only: bool = False,
    ignore_patterns: List[str] = None,
) -> None:
    """
    Recursively print directory tree.
    
    Args:
        directory: Current directory to process
        prefix: Prefix for current line
        is_last: Whether this is the last item at this level
        max_depth: Maximum depth to recurse (-1 for unlimited)
        current_depth: Current depth level
        show_files: Whether to show files
        dirs_only: Only show directories
        ignore_patterns: List of glob patterns to ignore
    """
    if ignore_patterns is None:
        ignore_patterns = []
    
    # Check if we should ignore this path
    for pattern in ignore_patterns:
        if directory.match(pattern):
            return
    
    # Check depth limit
    if max_depth != -1 and current_depth > max_depth:
        return
    
    # Print current directory
    connector = "└── " if is_last else "├── "
    print(prefix + connector + directory.name + "/")
    
    # Prepare prefix for children
    if is_last:
        new_prefix = prefix + "    "
    else:
        new_prefix = prefix + "│   "
    
    try:
        # Get all items
        items = list(directory.iterdir())
        
        # Filter and sort
        filtered_items = []
        for item in items:
            # Skip hidden files/dirs unless specifically allowed
            if item.name.startswith('.') and not show_files:
                continue
            
            # Check ignore patterns
            should_ignore = False
            for pattern in ignore_patterns:
                if item.match(pattern):
                    should_ignore = True
                    break
            if should_ignore:
                continue
            
            # Filter by type
            if dirs_only and not item.is_dir():
                continue
            if not show_files and item.is_file():
                continue
            
            filtered_items.append(item)
        
        # Sort: directories first, then files, both alphabetically
        filtered_items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        
        # Print items
        for i, item in enumerate(filtered_items):
            is_last_item = (i == len(filtered_items) - 1)
            if item.is_dir():
                print_tree(item, new_prefix, is_last_item, max_depth, current_depth + 1, 
                          show_files, dirs_only, ignore_patterns)
            else:
                connector = "└── " if is_last_item else "├── "
                print(new_prefix + connector + item.name)
                
    except (PermissionError, IOError, OSError):
        print(new_prefix + "└── [Permission Denied]")


def main():
    """Main entry point for the directory tree printer."""
    parser = argparse.ArgumentParser(
        description="Print directory structures in tree format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s /home/user/projects
  %(prog)s . -L 2 --dirs-only
  %(prog)s /var/log -I "*.log" --file
        """
    )
    
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to start from (default: current directory)'
    )
    
    parser.add_argument(
        '-L', '--level',
        type=int,
        default=-1,
        help='Max display depth (default: unlimited)'
    )
    
    parser.add_argument(
        '-d', '--dirs-only',
        action='store_true',
        help='List directories only'
    )
    
    parser.add_argument(
        '-f', '--file',
        action='store_true',
        help='List files as well as directories'
    )
    
    parser.add_argument(
        '-I', '--ignore',
        type=str,
        help='Ignore pattern (comma-separated list of glob patterns)'
    )
    
    parser.add_argument(
        '--charset',
        choices=['ascii', 'unicode'],
        default='unicode',
        help='Character set to use for drawing (default: unicode)'
    )
    
    args = parser.parse_args()
    
    directory = Path(args.directory).expanduser().resolve()
    
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    
    # Parse ignore patterns
    ignore_patterns = []
    if args.ignore:
        ignore_patterns = [p.strip() for p in args.ignore.split(',')]
    
    # Set connectors based on charset
    if args.charset == 'ascii':
        # These would be used in the print_tree function if we made it configurable
        pass
    
    print(f"{directory.name}/")
    print_tree(
        directory=directory,
        max_depth=args.level,
        show_files=args.file,
        dirs_only=args.dirs_only,
        ignore_patterns=ignore_patterns,
    )


if __name__ == '__main__':
    main()