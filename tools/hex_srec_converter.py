#!/usr/bin/env python3
"""
Intel HEX / Motorola S-Record Utility

Parses, validates checksums, and converts between Intel HEX (.hex) and
Motorola S-Record (.srec / .s19) firmware formats natively in pure Python.
Also reports memory block maps, base offsets, and sizes.

Usage:
    # Convert S-Record to Intel HEX:
    python hex_srec_converter.py firmware.srec -o firmware.hex

    # Validate and show memory blocks info:
    python hex_srec_converter.py firmware.hex --info
"""

import sys
import os
import argparse

def compute_intel_checksum(bytes_list):
    """Computes the 2's complement checksum for Intel HEX."""
    return (-sum(bytes_list)) & 0xFF

def compute_srec_checksum(bytes_list):
    """Computes the 1's complement checksum for Motorola S-Record."""
    return (~sum(bytes_list)) & 0xFF

def parse_intel_hex(content):
    """
    Parses Intel HEX file content.
    Returns:
        memory_blocks: dict of address -> list of bytes
        start_addr: int or None
        errors: list of strings
    """
    memory = {}
    errors = []
    start_addr = None
    
    # Track the base address for extended linear/segment address records
    base_address = 0
    
    for line_idx, line in enumerate(content.splitlines()):
        line = line.strip()
        if not line:
            continue
        line_num = line_idx + 1
        
        if not line.startswith(':'):
            errors.append(f"Line {line_num}: Invalid start character. Expected ':'.")
            continue
            
        try:
            line_bytes = bytes.fromhex(line[1:])
        except ValueError:
            errors.append(f"Line {line_num}: Non-hexadecimal characters found.")
            continue
            
        if len(line_bytes) < 5:
            errors.append(f"Line {line_num}: Record too short.")
            continue
            
        byte_count = line_bytes[0]
        address = (line_bytes[1] << 8) | line_bytes[2]
        record_type = line_bytes[3]
        data = line_bytes[4:-1]
        checksum = line_bytes[-1]
        
        # Validate length
        if len(data) != byte_count:
            errors.append(f"Line {line_num}: Byte count mismatch. Expected {byte_count}, got {len(data)}.")
            continue
            
        # Validate checksum
        calc_chk = compute_intel_checksum(line_bytes[:-1])
        if calc_chk != checksum:
            errors.append(f"Line {line_num}: Checksum mismatch. Expected {checksum:02X}, got {calc_chk:02X}.")
            continue
            
        # Record Types
        if record_type == 0:  # Data Record
            full_addr = base_address + address
            for i, byte in enumerate(data):
                memory[full_addr + i] = byte
        elif record_type == 1:  # End of File
            break
        elif record_type == 2:  # Extended Segment Address
            if len(data) == 2:
                base_address = ((data[0] << 8) | data[1]) << 4
            else:
                errors.append(f"Line {line_num}: Invalid data length for Extended Segment Address.")
        elif record_type == 4:  # Extended Linear Address
            if len(data) == 2:
                base_address = ((data[0] << 8) | data[1]) << 16
            else:
                errors.append(f"Line {line_num}: Invalid data length for Extended Linear Address.")
        elif record_type in (3, 5):  # Start Segment/Linear Address
            if len(data) == 4:
                start_addr = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
                
    return memory, start_addr, errors

def parse_motorola_srec(content):
    """
    Parses Motorola S-Record file content.
    Returns:
        memory_blocks: dict of address -> list of bytes
        start_addr: int or None
        errors: list of strings
    """
    memory = {}
    errors = []
    start_addr = None
    
    for line_idx, line in enumerate(content.splitlines()):
        line = line.strip()
        if not line:
            continue
        line_num = line_idx + 1
        
        if not line.startswith('S') or len(line) < 4:
            errors.append(f"Line {line_num}: Invalid start character. Expected 'S'.")
            continue
            
        rec_type = line[1]
        try:
            line_bytes = bytes.fromhex(line[2:])
        except ValueError:
            errors.append(f"Line {line_num}: Non-hexadecimal characters found.")
            continue
            
        byte_count = line_bytes[0]
        data_payload = line_bytes[1:]
        
        if len(data_payload) != byte_count:
            errors.append(f"Line {line_num}: Byte count mismatch. Expected {byte_count}, got {len(data_payload)}.")
            continue
            
        # Checksum validation
        calc_chk = compute_srec_checksum(line_bytes[:-1])
        checksum = line_bytes[-1]
        if calc_chk != checksum:
            errors.append(f"Line {line_num}: Checksum mismatch. Expected {checksum:02X}, got {calc_chk:02X}.")
            continue
            
        # Address length depends on record type
        addr_len = 0
        if rec_type in ('0', '1', '9'):
            addr_len = 2
        elif rec_type in ('2', '8'):
            addr_len = 3
        elif rec_type in ('3', '7'):
            addr_len = 4
        else:
            # Skip S5, S6 (count records) or other undefined records
            continue
            
        if len(data_payload) < addr_len + 1:
            errors.append(f"Line {line_num}: Record payload too short for address type.")
            continue
            
        address = 0
        for i in range(addr_len):
            address = (address << 8) | data_payload[i]
            
        data = data_payload[addr_len:-1]
        
        # Record Types
        if rec_type in ('1', '2', '3'):  # Data records
            for i, byte in enumerate(data):
                memory[address + i] = byte
        elif rec_type in ('7', '8', '9'):  # Termination records (start address)
            start_addr = address
            
    return memory, start_addr, errors

