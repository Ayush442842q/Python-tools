#!/usr/bin/env python3
"""
Binary File Analyzer
Analyzes binary files, generates custom hex dumps, computes Shannon entropy,
identifies common file signatures/magic bytes, and extracts printable ASCII strings.
"""

import sys
import os
import math
import argparse

# Common file signatures (magic numbers)
SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'PNG Image File (.png)',
    b'\xff\xd8\xff': 'JPEG Image File (.jpg)',
    b'GIF87a': 'GIF Image File (.gif)',
    b'GIF89a': 'GIF Image File (.gif)',
    b'%PDF': 'PDF Document File (.pdf)',
    b'PK\x03\x04': 'ZIP Archive File (.zip, .jar, .docx, .xlsx)',
    b'MZ': 'Windows Executable/DLL File (.exe, .dll)',
    b'\x7fELF': 'ELF Executable/Library (.elf, bin)',
    b'\x1f\x8b': 'GZIP Compressed File (.gz)',
    b'BZh': 'BZIP2 Compressed File (.bz2)',
    b'\xca\xfe\xba\xbe': 'Java Class File (.class)',
    b'ID3': 'MP3 Audio File with ID3 Metadata (.mp3)',
    b'fLaC': 'FLAC Audio File (.flac)',
    b'RIFF': 'Resource Interchange File Format (WAV, AVI, WEBP)',
    b'OggS': 'Ogg Container File (.ogg)',
    b'\x00\x00\x00\x18ftyp': 'MP4 Video File (.mp4)',
    b'\x30\x26\xB2\x75\x8E\x66\xCF\x11': 'ASF/WMV/WMA File (.wmv, .wma)',
}

def detect_file_type(file_path):
    """Detect file type by checking its header against common signatures."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)
            for sig, desc in SIGNATURES.items():
                if header.startswith(sig):
                    return desc
        return "Unknown Binary Format"
    except Exception as e:
        return f"Error reading file signature: {e}"

def calculate_entropy(file_path):
    """Calculate Shannon entropy of the file's byte distribution (0.0 to 8.0)."""
    if not os.path.exists(file_path):
        return 0.0
        
    total_bytes = os.path.getsize(file_path)
    if total_bytes == 0:
        return 0.0
        
    counts = [0] * 256
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                for byte in chunk:
                    counts[byte] += 1
                    
        entropy = 0.0
        for count in counts:
            if count > 0:
                p = count / total_bytes
                entropy -= p * math.log2(p)
        return entropy
    except Exception as e:
        print(f"Error calculating entropy: {e}", file=sys.stderr)
        return 0.0

def generate_hexdump(file_path, limit_bytes=512):
    """Generate a formatted hex dump of the file (similar to hexdump -C)."""
    if not os.path.exists(file_path):
        print("File not found.")
        return
        
    try:
        with open(file_path, 'rb') as f:
            offset = 0
            while limit_bytes is None or offset < limit_bytes:
                chunk = f.read(16)
                if not chunk:
                    break
                    
                hex_str = ' '.join(f"{b:02x}" for b in chunk)
                if len(chunk) < 16:
                    hex_str += ' ' * (3 * (16 - len(chunk)))
                    
                # Split hex representation into 8-byte blocks for readability
                if len(chunk) > 8:
                    hex_str = hex_str[:23] + '  ' + hex_str[24:]
                else:
                    hex_str = hex_str + ' '
                    
                ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                print(f"{offset:08x}  {hex_str:<49}  |{ascii_str}|")
                offset += 16
    except Exception as e:
        print(f"Error during hex dump: {e}", file=sys.stderr)

def extract_strings(file_path, min_len=4):
    """Extract and print printable ASCII strings from the binary file."""
    try:
        with open(file_path, 'rb') as f:
            current_str = []
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                for byte in chunk:
                    if 32 <= byte <= 126 or byte == 10 or byte == 13 or byte == 9:
                        current_str.append(chr(byte))
                    else:
                        if len(current_str) >= min_len:
                            print(''.join(current_str).strip())
                        current_str = []
            if len(current_str) >= min_len:
                print(''.join(current_str).strip())
    except Exception as e:
        print(f"Error extracting strings: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Binary File Analyzer - Inspect binary files, extract strings, and generate hex dumps",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the binary file to analyze")
    parser.add_argument("--hexdump", action="store_true", help="Generate a hex dump of the file")
    parser.add_argument("--limit", type=int, default=512, help="Limit hex dump to N bytes (0 for unlimited, default 512)")
    parser.add_argument("--strings", action="store_true", help="Extract and display printable ASCII strings")
    parser.add_argument("--min-len", type=int, default=4, help="Minimum string length for --strings (default 4)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        return 1
        
    if os.path.isdir(args.file):
        print(f"Error: '{args.file}' is a directory.", file=sys.stderr)
        return 1
        
    size_bytes = os.path.getsize(args.file)
    entropy = calculate_entropy(args.file)
    file_type = detect_file_type(args.file)
    
    print("=== Binary Analysis Summary ===")
    print(f"File Path:    {args.file}")
    print(f"File Size:    {size_bytes} bytes ({size_bytes / 1024:.2f} KB)")
    print(f"Signature:    {file_type}")
    print(f"Entropy:      {entropy:.4f} (out of 8.0)")
    
    # Entropy interpretation
    if entropy > 7.5:
        print("Interpretation: Extremely high entropy. The file is likely compressed, encrypted, or packed.")
    elif entropy > 6.0:
        print("Interpretation: High entropy. File may contain compressed elements or media content.")
    elif entropy < 1.0:
        print("Interpretation: Very low entropy. File contains lots of redundant bytes (e.g. padding).")
    else:
        print("Interpretation: Moderate entropy. Typical of structured code, text, or database files.")
    print("===============================\n")
    
    if args.hexdump:
        print("--- Hexadecimal Dump ---")
        limit = None if args.limit <= 0 else args.limit
        generate_hexdump(args.file, limit)
        print("-" * 24 + "\n")
        
    if args.strings:
        print(f"--- Extracted ASCII Strings (min length: {args.min_len}) ---")
        extract_strings(args.file, args.min_len)
        print("-" * 40 + "\n")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
