#!/usr/bin/env python3
"""
File Block Checksum Generator
A CLI utility to generate block-by-block cryptographic checksums (manifests) for large files.

Features:
- Splits a file logically into uniform block sizes (e.g. 1MB, 4MB, 16MB) and calculates independent hashes.
- Supported algorithms: SHA256, MD5, SHA1, SHA224, SHA384, SHA512.
- Generates structured JSON or CSV manifests detailing block index, start byte, end byte, block size, and block hash.
- Useful for multi-part uploads, chunk-based delta syncing, or local block-level validation.
"""

import sys
import os
import hashlib
import json
import csv
import argparse
from typing import Dict, Any, List

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def generate_block_manifest(filepath: str, block_size: int, algorithm: str) -> List[Dict[str, Any]]:
    """
    Computes block checksums for a file and returns a list of dictionaries with block details.
    """
    blocks: List[Dict[str, Any]] = []
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    block_index = 0
    start_byte = 0

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            
            actual_size = len(chunk)
            end_byte = start_byte + actual_size - 1

            hasher = hashlib.new(algorithm)
            hasher.update(chunk)
            block_hash = hasher.hexdigest()

            blocks.append({
                "index": block_index,
                "start_byte": start_byte,
                "end_byte": end_byte,
                "size_bytes": actual_size,
                "hash": block_hash
            })

            block_index += 1
            start_byte += actual_size

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate block-by-block cryptographic manifests for files.")
    parser.add_argument("file", help="Path to input file to hash.")
    parser.add_argument("-b", "--block-size", type=str, default="1M",
                        help="Block size in bytes, or with suffixes K, M, G (default: '1M').")
    parser.add_argument("-a", "--algorithm", choices=list(hashlib.algorithms_guaranteed), default="sha256",
                        help="Cryptographic hashing algorithm to use (default: 'sha256').")
    parser.add_argument("-f", "--format", choices=["json", "csv"], default="json",
                        help="Manifest output format (default: 'json').")
    parser.add_argument("-o", "--output", type=str, help="Output manifest file path (prints to stdout if omitted).")

    args = parser.parse_args()

    # Parse block size suffix
    bs_str = args.block_size.upper().strip()
    multiplier = 1
    if bs_str.endswith("K"):
        multiplier = 1024
        bs_str = bs_str[:-1]
    elif bs_str.endswith("M"):
        multiplier = 1024 * 1024
        bs_str = bs_str[:-1]
    elif bs_str.endswith("G"):
        multiplier = 1024 * 1024 * 1024
        bs_str = bs_str[:-1]

    try:
        block_size_bytes = int(bs_str) * multiplier
        if block_size_bytes <= 0:
            raise ValueError()
    except ValueError:
        print(f"Error: Invalid block size argument '{args.block_size}'. Must be a positive integer with K, M, or G.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.file) or os.path.isdir(args.file):
        print(f"Error: Target path '{args.file}' is not a valid file.", file=sys.stderr)
        sys.exit(1)

    try:
        blocks = generate_block_manifest(args.file, block_size_bytes, args.algorithm.lower())
    except Exception as e:
        print(f"Error calculating hashes: {e}", file=sys.stderr)
        sys.exit(1)

    # Format output
    if args.format == "json":
        meta = {
            "file": os.path.basename(args.file),
            "file_size_bytes": os.path.getsize(args.file),
            "block_size_bytes": block_size_bytes,
            "algorithm": args.algorithm,
            "blocks": blocks
        }
        output_str = json.dumps(meta, indent=2)
    else:  # csv
        import io
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["index", "start_byte", "end_byte", "size_bytes", "hash"])
        for block in blocks:
            writer.writerow([block["index"], block["start_byte"], block["end_byte"], block["size_bytes"], block["hash"]])
        output_str = csv_buffer.getvalue()

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Successfully generated block checksum manifest in {args.output}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