def consolidate_memory(memory_dict):
    """Consolidates flat memory dict into contiguous blocks (start_address, bytearray)."""
    if not memory_dict:
        return []
        
    sorted_addrs = sorted(memory_dict.keys())
    blocks = []
    
    curr_start = sorted_addrs[0]
    curr_block = bytearray([memory_dict[curr_start]])
    
    for addr in sorted_addrs[1:]:
        if addr == curr_start + len(curr_block):
            curr_block.append(memory_dict[addr])
        else:
            blocks.append((curr_start, bytes(curr_block)))
            curr_start = addr
            curr_block = bytearray([memory_dict[addr]])
            
    blocks.append((curr_start, bytes(curr_block)))
    return blocks

def write_intel_hex(memory_blocks, start_addr=None):
    """Formats consolidated memory blocks into Intel HEX representation."""
    lines = []
    
    for base_addr, data in memory_blocks:
        # Group data into 16-byte chunks (standard hex line size)
        for chunk_offset in range(0, len(data), 16):
            chunk = data[chunk_offset:chunk_offset+16]
            addr = base_addr + chunk_offset
            
            # If address exceeds 16-bit range (0xFFFF), output an Extended Linear Address (type 04)
            if addr > 0xFFFF:
                ext_addr = (addr >> 16) & 0xFFFF
                payload = [2, 0, 0, 4, (ext_addr >> 8) & 0xFF, ext_addr & 0xFF]
                chk = compute_intel_checksum(payload)
                lines.append(f":02000004{ext_addr:04X}{chk:02X}")
                
            addr_low = addr & 0xFFFF
            payload = [len(chunk), (addr_low >> 8) & 0xFF, addr_low & 0xFF, 0] + list(chunk)
            chk = compute_intel_checksum(payload)
            hex_data = "".join(f"{b:02X}" for b in chunk)
            lines.append(f":{len(chunk):02X}{addr_low:04X}00{hex_data}{chk:02X}")
            
    # Write Start address if available (type 05)
    if start_addr is not None:
        payload = [4, 0, 0, 5, (start_addr >> 24) & 0xFF, (start_addr >> 16) & 0xFF, (start_addr >> 8) & 0xFF, start_addr & 0xFF]
        chk = compute_intel_checksum(payload)
        lines.append(f":04000005{start_addr:08X}{chk:02X}")
        
    # End of File (type 01)
    lines.append(":00000001FF")
    return "\n".join(lines) + "\n"

