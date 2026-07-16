#!/usr/bin/env python3
"""
WebAssembly (Wasm) Binary Inspector

A standalone, zero-dependency parser for WebAssembly (.wasm) binary files.
Parses the Wasm header/version, decodes LEB128 section sizes, lists all Wasm
sections (Type, Import, Function, Memory, Export, Code, etc.), and extracts
exported and imported functions.

Usage:
    python wasm_binary_inspector.py [path_to_wasm_file]
"""

import sys
import os
import argparse

SECTION_NAMES = {
    0: "Custom Section (Names/Debug)",
    1: "Type Section (Signatures)",
    2: "Import Section",
    3: "Function Section (Declarations)",
    4: "Table Section",
    5: "Memory Section",
    6: "Global Section",
    7: "Export Section",
    8: "Start Section",
    9: "Element Section",
    10: "Code Section (Function Bodies)",
    11: "Data Section",
    12: "Data Count Section"
}

def decode_leb128(data, offset):
    """Decodes a variable-length unsigned LEB128 integer from bytes at offset."""
    result = 0
    shift = 0
    start_offset = offset
    while True:
        if offset >= len(data):
            raise ValueError("Unexpected End of File while decoding LEB128.")
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, offset

def read_wasm_string(data, offset):
    """Reads a UTF-8 string prefixed by its LEB128 length."""
    length, offset = decode_leb128(data, offset)
    string_bytes = data[offset:offset+length]
    return string_bytes.decode('utf-8', errors='ignore'), offset + length

