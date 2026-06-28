#!/usr/bin/env python3
"""
Environment Variable Encryption Tool - Encrypt and decrypt .env files securely.

Uses Fernet symmetric encryption to protect sensitive environment variables.
Perfect for storing encrypted .env files in version control.

Usage:
    python env_encryption_tool.py encrypt .env .env.enc  # Encrypt
    python env_encryption_tool.py decrypt .env.enc .env  # Decrypt
    python env_encryption_tool.py keygen                 # Generate new key
"""

import argparse
import base64
import os
import sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Error: cryptography package required. Install with: pip install cryptography")
    sys.exit(1)


KEY_FILE = ".env.key"


def generate_key():
    """Generate a new Fernet encryption key."""
    key = Fernet.generate_key()
    return key.decode()


def save_key(key, filepath=KEY_FILE):
    """Save encryption key to file."""
    with open(filepath, 'w') as f:
        f.write(key)
    print(f"Key saved to {filepath}")
    print(f"IMPORTANT: Store this key securely! Without it, encrypted data cannot be recovered.")
    os.chmod(filepath, 0o600)  # Restrict permissions


def load_key(filepath=KEY_FILE):
    """Load encryption key from file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Key file not found: {filepath}")
    with open(filepath, 'r') as f:
        return f.read().strip()


def encrypt_file(input_path, output_path, key=None):
    """Encrypt a file using Fernet encryption."""
    if key is None:
        key = load_key()
    
    fernet = Fernet(key.encode())
    
    with open(input_path, 'rb') as f:
        content = f.read()
    
    encrypted = fernet.encrypt(content)
    
    with open(output_path, 'wb') as f:
        f.write(encrypted)
    
    print(f"Encrypted: {input_path} -> {output_path}")


def decrypt_file(input_path, output_path, key=None):
    """Decrypt a file using Fernet encryption."""
    if key is None:
        key = load_key()
    
    fernet = Fernet(key.encode())
    
    with open(input_path, 'rb') as f:
        encrypted = f.read()
    
    try:
        decrypted = fernet.decrypt(encrypted)
    except Exception as e:
        print(f"Decryption failed: {e}")
        print("Make sure you're using the correct encryption key.")
        sys.exit(1)
    
    with open(output_path, 'wb') as f:
        f.write(decrypted)
    
    print(f"Decrypted: {input_path} -> {output_path}")


def encrypt_env_string(env_string, key=None):
    """Encrypt an environment variable string."""
    if key is None:
        key = load_key()
    
    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(env_string.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_env_string(encrypted_string, key=None):
    """Decrypt an environment variable string."""
    if key is None:
        key = load_key()
    
    fernet = Fernet(key.encode())
    encrypted = base64.urlsafe_b64decode(encrypted_string.encode())
    decrypted = fernet.decrypt(encrypted).decode()
    return decrypted


def main():
    parser = argparse.ArgumentParser(
        description="Encrypt and decrypt .env files securely using Fernet encryption"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Keygen command
    keygen_parser = subparsers.add_parser('keygen', help='Generate new encryption key')
    keygen_parser.add_argument('--output', '-o', default=KEY_FILE, help=f'Output file (default: {KEY_FILE})')
    
    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Encrypt a file')
    encrypt_parser.add_argument('input', help='Input file to encrypt')
    encrypt_parser.add_argument('output', help='Output encrypted file')
    encrypt_parser.add_argument('--key', '-k', help='Encryption key (or use key file)')
    
    # Decrypt command
    decrypt_parser = subparsers.add_parser('decrypt', help='Decrypt a file')
    decrypt_parser.add_argument('input', help='Input encrypted file')
    decrypt_parser.add_argument('output', help='Output decrypted file')
    decrypt_parser.add_argument('--key', '-k', help='Encryption key (or use key file)')
    
    # Encrypt string command
    encrypt_str_parser = subparsers.add_parser('encrypt-string', help='Encrypt a single value')
    encrypt_str_parser.add_argument('value', help='Value to encrypt')
    encrypt_str_parser.add_argument('--key', '-k', help='Encryption key (or use key file)')
    
    # Decrypt string command
    decrypt_str_parser = subparsers.add_parser('decrypt-string', help='Decrypt a single value')
    decrypt_str_parser.add_argument('value', help='Encrypted value to decrypt')
    decrypt_str_parser.add_argument('--key', '-k', help='Encryption key (or use key file)')
    
    args = parser.parse_args()
    
    if args.command == 'keygen':
        key = generate_key()
        save_key(key, args.output)
        print(f"\nYour encryption key: {key}")
    
    elif args.command == 'encrypt':
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)
        encrypt_file(args.input, args.output, args.key)
    
    elif args.command == 'decrypt':
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)
        decrypt_file(args.input, args.output, args.key)
    
    elif args.command == 'encrypt-string':
        encrypted = encrypt_env_string(args.value, args.key)
        print(f"Encrypted: {encrypted}")
    
    elif args.command == 'decrypt-string':
        try:
            decrypted = decrypt_env_string(args.value, args.key)
            print(f"Decrypted: {decrypted}")
        except Exception as e:
            print(f"Decryption failed: {e}")
            sys.exit(1)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()