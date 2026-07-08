#!/usr/bin/env python3
"""
UUIDv7 Generator, Parser, and Benchmarking Utility
A zero-dependency Python tool to generate cryptographically secure, time-ordered UUIDv7
identifiers (RFC 9562), parse them to extract timestamps, validate formats, and benchmark performance.
"""

import argparse
import datetime
import os
import re
import struct
import time
from typing import Dict, List, Optional, Tuple


# Global state for monotonic generation within the same millisecond
_last_timestamp = 0
_last_sequence = 0

UUIDV7_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE
)


def generate_uuidv7() -> str:
    """
    Generates a cryptographically secure, time-ordered UUIDv7 (RFC 9562).
    Ensures monotonicity in tight loops using a 12-bit sub-millisecond sequence counter.
    """
    global _last_timestamp, _last_sequence
    
    # Get current time in milliseconds
    ts_ms = int(time.time() * 1000)
    
    # Handle monotonic sub-millisecond ordering
    if ts_ms <= _last_timestamp:
        ts_ms = _last_timestamp
        _last_sequence += 1
    else:
        _last_timestamp = ts_ms
        _last_sequence = 0
        
    # If the 12-bit sequence space is exhausted (4,096 values in one millisecond),
    # we simulate time moving forward by 1 millisecond.
    if _last_sequence > 0xfff:
        ts_ms += 1
        _last_timestamp = ts_ms
        _last_sequence = 0

    # 48-bit unix_ts_ms (6 bytes)
    ts_bytes = struct.pack(">Q", ts_ms)[2:]
    
    # 12-bit sequence combined with 4-bit version (binary 0111 = 7) -> 16 bits (2 bytes)
    val_rand_a = 0x7000 | (_last_sequence & 0xfff)
    rand_a_bytes = struct.pack(">H", val_rand_a)
    
    # 62-bit random bits combined with 2-bit variant (binary 10) -> 64 bits (8 bytes)
    raw_rand_b = struct.unpack(">Q", os.urandom(8))[0]
    val_rand_b = (raw_rand_b & 0x3fffffffffffffff) | 0x8000000000000000
    rand_b_bytes = struct.pack(">Q", val_rand_b)
    
    # Combine to 16 bytes
    uuid_bytes = ts_bytes + rand_a_bytes + rand_b_bytes
    
    # Format to canonical 8-4-4-4-12 hex string
    hex_str = uuid_bytes.hex()
    return (
        f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"
    )


def validate_uuidv7(uuid_str: str) -> bool:
    """Validates if a string is a valid UUIDv7 format."""
    return bool(UUIDV7_REGEX.match(uuid_str.strip()))


def parse_uuidv7(uuid_str: str) -> Optional[Dict]:
    """
    Parses a UUIDv7 to extract the timestamp and metadata.
    Returns a dictionary of parsed details or None if invalid.
    """
    clean_uuid = uuid_str.strip().lower()
    if not validate_uuidv7(clean_uuid):
        return None
        
    # Remove dashes
    hex_digits = clean_uuid.replace("-", "")
    
    # Extract 48-bit unix_ts_ms from first 12 hex digits (6 bytes)
    ts_hex = hex_digits[0:12]
    ts_ms = int(ts_hex, 16)
    
    # Extract sequence number from characters 13 to 15 (12-bit rand_a field)
    # Character 12 is the version '7'
    seq_hex = hex_digits[13:16]
    seq_val = int(seq_hex, 16)
    
    # Convert timestamp to UTC datetime
    dt_utc = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
    
    return {
        "uuid": clean_uuid,
        "timestamp_ms": ts_ms,
        "datetime_utc": dt_utc.isoformat(timespec="milliseconds"),
        "sequence_counter": seq_val,
        "variant": hex_digits[16],  # Expect 8, 9, a, or b
    }


def run_benchmark(count: int = 100000) -> Tuple[float, float, bool]:
    """
    Benchmarks UUIDv7 generation speed and validates sorting order.
    Returns (gen_duration, sort_duration, is_ordered).
    """
    import uuid  # Standard library uuid module for comparison
    
    # 1. Benchmark Generation
    start_time = time.perf_counter()
    uuids = [generate_uuidv7() for _ in range(count)]
    gen_duration = time.perf_counter() - start_time
    
    # 2. Benchmark Sorting
    # Creating a shuffled copy to test sorting order
    import random
    shuffled_uuids = list(uuids)
    random.shuffle(shuffled_uuids)
    
    start_sort = time.perf_counter()
    shuffled_uuids.sort()
    sort_duration = time.perf_counter() - start_sort
    
    # Check if sorted list matches original insertion order (monotonic check)
    is_ordered = shuffled_uuids == uuids
    
    return gen_duration, sort_duration, is_ordered


def main():
    parser = argparse.ArgumentParser(
        description="UUIDv7 Generator, Validator, and Parser. "
                    "Works with time-ordered unique identifiers (RFC 9562)."
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-g", "--generate", type=int, nargs="?", const=1, metavar="COUNT",
                       help="Generate one or more UUIDv7 values (default: 1)")
    group.add_argument("-p", "--parse", metavar="UUID", help="Parse a UUIDv7 to extract its creation timestamp")
    group.add_argument("-c", "--check", metavar="UUID", help="Validate if a string is a valid UUIDv7")
    group.add_argument("-b", "--benchmark", type=int, nargs="?", const=50000, metavar="RUNS",
                       help="Benchmark generation and sorting performance (default: 50,000)")
                       
    args = parser.parse_args()
    
    if args.generate is not None:
        count = args.generate
        for _ in range(count):
            print(generate_uuidv7())
            
    elif args.parse:
        result = parse_uuidv7(args.parse)
        if result:
            print("[+] Parsed UUIDv7 Details:")
            print(f"    UUID:         {result['uuid']}")
            print(f"    Timestamp:    {result['timestamp_ms']} ms")
            print(f"    UTC Time:     {result['datetime_utc']}")
            print(f"    Sequence ID:  {result['sequence_counter']}")
            print(f"    Variant Bits: {result['variant']} (RFC 9562 compliant)")
        else:
            print("[-] Error: The string is not a valid UUIDv7 format.", file=sys.stderr)
            sys.exit(1)
            
    elif args.check:
        is_valid = validate_uuidv7(args.check)
        if is_valid:
            print("[+] Valid UUIDv7")
            sys.exit(0)
        else:
            print("[-] Invalid UUIDv7 format", file=sys.stderr)
            sys.exit(1)
            
    elif args.benchmark is not None:
        runs = args.benchmark
        print(f"[*] Benchmarking {runs:,} iterations...")
        gen_dur, sort_dur, is_ordered = run_benchmark(runs)
        
        gen_rate = runs / gen_dur
        sort_rate = runs / sort_dur
        
        print("-" * 50)
        print(f"UUIDv7 Generation Speed: {gen_rate:,.2f} ops/sec ({gen_dur:.4f} seconds total)")
        print(f"UUIDv7 Sorting Speed:    {sort_rate:,.2f} ops/sec ({sort_dur:.4f} seconds total)")
        print(f"Monotonic Sorting Order: {'PASSED (perfectly ordered by time)' if is_ordered else 'FAILED'}")
        print("-" * 50)


if __name__ == "__main__":
    main()
