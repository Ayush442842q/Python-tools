#!/usr/bin/env python3
"""Binary Struct Parser

Parse arbitrary binary files using a C-style struct definition or JSON format,
unpacking variables, offsets, raw hex bytes, and formatted values.
"""

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

# Type mappings: (struct_code, size, description)
TYPE_MAP = {
    "char": ("c", 1, "Character"),
    "int8": ("b", 1, "Signed 8-bit Integer"),
    "uint8": ("B", 1, "Unsigned 8-bit Integer"),
    "byte": ("B", 1, "Unsigned 8-bit Integer"),
    "int16": ("h", 2, "Signed 16-bit Integer"),
    "uint16": ("H", 2, "Unsigned 16-bit Integer"),
    "int32": ("i", 4, "Signed 32-bit Integer"),
    "uint32": ("I", 4, "Unsigned 32-bit Integer"),
    "int64": ("q", 8, "Signed 64-bit Integer"),
    "uint64": ("Q", 8, "Unsigned 64-bit Integer"),
    "float": ("f", 4, "Single-precision Float"),
    "double": ("d", 8, "Double-precision Float"),
}


class StructField:
    def __init__(self, name: str, data_type: str, count: int = 1):
        self.name = name
        self.data_type = data_type
        self.count = count  # For arrays (e.g. char[4] or uint32[10])


def parse_c_struct(definition: str) -> List[StructField]:
    """Parse simple C-style struct bodies into StructField objects."""
    # Strip comments and clean up whitespace
    cleaned = re.sub(r"//.*", "", definition)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Find the struct fields inside curly braces if they exist, otherwise parse directly
    match_braces = re.search(r"struct\s+\w+\s*\{(.*?)\}", cleaned, flags=re.DOTALL)
    fields_content = match_braces.group(1) if match_braces else cleaned

    fields = []
    # Match pattern: type name[count]; or type name;
    # E.g. "uint32 magic;" or "char signature[4];"
    pattern = re.compile(r"([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)(?:\[(\d+)\])?\s*;")
    for m in pattern.finditer(fields_content):
        d_type, name, count_str = m.groups()
        count = int(count_str) if count_str else 1
        fields.append(StructField(name, d_type, count))
        
    return fields


def parse_json_struct(definition: str) -> List[StructField]:
    """Parse JSON array of field configurations into StructField objects."""
    data = json.loads(definition)
    if not isinstance(data, list):
        raise ValueError("JSON struct definition must be an array of fields")
        
    fields = []
    for item in data:
        name = item.get("name")
        d_type = item.get("type")
        count = item.get("count", 1)
        if not name or not d_type:
            raise ValueError("Each JSON field must contain 'name' and 'type' keys")
        fields.append(StructField(name, d_type, count))
        
    return fields


def build_struct_format(fields: List[StructField], endian: str) -> Tuple[str, int]:
    """Compile fields list into a struct format string and calculate cumulative size."""
    fmt = endian
    size = 0
    for field in fields:
        d_type = field.data_type
        
        # Check standard types
        if d_type in TYPE_MAP:
            code, t_size, _ = TYPE_MAP[d_type]
            if field.count > 1:
                # E.g. char[4] is parsed as "4s" for strings, or "4I" for uint32 array
                if code == "c":
                    fmt += f"{field.count}s"
                    size += field.count
                else:
                    fmt += f"{field.count}{code}"
                    size += t_size * field.count
            else:
                fmt += code
                size += t_size
        else:
            raise ValueError(f"Unknown data type: {d_type}")
            
    return fmt, size


