#!/usr/bin/env python3
"""
Secure File Shredder - Securely delete files and directories.

This tool overwrites file contents multiple times with random bytes or zeros
before deleting them, rendering standard file recovery techniques useless.

Usage:
    python tools/file_shredder.py <file_or_dir> [options]
"""

import os
import sys
import argparse
import secrets
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Secure File Shredder - Securely wipe files or directories."
    )
    parser.add_argument(
        "target", help="File or directory to securely delete"
    )
    parser.add_argument(
        "-p", "--passes", type=int, default=3, help="Number of overwrite passes (default: 3)"
    )
    parser.add_argument(
        "-z", "--zero", action="store_true", help="Final pass overwrites with zeros (highly recommended)"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Shred directories recursively"
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Do not prompt for confirmation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate shredding without modifying or deleting files"
    )
    return parser.parse_args()


def confirm_action(target_path: Path, recursive: bool) -> bool:
    target_type = "directory (and all its contents)" if target_path.is_dir() else "file"
    print(f"WARNING: You are about to SECURELY SHRED the {target_type}:")
    print(f"  {target_path.resolve()}")
    print("This operation cannot be undone. Recovering the files will be impossible.")
    
    if target_path.is_dir() and not recursive:
        print("Error: Target is a directory. Use -r or --recursive to shred directories.", file=sys.stderr)
        return False
        
    try:
        response = input("Are you absolutely sure you want to proceed? (yes/no): ").strip().lower()
        return response in ("y", "yes")
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return False


def shred_file(filepath: Path, passes: int, final_zero: bool, dry_run: bool) -> bool:
    try:
        if not filepath.is_file():
            return False
            
        file_size = filepath.stat().st_size
        print(f"Shredding {filepath} ({file_size} bytes)...")
        
        if dry_run:
            print(f"  [Dry Run] Would shred with {passes} passes.")
            return True
            
        # Overwrite file multiple times
        with open(filepath, "ba+", buffering=0) as f:
            for p in range(1, passes + 1):
                f.seek(0)
                # If final pass and --zero option is set, overwrite with zeros.
                # Otherwise, generate cryptographically secure random bytes.
                if p == passes and final_zero:
                    print(f"  Pass {p}/{passes}: Overwriting with zeros...")
                    chunk_size = 65536
                    written = 0
                    while written < file_size:
                        write_len = min(chunk_size, file_size - written)
                        f.write(b"\x00" * write_len)
                        written += write_len
                else:
                    print(f"  Pass {p}/{passes}: Overwriting with random data...")
                    chunk_size = 65536
                    written = 0
                    while written < file_size:
                        write_len = min(chunk_size, file_size - written)
                        f.write(secrets.token_bytes(write_len))
                        written += write_len
                # Flush and sync changes to disk
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # fsync might fail on some platforms or filesystems, continue anyway
                    
        # Rename file to a random string to obscure the original name before deletion
        random_name = secrets.token_hex(8)
        new_path = filepath.parent / random_name
        filepath.rename(new_path)
        
        # Finally, delete the file
        new_path.unlink()
        print(f"✓ Successfully shredded and deleted.")
        return True
        
    except PermissionError:
        print(f"✗ Permission Error: Cannot access '{filepath}'. Run with appropriate permissions.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error shredding '{filepath}': {e}", file=sys.stderr)
        return False


def shred_directory(dirpath: Path, passes: int, final_zero: bool, recursive: bool, dry_run: bool) -> bool:
    if not dirpath.is_dir():
        return False
        
    success = True
    try:
        # Traverse and shred all files
        for entry in os.scandir(dirpath):
            entry_path = Path(entry.path)
            if entry.is_file():
                file_success = shred_file(entry_path, passes, final_zero, dry_run)
                if not file_success:
                    success = False
            elif entry.is_dir():
                if recursive:
                    dir_success = shred_directory(entry_path, passes, final_zero, recursive, dry_run)
                    if not dir_success:
                        success = False
                else:
                    print(f"Skipping subdirectory: {entry_path} (use -r to shred recursively)")
                    success = False
                    
        # Remove the directory itself
        if not dry_run:
            dirpath.rmdir()
            print(f"Deleted directory: {dirpath}")
        else:
            print(f"[Dry Run] Would remove directory: {dirpath}")
            
    except Exception as e:
        print(f"Error shredding directory '{dirpath}': {e}", file=sys.stderr)
        success = False
        
    return success


def main():
    args = parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists():
        print(f"Error: Target '{args.target}' does not exist.", file=sys.stderr)
        return 1
        
    if not args.force and not confirm_action(target_path, args.recursive):
        return 0
        
    if target_path.is_file():
        success = shred_file(target_path, args.passes, args.zero, args.dry_run)
    elif target_path.is_dir():
        success = shred_directory(target_path, args.passes, args.zero, args.recursive, args.dry_run)
    else:
        print("Error: Target is neither a file nor a directory.", file=sys.stderr)
        success = False
        
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
