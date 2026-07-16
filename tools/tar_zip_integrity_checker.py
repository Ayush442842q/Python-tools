#!/usr/bin/env python3
"""
Tarball & Archive Integrity Checker / Forensic Audit Tool
=========================================================
A zero-dependency command-line utility to run deep validation and security audits on
archives (.zip, .tar, .tar.gz, .tar.bz2, .tar.xz). Scans for corrupt headers, calculates
sizes and compression rates, and identifies security issues such as directory traversal
vulns ("Zip Slip" containing absolute or ../ paths) and Zip Bombs (unusually high compression ratios).

Author: Antigravity
License: MIT
"""

import os
import sys
import zipfile
import tarfile
import json
import argparse

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def format_size(size_bytes):
    """Format bytes into human-readable representation."""
    if size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class ArchiveAuditor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.file_size = os.path.getsize(filepath)
        self.archive_type = self._detect_archive_type()
        self.total_uncompressed = 0
        self.total_compressed = 0
        self.file_count = 0
        self.dir_count = 0
        self.symlink_count = 0
        
        # Security audit variables
        self.is_corrupt = False
        self.corruption_error = ""
        self.zip_slip_files = []
        self.zip_bomb_files = []
        self.broken_symlinks = []
        self.file_details = []

    def _detect_archive_type(self):
        _, ext = os.path.splitext(self.filepath.lower())
        if ext == '.zip':
            return 'zip'
        elif ext in ['.tar', '.tgz'] or self.filepath.lower().endswith('.tar.gz') or \
             self.filepath.lower().endswith('.tar.bz2') or self.filepath.lower().endswith('.tar.xz'):
            return 'tar'
        else:
            # Fallback signature detection
            with open(self.filepath, 'rb') as f:
                sig = f.read(4)
            if sig.startswith(b'PK'):
                return 'zip'
            elif sig.startswith(b'\x1f\x8b') or sig.startswith(b'BZh') or sig.startswith(b'\xfd7zXZ\x00') or sig.startswith(b'ustar'):
                return 'tar'
        return 'unknown'

    def audit(self):
        if self.archive_type == 'zip':
            self._audit_zip()
        elif self.archive_type == 'tar':
            self._audit_tar()
        else:
            raise ValueError("Unsupported archive format. Supported formats: ZIP and TAR (including compressed tarballs).")

    def _check_zip_slip(self, name):
        """Detect directory traversal paths (Zip Slip vulnerability)."""
        # Checks for absolute paths or path traversal '../' sequences
        normalized = os.path.normpath(name)
        if name.startswith('/') or name.startswith('\\') or '..' in name.split('/') or '..' in name.split('\\') or normalized.startswith('..'):
            return True
        return False

    def _audit_zip(self):
        try:
            if not zipfile.is_zipfile(self.filepath):
                self.is_corrupt = True
                self.corruption_error = "Header signature does not match standard ZIP files."
                return

            with zipfile.ZipFile(self.filepath, 'r') as zf:
                # Run standard testzip (checks CRC32 checksums of all file headers)
                corrupt_file = zf.testzip()
                if corrupt_file:
                    self.is_corrupt = True
                    self.corruption_error = f"CRC Checksum mismatch on file: '{corrupt_file}'"
                    return

                for info in zf.infolist():
                    name = info.filename
                    uncomp = info.file_size
                    comp = info.compress_size
                    
                    # Log sizes
                    self.total_uncompressed += uncomp
                    self.total_compressed += comp
                    
                    if info.is_dir():
                        self.dir_count += 1
                        is_dir = True
                    else:
                        self.file_count += 1
                        is_dir = False

                    # Check Zip Slip
                    if self._check_zip_slip(name):
                        self.zip_slip_files.append(name)

                    # Check Zip Bomb (Single-file compression ratio > 150x, or extremely large ratio for large file)
                    if comp > 0:
                        ratio = uncomp / comp
                        if ratio > 150.0 and uncomp > 1024 * 1024:  # > 1MB uncompressed
                            self.zip_bomb_files.append({
                                'name': name,
                                'ratio': ratio,
                                'uncompressed': uncomp,
                                'compressed': comp
                            })
                    else:
                        ratio = 0.0

                    self.file_details.append({
                        'name': name,
                        'size': uncomp,
                        'compressed_size': comp,
                        'ratio': ratio,
                        'is_dir': is_dir,
                        'is_symlink': False
                    })
        except zipfile.BadZipFile as e:
            self.is_corrupt = True
            self.corruption_error = f"BadZipFile error: {e}"
        except Exception as e:
            self.is_corrupt = True
            self.corruption_error = f"General extraction check error: {e}"

    def _audit_tar(self):
        try:
            # Detect compression mode
            mode = 'r:*'
            with tarfile.open(self.filepath, mode) as tf:
                for member in tf.getmembers():
                    name = member.name
                    uncomp = member.size
                    # Compressed size per member in TAR is not directly available because of block allocations,
                    # but we can look at member type details
                    
                    self.total_uncompressed += uncomp
                    
                    is_sym = member.issym() or member.islnk()
                    is_dir = member.isdir()

                    if is_dir:
                        self.dir_count += 1
                    elif is_sym:
                        self.symlink_count += 1
                        # Check for absolute symlink destinations (might leak host filesystem details)
                        linkname = member.linkname
                        if linkname.startswith('/') or linkname.startswith('\\') or '..' in linkname.split('/') or '..' in linkname.split('\\'):
                            self.broken_symlinks.append({
                                'name': name,
                                'target': linkname
                            })
                    else:
                        self.file_count += 1

                    # Check Zip Slip
                    if self._check_zip_slip(name):
                        self.zip_slip_files.append(name)

                    self.file_details.append({
                        'name': name,
                        'size': uncomp,
                        'compressed_size': 0, # not available per member in tar
                        'ratio': 1.0,
                        'is_dir': is_dir,
                        'is_symlink': is_sym,
                        'link_target': member.linkname if is_sym else ""
                    })
                    
            # Overall compression ratio check for Tarball (compressed tar size vs uncompressed contents)
            if self.file_size > 0:
                overall_ratio = self.total_uncompressed / self.file_size
                if overall_ratio > 150.0 and self.total_uncompressed > 50 * 1024 * 1024:  # > 50MB
                    self.zip_bomb_files.append({
                        'name': 'Archive Payload',
                        'ratio': overall_ratio,
                        'uncompressed': self.total_uncompressed,
                        'compressed': self.file_size
                    })
                    
        except tarfile.ReadError as e:
            self.is_corrupt = True
            self.corruption_error = f"Tar ReadError: {e}"
        except Exception as e:
            self.is_corrupt = True
            self.corruption_error = f"General Tar check error: {e}"

