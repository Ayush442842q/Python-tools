#!/usr/bin/env python3
"""
Mach-O Binary Inspector

A standalone, zero-dependency parser for macOS Mach-O executable and library files.
Natively parses Mach-O headers, detects FAT (universal) binary slices, translates
CPU types, mapping loading commands and segments.

Usage:
    python macho_binary_inspector.py [path_to_macho_file]
"""

import sys
import os
import argparse
import struct

# Magic number signatures
MH_MAGIC = 0xfeedface      # 32-bit little endian
MH_CIGAM = 0xcefaedfe      # 32-bit big endian
MH_MAGIC_64 = 0xfeedfacf   # 64-bit little endian
MH_CIGAM_64 = 0xcffaedfe   # 64-bit big endian
FAT_MAGIC = 0xcafebabe     # FAT little/big endian (usually big-endian)
FAT_CIGAM = 0xbebafeca

CPU_TYPES = {
    0x00000007: "x86",
    0x01000007: "x86_64",
    0x0000000c: "ARM",
    0x0100000c: "ARM64",
    0x00000012: "PowerPC",
    0x01000012: "PowerPC64"
}

FILE_TYPES = {
    1: "Object File (.o)",
    2: "Executable",
    3: "VM Shared Memory",
    4: "Core Dump",
    5: "Dynamic Shared Library (.dylib)",
    6: "Dynamic Linker Editor",
    7: "Dynamic Linker Bundle",
    8: "Static Library (stub)",
    9: "Debug Directory (.dSYM)",
    10: "Kext Bundle"
}

LOAD_COMMAND_TYPES = {
    0x1: "LC_SEGMENT",
    0x2: "LC_SYMTAB",
    0x4: "LC_THREAD",
    0xb: "LC_DYSYMTAB",
    0xc: "LC_LOAD_DYLIB",
    0xe: "LC_ID_DYLINKER",
    0x11: "LC_ROUTINES",
    0x19: "LC_SEGMENT_64",
    0x1d: "LC_UUID",
    0x20: "LC_LAZY_LOAD_DYLIB",
    0x22: "LC_DYLD_INFO_ONLY",
    0x25: "LC_VERSION_MIN_MACOSX",
    0x29: "LC_SOURCE_VERSION",
    0x2a: "LC_MAIN",
    0x2e: "LC_BUILD_VERSION"
}

def parse_header(data, offset=0):
    """Parses a single Mach-O header from data at offset."""
    if len(data) < offset + 28:
        return None, "File too small for Mach-O header."
        
    magic = struct.unpack_from("<I", data, offset)[0]
    
    # Determine endianness and bits
    is_64 = False
    is_swap = False
    
    if magic in (MH_MAGIC, MH_MAGIC_64):
        is_swap = False
        is_64 = (magic == MH_MAGIC_64)
    elif magic in (MH_CIGAM, MH_CIGAM_64):
        is_swap = True
        is_64 = (magic == MH_CIGAM_64)
    else:
        return None, f"Invalid magic signature: 0x{magic:08X}"
        
    fmt = ">" if is_swap else "<"
    header_len = 32 if is_64 else 28
    
    if len(data) < offset + header_len:
        return None, "Truncated Mach-O header."
        
    # Read header fields
    # uint32 magic, int32 cputype, int32 cpusubtype, uint32 filetype,
    # uint32 ncmds, uint32 sizeofcmds, uint32 flags, (uint32 reserved for 64-bit)
    if is_64:
        magic, cpu, sub, ftype, ncmds, sizecmds, flags, reserved = struct.unpack_from(fmt + "IIIIIIII", data, offset)
    else:
        magic, cpu, sub, ftype, ncmds, sizecmds, flags = struct.unpack_from(fmt + "IIIIIII", data, offset)
        
    return {
        'magic': magic,
        'cputype': CPU_TYPES.get(cpu, f"Unknown ({cpu})"),
        'filetype': FILE_TYPES.get(ftype, f"Unknown ({ftype})"),
        'ncmds': ncmds,
        'sizeofcmds': sizecmds,
        'flags': f"0x{flags:08X}",
        'is_64': is_64,
        'swap': is_swap,
        'header_len': header_len
    }, None

