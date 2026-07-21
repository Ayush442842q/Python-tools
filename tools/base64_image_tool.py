#!/usr/bin/env python3
"""
Base64 Image Encoder & Decoder
A standalone utility to encode image files to Base64 (including data URIs) and decode
Base64 strings back to image files.
"""

import argparse
import base64
import mimetypes
import os
import sys


def encode_image(image_path, output_path=None, use_data_uri=False, mime_type=None):
    """Encode an image file to a Base64 string."""
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.", file=sys.stderr)
        return 1

    try:
        with open(image_path, "rb") as image_file:
            encoded_bytes = base64.b64encode(image_file.read())
            encoded_str = encoded_bytes.decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}", file=sys.stderr)
        return 1

    if use_data_uri:
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                # Default to png if type cannot be guessed
                mime_type = "image/png"
        encoded_str = f"data:{mime_type};base64,{encoded_str}"

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as out_file:
                out_file.write(encoded_str)
            print(f"Successfully encoded '{image_path}' and saved to '{output_path}'")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            return 1
    else:
        print(encoded_str)
        
    return 0


def decode_base64(input_source, output_path):
    """Decode a Base64 string back into an image file."""
    # Check if input source is a file path or direct string
    base64_data = ""
    if os.path.exists(input_source):
        try:
            with open(input_source, "r", encoding="utf-8", errors="ignore") as f:
                base64_data = f.read().strip()
        except Exception as e:
            print(f"Error reading input file '{input_source}': {e}", file=sys.stderr)
            return 1
    else:
        base64_data = input_source.strip()

    # Strip data URI header if present (e.g. data:image/png;base64,...)
    if base64_data.startswith("data:"):
        header_end = base64_data.find(",")
        if header_end != -1:
            base64_data = base64_data[header_end + 1:]

    try:
        image_bytes = base64.b64decode(base64_data)
    except Exception as e:
        print(f"Error decoding Base64 string: {e}", file=sys.stderr)
        return 1

    try:
        # Guarantee parent directories exist
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(output_path, "wb") as image_file:
            image_file.write(image_bytes)
        print(f"Successfully decoded Base64 and saved image to '{output_path}'")
    except Exception as e:
        print(f"Error writing image file to '{output_path}': {e}", file=sys.stderr)
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Encode images to Base64 strings (or data URIs) and decode Base64 back to images."
    )
    
    subparsers = parser.add_subparsers(dest="action", required=True, help="Action to perform")
    
    # Subparser for encode
    encode_parser = subparsers.add_parser("encode", help="Encode an image to a Base64 text string")
    encode_parser.add_argument("image", help="Path to the input image file")
    encode_parser.add_argument("-o", "--output", help="Path to output text file (prints to stdout if omitted)")
    encode_parser.add_argument("-d", "--data-uri", action="store_true", help="Format output as a data URI")
    encode_parser.add_argument("-m", "--mime", help="Override mime type for data URI (e.g. image/jpeg)")
    
    # Subparser for decode
    decode_parser = subparsers.add_parser("decode", help="Decode a Base64 string/file to an image file")
    decode_parser.add_argument("input", help="Base64 text string OR path to file containing Base64 text")
    decode_parser.add_argument("-o", "--output", required=True, help="Path to output image file (e.g. output.png)")
    
    args = parser.parse_args()

    if args.action == "encode":
        return encode_image(
            args.image,
            output_path=args.output,
            use_data_uri=args.data_uri,
            mime_type=args.mime
        )
    elif args.action == "decode":
        return decode_base64(args.input, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
