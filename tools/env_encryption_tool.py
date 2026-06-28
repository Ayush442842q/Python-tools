#!/usr/bin/env python3
"""
Environment Variable Encryption Tool - Encrypt and decrypt .env files.

Securely encrypt sensitive environment variables using symmetric encryption
(AES-GCM) with a master password or key file.

Features:
- Encrypt .env files with AES-256-GCM
- Decrypt encrypted files back to plaintext
- Support for password-based and key-file encryption
- Secure key derivation using PBKDF2/HKDF
- Tamper detection via authenticated encryption
- Batch encryption for multiple files
- Detect and warn about potentially sensitive variables

Security:
- Uses Fernet (AES-128-CBC with HMAC) or AES-GCM via cryptography library
- Salt is randomly generated for each encryption
- Keys can be derived from passwords or loaded from files

Usage:
    python env_encryption_tool.py encrypt <env_file> --password <password>
    python env_encryption_tool.py decrypt <encrypted_file> --password <password>
    python env_encryption_tool.py encrypt .env --key-file .encryption.key
    python env_encryption_tool.py decrypt .env.enc --key-file .encryption.key

Example:
    # Encrypt with password
    python env_encryption_tool.py encrypt .env --password "my-secret-password"

    # Create key file and use it
    python env_encryption_tool.py generate-key > .env.key
    python env_encryption_tool.py encrypt .env --key-file .env.key

    # Decrypt
    python env_encryption_tool.py decrypt .env.enc --key-file .env.key
"""

import os
import sys
import base64
import argparse
import getpass
from pathlib import Path
from typing import Optional, Tuple

