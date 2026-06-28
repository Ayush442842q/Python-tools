#!/usr/bin/env python3
"""
Binary File Carver - A digital forensics utility that scans raw binary data files
(disk images, memory dumps, raw packet captures) for known file headers/trailers (signatures)
and extracts/carves files out recursively.
"""

import os
import sys
import argparse
from pathlib import Path

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_color(text, color):
    print(f"{color}{text}{RESET}")

# Supported file signatures with headers, trailers, and size resolution logic
SIGNATURES = {
    "png": {
        "header": b"\x89PNG\r\n\x1a\n",
        "trailer": b"IEND\xaeB`\x82",
        "trailer_offset": 8, # Length of trailer signature
        "max_size": 15 * 1024 * 1024  # 15 MB
    },
    "jpeg": {
        "header": b"\xff\xd8\xff",
        "trailer": b"\xff\xd9",
        "trailer_offset": 2,
        "max_size": 15 * 1024 * 1024
    },
    "gif": {
        "header": b"GIF89a",
        "trailer": b"\x00\x3b",
        "trailer_offset": 2,
        "max_size": 10 * 1024 * 1024
    },
    "gif87": {
        "header": b"GIF87a",
        "trailer": b"\x00\x3b",
        "trailer_offset": 2,
        "max_size": 10 * 1024 * 1024
    },
    "pdf": {
        "header": b"%PDF-",
        "trailer": b"%%EOF",
        "trailer_offset": 5,
        "max_size": 50 * 1024 * 1024  # 50 MB
    },
    "zip": {
        "header": b"PK\x03\x04",
        "trailer": b"PK\x05\x06",
        "trailer_offset": 22, # EOCD record is at least 22 bytes long
        "max_size": 100 * 1024 * 1024
    },
    "bmp": {
        "header": b"BM",
        "trailer": None,
        "size_func": lambda header_bytes: int.from_bytes(header_bytes[2:6], byteorder="little"),
        "header_read_size": 6,
        "max_size": 25 * 1024 * 1024
    }
}

def carve_binary(file_path, out_dir, enabled_types, verbose):
    target_path = Path(file_path).resolve()
    dest_path = Path(out_dir).resolve()

    if not target_path.exists() or not target_path.is_file():
        print_color(f"Error: Target file '{file_path}' does not exist or is not a file.", RED)
        return False

    dest_path.mkdir(parents=True, exist_ok=True)
    print_color(f"Scanning target file: {target_path}", BLUE)
    print_color(f"Carving files to: {dest_path}", BLUE)

    # Filter signatures
    sigs = {k: v for k, v in SIGNATURES.items() if k in enabled_types}
    if not sigs:
        print_color("Error: No valid signatures selected.", RED)
        return False

    # Read binary file
    try:
        data = target_path.read_bytes()
    except Exception as e:
        print_color(f"Error reading file: {e}", RED)
        return False

    file_size = len(data)
    print(f"File Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")

    carved_records = []
    offset = 0

    while offset < file_size:
        matched_sig = None
        matched_key = None

        # Look for headers at current offset
        for key, sig in sigs.items():
            header = sig["header"]
            if data[offset:offset+len(header)] == header:
                matched_sig = sig
                matched_key = key
                break

        if matched_sig:
            header_len = len(matched_sig["header"])
            max_limit = matched_sig["max_size"]
            
            carved_len = None
            
            # Case 1: Signature has a trailer
            if matched_sig["trailer"] is not None:
                trailer = matched_sig["trailer"]
                # Find trailer within the bounds of max size
                search_end = min(offset + max_limit, file_size)
                trailer_idx = data.find(trailer, offset + header_len, search_end)
                
                if trailer_idx != -1:
                    carved_len = (trailer_idx - offset) + matched_sig["trailer_offset"]
            
            # Case 2: Signature has a size resolution function (like BMP)
            elif "size_func" in matched_sig:
                read_size = matched_sig["header_read_size"]
                if offset + read_size <= file_size:
                    header_bytes = data[offset:offset+read_size]
                    try:
                        resolved_size = matched_sig["size_func"](header_bytes)
                        if 0 < resolved_size <= max_limit:
                            carved_len = resolved_size
                    except Exception:
                        pass

            if carved_len:
                # Carve the file block
                carved_data = data[offset:offset+carved_len]
                ext = matched_key
                # Group gif/gif87
                if ext == "gif87":
                    ext = "gif"
                
                carved_index = len(carved_records) + 1
                output_filename = f"carved_{carved_index:04d}.{ext}"
                output_filepath = dest_path / output_filename
                
                try:
                    output_filepath.write_bytes(carved_data)
                    carved_records.append({
                        "name": output_filename,
                        "type": ext,
                        "offset": offset,
                        "size": carved_len
                    })
                    if verbose:
                        print(f"Carved {ext.upper()} at offset {offset:08X} ({carved_len} bytes) -> {output_filename}")
                except Exception as e:
                    print_color(f"Error carving block to file: {e}", RED)

                # Skip past the carved data
                offset += carved_len
                continue

        # Move forward 1 byte if no match
        offset += 1

    # Print summary
    print_color(f"\n--- Carving Session Summary ---", BLUE)
    print(f"Total files carved: {len(carved_records)}")
    
    if carved_records:
        type_counts = {}
        for record in carved_records:
            type_counts[record["type"]] = type_counts.get(record["type"], 0) + 1
        
        for k, v in type_counts.items():
            print(f" - {k.upper()}: {v} file(s)")
            
        print_color(f"\nReport list saved in session logs.", GREEN)
        
        # Save a summary markdown or json inside the output folder
        summary_path = dest_path / "carving_manifest.json"
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(carved_records, f, indent=4)
            print(f"Manifest index saved to: {summary_path}")
        except Exception:
            pass
    else:
        print_color("No files were successfully carved.", YELLOW)

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Binary File Carver - A low-level digital forensics carver to extract media and documents from raw binary inputs."
    )
    parser.add_argument("binary_file", help="Path to the raw binary file to parse")
    parser.add_argument("-o", "--out-dir", required=True, help="Directory to save carved files to")
    parser.add_argument(
        "-t", "--types",
        default="png,jpeg,gif,pdf,zip,bmp",
        help="Comma-separated list of formats to scan for (supported: png, jpeg, gif, pdf, zip, bmp)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details of each file carved in real-time")

    args = parser.parse_args()

    # ANSI support on Windows
    if sys.platform == "win32":
        os.system("")

    # Parse and clean formats
    enabled_types = [t.strip().lower() for t in args.types.split(",")]
    
    # Map 'gif' to include both gif variations
    if "gif" in enabled_types:
        enabled_types.append("gif87")

    carve_binary(args.binary_file, args.out_dir, enabled_types, args.verbose)

if __name__ == "__main__":
    main()
