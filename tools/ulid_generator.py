#!/usr/bin/env python3
"""
ULID Generator & Analyzer
Generates, parses, validates, and converts ULIDs (Universally Unique Lexicographically Sortable Identifiers).
Compatible with UUIDs (128-bit) and lexicographically sortable.
"""

import argparse
import time
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone

# Crockford's Base32 Alphabet (excludes I, L, O, U to prevent confusion)
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET_MAP = {char: idx for idx, char in enumerate(ALPHABET)}

def encode_int(val, length):
    """Encode an integer to a Crockford Base32 string of a specific length."""
    result = []
    for _ in range(length):
        result.append(ALPHABET[val % 32])
        val //= 32
    return "".join(reversed(result))

def decode_str(s):
    """Decode a Crockford Base32 string to an integer."""
    val = 0
    for char in s:
        if char not in ALPHABET_MAP:
            raise ValueError(f"Invalid character in Base32 string: {char}")
        val = val * 32 + ALPHABET_MAP[char]
    return val

class MonotonicFactory:
    """Generates sequential/monotonic ULIDs for the same millisecond."""
    def __init__(self):
        self.last_ms = 0
        self.last_entropy = 0

    def generate(self, ms=None):
        if ms is None:
            ms = int(time.time() * 1000)
            
        if ms == self.last_ms:
            # Increment entropy
            self.last_entropy = (self.last_entropy + 1) & 0xFFFFFFFFFFFFFFFFFFFF # 80 bits
            if self.last_entropy == 0:
                # Overflowed entropy in the same ms, wait/increment ms
                ms += 1
                self.last_entropy = int.from_bytes(secrets.token_bytes(10), byteorder='big')
        else:
            self.last_entropy = int.from_bytes(secrets.token_bytes(10), byteorder='big')
            self.last_ms = ms
            
        # Encode
        ts_part = encode_int(ms, 10)
        entropy_part = encode_int(self.last_entropy, 16)
        return ts_part + entropy_part

def generate_ulid(ms=None):
    """Generate a single random ULID."""
    if ms is None:
        ms = int(time.time() * 1000)
    ts_part = encode_int(ms, 10)
    entropy_bytes = secrets.token_bytes(10)
    entropy_val = int.from_bytes(entropy_bytes, byteorder='big')
    entropy_part = encode_int(entropy_val, 16)
    return ts_part + entropy_part

def parse_ulid(ulid_str):
    """Parse a ULID into its timestamp (UTC datetime) and entropy value."""
    ulid_str = ulid_str.upper().replace('I', '1').replace('L', '1').replace('O', '0')
    if len(ulid_str) != 26:
        raise ValueError("ULID must be exactly 26 characters.")
    
    ts_part = ulid_str[:10]
    entropy_part = ulid_str[10:]
    
    ms = decode_str(ts_part)
    entropy = decode_str(entropy_part)
    
    dt = datetime.fromtimestamp(ms / 1000.0, timezone.utc)
    return ms, dt, entropy

def validate_ulid(ulid_str):
    """Check if a string is a valid ULID."""
    if not isinstance(ulid_str, str) or len(ulid_str) != 26:
        return False
    ulid_str = ulid_str.upper().replace('I', '1').replace('L', '1').replace('O', '0')
    return all(char in ALPHABET for char in ulid_str)

def ulid_to_uuid(ulid_str):
    """Convert a ULID to a standard UUIDv4 format."""
    ms, _, entropy = parse_ulid(ulid_str)
    # Combine 48-bit timestamp and 80-bit entropy to 128-bit integer
    val = (ms << 80) | entropy
    return uuid.UUID(int=val)

def uuid_to_ulid(uuid_obj):
    """Convert a UUID to a ULID string."""
    if isinstance(uuid_obj, str):
        uuid_obj = uuid.UUID(uuid_obj)
    val = uuid_obj.int
    ms = val >> 80
    entropy = val & 0xFFFFFFFFFFFFFFFFFFFF
    return encode_int(ms, 10) + encode_int(entropy, 16)

def main():
    parser = argparse.ArgumentParser(description="ULID Utility - Generate, Parse, Validate, and Convert ULIDs")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", aliases=["gen"], help="Generate new ULIDs")
    gen_parser.add_argument("-n", "--count", type=int, default=1, help="Number of ULIDs to generate")
    gen_parser.add_argument("-m", "--monotonic", action="store_true", help="Generate monotonically increasing ULIDs")
    gen_parser.add_argument("-t", "--timestamp", type=str, help="Custom timestamp (ISO format YYYY-MM-DD or Unix epoch ms)")

    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse a ULID to extract timestamp and entropy info")
    parse_parser.add_argument("ulid", help="The ULID string to parse")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate a ULID string")
    val_parser.add_argument("ulid", help="The ULID string to validate")

    # Convert command
    conv_parser = subparsers.add_parser("convert", help="Convert between ULID and UUID formats")
    conv_parser.add_argument("identifier", help="A ULID or UUID string to convert")

    args = parser.parse_args()

    if not args.command:
        # Default behavior: generate 1 ULID
        print(generate_ulid())
        return

    if args.command in ("generate", "gen"):
        ms = None
        if args.timestamp:
            try:
                # Try unix ms first
                ms = int(args.timestamp)
            except ValueError:
                # Try parsing as ISO format
                try:
                    dt = datetime.fromisoformat(args.timestamp)
                    ms = int(dt.timestamp() * 1000)
                except ValueError:
                    print("Error: Timestamp must be either Unix epoch milliseconds or ISO datetime string.", file=sys.stderr)
                    sys.exit(1)

        if args.monotonic:
            factory = MonotonicFactory()
            for _ in range(args.count):
                print(factory.generate(ms))
        else:
            for _ in range(args.count):
                print(generate_ulid(ms))

    elif args.command == "parse":
        try:
            ms, dt, entropy = parse_ulid(args.ulid)
            print(f"ULID:          {args.ulid.upper()}")
            print(f"Unix Epoch Ms: {ms}")
            print(f"Timestamp UTC: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
            print(f"Entropy Hex:   {hex(entropy)[2:].upper().zfill(20)}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "validate":
        valid = validate_ulid(args.ulid)
        if valid:
            print(f"✓ '{args.ulid}' is a VALID ULID format.")
            sys.exit(0)
        else:
            print(f"✗ '{args.ulid}' is an INVALID ULID format.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "convert":
        ident = args.identifier.strip()
        # Check if it looks like UUID
        if len(ident) in (32, 36) and '-' in ident or len(ident) == 32:
            try:
                u = uuid.UUID(ident)
                print(f"UUID: {u}")
                print(f"ULID: {uuid_to_ulid(u)}")
            except ValueError:
                print("Error: Invalid UUID format.", file=sys.stderr)
                sys.exit(1)
        elif len(ident) == 26:
            try:
                u = ulid_to_uuid(ident)
                print(f"ULID: {ident.upper()}")
                print(f"UUID: {u}")
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Input does not match length of a UUID (32/36 chars) or ULID (26 chars).", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
