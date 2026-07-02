#!/usr/bin/env python3
"""
Shamir's Secret Sharing Utility

A cryptographic utility that implements Shamir's Secret Sharing scheme to split 
a secret (text or file) into N shares, requiring at least K threshold shares 
to reconstruct the original secret.

Natively implements polynomial arithmetic over the large prime field GF(2^256 - 189) 
supporting arbitrary-length secrets via block-based sharing.
"""

import argparse
import base64
import json
import os
import secrets
import sys
from typing import List, Tuple, Dict

# Largest prime less than 2^256
PRIME = 2**256 - 189
BLOCK_SIZE = 31  # 31 bytes fits safely in a 256-bit prime field

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def log_success(msg: str):
    print(color_text("[+] " + msg, COLOR_GREEN))

def log_info(msg: str):
    print(color_text("[*] " + msg, COLOR_CYAN))

def log_warning(msg: str):
    print(color_text("[!] " + msg, COLOR_YELLOW))

def log_error(msg: str):
    print(color_text("[-] ERROR: " + msg, COLOR_RED), file=sys.stderr)

# --- Cryptographic Helpers (GF(p) Arithmetic) ---

def mod_inverse(k: int, prime: int) -> int:
    """Computes the modular multiplicative inverse of k modulo prime using Fermat's Little Theorem."""
    k = k % prime
    if k == 0:
        raise ZeroDivisionError("No modular inverse for 0")
    return pow(k, prime - 2, prime)

def eval_polynomial(coeffs: List[int], x: int, prime: int) -> int:
    """Evaluates a polynomial at x with given coefficients in GF(prime) using Horner's method."""
    y = 0
    for coeff in reversed(coeffs):
        y = (y * x + coeff) % prime
    return y

def lagrange_interpolation(points: List[Tuple[int, int]], prime: int) -> int:
    """
    Interpolates a polynomial from given points (x, y) and evaluates it at x=0.
    Uses Lagrange interpolation over GF(prime).
    """
    x_coords, y_coords = zip(*points)
    k = len(points)
    secret = 0
    
    for i in range(k):
        xi, yi = x_coords[i], y_coords[i]
        num = 1
        den = 1
        for j in range(k):
            if j == i:
                continue
            xj = x_coords[j]
            num = (num * -xj) % prime
            den = (den * (xi - xj)) % prime
            
        term = (yi * num * mod_inverse(den, prime)) % prime
        secret = (secret + term) % prime
        
    return secret

# --- Padding ---

def pkcs7_pad(data: bytes, block_size: int) -> bytes:
    """Pads bytes to a multiple of block_size using PKCS#7 padding."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)

def pkcs7_unpad(data: bytes) -> bytes:
    """Removes PKCS#7 padding from bytes."""
    if not data:
        raise ValueError("Cannot unpad empty byte array")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > len(data):
        raise ValueError("Invalid padding bytes")
    # Verify all padding bytes are equal to pad_len
    for b in data[-pad_len:]:
        if b != pad_len:
            raise ValueError("Invalid padding bytes")
    return data[:-pad_len]

# --- Core Shamir Operations ---

def split_secret(secret_bytes: bytes, n: int, k: int) -> List[Tuple[int, bytes]]:
    """
    Splits arbitrary secret_bytes into n shares with a threshold of k.
    Splits into blocks and concatenates evaluations.
    """
    padded = pkcs7_pad(secret_bytes, BLOCK_SIZE)
    num_blocks = len(padded) // BLOCK_SIZE
    
    # Store list of evaluations for each share
    # Each share i will have x = i, and a list of evaluations y_1, y_2, ..., y_num_blocks
    share_ys = {i: bytearray() for i in range(1, n + 1)}
    
    for b in range(num_blocks):
        block_bytes = padded[b * BLOCK_SIZE : (b + 1) * BLOCK_SIZE]
        # Convert block to integer (guaranteed to be < PRIME since BLOCK_SIZE = 31 bytes < 32 bytes)
        secret_val = int.from_bytes(block_bytes, byteorder='big')
        
        # Coefficients: a_0 = secret_val, and k-1 random coefficients
        coeffs = [secret_val] + [secrets.randbelow(PRIME) for _ in range(k - 1)]
        
        # Evaluate polynomial at x = 1, 2, ..., n
        for i in range(1, n + 1):
            y = eval_polynomial(coeffs, i, PRIME)
            # Encode y as a 32-byte big-endian integer
            share_ys[i].extend(y.to_bytes(32, byteorder='big'))
            
    return [(i, bytes(share_ys[i])) for i in range(1, n + 1)]

def reconstruct_secret(shares: List[Tuple[int, bytes]]) -> bytes:
    """Reconstructs the secret bytes from a list of shares (x, y_bytes_concatenated)."""
    if not shares:
        raise ValueError("No shares provided for reconstruction")
        
    # Check that all shares have the same length and it's a multiple of 32
    share_len = len(shares[0][1])
    if share_len % 32 != 0:
        raise ValueError("Invalid share data length (must be multiple of 32 bytes)")
    for x, y_bytes in shares:
        if len(y_bytes) != share_len:
            raise ValueError("Share lengths do not match")
            
    num_blocks = share_len // 32
    reconstructed_padded = bytearray()
    
    for b in range(num_blocks):
        # Gather points for this block
        points = []
        for x, y_bytes in shares:
            block_y_bytes = y_bytes[b * 32 : (b + 1) * 32]
            y_val = int.from_bytes(block_y_bytes, byteorder='big')
            points.append((x, y_val))
            
        # Interpolate and evaluate at x=0
        secret_val = lagrange_interpolation(points, PRIME)
        # Convert back to 31-byte block
        reconstructed_padded.extend(secret_val.to_bytes(BLOCK_SIZE, byteorder='big'))
        
    return pkcs7_unpad(bytes(reconstructed_padded))

