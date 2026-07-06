#!/usr/bin/env python3
"""
RFC 8785 JSON Canonicalization Scheme (JCS) & Cryptographic Digest Tool

Canonicalizes JSON structures according to RFC 8785 rules:
1. Object keys sorted deterministically by UTF-16 code units.
2. Uniform whitespace removal (compact representation).
3. Standardized number representation.
4. UTF-8 character encoding without unneeded escapes.

Computes canonical SHA-256 / SHA-512 hashes and provides structural diffing.

Usage:
    python json_canonicalizer.py [json_file] [options]
    python json_canonicalizer.py --diff file1.json file2.json
"""

import os
import sys
import json
import hashlib
import argparse
from typing import Any

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def canonicalize_obj(obj: Any) -> Any:
    """Recursively orders dictionary keys deterministically according to RFC 8785 rules."""
    if isinstance(obj, dict):
        # Sort keys by UTF-16 code unit representation
        sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16be"))
        return {k: canonicalize_obj(obj[k]) for k in sorted_keys}
    elif isinstance(obj, list):
        return [canonicalize_obj(item) for item in obj]
    elif isinstance(obj, float):
        # Format floats deterministically (integers without trailing zeros)
        if obj.is_integer():
            return int(obj)
        return obj
    return obj


def canonicalize_json_bytes(obj: Any) -> bytes:
    """Converts Python object into RFC 8785 canonical UTF-8 encoded JSON bytes."""
    canonical_data = canonicalize_obj(obj)
    # separators=(',', ':') removes whitespace, ensure_ascii=False keeps clean UTF-8
    json_str = json.dumps(canonical_data, separators=(",", ":"), ensure_ascii=False)
    return json_str.encode("utf-8")


def compute_digest(data_bytes: bytes, algo: str = "sha256") -> str:
    """Computes hex digest of canonical byte payload."""
    h = hashlib.new(algo)
    h.update(data_bytes)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="RFC 8785 JSON Canonicalization Scheme (JCS) & Digest Tool")
    parser.add_argument("target", nargs="?", help="Path to JSON file or raw JSON string")
    parser.add_argument("--algo", choices=["sha256", "sha512", "md5"], default="sha256", help="Hash algorithm (default: sha256)")
    parser.add_argument("--output", "-o", help="Save canonicalized JSON output to file")
    parser.add_argument("--digest-only", action="store_true", help="Print only the hex digest")
    parser.add_argument("--diff", nargs=2, metavar=("FILE1", "FILE2"), help="Compare canonical structures of two JSON files")
    parser.add_argument("--verify", metavar="HASH", help="Verify if JSON input matches target hash digest")

    args = parser.parse_args()

    if args.diff:
        file1, file2 = args.diff
        try:
            with open(file1, "r", encoding="utf-8") as f1, open(file2, "r", encoding="utf-8") as f2:
                obj1 = json.load(f1)
                obj2 = json.load(f2)
                
            bytes1 = canonicalize_json_bytes(obj1)
            bytes2 = canonicalize_json_bytes(obj2)
            hash1 = compute_digest(bytes1, args.algo)
            hash2 = compute_digest(bytes2, args.algo)

            print(f"\n{BOLD}{CYAN}=== Canonical JSON Structural Diff ==={RESET}")
            print(f"File 1: {file1} -> {args.algo}: {hash1}")
            print(f"File 2: {file2} -> {args.algo}: {hash2}\n")

            if bytes1 == bytes2:
                print(f"{GREEN}MATCH: Both JSON documents are structurally identical in canonical form.{RESET}\n")
                sys.exit(0)
            else:
                print(f"{RED}MISMATCH: Document contents differ in canonical structure.{RESET}\n")
                sys.exit(1)
        except Exception as e:
            print(f"{RED}Error comparing files: {e}{RESET}")
            sys.exit(1)

    if not args.target:
        parser.print_help()
        sys.exit(1)

    # Parse target (file path or json string)
    try:
        if os.path.isfile(args.target):
            with open(args.target, "r", encoding="utf-8") as f:
                obj = json.load(f)
        else:
            obj = json.loads(args.target)
    except Exception as e:
        print(f"{RED}Error parsing JSON input: {e}{RESET}")
        sys.exit(1)

    canonical_bytes = canonicalize_json_bytes(obj)
    digest = compute_digest(canonical_bytes, args.algo)

    if args.verify:
        expected = args.verify.strip().lower()
        actual = digest.lower()
        if expected == actual:
            print(f"{GREEN}VERIFICATION SUCCESS: Hash matches expected canonical digest.{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}VERIFICATION FAILED: Hash mismatch.{RESET}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
            sys.exit(1)

    if args.digest_only:
        print(digest)
        sys.exit(0)

    print(f"\n{BOLD}{CYAN}=== RFC 8785 Canonical JSON Output ==={RESET}")
    print(f"{BOLD}Algorithm:{RESET} {args.algo.upper()}")
    print(f"{BOLD}Digest:{RESET}    {GREEN}{digest}{RESET}")
    print(f"{BOLD}Payload:{RESET}   {canonical_bytes.decode('utf-8')}\n")

    if args.output:
        with open(args.output, "wb") as f:
            f.write(canonical_bytes)
        print(f"{GREEN}Saved canonical output to '{args.output}'.{RESET}")


if __name__ == "__main__":
    main()
