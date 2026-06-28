#!/usr/bin/env python3
"""
SQLite Backup Tool

A command-line utility to perform safe, online backups of SQLite databases.
Utilizes the official SQLite backup API to copy database contents without locking
or blocking concurrent writers. Supports timestamped files and automatic rotation.

Usage:
    python tools/sqlite_backup_tool.py path/to/database.db path/to/backup_dir/ [--keep 5]
"""

import argparse
import sys
import os
import sqlite3
import glob
from datetime import datetime

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def format_size(bytes_size):
    """Formats file size to readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def rotate_backups(backup_dir, db_basename, keep_count):
    """
    Finds existing backups matching the base name and prunes older ones,
    keeping only the latest `keep_count` backups.
    """
    # Pattern to match timestamped backups
    pattern = os.path.join(backup_dir, f"{db_basename}_backup_*.db")
    backups = glob.glob(pattern)
    
    # Sort backups by creation/modification time (oldest first)
    backups.sort(key=os.path.getmtime)
    
    if len(backups) > keep_count:
        to_remove = len(backups) - keep_count
        print(f"Rotating backups: keeping last {keep_count}, pruning {to_remove} older backup(s)...")
        for i in range(to_remove):
            try:
                os.remove(backups[i])
                print(f"  - Pruned old backup: {COLORS['yellow']}{os.path.basename(backups[i])}{COLORS['reset']}")
            except Exception as e:
                print(f"  - {COLORS['red']}Error pruning {backups[i]}: {e}{COLORS['reset']}", file=sys.stderr)
    else:
        print(f"Rotation: {len(backups)} backups exist, no pruning needed.")

def main():
    parser = argparse.ArgumentParser(description="Perform online, lock-free backups of a SQLite database.")
    parser.add_argument("db_path", help="Path to the source SQLite database file")
    parser.add_argument("backup_dir", help="Directory path to save the backup file")
    parser.add_argument("-k", "--keep", type=int, default=5, help="Number of latest backups to keep (default: 5)")
    parser.add_argument("--no-color", action="store_true", help="Disable console colors")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    db_path = os.path.abspath(args.db_path)
    backup_dir = os.path.abspath(args.backup_dir)
    
    # 1. Validation
    if not os.path.exists(db_path):
        print(f"{COLORS['red']}Error: Source database file '{db_path}' does not exist.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception as e:
        print(f"{COLORS['red']}Error creating backup directory: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    # Generate timestamped backup name
    db_filename = os.path.basename(db_path)
    db_basename, _ = os.path.splitext(db_filename)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_filename = f"{db_basename}_backup_{timestamp}.db"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    print(f"Source Database: {COLORS['cyan']}{db_path}{COLORS['reset']}")
    print(f"Backup Target:   {COLORS['cyan']}{backup_filepath}{COLORS['reset']}")
    
    # 2. Perform SQLite online backup
    src_conn = None
    dst_conn = None
    try:
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(backup_filepath)
        
        print("Backing up database pages...")
        # Use connection.backup API (safe online backup)
        with dst_conn:
            src_conn.backup(dst_conn)
            
        print(f"{COLORS['green']}Backup completed successfully!{COLORS['reset']}")
        
        # Print file statistics
        file_size = os.path.getsize(backup_filepath)
        print(f"Backup File Size: {COLORS['bold']}{format_size(file_size)}{COLORS['reset']}")
        
    except sqlite3.Error as se:
        print(f"{COLORS['red']}SQLite Backup Error: {se}{COLORS['reset']}", file=sys.stderr)
        if os.path.exists(backup_filepath):
            try:
                os.remove(backup_filepath)
            except Exception:
                pass
        sys.exit(1)
    except Exception as e:
        print(f"{COLORS['red']}Backup Error: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
    finally:
        if src_conn:
            src_conn.close()
        if dst_conn:
            dst_conn.close()
            
    # 3. Handle rotation
    rotate_backups(backup_dir, db_basename, args.keep)

if __name__ == "__main__":
    main()
