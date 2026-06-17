#!/usr/bin/env python3
"""
Secure File Shredder - Securely delete files and folders to prevent data recovery

This tool overwrites target files multiple times with random bytes and/or zero
patterns before removing them from the filesystem. It helps ensure that deleted
sensitive data cannot be easily recovered using file recovery software.

Usage:
    python tools/file_shredder.py PATH [options]

Options:
    -p, --passes N          Number of overwrite passes (default: 3)
    -z, --zero              Add a final pass of zeroes (default: True)
    -r, --recursive         Shred directories recursively
    -v, --verbose           Print verbose processing information
    -f, --force             Do not ask for confirmation before shredding
    -h, --help              Show this help message and exit

Example:
    python tools/file_shredder.py sensitive.txt -p 7 -v
"""

import argparse
import os
import random
import sys
from typing import List


def shred_file(file_path: str, passes: int, zero_final: bool, verbose: bool) -> bool:
    """Overwrites and deletes a single file securely."""
    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        return False
        
    try:
        file_size = os.path.getsize(file_path)
        if verbose:
            print(f"Shredding '{file_path}' ({file_size} bytes)...")
            
        # Overwrite passes
        # We open file in read/write binary mode to modify it in-place
        rw_mode = "r+" + "b"
        with open(file_path, rw_mode) as f:
            for p in range(1, passes + 1):
                if verbose:
                    print(f"  Pass {p}/{passes} (Random data)...")
                f.seek(0)
                # Write in chunks to handle large files efficiently
                remaining = file_size
                chunk_size = 65536
                while remaining > 0:
                    current_chunk = min(remaining, chunk_size)
                    random_bytes = bytearray(random.getrandbits(8) for _ in range(current_chunk))
                    f.write(random_bytes)
                    remaining -= current_chunk
                # Force flush to disk
                f.flush()
                os.fsync(f.fileno())
                
            # Final zero pass if requested
            if zero_final:
                if verbose:
                    print("  Final Pass (Zeroes)...")
                f.seek(0)
                remaining = file_size
                zero_chunk = b'\x00' * min(file_size, chunk_size)
                while remaining > 0:
                    current_chunk = min(remaining, chunk_size)
                    if len(zero_chunk) != current_chunk:
                        zero_chunk = b'\x00' * current_chunk
                    f.write(zero_chunk)
                    remaining -= current_chunk
                f.flush()
                os.fsync(f.fileno())
                
        # Rename file to obscure the original filename before deleting
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        obscured_name = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(len(base_name)))
        obscured_path = os.path.join(dir_name, obscured_name)
        
        try:
            os.rename(file_path, obscured_path)
            delete_path = obscured_path
        except Exception:
            # If renaming fails (e.g. permission or lock), delete the original directly
            delete_path = file_path
            
        os.remove(delete_path)
        if verbose:
            print(f"Successfully shredded and removed '{file_path}'.")
        return True
        
    except Exception as e:
        print(f"Error shredding '{file_path}': {e}", file=sys.stderr)
        return False


def shred_directory(dir_path: str, passes: int, zero_final: bool, recursive: bool, verbose: bool) -> bool:
    """Shreds files in a directory, optionally recursive."""
    if not os.path.isdir(dir_path):
        print(f"Error: '{dir_path}' is not a directory.", file=sys.stderr)
        return False
        
    success = True
    try:
        for root, dirs, files in os.walk(dir_path, topdown=False):
            if not recursive and root != dir_path:
                continue
                
            # Shred all files in current level
            for name in files:
                filepath = os.path.join(root, name)
                success &= shred_file(filepath, passes, zero_final, verbose)
                
            # Remove subdirectories
            for name in dirs:
                if recursive:
                    sub_dir_path = os.path.join(root, name)
                    try:
                        os.rmdir(sub_dir_path)
                        if verbose:
                            print(f"Removed directory '{sub_dir_path}'.")
                    except Exception as err:
                        print(f"Error removing directory '{sub_dir_path}': {err}", file=sys.stderr)
                        success = False
                        
        # Remove parent directory itself
        try:
            os.rmdir(dir_path)
            if verbose:
                print(f"Removed parent directory '{dir_path}'.")
        except Exception as err:
            print(f"Error removing parent directory '{dir_path}': {err}", file=sys.stderr)
            success = False
            
        return success
    except Exception as e:
        print(f"Error walking directory '{dir_path}': {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Secure file shredding utility.")
    parser.add_argument("path", help="Path to file or directory to shred")
    parser.add_argument("-p", "--passes", type=int, default=3, help="Number of overwrite passes")
    parser.add_argument("-z", "--zero", action="store_true", default=True, help="Add a final pass of zeroes")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively shred directories")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details of progress")
    parser.add_argument("-f", "--force", action="store_true", help="Do not prompt for confirmation")
    
    args = parser.parse_args()
    
    target_path = args.path
    if not os.path.exists(target_path):
        print(f"Error: Path '{target_path}' does not exist.", file=sys.stderr)
        return 1
        
    # Ask for confirmation if not forced
    if not args.force:
        target_type = "directory" if os.path.isdir(target_path) else "file"
        prompt = f"Are you absolutely sure you want to securely SHRED and delete this {target_type}? This operation CANNOT BE UNDONE. (y/N): "
        response = input(prompt)
        if response.lower() not in ('y', 'yes'):
            print("Operation cancelled.")
            return 0
            
    if os.path.isdir(target_path):
        if not args.recursive and not args.force:
            print(f"Warning: '{target_path}' is a directory. Use --recursive to shred folders.", file=sys.stderr)
            return 1
        success = shred_directory(target_path, args.passes, args.zero, args.recursive, args.verbose)
    else:
        success = shred_file(target_path, args.passes, args.zero, args.verbose)
        
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