def parse_macho_slices(data):
    """Identifies and decodes Mach-O slices (handles FAT/Universal binaries)."""
    if len(data) < 8:
        return [], "File too small to check signature."
        
    magic = struct.unpack_from(">I", data, 0)[0]
    
    # Check if this is a FAT binary
    if magic in (FAT_MAGIC, FAT_CIGAM):
        is_swap = (magic == FAT_CIGAM)
        fmt = "<" if is_swap else ">"
        
        num_archs = struct.unpack_from(fmt + "I", data, 4)[0]
        slices = []
        offset = 8
        
        for i in range(num_archs):
            if offset + 20 > len(data):
                break
            cpu, sub, arch_offset, size, align = struct.unpack_from(fmt + "IIIII", data, offset)
            
            slice_hdr, err = parse_header(data, arch_offset)
            slices.append({
                'index': i,
                'cpu': CPU_TYPES.get(cpu, f"Unknown ({cpu})"),
                'offset': arch_offset,
                'size': size,
                'header': slice_hdr,
                'error': err
            })
            offset += 20
            
        return slices, None
    else:
        # Single Mach-O binary
        slice_hdr, err = parse_header(data, 0)
        if err:
            return [], err
        return [{
            'index': 0,
            'cpu': slice_hdr['cputype'],
            'offset': 0,
            'size': len(data),
            'header': slice_hdr,
            'error': None
        }], None

def decode_load_commands(data, offset, header):
    """Loops through Mach-O load commands and extracts metadata."""
    is_64 = header['is_64']
    is_swap = header['swap']
    fmt = ">" if is_swap else "<"
    
    ncmds = header['ncmds']
    curr_offset = offset + header['header_len']
    
    commands = []
    
    for _ in range(ncmds):
        if curr_offset + 8 > len(data):
            break
        cmd_type, cmd_size = struct.unpack_from(fmt + "II", data, curr_offset)
        cmd_name = LOAD_COMMAND_TYPES.get(cmd_type, f"Unknown (0x{cmd_type:X})")
        
        cmd_info = {
            'type': cmd_name,
            'size': cmd_size,
            'offset': curr_offset
        }
        
        # Segment parsing helper
        if cmd_type in (0x1, 0x19):  # LC_SEGMENT (0x1), LC_SEGMENT_64 (0x19)
            seg_fmt = "16sIIIIIIII" if cmd_type == 0x1 else "16sQQQQIIII"
            seg_len = struct.calcsize(fmt + seg_fmt)
            
            if curr_offset + 8 + seg_len <= len(data):
                seg_fields = struct.unpack_from(fmt + seg_fmt, data, curr_offset + 8)
                segname = seg_fields[0].rstrip(b'\x00').decode('utf-8', errors='ignore')
                cmd_info['segment_name'] = segname
                
        commands.append(cmd_info)
        curr_offset += cmd_size
        
    return commands

def main():
    parser = argparse.ArgumentParser(
        description="Inspect Mach-O headers, FAT architectures, and load commands natively.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("binary_file", help="Path to the Mach-O binary file.")
    args = parser.parse_args()

    if not os.path.exists(args.binary_file):
        print(f"Error: File '{args.binary_file}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(args.binary_file, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    slices, err = parse_macho_slices(data)
    if err:
        print(f"Error parsing Mach-O slices: {err}", file=sys.stderr)
        return 1

    print("Mach-O Binary Inspector")
    print("=" * 70)
    print(f"File Path    : {args.binary_file}")
    print(f"File Size    : {len(data)} bytes")
    print(f"Universal/FAT: {'Yes' if len(slices) > 1 else 'No'}")
    print("=" * 70)

    for sl in slices:
        print(f"\nArchitecture Slice [{sl['index']}]: {sl['cpu']}")
        print(f"  File Offset : {sl['offset']} bytes")
        print(f"  Segment Size: {sl['size']} bytes")
        
        if sl['error']:
            print(f"  Error       : {sl['error']}")
            continue
            
        hdr = sl['header']
        print(f"  File Type   : {hdr['filetype']}")
        print(f"  Endianness  : {'Big Endian' if hdr['swap'] else 'Little Endian'}")
        print(f"  Format      : {'64-bit' if hdr['is_64'] else '32-bit'}")
        print(f"  Load Cmds   : {hdr['ncmds']} commands ({hdr['sizeofcmds']} bytes)")

        # Parse and print load commands
        cmds = decode_load_commands(data, sl['offset'], hdr)
        print("\n  [Load Commands]")
        print("  " + "-" * 62)
        print(f"    {'Command Name':<28} | {'Size (Bytes)':<12} | {'Offset (Hex)':<12}")
        print("    " + "-" * 58)
        for cmd in cmds:
            seg_desc = f" [{cmd['segment_name']}]" if 'segment_name' in cmd else ""
            print(f"    {cmd['type'] + seg_desc:<28} | {cmd['size']:<12} | 0x{cmd['offset']:08X}")
            
    print("\n" + "=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(main())
