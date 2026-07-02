#!/usr/bin/env python3
"""
ZIP Password Recovery Tool

Performs high-speed dictionary and parallel brute-force attacks on password-protected
ZIP archives. Uses Python's standard zipfile library and concurrent.futures for multi-threaded
cracking. Optimizes checking speed by verifying only the first byte of decryption.

Usage:
    python tools/zip_password_recovery.py path/to/archive.zip -w wordlist.txt
    python tools/zip_password_recovery.py path/to/archive.zip -b -c d --min 4 --max 6
"""

import argparse
import itertools
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator, Iterator, List, Optional, Tuple

CHARSETS = {
    "l": "abcdefghijklmnopqrstuvwxyz",
    "u": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "d": "0123456789",
    "p": "!@#$%^&*()-_=+[]{}|;:',.<>/?`~",
}

class ZipCracker:
    """Class to manage dictionary and brute-force cracking of ZIP files."""
    def __init__(self, zip_path: str, num_threads: int = 4) -> None:
        self.zip_path = zip_path
        self.num_threads = num_threads
        self.target_file: Optional[str] = None
        self.is_encrypted = False
        self._inspect_zip()

    def _inspect_zip(self) -> None:
        """Inspects the ZIP file to ensure it exists, is valid, and is encrypted."""
        if not os.path.exists(self.zip_path):
            raise FileNotFoundError(f"ZIP file '{self.zip_path}' not found.")
        
        if not zipfile.is_zipfile(self.zip_path):
            raise ValueError(f"File '{self.zip_path}' is not a valid ZIP archive.")
            
        with zipfile.ZipFile(self.zip_path) as z:
            namelist = z.namelist()
            if not namelist:
                raise ValueError("ZIP archive is empty.")
            
            # Find the first file in the ZIP to use as password validation target
            self.target_file = namelist[0]
            
            # Check if it requires a password
            for info in z.infolist():
                if info.flag_bits & 0x1:  # Bit 0 of flag_bits indicates encryption
                    self.is_encrypted = True
                    break

    def check_password(self, password: str) -> bool:
        """Test if a password is correct by trying to read 1 byte from the target file."""
        if not self.target_file:
            return False
        
        try:
            with zipfile.ZipFile(self.zip_path) as z:
                # Open the file with password. If password is wrong, f.read() will raise RuntimeError
                with z.open(self.target_file, pwd=password.encode('utf-8', errors='ignore')) as f:
                    f.read(1)
            return True
        except (RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
            # Typically raises RuntimeError("Bad password for file...")
            return False
        except Exception:
            return False

    def crack_with_wordlist(self, wordlist_path: str) -> Optional[str]:
        """Crack ZIP using a dictionary wordlist file."""
        if not os.path.exists(wordlist_path):
            print(f"Error: Wordlist file '{wordlist_path}' not found.", file=sys.stderr)
            return None
        
        print(f"Loading wordlist: {wordlist_path}...")
        try:
            with open(wordlist_path, "r", encoding="utf-8", errors="ignore") as f:
                passwords = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading wordlist: {e}", file=sys.stderr)
            return None

        total = len(passwords)
        print(f"Loaded {total} passwords. Starting multi-threaded check with {self.num_threads} threads...")
        
        start_time = time.time()
        checked_count = 0
        found_password = None

        # Execute using a ThreadPool
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # We process in chunks to print progress and allow clean interruption
            chunk_size = min(5000, max(500, total // 20))
            for i in range(0, total, chunk_size):
                chunk = passwords[i:i + chunk_size]
                futures = {executor.submit(self.check_password, pwd): pwd for pwd in chunk}
                
                for future in as_completed(futures):
                    pwd = futures[future]
                    checked_count += 1
                    if future.result():
                        found_password = pwd
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break
                
                if found_password:
                    break
                
                # Print progress
                elapsed = time.time() - start_time
                rate = checked_count / elapsed if elapsed > 0 else 0
                percent = (checked_count / total) * 100
                print(f"\rProgress: {checked_count}/{total} checked ({percent:.1f}%) | Rate: {rate:.1f} pwd/sec", end="", flush=True)

        print()  # Clear line
        return found_password

    def crack_brute_force(self, charset_str: str, min_len: int, max_len: int, prefix: str = "", suffix: str = "") -> Optional[str]:
        """Crack ZIP using parallel brute-force generation."""
        print(f"Brute-forcing with charset: {charset_str}")
        print(f"Length range: {min_len} to {max_len} characters")
        if prefix:
            print(f"Using Prefix: '{prefix}'")
        if suffix:
            print(f"Using Suffix: '{suffix}'")

        start_time = time.time()
        checked_count = 0
        found_password = None

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            for length in range(min_len, max_len + 1):
                print(f"Testing length {length}...")
                
                # Generator for candidates of current length
                candidates = itertools.product(charset_str, repeat=length)
                
                # Check in batches to avoid allocating millions of futures in memory
                batch_size = 10000
                batch = []
                
                for candidate in candidates:
                    candidate_pwd = prefix + "".join(candidate) + suffix
                    batch.append(candidate_pwd)
                    
                    if len(batch) >= batch_size:
                        futures = {executor.submit(self.check_password, pwd): pwd for pwd in batch}
                        for future in as_completed(futures):
                            pwd = futures[future]
                            checked_count += 1
                            if future.result():
                                found_password = pwd
                                for f in futures:
                                    f.cancel()
                                break
                        
                        if found_password:
                            break
                        
                        batch.clear()
                        
                        # Print progress
                        elapsed = time.time() - start_time
                        rate = checked_count / elapsed if elapsed > 0 else 0
                        print(f"\rChecked {checked_count} candidates... | Rate: {rate:.1f} pwd/sec", end="", flush=True)
                
                # Check remaining items in final batch of the current length
                if batch and not found_password:
                    futures = {executor.submit(self.check_password, pwd): pwd for pwd in batch}
                    for future in as_completed(futures):
                        pwd = futures[future]
                        checked_count += 1
                        if future.result():
                            found_password = pwd
                            break
                
                if found_password:
                    break

        print()  # Clear line
        return found_password

def main() -> None:
    parser = argparse.ArgumentParser(
        description="High-Speed ZIP Archive Password Recovery Tool"
    )
    parser.add_argument(
        "zipfile", help="Path to the password-protected ZIP file"
    )
    parser.add_argument(
        "-w", "--wordlist", help="Path to dictionary wordlist file"
    )
    parser.add_argument(
        "-b", "--brute", action="store_true", help="Perform a brute-force search"
    )
    parser.add_argument(
        "-c", "--charset", default="ld",
        help="Brute-force characters: 'l'=lowercase, 'u'=uppercase, 'd'=digits, 'p'=punctuation. (default: 'ld')"
    )
    parser.add_argument(
        "--min", type=int, default=1, help="Minimum password length for brute-force (default: 1)"
    )
    parser.add_argument(
        "--max", type=int, default=6, help="Maximum password length for brute-force (default: 6)"
    )
    parser.add_argument(
        "--prefix", default="", help="Static prefix to add to all tested passwords"
    )
    parser.add_argument(
        "--suffix", default="", help="Static suffix to add to all tested passwords"
    )
    parser.add_argument(
        "-t", "--threads", type=int, default=4, help="Number of concurrent threads (default: 4)"
    )

    args = parser.parse_args()

    # Validate cracking parameters
    if not args.wordlist and not args.brute:
        print("Error: You must specify either a wordlist (-w) or brute-force (-b).", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    print("=" * 65)
    print(" ZIP ARCHIVE PASSWORD RECOVERY TOOL")
    print("=" * 65)
    print(f"Target ZIP: {args.zipfile}")

    try:
        cracker = ZipCracker(args.zipfile, num_threads=args.threads)
    except Exception as e:
        print(f"Error initializing archive scanner: {e}", file=sys.stderr)
        sys.exit(1)

    if not cracker.is_encrypted:
        print("Warning: The selected ZIP archive does not appear to be encrypted/password-protected.")
        print("It can be extracted directly without a password.")
        sys.exit(0)

    # Compile charset
    brute_charset = ""
    for char in args.charset:
        if char in CHARSETS:
            brute_charset += CHARSETS[char]
        else:
            print(f"Warning: Unknown charset identifier '{char}' skipped.", file=sys.stderr)
    
    if args.brute and not brute_charset:
        print("Error: Selected charset is empty.", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()
    found_pwd = None

    try:
        if args.wordlist:
            found_pwd = cracker.crack_with_wordlist(args.wordlist)
        elif args.brute:
            found_pwd = cracker.crack_brute_force(
                brute_charset,
                min_len=args.min,
                max_len=args.max,
                prefix=args.prefix,
                suffix=args.suffix
            )
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user (Ctrl+C). Exiting...")
        sys.exit(1)

    duration = time.time() - start_time
    print("-" * 65)
    
    if found_pwd:
        print(f" SUCCESS: Password found in {duration:.2f} seconds!")
        print(f" Password: [ {found_pwd} ]")
    else:
        print(f" FAILURE: Password not found. Duration: {duration:.2f} seconds.")
        print(" Try increasing brute-force length bounds, modifying charset, or using a larger wordlist.")
    print("=" * 65)

if __name__ == "__main__":
    main()
