#!/usr/bin/env python3
"""
RSA Key Wizard - Pure Python implementation of RSA key generation, encryption, and decryption.
For educational and basic utility purposes.
"""

import argparse
import sys
import json
import random
import os

def egcd(a, b):
    """Extended Greatest Common Divisor."""
    if a == 0:
        return (b, 0, 1)
    else:
        g, y, x = egcd(b % a, a)
        return (g, x - (b // a) * y, y)

def modinv(a, m):
    """Modular multiplicative inverse."""
    g, x, y = egcd(a, m)
    if g != 1:
        raise ValueError('Modular inverse does not exist')
    else:
        return x % m

def is_prime(n, k=40):
    """Miller-Rabin Primality Test."""
    if n == 2 or n == 3:
        return True
    if n <= 1 or n % 2 == 0:
        return False
    
    # Write n - 1 as 2^s * r
    s = 0
    r = n - 1
    while r % 2 == 0:
        r //= 2
        s += 1
        
    for _ in range(k):
        a = random.randint(2, n - 2)
        x = pow(a, r, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

def generate_prime(bits):
    """Generate a random prime number of specified bit length."""
    while True:
        # Set MSB and LSB to 1
        n = random.getrandbits(bits)
        n |= (1 << (bits - 1)) | 1
        if is_prime(n):
            return n

def generate_keypair(key_size=1024):
    """
    Generate public and private keys.
    Returns: (public_key_dict, private_key_dict)
    """
    p_bits = key_size // 2
    
    print(f"Generating prime p ({p_bits} bits)...")
    p = generate_prime(p_bits)
    print(f"Generating prime q ({p_bits} bits)...")
    q = generate_prime(p_bits)
    
    while p == q:
        q = generate_prime(p_bits)
        
    n = p * q
    phi = (p - 1) * (q - 1)
    
    # Common public exponent
    e = 65537
    
    print("Computing modular inverse for private key d...")
    d = modinv(e, phi)
    
    public_key = {
        "n": hex(n),
        "e": hex(e),
        "bits": key_size
    }
    
    private_key = {
        "n": hex(n),
        "d": hex(d),
        "bits": key_size
    }
    
    return public_key, private_key

def encrypt(text, public_key):
    """Encrypt plain text using the public key."""
    n = int(public_key["n"], 16)
    e = int(public_key["e"], 16)
    bits = public_key["bits"]
    
    data = text.encode("utf-8")
    key_bytes = (bits + 7) // 8
    
    # Chunk size must be less than key_bytes.
    # We prefix 1 byte for chunk length, so chunk payload is key_bytes - 2.
    chunk_size = key_bytes - 2
    if chunk_size <= 0:
        raise ValueError("Key size is too small to encrypt data.")
        
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    cipher_ints = []
    
    for chunk in chunks:
        # Prefix with actual length byte
        padded = bytes([len(chunk)]) + chunk
        m = int.from_bytes(padded, 'big')
        if m >= n:
            raise ValueError("Numeric value of padded chunk is larger than modulus n.")
        c = pow(m, e, n)
        cipher_ints.append(hex(c))
        
    return cipher_ints

def decrypt(cipher_ints, private_key):
    """Decrypt cipher text integers using the private key."""
    n = int(private_key["n"], 16)
    d = int(private_key["d"], 16)
    bits = private_key["bits"]
    
    key_bytes = (bits + 7) // 8
    decrypted_bytes = bytearray()
    
    for c_hex in cipher_ints:
        c = int(c_hex, 16)
        m = pow(c, d, n)
        # Convert integer back to bytes
        padded = m.to_bytes(key_bytes - 1, 'big')
        length = padded[0]
        if length > len(padded) - 1:
            raise ValueError("Decryption failed: corrupted data or invalid key.")
        chunk = padded[1:1+length]
        decrypted_bytes.extend(chunk)
        
    return decrypted_bytes.decode("utf-8")

def main():
    parser = argparse.ArgumentParser(
        description="RSA Key Wizard - Pure Python RSA Encryption Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Key generation parser
    gen_parser = subparsers.add_parser("keygen", help="Generate a public/private keypair")
    gen_parser.add_argument(
        "-b", "--bits",
        type=int,
        choices=[512, 1024, 2048],
        default=1024,
        help="Key bit length (default: 1024. 512 is fastest, 2048 is most secure)"
    )
    gen_parser.add_argument(
        "--public",
        default="public_key.json",
        help="Output public key file name (default: public_key.json)"
    )
    gen_parser.add_argument(
        "--private",
        default="private_key.json",
        help="Output private key file name (default: private_key.json)"
    )
    
    # Encryption parser
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt text with a public key")
    enc_parser.add_argument(
        "text",
        nargs="?",
        help="Text to encrypt"
    )
    enc_parser.add_argument(
        "-f", "--file",
        help="Input text file to encrypt"
    )
    enc_parser.add_argument(
        "-k", "--key",
        default="public_key.json",
        help="Public key JSON file (default: public_key.json)"
    )
    enc_parser.add_argument(
        "-o", "--output",
        default="encrypted.json",
        help="Output JSON file for ciphertext (default: encrypted.json)"
    )
    
    # Decryption parser
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt text with a private key")
    dec_parser.add_argument(
        "file",
        nargs="?",
        default="encrypted.json",
        help="Encrypted JSON file containing ciphertext (default: encrypted.json)"
    )
    dec_parser.add_argument(
        "-k", "--key",
        default="private_key.json",
        help="Private key JSON file (default: private_key.json)"
    )
    dec_parser.add_argument(
        "-o", "--output",
        help="Output file for decrypted text (prints to stdout if omitted)"
    )
    
    args = parser.parse_args()
    
    if args.command == "keygen":
        print(f"Generating RSA keypair ({args.bits} bits)...")
        pub, priv = generate_keypair(args.bits)
        
        try:
            with open(args.public, "w") as f:
                json.dump(pub, f, indent=2)
            with open(args.private, "w") as f:
                json.dump(priv, f, indent=2)
            print("✓ Successfully generated keys:")
            print(f"  Public key: {args.public}")
            print(f"  Private key: {args.private}")
        except Exception as e:
            print(f"Error saving key files: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "encrypt":
        # Load public key
        try:
            with open(args.key, "r") as f:
                pub_key = json.load(f)
        except FileNotFoundError:
            print(f"Error: Public key file '{args.key}' not found. Run keygen command first.", file=sys.stderr)
            sys.exit(1)
            
        # Get plain text
        plain_text = ""
        if args.file:
            try:
                with open(args.file, "r", encoding="utf-8") as f:
                    plain_text = f.read()
            except Exception as e:
                print(f"Error reading input file: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.text:
            plain_text = args.text
        else:
            print("Error: Specify text or use -f/--file to load input text.", file=sys.stderr)
            sys.exit(1)
            
        print("Encrypting...")
        try:
            cipher = encrypt(plain_text, pub_key)
            with open(args.output, "w") as f:
                json.dump(cipher, f, indent=2)
            print(f"✓ Encrypted successfully! Saved ciphertext list to '{args.output}'")
        except Exception as e:
            print(f"Encryption failed: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "decrypt":
        # Load private key
        try:
            with open(args.key, "r") as f:
                priv_key = json.load(f)
        except FileNotFoundError:
            print(f"Error: Private key file '{args.key}' not found.", file=sys.stderr)
            sys.exit(1)
            
        # Load ciphertext
        try:
            with open(args.file, "r") as f:
                cipher = json.load(f)
        except FileNotFoundError:
            print(f"Error: Encrypted file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
            
        print("Decrypting...")
        try:
            decrypted_text = decrypt(cipher, priv_key)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(decrypted_text)
                print(f"✓ Decrypted successfully! Saved to '{args.output}'")
            else:
                print("\nDecrypted Plain Text:")
                print("-" * 40)
                print(decrypted_text)
                print("-" * 40)
        except Exception as e:
            print(f"Decryption failed: {e}", file=sys.stderr)
            sys.exit(1)
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
