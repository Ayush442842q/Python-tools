#!/usr/bin/env python3
"""
Hash Generator & Verifier

Generate cryptographic hashes for text, standard input, or files, 
and verify inputs against an expected hash.

Usage:
    python tools/hash_generator.py [options]

Requirements:
    - Python 3.6+
"""

import sys
import os
import argparse
import hashlib

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

SUPPORTED_ALGORITHMS = sorted(list(hashlib.algorithms_guaranteed))

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def generate_string_hash(text, algorithm, salt=None):
    """Generate the hash of a string with optional salt."""
    h = hashlib.new(algorithm)
    if salt:
        h.update(salt.encode('utf-8'))
    h.update(text.encode('utf-8'))
    return h.hexdigest()

def generate_file_hash(file_path, algorithm):
    """Generate the hash of a file by reading it in chunks."""
    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"
    if os.path.isdir(file_path):
        return None, f"Target path is a directory, not a file: {file_path}"
        
    try:
        h = hashlib.new(algorithm)
        # Read in 64kb chunks
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest(), None
    except Exception as e:
        return None, f"Error hashing file: {e}"

def main():
    parser = argparse.ArgumentParser(
        description="Generate and verify cryptographic hashes for strings and files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Input source options (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-t", "--text", help="Text string to hash")
    group.add_argument("-f", "--file", help="Path to file to hash")
    group.add_argument("-s", "--stdin", action="store_true", help="Read input from standard input (stdin)")
    
    # Configuration options
    parser.add_argument(
        "-a", "--algo", 
        default="sha256", 
        choices=SUPPORTED_ALGORITHMS,
        help="Hash algorithm to use (default: sha256)"
    )
    parser.add_argument("--salt", help="Optional salt string prepended to text input (only works with text/stdin)")
    parser.add_argument("-u", "--uppercase", action="store_true", help="Output hash in uppercase letters")
    parser.add_argument("-v", "--verify", help="Expected hash to verify against (case insensitive)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    # Check that chosen algorithm is available
    if args.algo not in hashlib.algorithms_available:
        print_colored(f"Error: Algorithm '{args.algo}' is not available in the current environment.", RED, use_color)
        return 1

    # Get the input content
    result_hash = None
    input_desc = ""
    
    if args.text is not None:
        result_hash = generate_string_hash(args.text, args.algo, args.salt)
        input_desc = f"Text string"
        if args.salt:
            input_desc += f" (salted)"
    elif args.stdin:
        # Read all of stdin
        try:
            stdin_content = sys.stdin.read()
            result_hash = generate_string_hash(stdin_content, args.algo, args.salt)
            input_desc = "Standard Input (stdin)"
            if args.salt:
                input_desc += " (salted)"
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return 1
    elif args.file:
        hash_val, err = generate_file_hash(args.file, args.algo)
        if err:
            print_colored(f"Error: {err}", RED, use_color)
            return 1
        result_hash = hash_val
        input_desc = f"File: {os.path.basename(args.file)}"

    if not result_hash:
        print_colored("Error: Could not generate hash.", RED, use_color)
        return 1

    # Formatting output case
    if args.uppercase:
        result_hash = result_hash.upper()
    else:
        result_hash = result_hash.lower()

    # If verification is requested
    if args.verify:
        expected = args.verify.strip().lower()
        actual = result_hash.lower()
        
        print(f"Target: {input_desc}")
        print(f"Algorithm: {args.algo}")
        print(f"Expected:  {expected}")
        print(f"Computed:  {actual}")
        
        if expected == actual:
            print_colored("Verification Result: MATCH (PASS)", GREEN, use_color)
            return 0
        else:
            print_colored("Verification Result: MISMATCH (FAIL)", RED, use_color)
            return 2
    else:
        # Standard printing
        print(f"Target: {input_desc}")
        print(f"Algorithm: {args.algo}")
        print_colored(f"Hash: {result_hash}", GREEN, use_color)
        return 0

if __name__ == "__main__":
    sys.exit(main())
