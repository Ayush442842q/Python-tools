#!/usr/bin/env python3
"""
Dictionary-based Hash Cracker

Cracks cryptographic hashes using dictionary attacks with support for
auto-detecting hash algorithms, batch cracking, and candidate mutation rules.

Supported algorithms: MD5, SHA-1, SHA-224, SHA-256, SHA-384, SHA-512.

Usage:
    python tools/hash_cracker.py -s 5e86291d15b5f272a29486c732442491a96c112e7a3317c46c14c46f6f96615b -w wordlist.txt
    python tools/hash_cracker.py -s 5d41402abc4b2a76b9719d911017c592 -r
"""

import argparse
import hashlib
import os
import sys
import time

# Auto-detect algorithm based on hex string length
HASH_LENGTHS = {
    32: 'md5',
    40: 'sha1',
    56: 'sha224',
    64: 'sha256',
    96: 'sha384',
    128: 'sha512'
}

# Quick built-in wordlist of common passwords for quick testing if no wordlist is supplied
DEFAULT_PASSWORDS = [
    "password", "123456", "123456789", "12345", "12345678", "1234", "qwerty", "password123",
    "admin", "letmein", "welcome", "football", "monkey", "charlie", "donald", "shadow",
    "mustang", "superman", "batman", "trustnoone", "love", "secret", "hunter2", "login",
    "change-me", "root", "oracle", "postgres", "password1234", "jesus", "christ", "god"
]

def detect_hash_type(hash_str):
    """Detects hash algorithm from hex digest length."""
    length = len(hash_str)
    return HASH_LENGTHS.get(length, None)

def generate_mutations(word):
    """Generates variations of a candidate word to increase cracking success."""
    mutations = {word}
    
    # Capitalizations
    mutations.add(word.lower())
    mutations.add(word.upper())
    mutations.add(word.capitalize())
    
    # Common suffix digits
    suffixes = ['1', '12', '123', '1234', '11', '22', '33', '88', '99', '01', '2025', '2026']
    for s in suffixes:
        mutations.add(word + s)
        mutations.add(word.lower() + s)
        mutations.add(word.capitalize() + s)
        
    # Leetspeak replacements
    leet_map = {'a': '@', 'e': '3', 'i': '1', 'o': '0', 's': '$', 't': '7'}
    leet_word = "".join(leet_map.get(c.lower(), c) for c in word)
    mutations.add(leet_word)
    mutations.add(leet_word.capitalize())
    for s in suffixes:
        mutations.add(leet_word + s)

    return list(mutations)

def hash_word(word, hash_type):
    """Hashes a string using the specified algorithm."""
    encoded = word.encode('utf-8', errors='ignore')
    if hash_type == 'md5':
        return hashlib.md5(encoded).hexdigest()
    elif hash_type == 'sha1':
        return hashlib.sha1(encoded).hexdigest()
    elif hash_type == 'sha224':
        return hashlib.sha224(encoded).hexdigest()
    elif hash_type == 'sha256':
        return hashlib.sha256(encoded).hexdigest()
    elif hash_type == 'sha384':
        return hashlib.sha384(encoded).hexdigest()
    elif hash_type == 'sha512':
        return hashlib.sha512(encoded).hexdigest()
    return None

