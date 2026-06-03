#!/usr/bin/env python3
"""
Base64 Encoder/Decoder

A simple tool to encode and decode base64 strings.

Usage:
    python tools/base64_encoder_decoder.py encode "Hello World"
    python tools/base64_encoder_decoder.py decode "SGVsbG8gV29ybGQ="
"""

import argparse
import sys
import base64

def main():
    parser = argparse.ArgumentParser(description="Base64 Encoder/Decoder")
    parser.add_argument('action', choices=['encode', 'decode'], help='Action to perform')
    parser.add_argument('text', help='Text to encode or decode')
    args = parser.parse_args()

    if args.action == 'encode':
        encoded = base64.b64encode(args.text.encode('utf-8')).decode('utf-8')
        print(f"Encoded: {encoded}")
    elif args.action == 'decode':
        try:
            decoded = base64.b64decode(args.text).decode('utf-8')
            print(f"Decoded: {decoded}")
        except Exception as e:
            print(f"Error decoding base64: {e}")
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
