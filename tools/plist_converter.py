#!/usr/bin/env python3
"""
plist_converter - Apple Property List (.plist) Converter

Converts Apple Property List (.plist) files between XML/Binary plist format and
JSON or YAML. Natively handles both XML and Binary formats of plist files.

Usage:
    # Convert plist to JSON
    python tools/plist_converter.py -i input.plist -o output.json

    # Convert JSON to binary plist
    python tools/plist_converter.py -i input.json -o output.plist --format binary

    # Convert plist to YAML (requires PyYAML)
    python tools/plist_converter.py -i input.plist -o output.yaml
"""

import argparse
import datetime
import json
import os
import plistlib
import sys

# Optional YAML import
HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass


class PlistEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle bytes and datetime objects commonly found in plists."""
    def default(self, obj):
        if isinstance(obj, bytes):
            return {"__bytes_hex__": obj.hex()}
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


def decode_custom_types(dct):
    """Helper to decode custom serialized types (like bytes) back when loading JSON."""
    if "__bytes_hex__" in dct:
        return bytes.fromhex(dct["__bytes_hex__"])
    return dct


def load_plist(file_path):
    """Loads and parses a plist file (supports both XML and Binary)."""
    with open(file_path, "rb") as f:
        return plistlib.load(f)


def save_plist(data, file_path, fmt=plistlib.FMT_XML):
    """Saves data to a plist file (XML or Binary format)."""
    with open(file_path, "wb") as f:
        plistlib.dump(data, f, fmt=fmt)


def load_json(file_path):
    """Loads and parses a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f, object_hook=decode_custom_types)


def save_json(data, file_path, indent=2):
    """Saves data to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=PlistEncoder, indent=indent)


def load_yaml(file_path):
    """Loads and parses a YAML file."""
    if not HAS_YAML:
        raise ImportError("PyYAML is required to parse YAML files. Install it using 'pip install PyYAML'.")
    with open(file_path, "r", encoding="utf-8") as f:
        # Resolve custom tags or load safely
        data = yaml.safe_load(f)
        # Recursively restore bytes from dict helpers if any
        return restore_bytes_in_data(data)


def restore_bytes_in_data(data):
    """Helper to restore bytes from dictionary representation recursively."""
    if isinstance(data, dict):
        if "__bytes_hex__" in data:
            return bytes.fromhex(data["__bytes_hex__"])
        return {k: restore_bytes_in_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [restore_bytes_in_data(x) for x in data]
    return data


def save_yaml(data, file_path):
    """Saves data to a YAML file."""
    if not HAS_YAML:
        raise ImportError("PyYAML is required to output YAML files. Install it using 'pip install PyYAML'.")
    
    # Custom representer for bytes
    def bytes_representer(dumper, data_bytes):
        return dumper.represent_mapping("!bytes", {"hex": data_bytes.hex()})
        
    yaml.add_representer(bytes, bytes_representer, Dumper=yaml.SafeDumper)
    
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def detect_file_type(file_path):
    """Detects file type based on extension or signature."""
    _, ext = os.path.splitext(file_path.lower())
    if ext == ".json":
        return "json"
    elif ext in (".yaml", ".yml"):
        return "yaml"
    elif ext in (".plist", ".plistb", ".xml"):
        return "plist"
    
    # Check signature for plist
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
            if header.startswith(b"bplist") or header.startswith(b"<?xml"):
                return "plist"
    except Exception:
        pass
        
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Convert Apple Property List (.plist) files to/from JSON and YAML."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the input file.")
    parser.add_argument("-o", "--output", required=True, help="Path to the output file.")
    parser.add_argument(
        "-f", "--format", 
        choices=["xml", "binary", "json", "yaml"], 
        help="Target plist sub-format (xml/binary) or output format if ambiguous."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose logs.")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    input_type = detect_file_type(args.input)
    output_type = detect_file_type(args.output)

    if not input_type:
        print(f"Error: Could not detect file type of input '{args.input}'. Specify format via file extension.", file=sys.stderr)
        sys.exit(1)

    if not output_type:
        print(f"Error: Could not detect target file type of output '{args.output}'. Specify format via file extension.", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Detected input format: {input_type.upper()}")
        print(f"Detected output format: {output_type.upper()}")

    try:
        # 1. Read input data
        if input_type == "plist":
            data = load_plist(args.input)
        elif input_type == "json":
            data = load_json(args.input)
        elif input_type == "yaml":
            data = load_yaml(args.input)
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

        # 2. Write output data
        if output_type == "plist":
            fmt = plistlib.FMT_XML
            if args.format == "binary" or args.output.endswith(".plistb"):
                fmt = plistlib.FMT_BINARY
            save_plist(data, args.output, fmt=fmt)
        elif output_type == "json":
            save_json(data, args.output)
        elif output_type == "yaml":
            save_yaml(data, args.output)
        else:
            raise ValueError(f"Unsupported output type: {output_type}")

        print(f"Successfully converted '{args.input}' -> '{args.output}'.")

    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