def print_audit_report(auditor, verbose=False):
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}                   ARCHIVE FORENSIC & INTEGRITY AUDITOR              {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    print(f"{BOLD}Archive File:{RESET}       {auditor.filepath}")
    print(f"{BOLD}Archive Format:{RESET}     {auditor.archive_type.upper()}")
    print(f"{BOLD}Archive File Size:{RESET}  {format_size(auditor.file_size)}")

    if auditor.is_corrupt:
        print(f"{BOLD}Integrity Status:{RESET}   {RED}{BOLD}CORRUPTED / INVALID{RESET}")
        print(f"{BOLD}Diagnostic Error:{RESET}   {RED}{auditor.corruption_error}{RESET}")
        print(f"\n{BOLD}{BLUE}======================================================================{RESET}\n")
        return

    print(f"{BOLD}Integrity Status:{RESET}   {GREEN}{BOLD}VALID / PARSABLE{RESET}")
    print(f"{BOLD}Files Count:{RESET}        {auditor.file_count}")
    print(f"{BOLD}Directories Count:{RESET}  {auditor.dir_count}")
    if auditor.archive_type == 'tar':
        print(f"{BOLD}Symlinks Count:{RESET}     {auditor.symlink_count}")
    
    print(f"{BOLD}Uncompressed Size:{RESET}  {format_size(auditor.total_uncompressed)}")
    
    # Calculate compression ratio
    ratio = auditor.total_uncompressed / auditor.file_size if auditor.file_size > 0 else 0
    print(f"{BOLD}Compression Ratio:{RESET}  {ratio:.2f}x")

    # Security Auditing Findings
    print(f"\n{BOLD}{BLUE}--- Security Audit Findings ---{RESET}")
    
    # 1. Zip Slip
    if auditor.zip_slip_files:
        print(f"  {RED}{BOLD}» [VULNERABILITY] PATH TRAVERSAL DETECTED (Zip Slip){RESET}")
        print(f"    Found {len(auditor.zip_slip_files)} items containing directory traversal paths:")
        for name in auditor.zip_slip_files[:10]:
            print(f"      - {name}")
        if len(auditor.zip_slip_files) > 10:
            print(f"      ... and {len(auditor.zip_slip_files) - 10} more.")
    else:
        print(f"  {GREEN}✓ Path Traversal Protection: OK (No dynamic paths detected){RESET}")

    # 2. Zip Bomb
    if auditor.zip_bomb_files:
        print(f"  {RED}{BOLD}» [VULNERABILITY] ZIP BOMB / DECOMPRESSION DOS DETECTED{RESET}")
        for item in auditor.zip_bomb_files:
            print(f"    Suspicious Compression Ratio on '{item['name']}':")
            print(f"      Ratio: {item['ratio']:.2f}x | Uncompressed: {format_size(item['uncompressed'])} | Compressed: {format_size(item['compressed'])}")
    else:
        print(f"  {GREEN}✓ Decompression Ratio limits: OK (No Zip Bomb indicators){RESET}")

    # 3. Symlink safety
    if auditor.archive_type == 'tar':
        if auditor.broken_symlinks:
            print(f"  {YELLOW}{BOLD}» [WARNING] OUT-OF-BOUNDS / TRAVERSING SYMLINKS DETECTED{RESET}")
            for link in auditor.broken_symlinks:
                print(f"      Link: '{link['name']}' targets '{link['target']}'")
        else:
            print(f"  {GREEN}✓ Symlink Boundaries: OK (No out-of-bounds targets found){RESET}")

    if verbose and auditor.file_details:
        print(f"\n{BOLD}{BLUE}--- Detailed Member List ---{RESET}")
        print(f"  {BOLD}{'Type':<8} {'Size':<12} {'Compressed':<12} {'Ratio':<6} {'Name'}{RESET}")
        for f in auditor.file_details:
            t_str = "DIR" if f['is_dir'] else ("SYM" if f.get('is_symlink') else "FILE")
            r_str = f"{f['ratio']:.1f}x" if f['compressed_size'] > 0 else "-"
            print(f"  {t_str:<8} {format_size(f['size']):<12} {format_size(f['compressed_size']):<12} {r_str:<6} {f['name']}")

    print(f"\n{BOLD}{BLUE}======================================================================{RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Tarball & Archive Integrity Checker - Perform checksum validations, size analysis, and security auditing on ZIP/TAR files."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the ZIP or TAR archive.")
    parser.add_argument("-v", "--verbose", action="store_true", help="List all members details inside the archive.")
    parser.add_argument("-j", "--json", action="store_true", help="Output audit report details in JSON format.")
    parser.add_argument("-e", "--check-only", action="store_true", help="Only exit with status code (0 = safe/valid, 1 = corrupt/unsafe).")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"{RED}Error: File '{args.input}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        auditor = ArchiveAuditor(args.input)
        auditor.audit()
    except Exception as e:
        print(f"{RED}Failed to run audit: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.check_only:
        # Exit codes: 1 if corrupt, Zip Slip detected, or Zip Bomb detected
        if auditor.is_corrupt or auditor.zip_slip_files or auditor.zip_bomb_files:
            sys.exit(1)
        sys.exit(0)

    if args.json:
        report_data = {
            'file': auditor.filepath,
            'file_size': auditor.file_size,
            'archive_type': auditor.archive_type,
            'is_corrupt': auditor.is_corrupt,
            'corruption_error': auditor.corruption_error,
            'file_count': auditor.file_count,
            'dir_count': auditor.dir_count,
            'symlink_count': auditor.symlink_count,
            'total_uncompressed': auditor.total_uncompressed,
            'total_compressed': auditor.total_compressed,
            'zip_slip_files': auditor.zip_slip_files,
            'zip_bomb_files': auditor.zip_bomb_files,
            'broken_symlinks': auditor.broken_symlinks,
            'members': auditor.file_details
        }
        print(json.dumps(report_data, indent=4))
    else:
        print_audit_report(auditor, verbose=args.verbose)

if __name__ == "__main__":
    main()
