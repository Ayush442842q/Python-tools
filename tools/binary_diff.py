#!/usr/bin/env python3
"""
Binary Hex Diff - Compares two binary files byte-by-byte and displays
their differences formatted in a highlighted side-by-side hex dump.
"""

import argparse
import os
import sys

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_MODIFIED = "\033[33m"  # Yellow for changed bytes
COLOR_ADDED = "\033[32m"     # Green for additions
COLOR_DELETED = "\033[31m"   # Red for deletions
COLOR_OFFSET = "\033[36m"    # Cyan for offsets


def format_hex_line(offset, block1, block2, colorize=True):
    """Formats a side-by-side hex dump line comparing block1 and block2."""
    max_len = max(len(block1), len(block2))
    
    hex_str1 = []
    hex_str2 = []
    ascii_str1 = []
    ascii_str2 = []
    
    for i in range(16):
        b1 = block1[i] if i < len(block1) else None
        b2 = block2[i] if i < len(block2) else None
        
        # Determine color for this byte comparison
        color = ""
        if colorize:
            if b1 is not None and b2 is not None:
                if b1 != b2:
                    color = COLOR_MODIFIED
            elif b1 is not None:
                color = COLOR_DELETED
            elif b2 is not None:
                color = COLOR_ADDED
        
        # Format File 1 byte
        if b1 is not None:
            h1 = f"{b1:02X}"
            c1 = chr(b1) if 32 <= b1 <= 126 else "."
            if color:
                hex_str1.append(f"{color}{h1}{COLOR_RESET}")
                ascii_str1.append(f"{color}{c1}{COLOR_RESET}")
            else:
                hex_str1.append(h1)
                ascii_str1.append(c1)
        else:
            hex_str1.append("  ")
            ascii_str1.append(" ")
            
        # Format File 2 byte
        if b2 is not None:
            h2 = f"{b2:02X}"
            c2 = chr(b2) if 32 <= b2 <= 126 else "."
            if color:
                hex_str2.append(f"{color}{h2}{COLOR_RESET}")
                ascii_str2.append(f"{color}{c2}{COLOR_RESET}")
            else:
                hex_str2.append(h2)
                ascii_str2.append(c2)
        else:
            hex_str2.append("  ")
            ascii_str2.append(" ")

    # Join elements
    h_part1 = " ".join(hex_str1[:8]) + "  " + " ".join(hex_str1[8:])
    h_part2 = " ".join(hex_str2[:8]) + "  " + " ".join(hex_str2[8:])
    a_part1 = "".join(ascii_str1)
    a_part2 = "".join(ascii_str2)
    
    offset_str = f"{COLOR_OFFSET}{offset:08X}{COLOR_RESET}" if colorize else f"{offset:08X}"
    
    return f"{offset_str}  {h_part1}  |{a_part1}|  vs  {h_part2}  |{a_part2}|"


def main():
    parser = argparse.ArgumentParser(
        description="Compare two binary files and display side-by-side hex differences."
    )
    parser.add_argument("file1", help="First binary file to compare.")
    parser.add_argument("file2", help="Second binary file to compare.")
    parser.add_argument(
        "-m", "--max-diffs", 
        type=int, 
        default=100, 
        help="Maximum number of differences to display before stopping (default: 100)."
    )
    parser.add_argument(
        "--no-color", 
        action="store_true", 
        help="Disable ANSI colored output in output."
    )
    parser.add_argument(
        "-q", "--quiet", 
        action="store_true", 
        help="Quiet mode. Suppress details, exit 0 if identical, 1 if different."
    )

    args = parser.parse_args()

    if not os.path.exists(args.file1):
        print(f"Error: File '{args.file1}' not found.", file=sys.stderr)
        return 2
    if not os.path.exists(args.file2):
        print(f"Error: File '{args.file2}' not found.", file=sys.stderr)
        return 2

    # Check if color is supported / disabled
    colorize = not args.no_color and sys.stdout.isatty()

    diff_count = 0
    identical = True
    offset = 0
    block_size = 16

    try:
        with open(args.file1, "rb") as f1, open(args.file2, "rb") as f2:
            while True:
                b1 = f1.read(block_size)
                b2 = f2.read(block_size)

                if not b1 and not b2:
                    break

                # Check if there is any mismatch in the blocks
                if b1 != b2:
                    identical = False
                    if not args.quiet:
                        print(format_hex_line(offset, b1, b2, colorize))
                        diff_count += 1
                        if args.max_diffs > 0 and diff_count >= args.max_diffs:
                            print(f"\n[Truncated: reached max-diffs limit of {args.max_diffs}]")
                            break

                offset += block_size
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        return 2

    if args.quiet:
        return 0 if identical else 1

    if identical:
        print("Files are identical.")
        return 0
    else:
        print(f"\nFiles differ. Displayed up to {diff_count} difference block(s).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
