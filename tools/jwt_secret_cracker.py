#!/usr/bin/env python3
"""
JWT HS256 Secret Cracker - Offline dictionary and brute-force key cracking tool.

This tool decodes the headers and payloads of HS256 JSON Web Tokens (JWTs) 
and performs offline dictionary or brute-force attacks to crack weak signature secrets.
It is completely standalone and uses only Python standard libraries.

Usage:
    python tools/jwt_secret_cracker.py JWT_TOKEN --wordlist WORDLIST_FILE
    python tools/jwt_secret_cracker.py JWT_TOKEN --brute --charset abcdef123 --max-len 4
"""

import argparse
import base64
import hashlib
import hmac
import itertools
import json
import os
import sys
import time


def init_colors():
    if sys.stdout.isatty() and os.name == 'nt':
        os.system('')
    use_color = sys.stdout.isatty()
    return {
        "green": "\033[92m" if use_color else "",
        "red": "\033[91m" if use_color else "",
        "yellow": "\033[93m" if use_color else "",
        "blue": "\033[94m" if use_color else "",
        "cyan": "\033[96m" if use_color else "",
        "bold": "\033[1m" if use_color else "",
        "reset": "\033[0m" if use_color else ""
    }


COLORS = init_colors()


def base64url_decode(payload):
    """Decodes base64url encoded strings by adding correct padding."""
    rem = len(payload) % 4
    if rem > 0:
        payload += '=' * (4 - rem)
    # Convert base64url alphabet to standard base64 alphabet
    converted = payload.replace('-', '+').replace('_', '/')
    return base64.b64decode(converted)


def parse_jwt(token):
    """Splits and decodes JWT parts."""
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format. Must contain exactly 3 segments separated by dots.")
        
    header_b64, payload_b64, signature_b64 = parts
    
    try:
        header = json.loads(base64url_decode(header_b64).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to decode header: {e}")
        
    try:
        payload = json.loads(base64url_decode(payload_b64).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to decode payload: {e}")
        
    try:
        signature = base64url_decode(signature_b64)
    except Exception as e:
        raise ValueError(f"Failed to decode signature: {e}")
        
    return {
        "header": header,
        "payload": payload,
        "signature": signature,
        "message": f"{header_b64}.{payload_b64}".encode('utf-8')
    }


def crack_dictionary(token_data, wordlist_path):
    """Attempts to crack JWT using a wordlist dictionary."""
    message = token_data['message']
    target_sig = token_data['signature']
    
    if not os.path.exists(wordlist_path):
        print(f"{COLORS['red']}[!] Wordlist file does not exist: {wordlist_path}{COLORS['reset']}")
        return None
        
    print(f"Starting dictionary attack using: {COLORS['cyan']}{os.path.basename(wordlist_path)}{COLORS['reset']}")
    
    start_time = time.perf_counter()
    count = 0
    
    try:
        with open(wordlist_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                key = line.strip()
                if not key:
                    continue
                    
                key_bytes = key.encode('utf-8')
                # Compute signature
                sig = hmac.new(key_bytes, message, hashlib.sha256).digest()
                count += 1
                
                if sig == target_sig:
                    elapsed = time.perf_counter() - start_time
                    return key, count, elapsed
                    
                if count % 100000 == 0:
                    elapsed = time.perf_counter() - start_time
                    hps = count / elapsed if elapsed > 0 else 0
                    print(f"  Tested {count} keys... Speed: {hps:.0f} keys/sec")
                    
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Attack paused/interrupted.{COLORS['reset']}")
        
    elapsed = time.perf_counter() - start_time
    return None, count, elapsed


def crack_brute_force(token_data, charset, min_len, max_len):
    """Attempts to crack JWT using brute-force character combinations."""
    message = token_data['message']
    target_sig = token_data['signature']
    
    print(f"Starting brute-force attack...")
    print(f"  Charset: {COLORS['bold']}{charset}{COLORS['reset']}")
    print(f"  Length range: {min_len} to {max_len} characters")
    
    start_time = time.perf_counter()
    count = 0
    
    try:
        for length in range(min_len, max_len + 1):
            print(f"  Testing keys of length: {length}")
            for combo in itertools.product(charset, repeat=length):
                key = "".join(combo)
                key_bytes = key.encode('utf-8')
                
                sig = hmac.new(key_bytes, message, hashlib.sha256).digest()
                count += 1
                
                if sig == target_sig:
                    elapsed = time.perf_counter() - start_time
                    return key, count, elapsed
                    
                if count % 100000 == 0:
                    elapsed = time.perf_counter() - start_time
                    hps = count / elapsed if elapsed > 0 else 0
                    print(f"    Tested {count} keys... Speed: {hps:.0f} keys/sec")
                    
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Attack paused/interrupted.{COLORS['reset']}")
        
    elapsed = time.perf_counter() - start_time
    return None, count, elapsed


def main():
    parser = argparse.ArgumentParser(description="Offline HS256 JWT Secret Cracker")
    parser.add_argument("token", help="The raw HS256 JWT string to crack")
    
    # Attack options
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-w", "--wordlist", help="Path to dictionary wordlist file")
    group.add_argument("-b", "--brute", action="store_true", help="Enable brute-force mode")
    
    # Brute force parameters
    parser.add_argument("-c", "--charset", default="abcdefghijklmnopqrstuvwxyz0123456789", 
                        help="Charset for brute force (default: lowercase alphanumeric)")
    parser.add_argument("--min-len", type=int, default=1, help="Minimum key length for brute-force (default: 1)")
    parser.add_argument("--max-len", type=int, default=5, help="Maximum key length for brute-force (default: 5)")
    
    args = parser.parse_args()
    
    # Decode token metadata
    try:
        token_data = parse_jwt(args.token)
    except ValueError as e:
        print(f"{COLORS['red']}[!] Error parsing token: {e}{COLORS['reset']}")
        sys.exit(1)
        
    # Inspect Header and Payload
    print(f"{COLORS['bold']}=== JWT INFORMATION ==={COLORS['reset']}")
    print(f"Header:  {COLORS['cyan']}{json.dumps(token_data['header'])}{COLORS['reset']}")
    print(f"Payload: {COLORS['green']}{json.dumps(token_data['payload'])}{COLORS['reset']}")
    print(f"Algorithm: {COLORS['bold']}{token_data['header'].get('alg')}{COLORS['reset']}")
    
    if token_data['header'].get('alg') != 'HS256':
        print(f"\n{COLORS['red']}[!] WARNING: Token algorithm is {token_data['header'].get('alg')}. Only HS256 is supported.{COLORS['reset']}")
        choice = input("Attempt to crack anyway? [y/N]: ").strip().lower()
        if choice not in ('y', 'yes'):
            sys.exit(0)
            
    print("=======================\n")
    
    if args.wordlist:
        key, count, elapsed = crack_dictionary(token_data, args.wordlist)
    else:
        key, count, elapsed = crack_brute_force(token_data, args.charset, args.min_len, args.max_len)
        
    # Display Results
    hps = count / elapsed if elapsed > 0 else 0
    print(f"\nFinished in {elapsed:.2f} seconds.")
    print(f"Total keys checked: {count} ({hps:.0f} keys/sec)")
    
    if key:
        print(f"\n{COLORS['green']}{COLORS['bold']}[+] CRACKED! Secret Key Found: {COLORS['reset']}{COLORS['reverse']}{COLORS['bold']}{key}{COLORS['reset']}")
    else:
        print(f"\n{COLORS['red']}[-] Crack failed. Key not found in search space.{COLORS['reset']}")


if __name__ == "__main__":
    main()
