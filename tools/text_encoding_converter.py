#!/usr/bin/env python3
"""
text_encoding_converter.py - Text Encoding Detector and UTF-8 Converter
Recursively scans files in a directory to identify current text encodings (UTF-8, UTF-16, ISO-8859-1, Windows-1252, etc.)
using byte pattern heuristics and BOM detection. Provides safe bulk conversion to standard UTF-8 with optional backups.
"""

import os
import sys
import argparse
import shutil

# Common text encodings to test (in order of priority/probability)
ENCODINGS_TO_TEST = [
    'utf-8',
    'windows-1252',
    'latin-1',      # Fallback, always succeeds but might map wrong chars
    'utf-16',
    'utf-16-le',
    'utf-16-be',
    'gbk',          # Chinese Simplified
    'gb18030',      # Chinese
    'shift_jis',    # Japanese
    'euc_jp',       # Japanese
    'euc_kr',       # Korean
    'cp1251',       # Cyrillic Windows
    'koi8-r',       # Cyrillic Russian
    'big5',         # Chinese Traditional
]

# BOM definitions
BOMS = [
    (b'\xef\xbb\xbf', 'utf-8-sig'),
    (b'\xff\xfe\x00\x00', 'utf-32-le'),
    (b'\x00\x00\xfe\xff', 'utf-32-be'),
    (b'\xff\xfe', 'utf-16-le'),
    (b'\xfe\xff', 'utf-16-be'),
]

# Default extensions to scan
DEFAULT_EXTENSIONS = {
    '.txt', '.py', '.html', '.css', '.js', '.jsx', '.ts', '.tsx',
    '.json', '.csv', '.md', '.xml', '.yaml', '.yml', '.ini', '.cfg',
    '.sh', '.bat', '.ps1', '.sql', '.cpp', '.h', '.c', '.java', '.go'
}

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def supports_color():
    return sys.stdout.isatty()

def print_color(text, color_code):
    if supports_color():
        print(f"{color_code}{text}{RESET}")
    else:
        print(text)

def is_binary(bytes_data):
    """
    Check if the byte sequence represents a binary file (e.g. contains NULL bytes or high ratio of control chars).
    """
    if not bytes_data:
        return False
    # A NULL byte in the first 8KB usually indicates a binary file
    chunk = bytes_data[:8192]
    if b'\x00' in chunk:
        # Check if it could be UTF-16 or UTF-32 (which contain many nulls)
        # If it matches a BOM, it's not a generic binary file
        for bom, _ in BOMS:
            if chunk.startswith(bom):
                return False
        return True
    
    # Calculate ratio of non-printable ASCII / control characters
    control_chars = sum(1 for b in chunk if b < 9 or (13 < b < 32))
    if len(chunk) > 0 and (control_chars / len(chunk)) > 0.30:
        return True
        
    return False

def detect_encoding(file_path):
    """
    Reads the file bytes and detects its encoding based on BOM and decoding tests.
    Returns (encoding_name, confidence_level, has_bom, error_msg)
    """
    try:
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()
    except Exception as e:
        return None, 0.0, False, f"Failed to read file: {e}"

    if not raw_bytes:
        return 'empty', 1.0, False, None

    if is_binary(raw_bytes):
        return 'binary', 1.0, False, None

    # 1. Check for BOM
    for bom_bytes, encoding_name in BOMS:
        if raw_bytes.startswith(bom_bytes):
            return encoding_name, 1.0, True, None

    # 2. Try decoding as UTF-8
    try:
        raw_bytes.decode('utf-8')
        # If it succeeds and has only ASCII characters
        try:
            raw_bytes.decode('ascii')
            return 'ascii', 1.0, False, None
        except UnicodeDecodeError:
            return 'utf-8', 1.0, False, None
    except UnicodeDecodeError:
        pass

    # 3. Try other encodings in order
    for enc in ENCODINGS_TO_TEST:
        if enc == 'utf-8':
            continue
        try:
            raw_bytes.decode(enc)
            # Make sure we don't just match latin-1 if another encoding might fit better.
            # latin-1 decodes any byte stream, so it's a fallback with low confidence.
            confidence = 0.5 if enc in ['latin-1', 'windows-1252'] else 0.9
            return enc, confidence, False, None
        except UnicodeDecodeError:
            continue

    return 'unknown', 0.0, False, "No matching encoding found"

