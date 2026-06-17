#!/usr/bin/env python3
"""
Cipher Utility
Encrypts and decrypts text or files using classical cryptographic ciphers:
Caesar, Vigenere, ROT13, Atbash, and XOR.
"""

import argparse
import base64
import sys

def caesar_cipher(text, shift, decrypt=False):
    """Applies Caesar cipher shifting to alphabet characters."""
    if decrypt:
        shift = -shift
    result = []
    for char in text:
        if char.isalpha():
            start = ord('A') if char.isupper() else ord('a')
            shifted = (ord(char) - start + shift) % 26
            result.append(chr(start + shifted))
        else:
            result.append(char)
    return "".join(result)

def vigenere_cipher(text, key, decrypt=False):
    """Applies Vigenere cipher using a keyword."""
    if not key or not key.isalpha():
        raise ValueError("Key must be a non-empty alphabetic string.")
    
    key = key.upper()
    result = []
    key_idx = 0
    
    for char in text:
        if char.isalpha():
            is_upper = char.isupper()
            start = ord('A') if is_upper else ord('a')
            
            # Get shift from key character
            shift = ord(key[key_idx % len(key)]) - ord('A')
            if decrypt:
                shift = -shift
                
            shifted = (ord(char) - start + shift) % 26
            result.append(chr(start + shifted))
            key_idx += 1
        else:
            result.append(char)
            
    return "".join(result)

def rot13_cipher(text):
    """Applies standard ROT13 substitution."""
    return caesar_cipher(text, 13)

def atbash_cipher(text):
    """Applies Atbash cipher (reverses the alphabet)."""
    result = []
    for char in text:
        if char.isalpha():
            if char.isupper():
                result.append(chr(ord('Z') - (ord(char) - ord('A'))))
            else:
                result.append(chr(ord('z') - (ord(char) - ord('a'))))
        else:
            result.append(char)
    return "".join(result)

def xor_cipher(text, key):
    """
    Applies XOR cipher with key. Since XOR is symmetric,
    encryption and decryption are the same operation.
    """
    if not key:
        raise ValueError("Key cannot be empty.")
    
    key_bytes = key.encode('utf-8')
    text_bytes = text.encode('utf-8')
    result = bytearray()
    
    for i in range(len(text_bytes)):
        result.append(text_bytes[i] ^ key_bytes[i % len(key_bytes)])
        
    return result

def main():
    parser = argparse.ArgumentParser(
        description="Encrypt/decrypt text using classic ciphers (Caesar, Vigenere, ROT13, Atbash, XOR)."
    )
    
    # Cipher Selection
    parser.add_argument('-c', '--cipher', required=True, 
                        choices=['caesar', 'vigenere', 'rot13', 'atbash', 'xor'],
                        help="Cipher algorithm to use")
    
    # Operation Mode
    parser.add_argument('-d', '--decrypt', action='store_true',
                        help="Perform decryption instead of encryption")
    
    # Inputs/Outputs
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--text', help="Text to process")
    group.add_argument('-f', '--file', help="File containing text to process")
    
    parser.add_argument('-o', '--output', help="Output file path (default: print to stdout)")
    
    # Cipher Parameters
    parser.add_argument('-k', '--key', help="Key for Vigenere or XOR ciphers (string)")
    parser.add_argument('-s', '--shift', type=int, default=3, help="Shift value for Caesar cipher (default: 3)")
    
    # Binary Formatting Options (for XOR)
    parser.add_argument('--encoding', choices=['raw', 'hex', 'base64'], default='base64',
                        help="Encoding for binary outputs/inputs, specifically for XOR (default: base64)")

    args = parser.parse_args()

    # Get input content
    content = ""
    if args.text:
        content = args.text
    else:
        try:
            if args.cipher == 'xor' and args.decrypt and args.encoding != 'raw':
                # Read raw data for decryption if using hex/base64
                with open(args.file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
            else:
                with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            return 1

    try:
        # Perform encryption/decryption
        if args.cipher == 'caesar':
            output_data = caesar_cipher(content, args.shift, args.decrypt)
            
        elif args.cipher == 'vigenere':
            if not args.key:
                print("Error: Vigenere cipher requires a key (-k/--key).", file=sys.stderr)
                return 1
            output_data = vigenere_cipher(content, args.key, args.decrypt)
            
        elif args.cipher == 'rot13':
            output_data = rot13_cipher(content)
            
        elif args.cipher == 'atbash':
            output_data = atbash_cipher(content)
            
        elif args.cipher == 'xor':
            if not args.key:
                print("Error: XOR cipher requires a key (-k/--key).", file=sys.stderr)
                return 1
                
            if args.decrypt:
                # Decode input bytes first if they are hex/base64
                try:
                    if args.encoding == 'hex':
                        input_bytes = bytes.fromhex(content)
                        text_to_xor = input_bytes.decode('utf-8', errors='ignore')
                    elif args.encoding == 'base64':
                        input_bytes = base64.b64decode(content.encode('utf-8'))
                        text_to_xor = input_bytes.decode('utf-8', errors='ignore')
                    else:
                        text_to_xor = content
                except Exception as e:
                    print(f"Error decoding input encoding '{args.encoding}': {e}", file=sys.stderr)
                    return 1
                
                # Decrypt is same as encrypt for XOR
                decrypted_bytes = xor_cipher(text_to_xor, args.key)
                output_data = decrypted_bytes.decode('utf-8', errors='ignore')
            else:
                # Encrypt text using XOR
                encrypted_bytes = xor_cipher(content, args.key)
                if args.encoding == 'hex':
                    output_data = encrypted_bytes.hex()
                elif args.encoding == 'base64':
                    output_data = base64.b64encode(encrypted_bytes).decode('utf-8')
                else:
                    output_data = encrypted_bytes.decode('utf-8', errors='ignore')
                    
    except Exception as e:
        print(f"Error during cipher operation: {e}", file=sys.stderr)
        return 1

    # Output results
    if args.output:
        try:
            mode = 'w'
            with open(args.output, mode, encoding='utf-8') as f:
                f.write(output_data)
            print(f"Output successfully written to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_data)

    return 0

if __name__ == '__main__':
    sys.exit(main())
