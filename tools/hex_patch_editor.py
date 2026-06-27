#!/usr/bin/env python3
"""
Hex & Binary Patch Editor
A command-line utility to view, search, and patch binary files.
Supports custom hex dumps, byte searching (hex and ASCII), and byte-level modifying with safety backups.
"""

import os
import sys
import argparse
import re

def parse_int(val):
    """Parse integer value that may be specified in decimal or hexadecimal (with 0x prefix)."""
    if not val:
        return 0
    val_str = str(val).strip()
    if val_str.lower().startswith('0x'):
        return int(val_str, 16)
    return int(val_str)

def format_hex_dump(data, start_offset=0, bytes_per_line=16):
    """Generate a formatted hex dump string for binary data."""
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i + bytes_per_line]
        offset = start_offset + i
        
        # Hex representation
        hex_parts = []
        for j, b in enumerate(chunk):
            hex_parts.append(f"{b:02X}")
            if j == (bytes_per_line // 2) - 1:
                hex_parts.append(" ") # Extra spacer in middle
        hex_str = " ".join(hex_parts)
        
        # Pad hex representation to keep ASCII column aligned
        expected_len = (bytes_per_line * 3) + (1 if bytes_per_line > 8 else 0) - 1
        hex_str = hex_str.ljust(expected_len)
        
        # ASCII representation
        ascii_parts = []
        for b in chunk:
            if 32 <= b <= 126:
                ascii_parts.append(chr(b))
            else:
                ascii_parts.append(".")
        ascii_str = "".join(ascii_parts)
        
        lines.append(f"{offset:08X}:  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)

def search_pattern(file_path, pattern, is_hex=True, max_results=50):
    """Search for a hex or ASCII pattern in a binary file."""
    if is_hex:
        # Normalize hex string: remove spaces, convert to lowercase hex bytes
        clean_pat = re.sub(r'[\s,.-]', '', pattern)
        if len(clean_pat) % 2 != 0:
            raise ValueError("Hex pattern must consist of full bytes (even number of characters).")
        try:
            search_bytes = bytes.fromhex(clean_pat)
        except ValueError as e:
            raise ValueError(f"Invalid hex characters in search pattern: {e}")
    else:
        search_bytes = pattern.encode('utf-8', errors='ignore')

    if not search_bytes:
        raise ValueError("Search pattern is empty.")

    print(f"Searching for: {' '.join(f'{b:02X}' for b in search_bytes)}")
    print(f"File: {file_path}\n")

    chunk_size = 1024 * 1024  # 1MB chunks
    overlap = len(search_bytes) - 1
    offset = 0
    results_found = 0

    with open(file_path, 'rb') as f:
        buffer = b''
        while True:
            new_chunk = f.read(chunk_size)
            if not new_chunk and not buffer:
                break
            
            buffer = buffer + new_chunk
            
            # Find occurrences in current buffer
            search_idx = 0
            while True:
                idx = buffer.find(search_bytes, search_idx)
                if idx == -1:
                    break
                
                absolute_offset = offset + idx
                print(f"Match found at offset: 0x{absolute_offset:X} ({absolute_offset} bytes)")
                results_found += 1
                if results_found >= max_results:
                    print(f"\nLimit of {max_results} results reached. Stopping search.")
                    return results_found
                
                search_idx = idx + 1
                
            # Retain overlap to handle patterns crossing the boundary
            if len(buffer) > overlap:
                offset += len(buffer) - overlap
                buffer = buffer[-overlap:]
            else:
                buffer = b''
                
    if results_found == 0:
        print("No matches found.")
    else:
        print(f"\nTotal matches found: {results_found}")
    return results_found

def cmd_dump(args):
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    try:
        offset = parse_int(args.offset)
        length = parse_int(args.length)
        cols = args.columns
        
        file_size = os.path.getsize(file_path)
        if offset >= file_size:
            print(f"Error: Start offset 0x{offset:X} ({offset}) is beyond file size (0x{file_size:X} / {file_size} bytes).")
            return 1

        with open(file_path, 'rb') as f:
            f.seek(offset)
            data = f.read(length)
            
        print(f"Hex Dump of: {file_path}")
        print(f"File size: {file_size} bytes")
        print(f"Showing {len(data)} bytes starting at offset 0x{offset:X}\n")
        print(format_hex_dump(data, start_offset=offset, bytes_per_line=cols))
        
    except ValueError as e:
        print(f"Error parsing offset, length, or columns: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_search(args):
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    if args.hex and args.ascii:
        print("Error: Specify either --hex or --ascii, not both.")
        return 1
    if not args.hex and not args.ascii:
        print("Error: Must specify a search pattern using --hex or --ascii.")
        return 1

    try:
        pattern = args.hex if args.hex else args.ascii
        is_hex = True if args.hex else False
        search_pattern(file_path, pattern, is_hex=is_hex, max_results=args.limit)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_patch(args):
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    if args.hex and args.ascii:
        print("Error: Specify either --hex or --ascii, not both.")
        return 1
    if not args.hex and not args.ascii:
        print("Error: Must specify patch data using --hex or --ascii.")
        return 1

    try:
        offset = parse_int(args.offset)
        file_size = os.path.getsize(file_path)
        if offset >= file_size:
            print(f"Error: Offset 0x{offset:X} ({offset}) is beyond file size ({file_size} bytes).")
            return 1

        # Parse replacement bytes
        if args.hex:
            clean_pat = re.sub(r'[\s,.-]', '', args.hex)
            if len(clean_pat) % 2 != 0:
                print("Error: Hex string must represent complete bytes (even number of characters).")
                return 1
            patch_bytes = bytes.fromhex(clean_pat)
        else:
            patch_bytes = args.ascii.encode('utf-8')

        if not patch_bytes:
            print("Error: Patch data is empty.")
            return 1

        end_offset = offset + len(patch_bytes)
        if end_offset > file_size:
            if not args.extend:
                print(f"Warning: Patch size ({len(patch_bytes)} bytes) would extend the file size.")
                confirm = input("Are you sure you want to grow the file? (y/N): ").strip().lower()
                if confirm != 'y':
                    print("Patch aborted.")
                    return 1

        # Create safety backup
        if not args.no_backup:
            backup_path = file_path + ".bak"
            print(f"Creating backup file: {backup_path}")
            try:
                import shutil
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                print(f"Error creating backup: {e}. Aborting patch.")
                return 1

        # Perform patching
        with open(file_path, 'r+b') as f:
            f.seek(offset)
            f.write(patch_bytes)

        print(f"Successfully patched {len(patch_bytes)} bytes at offset 0x{offset:X} ({offset})")
        
    except ValueError as e:
        print(f"Error: Invalid numbers or hex format. {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

def main():
    parser = argparse.ArgumentParser(description="Hex & Binary Patch Editor")
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)

    # Dump subcommand
    dump_parser = subparsers.add_parser("dump", help="Generate a hex dump of a binary file")
    dump_parser.add_argument("file", help="Path to the binary file")
    dump_parser.add_argument("-o", "--offset", default="0", help="Starting offset to dump (decimal or hex, e.g. 100 or 0x64)")
    dump_parser.add_argument("-l", "--length", default="256", help="Number of bytes to dump (decimal or hex, e.g. 512 or 0x200)")
    dump_parser.add_argument("-c", "--columns", type=int, default=16, help="Number of bytes per row in output (default: 16)")

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search for byte sequences in a binary file")
    search_parser.add_argument("file", help="Path to the binary file")
    search_parser.add_argument("-x", "--hex", help="Hex string to search for (e.g. 'E8 C2 05 00')")
    search_parser.add_argument("-a", "--ascii", help="ASCII string to search for")
    search_parser.add_argument("--limit", type=int, default=50, help="Maximum number of search results to display")

    # Patch subcommand
    patch_parser = subparsers.add_parser("patch", help="Modify specific bytes of a binary file")
    patch_parser.add_argument("file", help="Path to the binary file")
    patch_parser.add_argument("-o", "--offset", required=True, help="Target offset to write the patch (decimal or hex, e.g. 0x1A0)")
    patch_parser.add_argument("-x", "--hex", help="Hex string to patch in (e.g. '90 90 90')")
    patch_parser.add_argument("-a", "--ascii", help="ASCII text to patch in")
    patch_parser.add_argument("--extend", action="store_true", help="Allow patch to extend the file size without prompting")
    patch_parser.add_argument("--no-backup", action="store_true", help="Skip creating a backup .bak file before patching")

    args = parser.parse_args()

    if args.command == "dump":
        sys.exit(cmd_dump(args))
    elif args.command == "search":
        sys.exit(cmd_search(args))
    elif args.command == "patch":
        sys.exit(cmd_patch(args))

if __name__ == '__main__':
    main()
