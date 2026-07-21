#!/usr/bin/env python3
"""
file_hash - Compute SHA256 hash of a file

Usage:
    python tools/file_hash.py [FILE]

Example:
    python tools/file_hash.py essay.txt
"""

import argparse, hashlib, sys

def main():
    parser = argparse.ArgumentParser(description="Compute SHA256 hash of a file")
    parser.add_argument('path', help='Path to the file to hash')
    args = parser.parse_args()
    try:
        with open(args.path, 'rb') as f:
            data = f.read()
        digest = hashlib.sha256(data).hexdigest()
        print(digest)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
