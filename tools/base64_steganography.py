#!/usr/bin/env python3
"""
Base64 Padding Steganography - Hide secret messages in Base64 padding bits
This tool hides a secret message inside the unused padding bits of a Base64-encoded
cover file (e.g. Base64 images, PEM certificates, or standard Base64 text blocks).
Because standard Base64 decoders ignore these padding bits, the cover file remains fully
functional and decodes to its original contents without any error or visual change.
"""

import argparse
import base64
import sys
from typing import List, Tuple

BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CHAR_TO_VAL = {char: val for val, char in enumerate(BASE64_CHARS)}

def text_to_bits(text: str) -> List[int]:
    """Convert text string to a list of bits (MSB first)."""
    bits = []
    for byte in text.encode('utf-8'):
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_text(bits: List[int]) -> str:
    """Convert a list of bits to a UTF-8 string."""
    bytes_list = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i+8]
        if len(byte_bits) < 8:
            break
        byte_val = 0
        for bit in byte_bits:
            byte_val = (byte_val << 1) | bit
        bytes_list.append(byte_val)
    
    try:
        return bytes(bytes_list).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def calculate_capacity(b64_lines: List[str]) -> int:
    """Calculate the capacity in bits of a list of Base64 lines."""
    bits_count = 0
    for line in b64_lines:
        line = line.strip()
        if line.endswith('=='):
            bits_count += 4
        elif line.endswith('='):
            bits_count += 2
    return bits_count

def hide_message(b64_lines: List[str], secret_message: str) -> List[str]:
    """Hide a secret message inside Base64 padding bits. Returns the modified Base64 lines."""
    # Convert message to bits with a 32-bit length prefix to allow precise extraction
    secret_bits = text_to_bits(secret_message)
    length_prefix = []
    msg_len = len(secret_bits)
    for i in range(31, -1, -1):
        length_prefix.append((msg_len >> i) & 1)
        
    all_bits = length_prefix + secret_bits
    bit_idx = 0
    total_bits = len(all_bits)
    
    modified_lines = []
    
    for line in b64_lines:
        line_strip = line.strip()
        if not line_strip:
            modified_lines.append(line)
            continue
            
        if bit_idx >= total_bits:
            modified_lines.append(line)
            continue
            
        if line_strip.endswith('=='):
            # 4 bits of capacity in the character right before '=='
            char_idx = len(line_strip) - 3
            char = line_strip[char_idx]
            val = CHAR_TO_VAL.get(char, 0)
            
            # Read up to 4 bits
            bits_to_hide = all_bits[bit_idx : bit_idx + 4]
            bit_idx += len(bits_to_hide)
            
            # Pad with 0s if we run out of bits mid-character
            while len(bits_to_hide) < 4:
                bits_to_hide.append(0)
                
            # Construct new value: clear lower 4 bits, insert secret bits
            secret_val = 0
            for bit in bits_to_hide:
                secret_val = (secret_val << 1) | bit
            
            new_val = (val & 0b110000) | secret_val
            new_char = BASE64_CHARS[new_val]
            
            # Reconstruct line
            new_line = line_strip[:char_idx] + new_char + '=='
            modified_lines.append(new_line + line[len(line_strip):]) # keep original trailing whitespace/newlines
            
        elif line_strip.endswith('='):
            # 2 bits of capacity in the character right before '='
            char_idx = len(line_strip) - 2
            char = line_strip[char_idx]
            val = CHAR_TO_VAL.get(char, 0)
            
            # Read up to 2 bits
            bits_to_hide = all_bits[bit_idx : bit_idx + 2]
            bit_idx += len(bits_to_hide)
            
            while len(bits_to_hide) < 2:
                bits_to_hide.append(0)
                
            # Construct new value: clear lower 2 bits, insert secret bits
            secret_val = 0
            for bit in bits_to_hide:
                secret_val = (secret_val << 1) | bit
                
            new_val = (val & 0b111100) | secret_val
            new_char = BASE64_CHARS[new_val]
            
            # Reconstruct line
            new_line = line_strip[:char_idx] + new_char + '='
            modified_lines.append(new_line + line[len(line_strip):])
            
        else:
            modified_lines.append(line)
            
    if bit_idx < total_bits:
        print(f"Warning: Cover file capacity was insufficient. Only hid {bit_idx} of {total_bits} bits.", file=sys.stderr)
        
    return modified_lines

def extract_message(b64_lines: List[str]) -> str:
    """Extract the hidden message from Base64 padding bits."""
    extracted_bits = []
    
    for line in b64_lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        if line_strip.endswith('=='):
            char_idx = len(line_strip) - 3
            char = line_strip[char_idx]
            val = CHAR_TO_VAL.get(char, 0)
            # The lower 4 bits contain hidden data
            for i in range(3, -1, -1):
                extracted_bits.append((val >> i) & 1)
                
        elif line_strip.endswith('='):
            char_idx = len(line_strip) - 2
            char = line_strip[char_idx]
            val = CHAR_TO_VAL.get(char, 0)
            # The lower 2 bits contain hidden data
            for i in range(1, -1, -1):
                extracted_bits.append((val >> i) & 1)
                
    if len(extracted_bits) < 32:
        return "Error: No message found (insufficient bits)."
        
    # Read the 32-bit length prefix
    msg_len = 0
    for i in range(32):
        msg_len = (msg_len << 1) | extracted_bits[i]
        
    if msg_len <= 0 or msg_len > len(extracted_bits) - 32:
        return "Error: No hidden message detected or invalid length prefix."
        
    message_bits = extracted_bits[32 : 32 + msg_len]
    return bits_to_text(message_bits)

