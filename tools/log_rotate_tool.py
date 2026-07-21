#!/usr/bin/env python3
"""
Log Rotate Tool
A utility to manage, rotate, compress, and purge log files.
Supports size-based thresholds, retention limits, and ZIP compression.
"""

import sys
import os
import shutil
import zipfile
import argparse
from datetime import datetime

def parse_size(size_str):
    """Parse size string (e.g., '10M', '500K', '1024') into bytes."""
    size_str = size_str.upper().strip()
    if size_str.endswith('G'):
        return int(float(size_str[:-1]) * 1024 * 1024 * 1024)
    elif size_str.endswith('M'):
        return int(float(size_str[:-1]) * 1024 * 1024)
    elif size_str.endswith('K'):
        return int(float(size_str[:-1]) * 1024)
    elif size_str.isdigit():
        return int(size_str)
    else:
        raise ValueError(f"Invalid size format: {size_str}. Use e.g. 10M, 500K, or bytes count.")

def compress_file(file_path, dry_run=False):
    """Compress a file into a zip archive and delete the original."""
    zip_path = file_path + ".zip"
    if dry_run:
        print(f"[Dry Run] Would compress '{file_path}' into '{zip_path}' and delete the original.")
        return zip_path
        
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        os.remove(file_path)
        print(f"Compressed: '{file_path}' -> '{zip_path}'")
        return zip_path
    except Exception as e:
        print(f"Error compressing '{file_path}': {e}", file=sys.stderr)
        return None

def rotate_log(log_path, max_backups=5, compress=False, force=False, max_size=None, dry_run=False):
    """Rotate the log file if criteria are met."""
    if not os.path.exists(log_path):
        print(f"Error: Log file '{log_path}' does not exist.", file=sys.stderr)
        return False
        
    file_size = os.path.getsize(log_path)
    
    if max_size and file_size < max_size and not force:
        print(f"Log file '{log_path}' ({file_size} bytes) is below rotation threshold ({max_size} bytes). Skipping.")
        return True

    print(f"Rotating log file '{log_path}' ({file_size} bytes)...")
    
    # 1. Remove the oldest backup if it exceeds max_backups
    # Backup files can be log_path.N or log_path.N.zip
    # We shift backups: log_path.1 -> log_path.2, etc.
    # So we find existing backups up to max_backups
    for i in range(max_backups - 1, -1, -1):
        for ext in ['', '.zip']:
            old_name = f"{log_path}.{i}{ext}" if i > 0 else f"{log_path}{ext}"
            new_name = f"{log_path}.{i+1}{ext}"
            
            if i == 0:
                # Special handle for active log file (which is log_path itself)
                continue
                
            if os.path.exists(old_name):
                if i + 1 > max_backups:
                    if dry_run:
                        print(f"[Dry Run] Would delete expired backup '{old_name}'")
                    else:
                        os.remove(old_name)
                        print(f"Deleted expired backup: '{old_name}'")
                else:
                    if dry_run:
                        print(f"[Dry Run] Would rename '{old_name}' -> '{new_name}'")
                    else:
                        if os.path.exists(new_name):
                            os.remove(new_name)
                        os.rename(old_name, new_name)
                        print(f"Shifted backup: '{old_name}' -> '{new_name}'")

    # 2. Rename the active log file to log_path.1
    backup_1 = f"{log_path}.1"
    if dry_run:
        print(f"[Dry Run] Would rename '{log_path}' -> '{backup_1}'")
        print(f"[Dry Run] Would recreate empty file '{log_path}'")
    else:
        if os.path.exists(backup_1):
            os.remove(backup_1)
        # Check zip backup 1
        backup_1_zip = backup_1 + ".zip"
        if os.path.exists(backup_1_zip):
            os.remove(backup_1_zip)
            
        shutil.copy2(log_path, backup_1)
        
        # Recreate active log as empty file
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"# Log rotated on {datetime.now().isoformat()}\n")
            
        print(f"Rotated active log to '{backup_1}' and cleared active log.")
        
        # 3. Compress if required
        if compress:
            compress_file(backup_1, dry_run=False)
            
    print("Log rotation completed successfully.")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Log Rotate Tool - Managed rotation, compression, and pruning of log files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("log_file", help="Path to the log file to rotate")
    parser.add_argument("--size", "-s", help="Rotation size threshold (e.g. 10M, 500K, 2048, default: always rotate)")
    parser.add_argument("--backups", "-b", type=int, default=5, help="Maximum number of backups to keep (default: 5)")
    parser.add_argument("--compress", "-c", action="store_true", help="Compress rotated backups into ZIP format")
    parser.add_argument("--force", "-f", action="store_true", help="Force rotation even if size threshold is not met")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Show actions that would be performed without modifying files")
    
    args = parser.parse_args()
    
    max_size = None
    if args.size:
        try:
            max_size = parse_size(args.size)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
    success = rotate_log(
        log_path=args.log_file,
        max_backups=args.backups,
        compress=args.compress,
        force=args.force,
        max_size=max_size,
        dry_run=args.dry_run
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
