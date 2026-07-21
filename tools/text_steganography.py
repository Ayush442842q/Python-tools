#!/usr/bin/env python3
"""
Text Steganography Tool - Hide and extract secret messages using zero-width characters

This tool enables hiding a secret message inside an arbitrary cover text using
invisible Unicode characters (zero-width space and zero-width non-joiner).
The resulting text looks completely normal but contains the hidden payload.

Usage:
    python tools/text_steganography.py hide -c "Cover text" -s "Secret message" [options]
    python tools/text_steganography.py extract -f steg_file.txt [options]

Options (hide):
    -c, --cover TEXT/FILE     The cover text or path to cover text file
    -s, --secret TEXT/FILE    The secret message or path to secret file
    -o, --output FILE         Write stego text to a file

Options (extract):
    -f, --file FILE           The stego file to extract the secret from
    -t, --text TEXT           Extract directly from a text string
"""

import argparse
import os
import sys
from typing import Optional

# Zero-width Unicode constants
ZW_ZERO = '\u200b'  # Zero-width space represents bit 0
ZW_ONE = '\u200c'   # Zero-width non-joiner represents bit 1
ZW_START = '\u200d' # Zero-width joiner represents start/end boundary


def encode_message(secret: str) -> str:
    """Encode a secret string into a sequence of zero-width characters."""
    secret_bytes = secret.encode('utf-8')
    bits_str = ""
    for byte in secret_bytes:
        bits_str += f"{byte:08b}"
        
    zw_encoded = ZW_START
    for bit in bits_str:
        if bit == '0':
            zw_encoded += ZW_ZERO
        else:
            zw_encoded += ZW_ONE
    zw_encoded += ZW_START
    return zw_encoded


def decode_message(stego_text: str) -> Optional[str]:
    """Extract and decode a secret message from steganographic text."""
    # Find the boundary marks
    start_idx = stego_text.find(ZW_START)
    if start_idx == -1:
        return None
        
    end_idx = stego_text.find(ZW_START, start_idx + 1)
    if end_idx == -1:
        return None

    zw_bits = stego_text[start_idx + 1:end_idx]
    
    # Reconstruct the bit string
    bits_str = ""
    for char in zw_bits:
        if char == ZW_ZERO:
            bits_str += '0'
        elif char == ZW_ONE:
            bits_str += '1'

    # Check if length is multiple of 8
    if not bits_str or len(bits_str) % 8 != 0:
        return None

    # Convert bits to bytes
    byte_list = []
    for i in range(0, len(bits_str), 8):
        byte_chunk = bits_str[i:i+8]
        byte_list.append(int(byte_chunk, 2))

    try:
        return bytes(byte_list).decode('utf-8')
    except UnicodeDecodeError:
        return None


def get_content(param: str) -> str:
    """Get content from parameter directly or read from file if path exists."""
    if os.path.exists(param):
        try:
            with open(param, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading path '{param}': {e}", file=sys.stderr)
            sys.exit(1)
    return param


def main():
    parser = argparse.ArgumentParser(description="Invisibly hide or extract secrets inside text using zero-width characters.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command to run")

    # Hide subparser
    hide_parser = subparsers.add_parser("hide", help="Hide a secret inside a cover text")
    hide_parser.add_argument("-c", "--cover", required=True, help="Cover text or path to cover text file")
    hide_parser.add_argument("-s", "--secret", required=True, help="Secret message text or path to secret file")
    hide_parser.add_argument("-o", "--output", help="Write output stego text to this file path")

    # Extract subparser
    extract_parser = subparsers.add_parser("extract", help="Extract a secret from stego text")
    extract_group = extract_parser.add_mutually_exclusive_group(required=True)
    extract_group.add_argument("-f", "--file", help="Path to stego text file")
    extract_group.add_argument("-t", "--text", help="Stego text string")

    args = parser.parse_args()

    if args.command == "hide":
        cover_content = get_content(args.cover)
        secret_content = get_content(args.secret)

        if not cover_content:
            print("Error: Cover text is empty.", file=sys.stderr)
            return 1
        if not secret_content:
            print("Error: Secret message is empty.", file=sys.stderr)
            return 1

        zw_encoded = encode_message(secret_content)
        
        # Inject the zero-width string into the cover text.
        # Place it right after the first character or word so it is embedded.
        if ' ' in cover_content:
            first_space = cover_content.index(' ')
            stego_text = cover_content[:first_space] + zw_encoded + cover_content[first_space:]
        else:
            stego_text = cover_content + zw_encoded

        if args.output:
            try:
                w_mode = 'w'
                with open(args.output, w_mode, encoding='utf-8') as f:
                    f.write(stego_text)
                print(f"Secret successfully hidden inside '{args.output}'.")
            except Exception as e:
                print(f"Error writing output file: {e}", file=sys.stderr)
                return 1
        else:
            print("Stego Output:")
            print("-" * 40)
            sys.stdout.write(stego_text)
            print()
            print("-" * 40)
            print(f"(Note: Secret embedded. Zero-width chars are invisible!)")

    elif args.command == "extract":
        if args.file:
            if not os.path.exists(args.file):
                print(f"Error: Stego file not found: {args.file}", file=sys.stderr)
                return 1
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    stego_content = f.read()
            except Exception as e:
                print(f"Error reading stego file: {e}", file=sys.stderr)
                return 1
        else:
            stego_content = args.text

        secret = decode_message(stego_content)
        if secret is None:
            print("Error: No hidden message could be extracted.", file=sys.stderr)
            return 1
        
        print("Extracted Secret:")
        print("-" * 40)
        print(secret)
        print("-" * 40)

    return 0


if __name__ == "__main__":
    sys.exit(main())