def unpack_and_format(
    fields: List[StructField],
    fmt: str,
    data: bytes,
    offset: int
) -> List[Dict[str, Any]]:
    """Unpack raw binary bytes using structure layout and return detailed report list."""
    unpacked_vals = struct.unpack_from(fmt, data, offset)
    
    results = []
    val_idx = 0
    current_offset = offset
    
    for field in fields:
        d_type = field.data_type
        code, t_size, _ = TYPE_MAP.get(d_type, ("s", 1, ""))
        
        field_size = t_size * field.count
        raw_bytes = data[current_offset:current_offset + field_size]
        
        # Resolve value(s) from unpacked tuple
        if field.count > 1:
            if code == "c":  # String/Char array
                val = unpacked_vals[val_idx]
                # Try decoding string
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="ignore").rstrip("\x00")
                val_idx += 1
            else:
                val = list(unpacked_vals[val_idx:val_idx + field.count])
                val_idx += field.count
        else:
            val = unpacked_vals[val_idx]
            if isinstance(val, bytes) and code == "c":
                val = val.decode("utf-8", errors="ignore")
            val_idx += 1
            
        results.append({
            "name": field.name,
            "type": f"{d_type}[{field.count}]" if field.count > 1 else d_type,
            "offset": current_offset,
            "raw": raw_bytes,
            "value": val
        })
        
        current_offset += field_size
        
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Binary Struct Parser - Parses binary files based on C-style/JSON layout rules."
    )
    parser.add_argument("binary_file", help="Path to the binary file to analyze")
    parser.add_argument("struct_def", help="Path to the struct definition file (.h, .c, or .json)")
    parser.add_argument(
        "-o", "--offset",
        type=int,
        default=0,
        help="Offset in bytes to start parsing from (default: 0)"
    )
    parser.add_argument(
        "-e", "--endian",
        choices=["little", "big", "native"],
        default="little",
        help="Endianness of the structure (default: little)"
    )
    parser.add_argument(
        "--json-out",
        action="store_true",
        help="Output results as JSON"
    )
    args = parser.parse_args()

    bin_path = Path(args.binary_file).resolve()
    def_path = Path(args.struct_def).resolve()

    if not bin_path.exists():
        print(f"{COLOR_RED}Error: Binary file '{bin_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
    if not def_path.exists():
        print(f"{COLOR_RED}Error: Struct definition '{def_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Read binary file
    try:
        with open(bin_path, "rb") as f:
            bin_data = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading binary file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Read struct definition
    try:
        with open(def_path, "r", encoding="utf-8", errors="ignore") as f:
            def_content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading struct definition: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Parse fields
    try:
        if def_path.suffix.lower() == ".json":
            fields = parse_json_struct(def_content)
        else:
            fields = parse_c_struct(def_content)
    except Exception as e:
        print(f"{COLOR_RED}Error parsing struct definition: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    if not fields:
        print(f"{COLOR_RED}Error: No valid struct fields identified in the definition.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Map endian character
    endian_char = {"little": "<", "big": ">", "native": "@"}[args.endian]

    # Build layout
    try:
        fmt, expected_size = build_struct_format(fields, endian_char)
    except ValueError as e:
        print(f"{COLOR_RED}Layout compilation error: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Verify size
    if args.offset + expected_size > len(bin_data):
        print(
            f"{COLOR_RED}Error: Layout size ({expected_size} bytes) from offset {args.offset} exceeds binary file size ({len(bin_data)} bytes).{COLOR_RESET}",
            file=sys.stderr
        )
        sys.exit(1)

    # Unpack values
    try:
        results = unpack_and_format(fields, fmt, bin_data, args.offset)
    except Exception as e:
        print(f"{COLOR_RED}Error unpacking binary data: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Output formatting
    if args.json_out:
        # Prep results for JSON dump
        json_results = []
        for r in results:
            json_results.append({
                "name": r["name"],
                "type": r["type"],
                "offset": r["offset"],
                "raw_hex": r["raw"].hex(),
                "value": r["value"]
            })
        print(json.dumps(json_results, indent=4))
        sys.exit(0)

    # Print terminal report
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Binary Structure Layout Report ==={COLOR_RESET}\n")
    print(f"{COLOR_BOLD}Binary File:{COLOR_RESET} {bin_path.name}")
    print(f"{COLOR_BOLD}Definition: {COLOR_RESET} {def_path.name}")
    print(f"{COLOR_BOLD}Endianness: {COLOR_RESET} {args.endian}")
    print(f"{COLOR_BOLD}Unpacked Size:{COLOR_RESET} {expected_size} bytes (From offset: {args.offset})\n")

    col_off = "Offset (Hex)"
    col_name = "Field Name"
    col_type = "Data Type"
    col_hex = "Raw Bytes (Hex)"
    col_val = "Parsed Value"

    w_off = len(col_off)
    w_name = max(max(len(r["name"]) for r in results), len(col_name))
    w_type = max(max(len(r["type"]) for r in results), len(col_type))
    w_hex = max(max(len(r["raw"].hex()) for r in results), len(col_hex))

    # Print table header
    header = f"{COLOR_BOLD}{col_off:<{w_off}} | {col_name:<{w_name}} | {col_type:<{w_type}} | {col_hex:<{w_hex}} | {col_val}{COLOR_RESET}"
    divider = "-" * w_off + "+" + "-" * (w_name + 2) + "+" + "-" * (w_type + 2) + "+" + "-" * (w_hex + 2) + "+" + "-" * 20
    print(header)
    print(divider)

    for r in results:
        off_str = f"0x{r['offset']:08X} ({r['offset']})"
        name_str = f"{COLOR_CYAN}{r['name']:<{w_name}}{COLOR_RESET}"
        type_str = f"{COLOR_GREEN}{r['type']:<{w_type}}{COLOR_RESET}"
        raw_hex_str = f"{COLOR_GREY}{r['raw'].hex():<{w_hex}}{COLOR_RESET}"
        
        # Colorize values depending on types
        val = r["value"]
        if isinstance(val, int):
            val_str = f"{COLOR_YELLOW}{val}{COLOR_RESET}"
        elif isinstance(val, float):
            val_str = f"{COLOR_YELLOW}{val:.6f}{COLOR_RESET}"
        elif isinstance(val, str):
            val_str = f"{COLOR_BLUE}\"{val}\"{COLOR_RESET}"
        else:
            val_str = str(val)

        print(f"{off_str:<{w_off}} | {name_str} | {type_str} | {raw_hex_str} | {val_str}")
    print()


if __name__ == "__main__":
    main()
