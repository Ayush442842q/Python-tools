#!/usr/bin/env python3
"""
Codec Utility - A tool to encode and decode strings or files using Base64, URL, Hex, Binary, and HTML formats.
"""

import argparse
import base64
import urllib.parse
import html
import sys
import os

def encode_data(data, format_type):
    """Encode string or bytes data into the target format."""
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = data
        
    if format_type == 'base64':
        return base64.b64encode(data_bytes).decode('utf-8')
    elif format_type == 'url':
        # URL encode requires string
        return urllib.parse.quote(data if isinstance(data, str) else data_bytes.decode('utf-8', errors='replace'))
    elif format_type == 'hex':
        return data_bytes.hex()
    elif format_type == 'binary':
        return ' '.join(f'{b:08b}' for b in data_bytes)
    elif format_type == 'html':
        return html.escape(data if isinstance(data, str) else data_bytes.decode('utf-8', errors='replace'))
    else:
        raise ValueError(f"Unknown format: {format_type}")

def decode_data(data_str, format_type):
    """Decode formatted string data back to bytes/string."""
    data_str = data_str.strip()
    
    if format_type == 'base64':
        try:
            return base64.b64decode(data_str.encode('utf-8'))
        except Exception as e:
            raise ValueError(f"Invalid Base64 input: {e}")
    elif format_type == 'url':
        return urllib.parse.unquote(data_str).encode('utf-8')
    elif format_type == 'hex':
        try:
            return bytes.fromhex(data_str)
        except Exception as e:
            raise ValueError(f"Invalid Hex input: {e}")
    elif format_type == 'binary':
        try:
            clean_str = data_str.replace(' ', '').replace('\n', '').replace('\t', '')
            if not all(c in '01' for c in clean_str):
                raise ValueError("Binary string must contain only 0 and 1.")
            if len(clean_str) % 8 != 0:
                raise ValueError("Binary string length must be a multiple of 8.")
            byte_list = [int(clean_str[i:i+8], 2) for i in range(0, len(clean_str), 8)]
            return bytes(byte_list)
        except Exception as e:
            raise ValueError(f"Invalid Binary input: {e}")
    elif format_type == 'html':
        return html.unescape(data_str).encode('utf-8')
    else:
        raise ValueError(f"Unknown format: {format_type}")

def main():
    parser = argparse.ArgumentParser(description="Codec Utility - Encode/Decode Base64, URL, Hex, Binary, and HTML entities.")
    
    # Operation Mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("-e", "--encode", action="store_true", help="Encode input")
    mode_group.add_argument("-d", "--decode", action="store_true", help="Decode input")
    
    # Formats
    parser.add_argument("-f", "--format", choices=['base64', 'url', 'hex', 'binary', 'html'], required=True,
                        help="Codec format to use")
    
    # Inputs & Outputs
    parser.add_argument("input_data", nargs="?", help="Direct input string (reads from stdin/file if omitted)")
    parser.add_argument("-i", "--input-file", help="Input file path")
    parser.add_argument("-o", "--output-file", help="Output file path")
    parser.add_argument("-b", "--binary-mode", action="store_true", 
                        help="Read/write files in raw binary mode (important for non-text Base64/Hex encoding)")
    
    args = parser.parse_args()
    
    # Resolve input data
    input_content = None
    if args.input_file:
        if not os.path.exists(args.input_file):
            print(f"Error: Input file '{args.input_file}' does not exist.", file=sys.stderr)
            sys.exit(1)
        try:
            mode = 'rb' if args.binary_mode or args.encode else 'r'
            with open(args.input_file, mode) as f:
                input_content = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.input_data is not None:
        input_content = args.input_data
    else:
        # Read from stdin
        if args.binary_mode:
            input_content = sys.stdin.buffer.read()
        else:
            input_content = sys.stdin.read()
            
    if not input_content:
        print("Error: Input data is empty.", file=sys.stderr)
        sys.exit(1)
        
    try:
        if args.encode:
            result = encode_data(input_content, args.format)
            # Encoding outputs a string
            if args.output_file:
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"Encoded output saved to {args.output_file}")
            else:
                print(result)
        else:
            # Decode returns bytes
            if isinstance(input_content, bytes):
                input_content = input_content.decode('utf-8', errors='ignore')
            decoded_bytes = decode_data(input_content, args.format)
            
            if args.output_file:
                mode = 'wb' if args.binary_mode else 'w'
                with open(args.output_file, mode) as f:
                    if 'w' in mode:
                        f.write(decoded_bytes.decode('utf-8', errors='replace'))
                    else:
                        f.write(decoded_bytes)
                print(f"Decoded output saved to {args.output_file}")
            else:
                try:
                    # Try to print as UTF-8 string
                    print(decoded_bytes.decode('utf-8'))
                except UnicodeDecodeError:
                    # Output raw bytes representation
                    print(f"Raw Bytes (Not printable UTF-8): {decoded_bytes}")
                    
    except ValueError as ve:
        print(f"Conversion Error: {ve}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
