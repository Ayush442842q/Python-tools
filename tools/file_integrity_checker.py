#!/usr/bin/env python3
import argparse
import os
import sys
import hashlib

class FileIntegrityChecker:
    def __init__(self):
        pass
    
    def calculate_hash(self, filename, algorithm='sha256'):
        """Calculate hash of a file"""
        hash_obj = hashlib.new(algorithm)
        try:
            with open(filename, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except FileNotFoundError:
            print(f"File {filename} not found")
            return None
        except Exception as e:
            print(f"Error calculating hash: {e}")
            return None
    
    def verify_integrity(self, filename, expected_hash, algorithm='sha256'):
        """Verify file integrity by comparing hashes"""
        calculated_hash = self.calculate_hash(filename, algorithm)
        if calculated_hash and calculated_hash.lower() == expected_hash.lower():
            print(f"File integrity verified for {filename}")
            return True
        else:
            print(f"File integrity check failed for {filename}")
            return False

def main():
    # Simple file integrity checker
    print("File Integrity Checker Tool")
    print("Use this tool to verify file integrity using hash functions")

if __name__ == "__main__":
    main()