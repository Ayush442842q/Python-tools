#!/usr/bin/env python3
"""
File Organizer - Automatically organize files in a directory by type.

This script scans a directory and moves files into categorized subdirectories
based on their file extensions. It helps keep downloads folders, desktops, 
and other directories tidy.

Usage:
    python file_organizer.py /path/to/directory [--dry-run] [--verbose]

Features:
    - Organizes files by category (images, documents, videos, etc.)
    - Creates category folders automatically
    - Dry-run mode to preview changes
    - Verbose output for detailed logging
    - Handles files without extensions
    - Skips already organized files
    - Preserves original filenames
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

# Define file categories and their extensions
FILE_CATEGORIES: Dict[str, List[str]] = {
    'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.ico', '.raw'],
    'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.pages', '.tex', '.md', '.csv', 
                  '.xls', '.xlsx', '.ppt', '.pptx', '.ods', '.odp'],
    'Videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', 
               '.3gp', '.ts', '.vob'],
    'Audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.aiff', '.alac', '.mid', '.midi'],
    'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso', '.dmg', '.cab', '.apk'],
    'Code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', 
             '.rs', '.swift', '.kt', '.scala', '.pl', '.sh', '.bash', '.zsh', '.fish', '.sql', 
             '.xml', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'],
    'Executables': ['.exe', '.msi', '.deb', '.rpm', '.dmg', '.app', '.bin', '.run'],
    'Fonts': ['.ttf', '.otf', '.woff', '.woff2', '.eot', '.pfb', '.pfm'],
}

def get_category(extension: str) -> str:
    """
    Determine the category for a given file extension.
    
    Args:
        extension: File extension (including the dot, e.g., '.jpg')
        
    Returns:
        Category name or 'Others' if not found
    """
    extension = extension.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category
    return 'Others'

def organize_directory(directory: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[int, int]:
    """
    Organize files in the specified directory.
    
    Args:
        directory: Path to directory to organize
        dry_run: If True, only show what would be done without making changes
        verbose: If True, print detailed information
        
    Returns:
        Tuple of (files_processed, files_moved)
    """
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist.")
        return 0, 0
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.")
        return 0, 0
    
    files_processed = 0
    files_moved = 0
    
    # Get all files in the directory (not recursive)
    items = list(directory.iterdir())
    files = [item for item in items if item.is_file()]
    
    if verbose:
        print(f"Found {len(files)} files to process in '{directory}'")
    
    for file_path in files:
        files_processed += 1
        
        # Skip hidden files and the script itself
        if file_path.name.startswith('.') or file_path.name == 'file_organizer.py':
            if verbose:
                print(f"Skipping: {file_path.name}")
            continue
        
        # Get file extension
        extension = file_path.suffix
        if not extension:
            # No extension - put in 'No Extension' category
            category = 'No Extension'
        else:
            category = get_category(extension)
        
        # Create target directory
        target_dir = directory / category
        if not dry_run:
            target_dir.mkdir(exist_ok=True)
        
        # Determine target file path
        target_file = target_dir / file_path.name
        
        # Handle filename conflicts
        counter = 1
        original_target = target_file
        while target_file.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            target_file = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        if verbose or dry_run:
            action = "[DRY RUN] Would move" if dry_run else "Moving"
            print(f"{action}: {file_path.name} → {category}/")
            if target_file != original_target:
                print(f"  (renamed to avoid conflict: {target_file.name})")
        
        # Perform the move (if not dry run)
        if not dry_run:
            try:
                shutil.move(str(file_path), str(target_file))
                files_moved += 1
            except Exception as e:
                print(f"Error moving {file_path.name}: {e}")
    
    return files_processed, files_moved

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'directory',
        type=str,
        help='Directory to organize'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    directory = Path(args.directory).expanduser().resolve()
    
    print(f"Organizing files in: {directory}")
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
    print("-" * 50)
    
    files_processed, files_moved = organize_directory(directory, args.dry_run, args.verbose)
    
    print("-" * 50)
    print(f"Summary:")
    print(f"  Files processed: {files_processed}")
    if args.dry_run:
        print(f"  Files that would be moved: {files_moved}")
    else:
        print(f"  Files moved: {files_moved}")
    
    if args.dry_run and files_moved > 0:
        print("\nTo actually perform the organization, run without --dry-run")

if __name__ == '__main__':
    main()