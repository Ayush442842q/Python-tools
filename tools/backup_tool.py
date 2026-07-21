#!/usr/bin/env python3
"""
Backup Utility - Create timestamped backups of files and directories.

This script creates compressed backups with timestamps and can
maintain a rotation of recent backups.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import tarfile
import gzip


def create_backup(
    source: Path,
    backup_dir: Path,
    prefix: str = None,
    compress: bool = True,
    keep_days: int = None,
    keep_count: int = None,
) -> Path:
    """
    Create a backup of a file or directory.
    
    Args:
        source: File or directory to backup
        backup_dir: Directory to store backups
        prefix: Prefix for backup filename (defaults to source name)
        compress: Whether to compress the backup
        keep_days: Number of days of backups to keep
        keep_count: Number of backups to keep
        
    Returns:
        Path to the created backup file
    """
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    if prefix is None:
        prefix = source.name
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if compress:
        backup_name = f"{prefix}_{timestamp}.tar.gz"
        backup_path = backup_dir / backup_name
        
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(source, arcname=os.path.basename(source))
    else:
        backup_name = f"{prefix}_{timestamp}.tar"
        backup_path = backup_dir / backup_name
        
        with tarfile.open(backup_path, "w") as tar:
            tar.add(source, arcname=os.path.basename(source))
    
    # Cleanup old backups if requested
    if keep_days is not None or keep_count is not None:
        cleanup_old_backups(backup_dir, prefix, keep_days, keep_count, compress)
    
    return backup_path


def cleanup_old_backups(
    backup_dir: Path,
    prefix: str,
    keep_days: int = None,
    keep_count: int = None,
    compress: bool = True,
) -> None:
    """
    Remove old backups based on retention policy.
    
    Args:
        backup_dir: Directory containing backups
        prefix: Backup file prefix to match
        keep_days: Number of days to keep
        keep_count: Number of backups to keep
        compress: Whether backups are compressed
    """
    extension = "tar.gz" if compress else "tar"
    pattern = f"{prefix}_*.{extension}"
    
    backup_files = list(backup_dir.glob(pattern))
    
    # Sort by modification time (oldest first)
    backup_files.sort(key=lambda x: x.stat().st_mtime)
    
    # Remove by count
    if keep_count is not None and len(backup_files) > keep_count:
        files_to_remove = backup_files[:-keep_count]
        for file_path in files_to_remove:
            file_path.unlink()
    
    # Remove by age
    if keep_days is not None:
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
        for file_path in backup_files:
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()


def main():
    """Main entry point for the backup utility."""
    parser = argparse.ArgumentParser(
        description="Create timestamped backups of files and directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Documents --backup-dir ~/Backups
  %(prog)s /var/www/myapp -d /backups --keep-days 30
  %(prog)s ~/project -p myapp --keep-count 10 --no-compress
        """
    )
    
    parser.add_argument(
        'source',
        type=str,
        help='File or directory to backup'
    )
    
    parser.add_argument(
        '-d', '--backup-dir',
        type=str,
        default='./backups',
        help='Directory to store backups (default: ./backups)'
    )
    
    parser.add_argument(
        '-p', '--prefix',
        type=str,
        help='Prefix for backup filename (default: source name)'
    )
    
    parser.add_argument(
        '--no-compress',
        action='store_true',
        help='Create uncompressed tar backups'
    )
    
    parser.add_argument(
        '--keep-days',
        type=int,
        help='Number of days of backups to keep'
    )
    
    parser.add_argument(
        '--keep-count',
        type=int,
        help='Number of backups to keep'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List existing backups and exit'
    )
    
    args = parser.parse_args()
    
    source = Path(args.source).expanduser().resolve()
    backup_dir = Path(args.backup_dir).expanduser().resolve()
    
    if args.list:
        if not backup_dir.exists():
            print(f"Backup directory '{backup_dir}' does not exist.")
            return
        
        extension = "tar.gz" if not args.no_compress else "tar"
        prefix = args.prefix if args.prefix else source.name
        pattern = f"{prefix}_*.{extension}"
        
        backups = list(backup_dir.glob(pattern))
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not backups:
            print(f"No backups found matching pattern '{pattern}' in {backup_dir}")
            return
        
        print(f"Backups in {backup_dir}:")
        print("-" * 60)
        for backup in backups:
            stat = backup.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size
            print(f"{mtime.strftime('%Y-%m-%d %H:%M:%S')} {backup.name:>30} {size:>10} bytes")
        return
    
    try:
        print(f"Creating backup of: {source}")
        print(f"Backup directory: {backup_dir}")
        
        backup_path = create_backup(
            source=source,
            backup_dir=backup_dir,
            prefix=args.prefix,
            compress=not args.no_compress,
            keep_days=args.keep_days,
            keep_count=args.keep_count,
        )
        
        size = backup_path.stat().st_size
        print(f"\nBackup created successfully!")
        print(f"Backup file: {backup_path}")
        print(f"Size: {size:,} bytes")
        
        if args.keep_days or args.keep_count:
            print(f"Retention policy applied.")
        
    except Exception as e:
        print(f"Error creating backup: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()