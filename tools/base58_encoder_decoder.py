#!/usr/bin/env python3
"""
Base58 Encoder & Decoder
Encodes and decodes strings or files to/from Base58 format.
Supports Bitcoin, Ripple, and Flickr alphabets.
"""

import argparse
import sys

# Presets for popular Base58 Alphabets
ALPHABETS = {
    "bitcoin": "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
    "ripple": "rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyZ",
    "flickr": "123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
}

def encode_base58(data_bytes, alphabet_name="bitcoin"):
    """
    Encode bytes to a Base58 string.
    """
    alphabet = ALPHABETS[alphabet_name]
    
    # Count leading zero bytes
    leading_zeros = 0
    for byte in data_bytes:
        if byte == 0:
            leading_zeros += 1
        else:
            break
            
    # Convert bytes to a single big integer
    val = int.from_bytes(data_bytes, byteorder='big')
    
    # Build the base58 string
    result = []
    while val > 0:
        val, remainder = divmod(val, 58)
        result.append(alphabet[remainder])
        
    # Add leading zeros (represented by the first character of the alphabet)
    result.extend([alphabet[0]] * leading_zeros)
    
    return "".join(reversed(result))

def decode_base58(b58_str, alphabet_name="bitcoin"):
    """
    Decode a Base58 string back to bytes.
    """
    alphabet = ALPHABETS[alphabet_name]
    char_map = {char: idx for idx, char in enumerate(alphabet)}
    
    # Strip any whitespace
    b58_str = b58_str.strip()
    
    # Validate characters
    for char in b58_str:
        if char not in char_map:
            raise ValueError(f"Invalid character '{char}' for Base58 alphabet '{alphabet_name}'")
            
    # Count leading zeros (represented by the first character of the alphabet)
    leading_zeros = 0
    for char in b58_str:
        if char == alphabet[0]:
            leading_zeros += 1
        else:
            break
            
    # Decode the string to an integer
    val = 0
    for char in b58_str[leading_zeros:]:
        val = val * 58 + char_map[char]
        
    # Convert integer to bytes
    # Calculate bytes length needed
    if val == 0:
        byte_len = 0
    else:
        byte_len = (val.bit_length() + 7) // 8
        
    decoded_bytes = val.to_bytes(byte_len, byteorder='big')
    
    # Prepend leading zeros
    return b'\x00' * leading_zeros + decoded_bytes

def main():
    parser = argparse.ArgumentParser(description="Base58 Encoder/Decoder - Encode/decode strings or files using Base58")
    
    # Action selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-e", "--encode", action="store_true", help="Encode input to Base58")
    group.add_argument("-d", "--decode", action="store_true", help="Decode Base58 input back to original format")
    
    # Input selection
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("data", nargs="?", help="Input string data to process")
    input_group.add_argument("-f", "--file", help="Path to file to process")
    
    # Configuration options
    parser.add_argument("-a", "--alphabet", choices=list(ALPHABETS.keys()), default="bitcoin",
                        help="The Base58 alphabet dialect to use (default: bitcoin)")
    parser.add_argument("-o", "--output", help="Path to output file (writes to stdout by default)")
    parser.add_argument("-t", "--text", action="store_true",
                        help="When decoding, treat result as text (UTF-8 string) instead of binary bytes")

    args = parser.parse_args()

    # Determine input data bytes or string
    input_bytes = b""
    if args.file:
        try:
            with open(args.file, "rb") as f:
                input_bytes = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.data is None:
            # Try reading from stdin
            if not sys.stdin.isatty():
                input_str = sys.stdin.read()
            else:
                print("Error: No input data provided. Specify data argument, use -f for files, or pipe to stdin.", file=sys.stderr)
                parser.print_usage()
                sys.exit(1)
        else:
            input_str = args.data
            
        input_bytes = input_str.encode("utf-8")

    # Perform operation
    if args.encode:
        # Encoding input_bytes to Base58 string
        result_str = encode_base58(input_bytes, args.alphabet)
        
        # Output result
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result_str + "\n")
            except Exception as e:
                print(f"Error writing output to '{args.output}': {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(result_str)
            
    elif args.decode:
        # Decoding Base58 string from input data
        # If it was a file, it might contain raw bytes or a string, convert to string
        b58_input = input_bytes.decode("utf-8", errors="ignore").strip()
        
        try:
            decoded_bytes = decode_base58(b58_input, args.alphabet)
        except ValueError as e:
            print(f"Decode Error: {e}", file=sys.stderr)
            sys.exit(1)
            
        # Output result
        if args.output:
            try:
                with open(args.output, "wb") as f:
                    f.write(decoded_bytes)
            except Exception as e:
                print(f"Error writing output to '{args.output}': {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Print as text or bytes
            if args.text:
                try:
                    print(decoded_bytes.decode("utf-8"))
                except UnicodeDecodeError:
                    print("Error: Decoded bytes are not valid UTF-8 text. Use default mode to write bytes/output to file.", file=sys.stderr)
                    sys.exit(1)
            else:
                # Write directly to stdout stream as bytes
                sys.stdout.buffer.write(decoded_bytes)

if __name__ == "__main__":
    main()
