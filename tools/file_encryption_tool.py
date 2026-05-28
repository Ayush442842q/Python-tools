#!/usr/bin/env python3
import argparse
import os
import sys
from cryptography.fernet import Fernet
import hashlib

class FileEncryptionTool:
    def __init__(self):
        self.key = None
    
    def generate_key(self):
        """Generate a key for encryption"""
        self.key = Fernet.generate_key()
        return self.key
    
    def save_key(self, key_file):
        """Save the encryption key to a file"""
        if self.key:
            with open(key_file, 'wb') as f:
                f.write(self.key)
            return True
        return False
    
    def encrypt_file(self, filename, key_file):
        """Encrypt a file using the provided key file"""
        if not self.key:
            print("No encryption key available")
            return False
            
        # Read the key from file
        with open(key_file, 'rb') as f:
            self.key = f.read()
        
        # Read the file to encrypt
        with open(filename, 'rb') as f:
            file_data = f.read()
        
        # Encrypt the data
        f = Fernet(self.key)
        encrypted_data = f.encrypt(file_data)
        
        # Write encrypted data to a new file
        encrypted_filename = filename + '.encrypted'
        with open(encrypted_filename, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"File {filename} encrypted successfully as {encrypted_filename}")
        return True

def main():
    # Create the file encryption tool
    tool = FileEncryptionTool()
    
    # Generate and save key
    key = tool.generate_key()
    with open('encryption_key.key', 'wb') as f:
        f.write(key)
    print("Encryption key generated and saved as 'encryption_key.key'")
    
    # Example usage
    tool.save_key('encryption_key.key')
    print("File encryption tool executed successfully")

if __name__ == "__main__":
    main()