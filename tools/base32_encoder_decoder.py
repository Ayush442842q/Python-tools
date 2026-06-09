"""
Base32 Encoder/Decoder Tool
Encodes and decodes strings or files using Base32.
"""
import argparse
import base64
import os
import sys

def main():
    parser = argparse.ArgumentParser(
        description="Encode and decode strings or file content using Base32."
    )
    
    # Create mutually exclusive group for input
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--string", help="The text string to encode or decode.")
    group.add_argument("-f", "--file", help="Path to a file whose contents should be processed.")
    
    parser.add_argument(
        "-d", "--decode",
        action="store_true",
        help="Decode the input (default is to encode)."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save the output. If not specified, prints to stdout."
    )

    args = parser.parse_args()

    # Read input data
    if args.string is not None:
        input_bytes = args.string.encode('utf-8')
    else:
        if not os.path.isfile(args.file):
            print(f"[ERROR] File not found: {args.file}")
            sys.exit(1)
        try:
            with open(args.file, 'rb') as f:
                input_bytes = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file: {e}")
            sys.exit(1)

    if args.decode:
        try:
            # Base32 decoding
            # Remove whitespace or newlines if any
            cleaned_input = input_bytes.strip()
            decoded_bytes = base64.b32decode(cleaned_input, casefold=True)
            output_bytes = decoded_bytes
        except Exception as e:
            print(f"[ERROR] Failed to decode Base32: {e}")
            sys.exit(1)
    else:
        # Base32 encoding
        output_bytes = base64.b32encode(input_bytes)

    # Output handling
    if args.output:
        try:
            with open(args.output, 'wb') as f:
                f.write(output_bytes)
            print(f"[OK] Output successfully saved to: {args.output}")
        except Exception as e:
            print(f"[ERROR] Failed to write output file: {e}")
            sys.exit(1)
    else:
        # Print to stdout
        if args.decode:
            try:
                # Try to decode to UTF-8 for displaying
                print(output_bytes.decode('utf-8'))
            except UnicodeDecodeError:
                # If binary content, print representation or notice
                print(f"[OK] Decoded successfully (binary content, size: {len(output_bytes)} bytes).")
                print(output_bytes)
        else:
            print(output_bytes.decode('ascii'))

    sys.exit(0)

if __name__ == "__main__":
    main()
