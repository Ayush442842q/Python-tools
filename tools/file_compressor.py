#!/usr/bin/env python3
"""
File Compressor - A command line archiving and compression tool supporting ZIP and TAR formats.
"""

import argparse
import os
import zipfile
import tarfile
import sys
import fnmatch

def format_size(size_bytes):
    """Format size in human readable units."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_ignored_patterns(exclude_str):
    """Parse comma-separated exclude patterns."""
    if not exclude_str:
        return []
    return [pattern.strip() for pattern in exclude_str.split(',')]

def should_exclude(path, exclude_patterns):
    """Check if the given path matches any exclude pattern."""
    basename = os.path.basename(path)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(path, pattern):
            return True
    return False

def create_zip(source, output_name, exclude_patterns, compression_level):
    """Create a ZIP archive of a file or directory."""
    compression = zipfile.ZIP_DEFLATED
    
    total_original_size = 0
    file_count = 0
    
    with zipfile.ZipFile(output_name, 'w', compression=compression, compresslevel=compression_level) as zipf:
        if os.path.isfile(source):
            if not should_exclude(source, exclude_patterns):
                zipf.write(source, os.path.basename(source))
                total_original_size += os.path.getsize(source)
                file_count += 1
                print(f"Adding: {source}")
        else:
            for root, dirs, files in os.walk(source):
                # Modify dirs in-place to skip excluded directories during walking
                dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), exclude_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if should_exclude(file_path, exclude_patterns):
                        continue
                    
                    arcname = os.path.relpath(file_path, os.path.dirname(source))
                    print(f"Adding: {arcname}")
                    zipf.write(file_path, arcname)
                    total_original_size += os.path.getsize(file_path)
                    file_count += 1
                    
    compressed_size = os.path.getsize(output_name)
    return file_count, total_original_size, compressed_size

def create_tar(source, output_name, mode, exclude_patterns):
    """Create a TAR archive (tar, tar.gz, tar.bz2)."""
    total_original_size = 0
    file_count = 0
    
    with tarfile.open(output_name, mode) as tar:
        if os.path.isfile(source):
            if not should_exclude(source, exclude_patterns):
                tar.add(source, arcname=os.path.basename(source))
                total_original_size += os.path.getsize(source)
                file_count += 1
                print(f"Adding: {source}")
        else:
            for root, dirs, files in os.walk(source):
                dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), exclude_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if should_exclude(file_path, exclude_patterns):
                        continue
                    
                    arcname = os.path.relpath(file_path, os.path.dirname(source))
                    print(f"Adding: {arcname}")
                    tar.add(file_path, arcname=arcname)
                    total_original_size += os.path.getsize(file_path)
                    file_count += 1
                    
    compressed_size = os.path.getsize(output_name)
    return file_count, total_original_size, compressed_size

def extract_archive(archive_path, dest_dir):
    """Extract a ZIP or TAR archive to a destination directory."""
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    print(f"Extracting {archive_path} to {dest_dir}...")
    
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(dest_dir)
            print("Extraction complete.")
            return True
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, 'r:*') as tar:
            tar.extractall(dest_dir)
            print("Extraction complete.")
            return True
    else:
        print("Error: Unsupported archive format or file is corrupt.", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="File Compressor & Archiver - Zip/Unzip and Tar/Untar utilities.")
    
    # Operation Mode
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compress", help="Compress the specified source folder/file")
    group.add_argument("-x", "--extract", help="Extract the specified archive file")
    
    # Options
    parser.add_argument("-o", "--output", help="Output archive name/path (required for compression)")
    parser.add_argument("-d", "--dest", help="Destination folder for extraction (default: current directory)")
    parser.add_argument("-f", "--format", choices=['zip', 'tar', 'tar.gz', 'tar.bz2'], default='zip',
                        help="Archive format to create (default: zip)")
    parser.add_argument("-e", "--exclude", help="Comma-separated file/folder patterns to exclude (e.g. '*.git,*.log')")
    parser.add_argument("-l", "--level", type=int, default=6, choices=range(0, 10),
                        help="ZIP Compression level 0-9 (default: 6)")
    
    args = parser.parse_args()
    
    # Extraction flow
    if args.extract:
        dest = args.dest or os.getcwd()
        if not os.path.exists(args.extract):
            print(f"Error: Archive file '{args.extract}' does not exist.", file=sys.stderr)
            sys.exit(1)
        success = extract_archive(args.extract, dest)
        sys.exit(0 if success else 1)
        
    # Compression flow
    if args.compress:
        if not args.output:
            print("Error: Output path (-o/--output) is required for compression.", file=sys.stderr)
            sys.exit(1)
            
        source = args.compress
        if not os.path.exists(source):
            print(f"Error: Source '{source}' does not exist.", file=sys.stderr)
            sys.exit(1)
            
        exclude_patterns = get_ignored_patterns(args.exclude)
        fmt = args.format
        output = args.output
        
        # Auto-append suffix if missing
        if fmt == 'zip' and not output.endswith('.zip'):
            output += '.zip'
        elif fmt == 'tar' and not output.endswith('.tar'):
            output += '.tar'
        elif fmt == 'tar.gz' and not (output.endswith('.tar.gz') or output.endswith('.tgz')):
            output += '.tar.gz'
        elif fmt == 'tar.bz2' and not (output.endswith('.tar.bz2') or output.endswith('.tbz2')):
            output += '.tar.bz2'
            
        print(f"Compressing '{source}' into '{output}' using format: {fmt}...")
        
        try:
            if fmt == 'zip':
                files_added, orig_size, comp_size = create_zip(source, output, exclude_patterns, args.level)
            else:
                tar_modes = {'tar': 'w:', 'tar.gz': 'w:gz', 'tar.bz2': 'w:bz2'}
                files_added, orig_size, comp_size = create_tar(source, output, tar_modes[fmt], exclude_patterns)
                
            ratio = (1.0 - (comp_size / max(orig_size, 1))) * 100.0
            print("\n" + "="*40)
            print("Compression Summary:")
            print(f"  Files Added:      {files_added}")
            print(f"  Original Size:    {format_size(orig_size)}")
            print(f"  Compressed Size:  {format_size(comp_size)}")
            print(f"  Space Saved:      {ratio:.2f}%")
            print("="*40)
            
        except Exception as e:
            print(f"Error during compression: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
