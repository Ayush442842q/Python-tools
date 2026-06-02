#!/usr/bin/env python3
"""
ASCII Art Generator

A simple command-line tool to generate ASCII art from text.

Usage:
    python tools/ascii_art_generator.py "Hello World"
"""

import argparse
import sys

def text_to_ascii(text):
    # A very simplified mock ASCII art generator for letters
    # In a real scenario, this would use a library like 'art' or 'pyfiglet'
    # or have a full character map. This is just for demonstration.
    art = ""
    for char in text:
        art += f"[{char.upper()}] "
    return art

def main():
    parser = argparse.ArgumentParser(description="Generate ASCII art from text")
    parser.add_argument('text', help='Text to convert to ASCII art')
    args = parser.parse_args()

    print("ASCII Art:")
    print("==========")
    print(text_to_ascii(args.text))
    print("==========")
    return 0

if __name__ == "__main__":
    sys.exit(main())