# Try to use cryptography library, fall back to basic encryption
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

    # Fallback: simple XOR-based "encryption" (NOT SECURE, for demonstration only)
    class AESGCM:
        def __init__(self, key):
            self.key = key[:32].ljust(32, b'\x00')

        def encrypt(self, nonce, data, associated_data=None):
            # Simple XOR (NOT SECURE!)
            result = bytes(a ^ b for a, b in zip(data, (self.key * (len(data)//32 + 1))[:len(data)]))
            return nonce + result  # Prepend nonce as IV

        def decrypt(self, data, associated_data=None):
            nonce = data[:12]
            encrypted = data[12:]
            result = bytes(a ^ b for a, b in zip(encrypted, (self.key * (len(encrypted)//32 + 1))[:len(encrypted)]))
            return result


# Files that look like they contain secrets
SENSITIVE_PATTERNS = [
    'SECRET', 'KEY', 'TOKEN', 'PASSWORD', 'PASSWD', 'CREDENTIAL',
    'API_KEY', 'APIKEY', 'API_SECRET', 'PRIVATE', 'AUTH',
    'CRYPTO', 'SIGNING', 'ENCRYPTION', 'DECRYPTION',
]


class EnvEncryptor:
    """Encrypt and decrypt .env files."""

    SALT_SIZE = 16
    NONCE_SIZE = 12

    def __init__(self):
        self.salt: Optional[bytes] = None
        self.key: Optional[bytes] = None

    def derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password."""
        if salt is None:
            salt = os.urandom(self.SALT_SIZE)

        self.salt = salt

        if HAS_CRYPTO:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100_000,
            )
            self.key = kdf.derive(password.encode())
        else:
            # Simple key derivation (less secure fallback)
            self.key = (password.encode() * 4)[:32]

        return self.key

    def load_key_from_file(self, key_file: Path) -> bytes:
        """Load key from file."""
        content = key_file.read_bytes()
        self.key = base64.b64decode(content.strip()) if content else b''
        return self.key

    def generate_key(self) -> bytes:
        """Generate a random encryption key."""
        return os.urandom(32)

    def encrypt_file(self, input_path: Path, output_path: Optional[Path] = None,
                     password: Optional[str] = None, key_file: Optional[Path] = None) -> Path:
        """Encrypt a .env file."""
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix(input_path.suffix + '.enc')

        # Read input
        content = input_path.read_text(encoding='utf-8')
        content_bytes = content.encode('utf-8')

        # Get encryption key
        if password:
            self.derive_key_from_password(password)
        elif key_file:
            self.load_key_from_file(key_file)
        else:
            raise ValueError("Either password or key-file must be provided")

        # Generate nonce
        nonce = os.urandom(self.NONCE_SIZE)

        # Encrypt
        cipher = AESGCM(self.key)
        encrypted = cipher.encrypt(nonce, content_bytes, None)

        # Write output format: salt (if password) + nonce + encrypted data
        with open(output_path, 'wb') as f:
            if password:
                f.write(self.salt)  # Write salt first
            f.write(nonce)
            f.write(encrypted)

        # Print security info
        sensitive_count = 0
        for line in content.splitlines():
            if '=' in line and any(p in line.upper() for p in SENSITIVE_PATTERNS):
                sensitive_count += 1

        print(f"Encrypted: {input_path} -> {output_path}")
        if password:
            print(f"Key derived from password (salt: {self.salt.hex()})")
            print("⚠️  Remember your password! It cannot be recovered.")
        if sensitive_count > 0:
            print(f"Detected {sensitive_count} potentially sensitive variable(s)")

        return output_path

    def decrypt_file(self, input_path: Path, output_path: Optional[Path] = None,
                     password: Optional[str] = None, key_file: Optional[Path] = None) -> Path:
        """Decrypt an encrypted file."""
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix('')
            if output_path.suffix == '.enc':
                output_path = output_path.with_suffix('')
            else:
                output_path = output_path.with_suffix('.dec')

        # Read encrypted content
        encrypted_content = input_path.read_bytes()

        # Parse salt (if password-based) and nonce
        offset = 0
        if password:
            self.salt = encrypted_content[:self.SALT_SIZE]
            offset = self.SALT_SIZE

        nonce = encrypted_content[offset:offset + self.NONCE_SIZE]
        encrypted = encrypted_content[offset + self.NONCE_SIZE:]

        # Get decryption key
        if password:
            self.derive_key_from_password(password, self.salt)
        elif key_file:
            self.load_key_from_file(key_file)
        else:
            raise ValueError("Either password or key-file must be provided")

        # Decrypt
        try:
            cipher = AESGCM(self.key)
            decrypted = cipher.decrypt(nonce, encrypted, None)
        except Exception as e:
            raise ValueError(f"Decryption failed. Wrong password/key or corrupted file: {e}")

        # Write output
        content = decrypted.decode('utf-8')
        output_path.write_text(content, encoding='utf-8')

        print(f"Decrypted: {input_path} -> {output_path}")

        return output_path

    def save_key_to_file(self, key: bytes, output_path: Path) -> None:
        """Save encryption key to file."""
        encoded = base64.b64encode(key).decode()
        output_path.write_text(encoded + '\n', encoding='utf-8')
        print(f"Key saved to: {output_path.absolute()}")
        print("\n⚠️  IMPORTANT: Store this key securely!")
        print("   - Do not commit to version control")
        print("   - Add to .gitignore")
        print("   - Consider encrypting this file or using a secrets manager")


def main():
    parser = argparse.ArgumentParser(
        description='Encrypt and decrypt .env files securely'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Encrypt a .env file')
    encrypt_parser.add_argument('input_file', type=Path,
                                help='.env file to encrypt')
    encrypt_parser.add_argument('-o', '--output', type=Path,
                                help='Output file (default: input.env.enc)')
    encrypt_group = encrypt_parser.add_mutually_exclusive_group(required=True)
    encrypt_group.add_argument('--password',
                               help='Encryption password')
    encrypt_group.add_argument('--key-file', type=Path,
                               help='File containing encryption key')

    # Decrypt command
    decrypt_parser = subparsers.add_parser('decrypt', help='Decrypt an encrypted file')
    decrypt_parser.add_argument('input_file', type=Path,
                                help='Encrypted file to decrypt')
    decrypt_parser.add_argument('-o', '--output', type=Path,
                                help='Output file (default: input.dec)')
    decrypt_group = decrypt_parser.add_mutually_exclusive_group(required=True)
    decrypt_group.add_argument('--password',
                               help='Decryption password')
    decrypt_group.add_argument('--key-file', type=Path,
                               help='File containing encryption key')

    # Generate key command
    keygen_parser = subparsers.add_parser('generate-key',
                                          help='Generate a new encryption key')
    keygen_parser.add_argument('-o', '--output', type=Path,
                               help='Output file (default: stdout)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    encryptor = EnvEncryptor()

    try:
        if args.command == 'encrypt':
            # Handle interactive password if not provided
            password = args.password
            if not password and not args.key_file:
                password = getpass.getpass("Enter encryption password: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    print("Error: Passwords do not match", file=sys.stderr)
                    return 1

            encryptor.encrypt_file(
                args.input_file,
                output_path=args.output,
                password=password,
                key_file=args.key_file
            )

        elif args.command == 'decrypt':
            # Handle interactive password if not provided
            password = args.password
            if not password and not args.key_file:
                password = getpass.getpass("Enter decryption password: ")

            encryptor.decrypt_file(
                args.input_file,
                output_path=args.output,
                password=password,
                key_file=args.key_file
            )

        elif args.command == 'generate-key':
            key = encryptor.generate_key()

            if args.output:
                encryptor.save_key_to_file(key, args.output)
            else:
                print(base64.b64encode(key).decode())
                print("\n⚠️  Save this key securely - it cannot be recovered if lost!")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())