def parse_wasm(filepath):
    """Parses a WebAssembly binary file and prints structure/metadata."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        return None
        
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        return None

    # WebAssembly header: magic number \x00asm (0x00 0x61 0x73 0x6D)
    # followed by version 0x01 0x00 0x00 0x00
    if len(data) < 8:
        print("Error: File too small to be a valid Wasm binary.", file=sys.stderr)
        return None

    magic = data[:4]
    version = data[4:8]
    if magic != b'\x00asm':
        print("Error: Invalid Wasm file. Magic number '\\x00asm' not found.", file=sys.stderr)
        return None

    version_num = int.from_bytes(version, byteorder='little')
    print("WebAssembly Binary Inspector")
    print("=" * 65)
    print(f"File Path    : {filepath}")
    print(f"File Size    : {len(data)} bytes")
    print(f"Wasm Version : {version_num}")
    print("=" * 65)

    offset = 8
    sections = []
    exports = []
    imports = []
    signatures = []
    func_types = []

    while offset < len(data):
        try:
            sec_id = data[offset]
            offset += 1
            sec_size, offset = decode_leb128(data, offset)
            sec_payload = data[offset:offset+sec_size]
            
            sections.append({
                'id': sec_id,
                'name': SECTION_NAMES.get(sec_id, f"Unknown ID {sec_id}"),
                'size': sec_size,
                'offset': offset - 1 # starts at the ID byte
            })

            # Parse interesting sections
            if sec_id == 1:  # Type section
                try:
                    p_offset = 0
                    num_types, p_offset = decode_leb128(sec_payload, p_offset)
                    for _ in range(num_types):
                        form = sec_payload[p_offset]
                        p_offset += 1
                        if form == 0x60:  # func type flag
                            num_params, p_offset = decode_leb128(sec_payload, p_offset)
                            params = []
                            for _ in range(num_params):
                                params.append(sec_payload[p_offset])
                                p_offset += 1
                            num_results, p_offset = decode_leb128(sec_payload, p_offset)
                            results = []
                            for _ in range(num_results):
                                results.append(sec_payload[p_offset])
                                p_offset += 1
                            signatures.append((params, results))
                except Exception:
                    pass

            elif sec_id == 2:  # Import section
                try:
                    p_offset = 0
                    num_imports, p_offset = decode_leb128(sec_payload, p_offset)
                    for _ in range(num_imports):
                        mod_name, p_offset = read_wasm_string(sec_payload, p_offset)
                        field_name, p_offset = read_wasm_string(sec_payload, p_offset)
                        kind = sec_payload[p_offset]
                        p_offset += 1
                        
                        kind_name = "Unknown"
                        if kind == 0x00:
                            kind_name = "Function"
                            func_idx, p_offset = decode_leb128(sec_payload, p_offset)
                            imports.append((mod_name, field_name, f"Function (Type Index {func_idx})"))
                        elif kind == 0x01:
                            kind_name = "Table"
                            p_offset += 1 # skip table type
                            imports.append((mod_name, field_name, "Table"))
                        elif kind == 0x02:
                            kind_name = "Memory"
                            p_offset += 1 # skip limits
                            imports.append((mod_name, field_name, "Memory"))
                        elif kind == 0x03:
                            kind_name = "Global"
                            p_offset += 2 # skip global type
                            imports.append((mod_name, field_name, "Global"))
                except Exception:
                    pass

            elif sec_id == 3:  # Function section
                try:
                    p_offset = 0
                    num_funcs, p_offset = decode_leb128(sec_payload, p_offset)
                    for _ in range(num_funcs):
                        idx, p_offset = decode_leb128(sec_payload, p_offset)
                        func_types.append(idx)
                except Exception:
                    pass

            elif sec_id == 7:  # Export section
                try:
                    p_offset = 0
                    num_exports, p_offset = decode_leb128(sec_payload, p_offset)
                    for _ in range(num_exports):
                        name, p_offset = read_wasm_string(sec_payload, p_offset)
                        kind = sec_payload[p_offset]
                        p_offset += 1
                        index, p_offset = decode_leb128(sec_payload, p_offset)
                        
                        kind_name = "Unknown"
                        if kind == 0x00:
                            kind_name = "Function"
                        elif kind == 0x01:
                            kind_name = "Table"
                        elif kind == 0x02:
                            kind_name = "Memory"
                        elif kind == 0x03:
                            kind_name = "Global"
                            
                        exports.append((name, kind_name, index))
                except Exception:
                    pass

            offset += sec_size
        except Exception as e:
            print(f"Error parsing section: {e}", file=sys.stderr)
            break

    # Display Sections list
    print("SECTIONS OVERVIEW")
    print("-" * 65)
    print(f"  {'ID':<4} | {'Section Name':<30} | {'Offset (Hex)':<12} | {'Size (Bytes)':<10}")
    print("  " + "-" * 61)
    for sec in sections:
        print(f"  {sec['id']:<4} | {sec['name']:<30} | 0x{sec['offset']:08X} | {sec['size']:<10}")
    print("-" * 65)

    # Display Type section signatures
    if signatures:
        print("\nFUNCTION SIGNATURES (Type Section)")
        print("-" * 65)
        # Type representations
        val_types = {0x7F: "i32", 0x7E: "i64", 0x7D: "f32", 0x7C: "f64"}
        for idx, (params, results) in enumerate(signatures):
            p_str = ", ".join(val_types.get(p, "unknown") for p in params)
            r_str = ", ".join(val_types.get(r, "unknown") for r in results)
            print(f"  Type {idx:2d} : ({p_str}) -> ({r_str})")
        print("-" * 65)

    # Display Imports
    if imports:
        print("\nIMPORTS")
        print("-" * 65)
        print(f"  {'Module':<15} | {'Field/Name':<20} | {'Kind / Type info'}")
        print("  " + "-" * 61)
        for mod, field, info in imports:
            print(f"  {mod:<15} | {field:<20} | {info}")
        print("-" * 65)

    # Display Exports
    if exports:
        print("\nEXPORTS")
        print("-" * 65)
        print(f"  {'Export Name':<25} | {'Kind':<10} | {'Index (ID)'}")
        print("  " + "-" * 61)
        for name, kind, idx in exports:
            print(f"  {name:<25} | {kind:<10} | {idx}")
        print("-" * 65)

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Inspects WebAssembly (.wasm) binaries and decodes section metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "wasm_file",
        help="Path to the WebAssembly (.wasm) file."
    )
    
    args = parser.parse_args()
    
    success = parse_wasm(args.wasm_file)
    if not success:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
