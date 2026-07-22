#!/usr/bin/env python3
"""
Base85 Encoder & Decoder
A CLI utility to encode and decode text/binary data to/from Ascii85 and RFC 1924 / ZeroMQ Base85 formats.

Features:
- Encodes and decodes using the standard library `base64` module.
- Supports standard Ascii85 (Adobe variant) and Z85 (ZeroMQ / RFC 1924 variant) formats.
- Supports input from string arguments, input files, or standard input.
- Handles padding, UTF-8 strings, and clean CLI formatting.
"""

import sys
import os
import base64
import argparse
from typing import Union

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def encode_base85(data: bytes, variant: str) -> str:
    """Encodes bytes into a Base85 string using specified variant."""
    if variant == "z85":
        # ZeroMQ Base85 requires input size to be a multiple of 4 bytes
        padding = (4 - (len(data) % 4)) % 4
        padded_data = data + b"\x00" * padding
        encoded = base64.b85encode(padded_data).decode("ascii")
        # Store padding length in encoded form or handle padding manually
        # Standard Z85 does not natively support arbitrary length padding,
        # but base64.b85encode implementation handles it by appending padding or raising error.
        return encoded
    else:  # ascii85
        return base64.a85encode(data).decode("ascii")


def decode_base85(data_str: str, variant: str) -> bytes:
    """Decodes a Base85 string into bytes using specified variant."""
    clean_data = data_str.strip().encode("ascii")
    if variant == "z85":
        return base64.b85decode(clean_data)
    else:  # ascii85
        return base64.a85decode(clean_data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode and decode text/binary data to/from Base85 formats.")
    parser.add_argument("input", nargs="?", type=str, help="Input string or path to input file (reads stdin if omitted).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-e", "--encode", action="store_true", help="Encode input data to Base85.")
    group.add_argument("-d", "--decode", action="store_true", help="Decode Base85 input data.")
    
    parser.add_argument("-f", "--format", choices=["ascii85", "z85"], default="ascii85",
                        help="Base85 variant to use: 'ascii85' (Adobe/default) or 'z85' (ZeroMQ / RFC 1924).")
    parser.add_argument("-o", "--output", type=str, help="Output file path.")

    args = parser.parse_args()

    content_bytes = b""
    if args.input:
        if os.path.exists(args.input):
            with open(args.input, "rb") as f:
                content_bytes = f.read()
        else:
            content_bytes = args.input.encode("utf-8")
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        content_bytes = sys.stdin.buffer.read()

    try:
        if args.encode:
            result_str = encode_base85(content_bytes, args.format)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result_str + "\n")
                print(f"Successfully saved encoded output to {args.output}")
            else:
                print(result_str)
        else:  # decode
            # If we decode, the input is expected to be ASCII text
            input_str = content_bytes.decode("utf-8", errors="ignore")
            result_bytes = decode_base85(input_str, args.format)
            if args.output:
                with open(args.output, "wb") as f:
                    f.write(result_bytes)
                print(f"Successfully saved decoded output to {args.output}")
            else:
                try:
                    print(result_bytes.decode("utf-8"))
                except UnicodeDecodeError:
                    # Write binary stdout
                    sys.stdout.buffer.write(result_bytes)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
