#!/usr/bin/env python3
"""
Hex Dumper (xxd equivalent)
A bidirectional command-line tool that generates formatted hex dumps from binary files
and reconstructs the original binary files from formatted hex dump files.
Supports colorized output, customizable grouping, seeking, and length limits.
"""

import argparse
import sys
import os
import re

# ANSI Color Codes
COLOR_OFFSET = "\033[90m"     # Dark Grey
COLOR_HEX_EVEN = "\033[36m"   # Cyan
COLOR_HEX_ODD = "\033[34m"    # Blue
COLOR_ASCII = "\033[92m"      # Light Green
COLOR_RESET = "\033[0m"


def dump_hex(infile_path, outfile_path=None, seek=0, length=None, columns=16, group_by=1, color=False):
    """Generates hex dump of infile_path and outputs it."""
    if not os.path.exists(infile_path):
        print(f"Error: Input file '{infile_path}' not found.", file=sys.stderr)
        return 1

    try:
        with open(infile_path, 'rb') as f:
            if seek > 0:
                f.seek(seek)
            
            # If length is specified, read only that amount, otherwise read everything
            if length is not None:
                data = f.read(length)
            else:
                data = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1

    out_lines = []
    total_bytes = len(data)
    offset = seek

    for i in range(0, total_bytes, columns):
        chunk = data[i:i + columns]
        
        # 1. Format offset
        offset_str = f"{offset:08x}"
        if color:
            offset_str = f"{COLOR_OFFSET}{offset_str}{COLOR_RESET}"
            
        # 2. Format hex bytes
        hex_parts = []
        for j, byte in enumerate(chunk):
            byte_str = f"{byte:02x}"
            if color:
                clr = COLOR_HEX_EVEN if (j // group_by) % 2 == 0 else COLOR_HEX_ODD
                byte_str = f"{clr}{byte_str}{COLOR_RESET}"
            hex_parts.append(byte_str)
            
        # Insert grouping spaces
        hex_grouped = []
        for j in range(0, len(hex_parts), group_by):
            hex_grouped.append("".join(hex_parts[j:j + group_by]))
        hex_str = " ".join(hex_grouped)
        
        # Calculate padding space for hex columns
        # Each byte is 2 hex chars. Plus (columns / group_by - 1) spaces if full.
        full_width_hex_chars = columns * 2
        full_width_spaces = (columns + group_by - 1) // group_by - 1
        expected_width = full_width_hex_chars + full_width_spaces
        
        # If we have color codes, len(hex_str) will be larger, so calculate length without colors
        actual_chars_len = len(chunk) * 2 + (len(chunk) + group_by - 1) // group_by - 1
        padding = " " * (expected_width - actual_chars_len)
        
        # 3. Format ASCII representation
        ascii_parts = []
        for byte in chunk:
            if 32 <= byte <= 126:
                char = chr(byte)
            else:
                char = "."
            if color:
                char = f"{COLOR_ASCII}{char}{COLOR_RESET}"
            ascii_parts.append(char)
        ascii_str = "".join(ascii_parts)
        
        # Combine line
        line = f"{offset_str}: {hex_str}{padding}  |{ascii_str}|"
        out_lines.append(line)
        offset += columns

    output_text = "\n".join(out_lines) + "\n"

    if outfile_path:
        try:
            with open(outfile_path, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(f"Hex dump written to '{outfile_path}'.")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(output_text)
        
    return 0


def restore_hex(infile_path, outfile_path):
    """Reconstructs original binary file from a formatted hex dump file."""
    if not os.path.exists(infile_path):
        print(f"Error: Input hex dump file '{infile_path}' not found.", file=sys.stderr)
        return 1

    try:
        with open(infile_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading hex dump file: {e}", file=sys.stderr)
        return 1

    binary_data = bytearray()
    
    # Matches: [optional whitespace] [hex offset]: [hex bytes (whitespace/grouping allowed)] [spaces] |[ASCII]|
    # We care primarily about everything between ':' and '|' (or end of line if no '|' is present)
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        # Strip ANSI colors if any exist
        line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        
        if ':' not in line:
            continue
            
        parts = line.split(':', 1)
        content = parts[1]
        
        # If there is a '|' bar separating ASCII, drop the ASCII part
        if '|' in content:
            hex_part = content.split('|', 1)[0]
        else:
            hex_part = content
            
        # Extract valid hex sequences
        hex_digits = re.findall(r'[0-9a-fA-F]', hex_part)
        if len(hex_digits) % 2 != 0:
            print(f"Warning: Line {line_num} has an odd number of hex digits. Ignoring the trailing digit.", file=sys.stderr)
            hex_digits = hex_digits[:-1]
            
        for k in range(0, len(hex_digits), 2):
            byte_hex = hex_digits[k] + hex_digits[k+1]
            binary_data.append(int(byte_hex, 16))

    try:
        with open(outfile_path, 'wb') as f:
            f.write(binary_data)
        print(f"Binary file successfully restored to '{outfile_path}' ({len(binary_data)} bytes).")
    except Exception as e:
        print(f"Error writing restored binary file: {e}", file=sys.stderr)
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Hex Dumper - View binary files as formatted hex or restore binary from hex."
    )
    parser.add_argument(
        'infile',
        help="Input file path (binary file to dump, or hex dump file to restore)"
    )
    parser.add_argument(
        'outfile', nargs='?',
        help="Output file path (prints to stdout if omitted for dump; required for restore)"
    )
    parser.add_argument(
        '-r', '--reverse', action='store_true',
        help="Reverse operation: restore binary file from hex dump"
    )
    parser.add_argument(
        '-s', '--seek', type=int, default=0,
        help="Byte offset to start dumping from (default: 0)"
    )
    parser.add_argument(
        '-n', '--length', type=int,
        help="Number of bytes to dump"
    )
    parser.add_argument(
        '-c', '--columns', type=int, default=16,
        help="Number of hex columns/bytes per line (default: 16)"
    )
    parser.add_argument(
        '-g', '--group', type=int, default=1,
        help="Number of bytes to group together (default: 1)"
    )
    parser.add_argument(
        '--color', action='store_true',
        help="Enable ANSI color highlights in terminal output"
    )

    args = parser.parse_args()

    # Validations
    if args.columns <= 0:
        print("Error: Columns must be a positive integer.", file=sys.stderr)
        return 1
    if args.group <= 0 or args.columns % args.group != 0:
        print("Error: Group size must divide columns size evenly.", file=sys.stderr)
        return 1
    if args.seek < 0:
        print("Error: Seek offset must be non-negative.", file=sys.stderr)
        return 1

    if args.reverse:
        if not args.outfile:
            print("Error: Reversing a hex dump requires an output file path.", file=sys.stderr)
            return 1
        return restore_hex(args.infile, args.outfile)
    else:
        return dump_hex(
            infile_path=args.infile,
            outfile_path=args.outfile,
            seek=args.seek,
            length=args.length,
            columns=args.columns,
            group_by=args.group,
            color=args.color
        )


if __name__ == "__main__":
    sys.exit(main())
