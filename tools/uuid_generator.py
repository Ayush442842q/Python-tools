#!/usr/bin/env python3
"""
UUID Generator

Generates random UUIDs (v4).

Usage:
    python tools/uuid_generator.py [--count 5]
"""

import argparse
import sys
import uuid

def main():
    parser = argparse.ArgumentParser(description="Generate random UUIDs")
    parser.add_argument('-c', '--count', type=int, default=1, help='Number of UUIDs to generate (default: 1)')
    args = parser.parse_args()

    for _ in range(args.count):
        print(uuid.uuid4())
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
