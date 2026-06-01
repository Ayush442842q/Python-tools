#!/usr/bin/env python3
"""
hello - Say hello to the world

A simple Python command‑line tool that prints a greeting.

Usage:
    python tools/hello.py [name]

Options:
    -h, --help     Show this help message and exit
    name          Name to greet (default: "world")

Example:
    python tools/hello.py Alice
    
"""

import argparse
import sys


def main():
    """Main entry point for the tool."""
    parser = argparse.ArgumentParser(description="Prints a friendly greeting")
    parser.add_argument('name', nargs='?', default='world', help='Name to greet')
    args = parser.parse_args()
    print(f"Hello, {args.name}!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
