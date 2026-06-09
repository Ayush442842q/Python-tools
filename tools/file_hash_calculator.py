"""
File Hash Calculator Tool
Calculates MD5, SHA-1, and SHA-256 hashes of a specified file.
"""
import argparse
import hashlib
import os
import sys

def calculate_hashes(file_path, algorithms):
    # Check if file exists
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return None

    # Initialize hash objects
    hash_objs = {}
    for algo in algorithms:
        try:
            hash_objs[algo] = hashlib.new(algo)
        except ValueError:
            print(f"[ERROR] Unsupported hash algorithm: {algo}")
            return None

    # Read file in chunks to handle large files efficiently
    chunk_size = 65536  # 64 KB
    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                for obj in hash_objs.values():
                    obj.update(data)
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        return None

    # Return hex digests
    return {algo: obj.hexdigest() for algo, obj in hash_objs.items()}

def main():
    parser = argparse.ArgumentParser(
        description="Calculate MD5, SHA-1, and SHA-256 hashes of a specified file."
    )
    parser.add_argument("file", help="Path to the file to hash")
    parser.add_argument(
        "-a", "--algorithm",
        choices=["md5", "sha1", "sha256", "all"],
        default="all",
        help="Hash algorithm to use (default: all)"
    )
    
    args = parser.parse_args()
    
    algos = ["md5", "sha1", "sha256"] if args.algorithm == "all" else [args.algorithm]
    
    print(f"Calculating hashes for: {args.file}")
    results = calculate_hashes(args.file, algos)
    
    if results is None:
        sys.exit(1)
        
    print("[OK] Hash calculation completed successfully:")
    for algo, digest in results.items():
        print(f"  {algo.upper()}: {digest}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