def convert_to_utf8(file_path, current_encoding, backup=True):
    """
    Converts a file from current_encoding to standard UTF-8 (without BOM).
    Returns (success, error_msg)
    """
    try:
        # Create backup
        if backup:
            backup_path = file_path + ".bak"
            shutil.copy2(file_path, backup_path)

        # Read content using current detected encoding
        with open(file_path, 'r', encoding=current_encoding, errors='replace') as f:
            content = f.read()

        # Write content back in UTF-8
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)

        return True, None
    except Exception as e:
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(
        description="Scans and converts text files recursively to standard UTF-8 encoding."
    )
    parser.add_argument(
        'path', 
        nargs='?', 
        default='.',
        help="Path to file or directory to scan/convert (default: current directory)."
    )
    parser.add_argument(
        '-e', '--extensions',
        help="Comma-separated file extensions to scan (e.g. '.py,.txt,.json')."
    )
    parser.add_argument(
        '-c', '--convert',
        action='store_true',
        help="Convert detected non-UTF-8 text files to UTF-8."
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help="Do not create .bak backup files before converting."
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Show details of every scanned file, including ASCII/UTF-8 files."
    )
    parser.add_argument(
        '--exclude-dir',
        help="Directories to exclude from scanning (comma-separated, e.g. '.git,node_modules,venv')."
    )

    args = parser.parse_args()

    # Parse extensions
    extensions = DEFAULT_EXTENSIONS
    if args.extensions:
        extensions = {ext.strip().lower() for ext in args.extensions.split(',') if ext.strip()}
        # Ensure all start with dot
        extensions = {ext if ext.startswith('.') else f".{ext}" for ext in extensions}

    # Parse excluded directories
    excluded_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', '.agents', '.gemini'}
    if args.exclude_dir:
        for d in args.exclude_dir.split(','):
            excluded_dirs.add(d.strip())

    target_path = os.path.abspath(args.path)
    if not os.path.exists(target_path):
        print_color(f"Error: Path '{target_path}' does not exist.", RED)
        sys.exit(1)

    files_to_scan = []
    if os.path.isfile(target_path):
        files_to_scan.append(target_path)
    else:
        for root, dirs, files in os.walk(target_path):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    files_to_scan.append(os.path.join(root, file))

    if not files_to_scan:
        print("No files found matching the scanning criteria.")
        sys.exit(0)

    print_color(f"Scanning {len(files_to_scan)} files in: {target_path}", BOLD)
    print("=" * 60)

    stats = {
        'total': len(files_to_scan),
        'ascii': 0,
        'utf-8': 0,
        'utf-8-sig': 0,
        'binary': 0,
        'converted': 0,
        'failed_conversion': 0,
        'errors': 0,
        'non_utf8': {}
    }

    for file_path in files_to_scan:
        rel_path = os.path.relpath(file_path, target_path)
        enc, conf, has_bom, err = detect_encoding(file_path)

        if err:
            print_color(f"[ERROR] {rel_path} - {err}", RED)
            stats['errors'] += 1
            continue

        if enc == 'binary':
            stats['binary'] += 1
            if args.verbose:
                print(f"[BINARY] {rel_path}")
            continue

        if enc in ['ascii', 'utf-8'] and not has_bom:
            if enc == 'ascii':
                stats['ascii'] += 1
            else:
                stats['utf-8'] += 1
            if args.verbose:
                print(f"[OK] {rel_path} ({enc})")
            continue

        # Found non-UTF-8 or UTF-8 with BOM
        stats['non_utf8'][enc] = stats['non_utf8'].get(enc, 0) + 1
        bom_str = " (with BOM)" if has_bom else ""
        print_color(f"[ACTION REQUIRED] {rel_path} -> Detected: {enc}{bom_str} (Confidence: {conf:.2f})", YELLOW)

        if args.convert:
            # Skip if it is empty
            if enc == 'empty':
                continue
                
            success, conv_err = convert_to_utf8(file_path, enc, backup=not args.no_backup)
            if success:
                print_color(f"  [CONVERTED] Successfully rewritten to UTF-8", GREEN)
                stats['converted'] += 1
            else:
                print_color(f"  [FAILED] Conversion failed: {conv_err}", RED)
                stats['failed_conversion'] += 1

    print("=" * 60)
    print_color("Scan Summary:", BOLD)
    print(f"  Total Files Scanned: {stats['total']}")
    print(f"  Clean ASCII Files:   {stats['ascii']}")
    print(f"  Clean UTF-8 Files:   {stats['utf-8']}")
    print(f"  Binary Files Skipped:{stats['binary']}")
    
    if stats['non_utf8']:
        print_color("  Non-Standard Encodings Found:", YELLOW)
        for enc, count in stats['non_utf8'].items():
            print(f"    - {enc}: {count} files")
            
    if args.convert:
        print_color(f"  Successfully Converted to UTF-8: {stats['converted']}", GREEN)
        if stats['failed_conversion'] > 0:
            print_color(f"  Failed Conversions:              {stats['failed_conversion']}", RED)
    else:
        if stats['non_utf8']:
            print_color(f"\nRun with '--convert' to automatically rewrite these {sum(stats['non_utf8'].values())} files to standard UTF-8.", BOLD)

if __name__ == '__main__':
    main()