# --- CLI and Serialization ---

def encode_share(x: int, y_bytes: bytes) -> str:
    """Encodes a share (index and byte data) into a readable Base64-based string."""
    combined = x.to_bytes(2, byteorder='big') + y_bytes
    b64 = base64.b64encode(combined).decode('utf-8')
    return f"sss_share_{b64}"

def decode_share(share_str: str) -> Tuple[int, bytes]:
    """Decodes a share string back to (x, y_bytes)."""
    share_str = share_str.strip()
    if not share_str.startswith("sss_share_"):
        raise ValueError("Invalid share format (must start with 'sss_share_')")
    b64_part = share_str[len("sss_share_"):]
    combined = base64.b64decode(b64_part)
    if len(combined) < 34:  # 2 bytes for x + at least 32 bytes for y
        raise ValueError("Decoded share data too short")
    x = int.from_bytes(combined[:2], byteorder='big')
    y_bytes = combined[2:]
    return x, y_bytes

def main():
    parser = argparse.ArgumentParser(
        description="Shamir's Secret Sharing Splitter and Reconstructor"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Split subcommand
    split_parser = subparsers.add_parser("split", help="Split a secret into N shares")
    split_parser.add_argument("-s", "--secret", type=str, help="The secret string to split")
    split_parser.add_argument("-f", "--file", type=str, help="Path to a file containing the secret")
    split_parser.add_argument("-n", "--shares", type=int, required=True, help="Total number of shares to generate (N)")
    split_parser.add_argument("-k", "--threshold", type=int, required=True, help="Threshold number of shares required to reconstruct (K)")
    split_parser.add_argument("-o", "--output", type=str, help="Directory to save shares as individual files")
    
    # Reconstruct subcommand
    recon_parser = subparsers.add_parser("reconstruct", help="Reconstruct a secret from K shares")
    recon_parser.add_argument("-i", "--input", type=str, nargs="+", help="Share strings or paths to share files")
    recon_parser.add_argument("-o", "--output", type=str, help="Path to save reconstructed file (if not printing text)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    if args.command == "split":
        if args.threshold > args.shares:
            log_error("Threshold (K) cannot be greater than Total Shares (N)")
            sys.exit(1)
        if args.threshold < 2:
            log_error("Threshold (K) must be at least 2")
            sys.exit(1)
            
        secret_bytes = None
        if args.secret:
            secret_bytes = args.secret.encode('utf-8')
        elif args.file:
            if not os.path.exists(args.file):
                log_error(f"File not found: {args.file}")
                sys.exit(1)
            with open(args.file, 'rb') as f:
                secret_bytes = f.read()
        else:
            log_error("Either --secret or --file must be provided for splitting")
            sys.exit(1)
            
        log_info(f"Generating {args.shares} shares with a threshold of {args.threshold}...")
        shares = split_secret(secret_bytes, args.shares, args.threshold)
        
        encoded_shares = []
        for x, y_bytes in shares:
            encoded_shares.append(encode_share(x, y_bytes))
            
        if args.output:
            os.makedirs(args.output, exist_ok=True)
            for idx, sh in enumerate(encoded_shares, start=1):
                filename = os.path.join(args.output, f"share_{idx}.txt")
                with open(filename, 'w') as f:
                    f.write(sh)
            log_success(f"Successfully wrote {args.shares} share files to directory: {args.output}")
        else:
            print("\n" + color_text("--- GENERATED SHARES ---", COLOR_BOLD))
            for idx, sh in enumerate(encoded_shares, start=1):
                print(f"Share #{idx}: {color_text(sh, COLOR_GREEN)}")
            print(color_text("------------------------", COLOR_BOLD))
            log_warning("Store these shares securely. Any K of them can reconstruct the secret.")
            
    elif args.command == "reconstruct":
        if not args.input:
            log_error("Must specify at least one share using --input")
            sys.exit(1)
            
        # Load shares from arguments/files
        raw_shares = []
        for item in args.input:
            if os.path.exists(item):
                with open(item, 'r') as f:
                    content = f.read().strip()
                    raw_shares.append(content)
            else:
                raw_shares.append(item)
                
        decoded = []
        for idx, sh_str in enumerate(raw_shares):
            try:
                x, y_bytes = decode_share(sh_str)
                decoded.append((x, y_bytes))
            except Exception as e:
                log_error(f"Failed to parse input share {idx+1}: {e}")
                sys.exit(1)
                
        # Remove duplicate shares by index
        unique_shares = {}
        for x, y_bytes in decoded:
            unique_shares[x] = y_bytes
            
        shares_list = list(unique_shares.items())
        log_info(f"Loaded {len(shares_list)} unique shares (Threshold required depends on generation config).")
        
        try:
            reconstructed = reconstruct_secret(shares_list)
            
            if args.output:
                with open(args.output, 'wb') as f:
                    f.write(reconstructed)
                log_success(f"Reconstructed secret written to: {args.output}")
            else:
                # Try to decode as UTF-8, else hex dump
                try:
                    text = reconstructed.decode('utf-8')
                    print("\n" + color_text("--- RECONSTRUCTED SECRET ---", COLOR_BOLD))
                    print(text)
                    print(color_text("----------------------------", COLOR_BOLD))
                except UnicodeDecodeError:
                    log_warning("Reconstructed data is binary (not valid UTF-8). Hex representation:")
                    print(reconstructed.hex())
        except Exception as e:
            log_error(f"Reconstruction failed: {e}")
            log_warning("Verify that you have provided the correct number of valid shares (K threshold).")
            sys.exit(1)

if __name__ == "__main__":
    main()
