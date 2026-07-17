#!/usr/bin/env python3
"""
Archive Structural Diff Tool

A standalone utility to compare two ZIP or TAR archives.
Natively reads archive structures (using python's built-in `zipfile` and `tarfile`
libraries), extracts file lists, sizes, modification times, and CRC32 checksums,
and reports:
1. Files added (present only in Archive 2).
2. Files deleted (present only in Archive 1).
3. Files modified (size or CRC32 checksum mismatch).
4. Total size differences and compression summaries.

Usage:
    python archive_diff.py package_v1.zip package_v2.zip
"""

import sys
import os
import argparse
import zipfile
import tarfile
from datetime import datetime

def format_bytes(size_bytes):
    """Formats bytes size into human-readable data representation."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_archive_manifest(filepath):
    """
    Decodes the manifest of a ZIP or TAR archive without extracting it.
    Returns:
        manifest: dict of filename -> {size, date, crc/checksum}
        error: str or None
    """
    manifest = {}
    if not os.path.exists(filepath):
        return None, f"File '{filepath}' not found."

    # 1. Handle ZIP files
    if zipfile.is_zipfile(filepath):
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                for info in z.infolist():
                    # Skip directory entries ending with slash
                    if info.filename.endswith('/'):
                        continue
                    manifest[info.filename] = {
                        'size': info.file_size,
                        'date': datetime(*info.date_time).strftime('%Y-%m-%d %H:%M:%S'),
                        'crc': f"{info.CRC:08X}"
                    }
            return manifest, None
        except Exception as e:
            return None, f"Failed parsing ZIP archive: {e}"

    # 2. Handle TAR files
    try:
        with tarfile.open(filepath, 'r') as t:
            for member in t.getmembers():
                if member.isdir():
                    continue
                # Tar file member doesn't have native CRC32, so we use mtime + size as surrogate
                manifest[member.name] = {
                    'size': member.size,
                    'date': datetime.fromtimestamp(member.mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'crc': f"mtime_{member.mtime}"
                }
        return manifest, None
    except Exception as e:
        return None, f"File format not recognized as valid ZIP or TAR archive: {e}"

def diff_archives(arch1, arch2):
    """Compares files in two archive manifests."""
    m1, err1 = get_archive_manifest(arch1)
    if err1:
        print(f"Error reading Archive 1: {err1}", file=sys.stderr)
        return False
        
    m2, err2 = get_archive_manifest(arch2)
    if err2:
        print(f"Error reading Archive 2: {err2}", file=sys.stderr)
        return False

    added = []
    deleted = []
    modified = []
    identical_count = 0
    
    total_size1 = sum(item['size'] for item in m1.values())
    total_size2 = sum(item['size'] for item in m2.values())

    # Find deleted and modified files
    for name, info1 in m1.items():
        if name not in m2:
            deleted.append((name, info1['size']))
        else:
            info2 = m2[name]
            # Check size and CRC/mtime
            if info1['size'] != info2['size'] or info1['crc'] != info2['crc']:
                modified.append((name, info1['size'], info2['size']))
            else:
                identical_count += 1

    # Find added files
    for name, info2 in m2.items():
        if name not in m1:
            added.append((name, info2['size']))

    print("Archive Structural Diff")
    print("=" * 75)
    print(f"Archive 1: {arch1} ({format_bytes(total_size1)} total unpack size)")
    print(f"Archive 2: {arch2} ({format_bytes(total_size2)} total unpack size)")
    print(f"Size Diff: {format_bytes(total_size2 - total_size1)}")
    print("=" * 75)

    # Output deleted files
    if deleted:
        print(f"\n[-] Removed/Deleted Files ({len(deleted)}):")
        print("-" * 75)
        for name, size in sorted(deleted):
            print(f"  - {name:<50} ({format_bytes(size)})")
            
    # Output added files
    if added:
        print(f"\n[+] Added Files ({len(added)}):")
        print("-" * 75)
        for name, size in sorted(added):
            print(f"  + {name:<50} ({format_bytes(size)})")

    # Output modified files
    if modified:
        print(f"\n[*] Modified Files ({len(modified)}):")
        print("-" * 75)
        print(f"  {'Filename':<45} | {'Size (V1)':<12} | {'Size (V2)':<12}")
        print("  " + "-" * 71)
        for name, size1, size2 in sorted(modified):
            print(f"  * {name:<45} | {format_bytes(size1):<12} | {format_bytes(size2):<12}")

    print("\n" + "=" * 75)
    print("DIFF SUMMARY")
    print(f"  Identical Files: {identical_count}")
    print(f"  Modified Files : {len(modified)}")
    print(f"  Added Files    : {len(added)}")
    print(f"  Deleted Files  : {len(deleted)}")
    print("=" * 75)
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Compare files, checksums, and structural listings of two compressed archives.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("archive1", help="Path to the first archive file.")
    parser.add_argument("archive2", help="Path to the second archive file.")
    
    args = parser.parse_args()
    
    success = diff_archives(args.archive1, args.archive2)
    if not success:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