def write_motorola_srec(memory_blocks, start_addr=0):
    """Formats consolidated memory blocks into Motorola S-Record representation."""
    lines = []
    
    # S0 Header Record
    header_data = b"HDR"
    h_payload = [len(header_data) + 3, 0, 0] + list(header_data)
    chk = compute_srec_checksum(h_payload)
    lines.append(f"S0{len(header_data)+3:02X}0000" + "".join(f"{b:02X}" for b in header_data) + f"{chk:02X}")
    
    record_count = 0
    
    for base_addr, data in memory_blocks:
        # Group into 16-byte chunks
        for chunk_offset in range(0, len(data), 16):
            chunk = data[chunk_offset:chunk_offset+16]
            addr = base_addr + chunk_offset
            record_count += 1
            
            # Determine address size (S1: 16-bit, S2: 24-bit, S3: 32-bit)
            if addr <= 0xFFFF:
                s_type = "S1"
                addr_len = 2
                addr_fmt = f"{addr:04X}"
                addr_bytes = [ (addr >> 8) & 0xFF, addr & 0xFF ]
            elif addr <= 0xFFFFFF:
                s_type = "S2"
                addr_len = 3
                addr_fmt = f"{addr:06X}"
                addr_bytes = [ (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF ]
            else:
                s_type = "S3"
                addr_len = 4
                addr_fmt = f"{addr:08X}"
                addr_bytes = [ (addr >> 24) & 0xFF, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF ]
                
            payload = [len(chunk) + addr_len + 1] + addr_bytes + list(chunk)
            chk = compute_srec_checksum(payload)
            hex_data = "".join(f"{b:02X}" for b in chunk)
            lines.append(f"{s_type}{len(chunk)+addr_len+1:02X}{addr_fmt}{hex_data}{chk:02X}")
            
    # Count record (S5: 16-bit count)
    if record_count <= 0xFFFF:
        payload = [3, (record_count >> 8) & 0xFF, record_count & 0xFF]
        chk = compute_srec_checksum(payload)
        lines.append(f"S503{record_count:04X}{chk:02X}")
        
    # Termination record (S7: 32-bit, S8: 24-bit, S9: 16-bit)
    if start_addr is None:
        start_addr = 0
        
    if start_addr <= 0xFFFF:
        s_type = "S9"
        addr_len = 2
        addr_fmt = f"{start_addr:04X}"
        addr_bytes = [ (start_addr >> 8) & 0xFF, start_addr & 0xFF ]
    elif start_addr <= 0xFFFFFF:
        s_type = "S8"
        addr_len = 3
        addr_fmt = f"{start_addr:06X}"
        addr_bytes = [ (start_addr >> 16) & 0xFF, (start_addr >> 8) & 0xFF, start_addr & 0xFF ]
    else:
        s_type = "S7"
        addr_len = 4
        addr_fmt = f"{start_addr:08X}"
        addr_bytes = [ (start_addr >> 24) & 0xFF, (start_addr >> 16) & 0xFF, (start_addr >> 8) & 0xFF, start_addr & 0xFF ]
        
    payload = [addr_len + 1] + addr_bytes
    chk = compute_srec_checksum(payload)
    lines.append(f"{s_type}{addr_len+1:02X}{addr_fmt}{chk:02X}")
    
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(
        description="Convert and inspect Intel HEX and Motorola S-Record firmware binaries.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "input_file",
        help="Path to the input firmware file."
    )
    
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path to write the converted output file."
    )
    
    parser.add_argument(
        "--format",
        choices=['hex', 'srec'],
        default=None,
        help="Output format choice ('hex' or 'srec'). Auto-detected by default."
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Display parsed memory structure, address blocks, and sizes without converting."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(args.input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{args.input_file}': {e}", file=sys.stderr)
        return 1
        
    # Auto-detect input format
    input_format = None
    stripped = content.strip()
    if stripped.startswith(':'):
        input_format = 'hex'
    elif stripped.startswith('S'):
        input_format = 'srec'
    else:
        print("Error: Could not auto-detect input format. File must start with ':' or 'S'.", file=sys.stderr)
        return 1
        
    print(f"Detected Input Format: {input_format.upper()}")
    
    # Parse input
    if input_format == 'hex':
        memory, start_addr, errors = parse_intel_hex(content)
    else:
        memory, start_addr, errors = parse_motorola_srec(content)
        
    if errors:
        print(f"\n\033[91mErrors parsed during import ({len(errors)}):\033[0m")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more errors.")
        return 1
        
    # Consolidate memory blocks
    blocks = consolidate_memory(memory)
    
    # 1. Info display mode
    if args.info or not args.output:
        print("\n" + "=" * 60)
        print("FIRMWARE MEMORY MAP")
        print("=" * 60)
        if start_addr is not None:
            print(f"Start/Execution Address : 0x{start_addr:08X}")
        else:
            print("Start/Execution Address : Not defined")
            
        print(f"Total Bytes             : {len(memory)} bytes")
        print(f"Memory Blocks Count     : {len(blocks)}")
        print("\nContiguous Memory Segments:")
        print(f"  {'Index':<6} | {'Start Addr':<12} | {'End Addr':<12} | {'Size (Bytes)':<12}")
        print("  " + "-" * 50)
        for idx, (start, data) in enumerate(blocks):
            print(f"  {idx:<6} | 0x{start:08X} | 0x{start+len(data)-1:08X} | {len(data):<12}")
        print("=" * 60)
        
        # If output was not specified, exit here
        if not args.output:
            return 0
            
    # 2. Conversion Mode
    # Determine target format
    target_format = args.format
    if not target_format:
        ext = os.path.splitext(args.output)[1].lower()
        if ext in ('.hex', '.ihex'):
            target_format = 'hex'
        elif ext in ('.srec', '.s19', '.s28', '.s37', '.mot'):
            target_format = 'srec'
        else:
            # Fallback to opposite of input format
            target_format = 'srec' if input_format == 'hex' else 'hex'
            
    print(f"Converting to target format: {target_format.upper()}")
    
    if target_format == 'hex':
        out_content = write_intel_hex(blocks, start_addr)
    else:
        out_content = write_motorola_srec(blocks, start_addr)
        
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(out_content)
        print(f"Successfully wrote converted output to: {args.output}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
