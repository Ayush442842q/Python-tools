#!/usr/bin/env python3
"""
Binary Pattern Visualizer
Reads a binary file and renders a grid-based visual map of its contents in the terminal
using ANSI colors to identify different classes of bytes (nulls, ASCII, controls, high bytes).
"""

import os
import sys
import math
import argparse

# ANSI Escape Sequences for background colors
COLOR_NULL = '\033[48;5;236m'      # Dark grey
COLOR_ASCII = '\033[48;5;28m'      # Dark green
COLOR_CONTROL = '\033[48;5;124m'    # Red
COLOR_HIGH = '\033[48;5;25m'       # Blue
COLOR_RESET = '\033[0m'
COLOR_TEXT_WHITE = '\033[97m'

def calculate_entropy(data):
    """Calculate Shannon entropy of the binary data (0.0 to 8.0)."""
    if not data:
        return 0.0
    entropy = 0
    length = len(data)
    # Count frequencies
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    # Calculate entropy
    for count in counts:
        if count == 0:
            continue
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def get_byte_style(b):
    """Return background color code and visual character for a byte."""
    if b == 0x00:
        return COLOR_NULL, '0'
    elif 32 <= b <= 126:
        # Printable ASCII: show character (if not too long) or block
        return COLOR_ASCII, chr(b)
    elif b in (9, 10, 13):  # tab, lf, cr
        return COLOR_ASCII, '.'
    elif b < 32:
        # Control characters
        return COLOR_CONTROL, 'c'
    else:
        # High bytes (non-ASCII, 128-255)
        return COLOR_HIGH, 'x'

def print_legend():
    """Print color coding legend."""
    print("Legend:")
    print(f"  {COLOR_NULL} 0 {COLOR_RESET} Null bytes (0x00)")
    print(f"  {COLOR_ASCII} a {COLOR_RESET} Printable ASCII (0x20 - 0x7E, whitespace)")
    print(f"  {COLOR_CONTROL} c {COLOR_RESET} Control chars (0x01 - 0x1F)")
    print(f"  {COLOR_HIGH} x {COLOR_RESET} High bytes (0x80 - 0xFF)")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Binary Pattern Visualizer - Visualize binary file patterns using ANSI colors",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the binary file to visualize")
    parser.add_argument("-w", "--width", type=int, default=16,
                        help="Number of bytes per row in the grid (default: 16)")
    parser.add_argument("-l", "--limit", type=int, default=1024,
                        help="Maximum bytes to visualize to prevent terminal flooding (default: 1024)")
    parser.add_argument("-s", "--skip", type=int, default=0,
                        help="Offset/bytes to skip from the beginning of the file (default: 0)")
    parser.add_argument("--no-legend", action="store_true", help="Do not print the color legend")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        file_size = os.path.getsize(args.file)
        with open(args.file, "rb") as f:
            if args.skip > 0:
                f.seek(args.skip)
            data = f.read(args.limit)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if not data:
        print("No data to display (file is empty or skipped past EOF).")
        sys.exit(0)

    # Calculate statistics on the read block
    entropy = calculate_entropy(data)
    
    print(f"File: {os.path.basename(args.file)}")
    print(f"Total Size: {file_size} bytes")
    print(f"Showing: {len(data)} bytes starting at offset {args.skip}")
    print(f"Entropy: {entropy:.4f} bits/byte (high entropy indicates compression/encryption)")
    print("-" * 50)

    if not args.no_legend:
        print_legend()

    # Visualizing
    width = args.width
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        offset = args.skip + i
        
        # Print offset (hex)
        line = [f"{offset:08x}  "]
        
        # Color bytes
        for b in chunk:
            color, char = get_byte_style(b)
            line.append(f"{color}{char}{COLOR_RESET}")
            
        # Padding for last line if incomplete
        if len(chunk) < width:
            line.append(" " * (width - len(chunk)))
            
        line.append("  |")
        # Text representation (safe printable chars, else '.')
        for b in chunk:
            if 32 <= b <= 126:
                line.append(chr(b))
            else:
                line.append('.')
        line.append("|")
        
        print("".join(line))

    # Summary distribution
    nulls = sum(1 for b in data if b == 0x00)
    asciis = sum(1 for b in data if 32 <= b <= 126 or b in (9, 10, 13))
    controls = sum(1 for b in data if b < 32 and b not in (9, 10, 13))
    highs = sum(1 for b in data if b >= 128)
    
    total = len(data)
    print("-" * 50)
    print("Byte Distribution:")
    print(f"  Null:    {nulls:5d} ({nulls/total*100:5.1f}%)")
    print(f"  ASCII:   {asciis:5d} ({asciis/total*100:5.1f}%)")
    print(f"  Control: {controls:5d} ({controls/total*100:5.1f}%)")
    print(f"  High:    {highs:5d} ({highs/total*100:5.1f}%)")

if __name__ == "__main__":
    main()
