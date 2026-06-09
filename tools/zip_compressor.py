#!/usr/bin/env python3
"""
Zip Compressor and Extractor
A command-line tool for compressing files and folders into ZIP archives,
extracting ZIP files, and listing ZIP contents.
"""

import argparse
import os
import sys
import zipfile

def get_compression_method():
    try:
        import zlib
        return zipfile.ZIP_DEFLATED
    except ImportError:
        print("[WARNING] zlib module not found. Archive will be created with ZIP_STORED (no compression).")
        return zipfile.ZIP_STORED

def compress(source_path, output_zip, verbose=False):
    if not os.path.exists(source_path):
        print(f"[ERROR] Source path '{source_path}' does not exist.")
        sys.exit(1)

    # Resolve output name if not provided
    if not output_zip:
        base = os.path.basename(os.path.normpath(source_path))
        output_zip = f"{base}.zip"

    method = get_compression_method()

    print(f"[*] Compressing '{source_path}' into '{output_zip}'...")
    try:
        with zipfile.ZipFile(output_zip, 'w', method) as zip_file:
            if os.path.isfile(source_path):
                arcname = os.path.basename(source_path)
                zip_file.write(source_path, arcname)
                if verbose:
                    print(f"  Added: {source_path} as {arcname}")
            elif os.path.isdir(source_path):
                # We want the folder name itself to be the top-level directory in the zip
                top_dir = os.path.basename(os.path.normpath(source_path))
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        filepath = os.path.join(root, file)
                        # Determine relative path from parent of source_path
                        relpath = os.path.relpath(filepath, start=os.path.dirname(os.path.normpath(source_path)))
                        zip_file.write(filepath, relpath)
                        if verbose:
                            print(f"  Added: {filepath} as {relpath}")
        print(f"[PASS] Successfully created zip archive: '{output_zip}'")
    except Exception as e:
        print(f"[ERROR] Failed to compress: {e}")
        sys.exit(1)

def extract(zip_path, output_dir, verbose=False):
    if not os.path.exists(zip_path):
        print(f"[ERROR] ZIP file '{zip_path}' does not exist.")
        sys.exit(1)
    if not zipfile.is_zipfile(zip_path):
        print(f"[ERROR] '{zip_path}' is not a valid ZIP archive.")
        sys.exit(1)

    # Resolve destination folder
    if not output_dir:
        # Default to a folder with the same name as the zip (without extension)
        output_dir = os.path.splitext(os.path.basename(zip_path))[0]

    print(f"[*] Extracting '{zip_path}' to '{output_dir}'...")
    try:
        os.makedirs(output_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # We check and list extracted files if verbose
            if verbose:
                for member in zip_file.infolist():
                    zip_file.extract(member, path=output_dir)
                    print(f"  Extracted: {member.filename}")
            else:
                zip_file.extractall(path=output_dir)
        print(f"[PASS] Successfully extracted archive to '{output_dir}'")
    except Exception as e:
        print(f"[ERROR] Failed to extract: {e}")
        sys.exit(1)

def list_archive(zip_path):
    if not os.path.exists(zip_path):
        print(f"[ERROR] ZIP file '{zip_path}' does not exist.")
        sys.exit(1)
    if not zipfile.is_zipfile(zip_path):
        print(f"[ERROR] '{zip_path}' is not a valid ZIP archive.")
        sys.exit(1)

    print(f"[*] Listing contents of '{zip_path}':")
    print("-" * 60)
    print(f"{'File Name':<35} {'Size (Bytes)':<12} {'Compressed Size':<12}")
    print("-" * 60)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for info in zip_file.infolist():
                print(f"{info.filename:<35} {info.file_size:<12} {info.compress_size:<12}")
        print("-" * 60)
    except Exception as e:
        print(f"[ERROR] Failed to read ZIP info: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Compress files/folders into a ZIP archive, or extract zip files."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compress", help="File or folder path to compress")
    group.add_argument("-x", "--extract", help="ZIP archive path to extract")
    group.add_argument("-l", "--list", help="ZIP archive path to list contents of")

    parser.add_argument("-o", "--output", help="Output zip file path (when compressing) or destination directory (when extracting)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose details of files compressed or extracted")

    args = parser.parse_args()

    if args.compress:
        compress(args.compress, args.output, args.verbose)
    elif args.extract:
        extract(args.extract, args.output, args.verbose)
    elif args.list:
        list_archive(args.list)

if __name__ == "__main__":
    main()
