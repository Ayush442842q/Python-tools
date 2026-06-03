#!/usr/bin/env python3
"""
Hex to RGB Converter

Converts a hex color code to RGB format.

Usage:
    python tools/hex_to_rgb_converter.py "#FF5733"
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Hex to RGB Converter")
    parser.add_argument('hexcode', help='Hex color code (e.g. #FF5733 or FF5733)')
    args = parser.parse_args()

    hex_color = args.hexcode.lstrip('#')
    
    if len(hex_color) != 6:
        print("Error: Hex code must be 6 characters long.")
        return 1
        
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        print(f"RGB({r}, {g}, {b})")
    except ValueError:
        print("Error: Invalid hex code characters.")
        return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