def generate_padded_base64(data_bytes: bytes, min_padding_needed: int) -> List[str]:
    """
    Encode binary data to Base64 in custom short chunks (e.g. 1 or 2 bytes)
    to dynamically generate enough padding characters to fit the secret message.
    """
    lines = []
    idx = 0
    total_len = len(data_bytes)
    padding_created = 0
    
    # We can encode in chunks of 1 byte (gives == -> 4 bits), 2 bytes (gives = -> 2 bits), or 3 bytes (gives no padding)
    while idx < total_len:
        remaining_needed = min_padding_needed - padding_created
        
        if remaining_needed > 0:
            if remaining_needed >= 4 and idx + 1 <= total_len:
                # Encode 1 byte -> yields '==' (4 bits)
                chunk = data_bytes[idx : idx + 1]
                idx += 1
                lines.append(base64.b64encode(chunk).decode('utf-8'))
                padding_created += 4
            elif idx + 2 <= total_len:
                # Encode 2 bytes -> yields '=' (2 bits)
                chunk = data_bytes[idx : idx + 2]
                idx += 2
                lines.append(base64.b64encode(chunk).decode('utf-8'))
                padding_created += 2
            else:
                # Fallback to whatever is left
                chunk = data_bytes[idx : idx + 3]
                idx += len(chunk)
                lines.append(base64.b64encode(chunk).decode('utf-8'))
        else:
            # Standard 3-byte chunk (no padding created) or normal line grouping
            chunk = data_bytes[idx : idx + 48] # 48 bytes yields 64 Base64 chars
            idx += len(chunk)
            lines.append(base64.b64encode(chunk).decode('utf-8'))
            
    return lines

def main():
    parser = argparse.ArgumentParser(
        description="Base64 Padding Steganography - Hide secret messages in Base64 padding bits",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Steganography commands')
    
    # Subcommand: capacity
    cap_parser = subparsers.add_parser('capacity', help='Calculate the steganographic capacity of a Base64 file')
    cap_parser.add_argument('-f', '--file', required=True, help='Path to the Base64 file to analyze')
    
    # Subcommand: hide
    hide_parser = subparsers.add_parser('hide', help='Hide a secret message inside Base64 cover file')
    hide_parser.add_argument('-c', '--cover', required=True, help='Path to the Base64 cover file')
    hide_parser.add_argument('-s', '--secret', required=True, help='Secret message string to hide')
    hide_parser.add_argument('-o', '--output', required=True, help='Path to save the modified Base64 output')
    
    # Subcommand: extract
    ext_parser = subparsers.add_parser('extract', help='Extract a hidden message from a Base64 file')
    ext_parser.add_argument('-f', '--file', required=True, help='Path to the Base64 stego file')
    
    # Subcommand: generate
    gen_parser = subparsers.add_parser('generate', help='Generate a padded Base64 file from plain text to hold a secret')
    gen_parser.add_argument('-c', '--cover-text', required=True, help='Path to plain text file to use as cover')
    gen_parser.add_argument('-s', '--secret', required=True, help='Secret message string to hide')
    gen_parser.add_argument('-o', '--output', required=True, help='Path to save the generated Base64 output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == 'capacity':
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            cap = calculate_capacity(lines)
            print(f"File: {args.file}")
            print(f"Total Base64 lines: {len(lines)}")
            print(f"Steganographic capacity: {cap} bits ({cap // 8} bytes)")
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == 'hide':
        try:
            with open(args.cover, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            cap = calculate_capacity(lines)
            msg_bits_needed = 32 + len(secret_bits := text_to_bits(args.secret))
            print(f"Cover capacity: {cap} bits ({cap // 8} bytes)")
            print(f"Message size: {msg_bits_needed} bits ({msg_bits_needed / 8:.1f} bytes)")
            
            if cap < msg_bits_needed:
                print(f"Error: Insufficient capacity. Need {msg_bits_needed} bits but cover only has {cap} bits.", file=sys.stderr)
                print("Suggestion: Use the 'generate' command to create a custom cover with higher capacity.", file=sys.stderr)
                sys.exit(1)
                
            modified = hide_message(lines, args.secret)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.writelines(modified)
                
            print(f"Success! Secret message hidden. Saved to [output](file:///{args.output.replace('\\', '/')})")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == 'extract':
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            secret = extract_message(lines)
            print("Extracted Message:")
            print("=" * 40)
            print(secret)
            print("=" * 40)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == 'generate':
        try:
            with open(args.cover_text, 'rb') as f:
                cover_data = f.read()
                
            msg_bits_needed = 32 + len(text_to_bits(args.secret))
            print(f"Cover text size: {len(cover_data)} bytes")
            print(f"Required capacity: {msg_bits_needed} bits")
            
            # Generate Base64 stream with plenty of padding by splitting chunks
            lines = generate_padded_base64(cover_data, msg_bits_needed)
            
            # Check capacity of generated base64 lines
            cap = calculate_capacity(lines)
            if cap < msg_bits_needed:
                print(f"Error: Even with custom padding, cover text of size {len(cover_data)} is too small to hide the message.", file=sys.stderr)
                sys.exit(1)
                
            # Now hide the message in the newly formatted lines
            modified = hide_message([line + '\n' for line in lines], args.secret)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.writelines(modified)
                
            print(f"Success! Custom cover generated and secret hidden. Saved to [output](file:///{args.output.replace('\\', '/')})")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