def crack_hash(target_hash, wordlist_source, hash_type=None, apply_rules=False):
    """Attempts to crack a single hash."""
    target_hash = target_hash.strip().lower()
    
    if not hash_type:
        hash_type = detect_hash_type(target_hash)
        if not hash_type:
            print(f"⚠️ Could not auto-detect hash type for '{target_hash}' (length {len(target_hash)}). Skipping.")
            return None
            
    print(f"🔎 Attempting to crack: {target_hash}")
    print(f"🧮 Algorithm: {hash_type.upper()}")
    print(f"⚙️ Mutation rules: {'Enabled' if apply_rules else 'Disabled'}")

    start_time = time.time()
    counter = 0
    
    for word in wordlist_source:
        candidates = generate_mutations(word) if apply_rules else [word]
        
        for candidate in candidates:
            counter += 1
            hashed = hash_word(candidate, hash_type)
            if hashed == target_hash:
                elapsed = time.time() - start_time
                print(f"🎉 SUCCESS! Hash cracked in {elapsed:.2f} seconds.")
                print(f"🔑 Plaintext: {candidate}")
                print(f"📊 Attempts : {counter}")
                return candidate
                
            # Periodically print progress speed (every 100k hashes)
            if counter % 500000 == 0:
                elapsed = time.time() - start_time
                rate = counter / elapsed if elapsed > 0 else 0
                print(f"   ... tried {counter} combinations ({rate:.0f} hashes/sec)")

    elapsed = time.time() - start_time
    rate = counter / elapsed if elapsed > 0 else 0
    print(f"❌ Failed to crack hash. Checked {counter} candidates in {elapsed:.2f}s ({rate:.0f} hashes/sec).")
    return None

def main():
    parser = argparse.ArgumentParser(description="Dictionary-based Hash Cracker - Crack MD5, SHA-1, SHA-256 etc. using wordlists.")
    parser.add_argument('-s', '--hash', help='The target hash string to crack')
    parser.add_argument('-f', '--hash-file', help='Path to a file containing hashes (one per line) to crack')
    parser.add_argument('-w', '--wordlist', help='Path to the password dictionary wordlist file')
    parser.add_argument('-t', '--type', choices=['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512'], 
                        help='Force hash type/algorithm (defaults to auto-detection based on hash length)')
    parser.add_argument('-r', '--rules', action='store_true', help='Enable word mutation rules (leetspeak, capitalization, numbers)')

    args = parser.parse_args()

    if not args.hash and not args.hash-file if hasattr(args, 'hash_file') else not (args.hash or args.hash_file):
        parser.print_help()
        print("\n❌ Error: Please specify a hash (-s) or a hash file (-f).", file=sys.stderr)
        return 1

    # Load wordlist source
    wordlist = []
    if args.wordlist:
        if not os.path.exists(args.wordlist):
            print(f"❌ Error: Wordlist file '{args.wordlist}' not found.", file=sys.stderr)
            return 1
        print(f"📖 Loading wordlist from '{args.wordlist}'...")
        try:
            with open(args.wordlist, 'r', encoding='utf-8', errors='ignore') as f:
                wordlist = [line.rstrip('\n') for line in f]
            print(f"   Loaded {len(wordlist):,} base words.")
        except Exception as e:
            print(f"❌ Error reading wordlist file: {e}", file=sys.stderr)
            return 1
    else:
        print("💡 No wordlist specified. Using quick built-in dictionary (30+ common passwords).")
        wordlist = DEFAULT_PASSWORDS

    # Load targets
    targets = []
    if args.hash:
        targets.append(args.hash)
    
    hash_file_path = args.hash_file if hasattr(args, 'hash_file') else None
    if not hash_file_path and hasattr(args, 'hash-file'):
        hash_file_path = getattr(args, 'hash-file')
        
    if hash_file_path:
        if not os.path.exists(hash_file_path):
            print(f"❌ Error: Hash file '{hash_file_path}' not found.", file=sys.stderr)
            return 1
        try:
            with open(hash_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    h = line.strip()
                    if h and not h.startswith('#'):
                        targets.append(h)
            print(f"🎯 Loaded {len(targets)} hashes from file.")
        except Exception as e:
            print(f"❌ Error reading hash file: {e}", file=sys.stderr)
            return 1

    # Crack targets
    results = {}
    print("-" * 50)
    for target in targets:
        plain = crack_hash(target, wordlist, hash_type=args.type, apply_rules=args.rules)
        if plain:
            results[target] = plain
        print("-" * 50)

    # Print summary
    if len(targets) > 1:
        print("\n🏆 BATCH CRACKING SUMMARY:")
        print(f"  Total Loaded : {len(targets)}")
        print(f"  Cracked      : {len(results)}")
        for h, p in results.items():
            print(f"  {h} => {p}")
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
