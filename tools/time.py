#!/usr/bin/env python3
"""
current_time - Display current local time

A simple CLI tool that prints the current local time in ISO format.

Usage:
    python tools/current_time.py [--format FORMAT]

Options:
    --format FORMAT   ISO format string for datetime.strftime (default: %Y-%m-%d %H:%M:%S)
    -h, --help        Show this help message and exit

Example:
    python tools/current_time.py --format "%H:%M"
"""

import argparse
import datetime
import sys

def main():
    parser = argparse.ArgumentParser(description="Print current local time")
    parser.add_argument('--format', default="%Y-%m-%d %H:%M:%S", help="strftime format string")
    args = parser.parse_args()
    now = datetime.datetime.now()
    print(now.strftime(args.format))
    return 0

if __name__ == "__main__":
    sys.exit(main())
