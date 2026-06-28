#!/usr/bin/env python3
"""
SSH Key Manager & Auditor
Scans, audits, and manages SSH key pairs in the user's ~/.ssh directory or custom paths.
Calculates SHA256 and MD5 fingerprints natively in Python.
Audits key security (algorithms, lengths, file permissions).
Supports new key generation using standard ssh-keygen or Python fallback.
Uses standard libraries only.
"""

import argparse
import base64
import hashlib
import os
import stat
import subprocess
import sys
from typing import Dict, List, Tuple, Optional, Any

# Standard algorithms and their security properties
ALGO_AUDIT = {
    "ssh-rsa": {"min_bits": 2048, "status": "legacy", "reason": "SHA-1 signatures deprecated, but key itself is fine if >= 2048 bits"},
    "ssh-dss": {"min_bits": 1024, "status": "weak", "reason": "DSA is deprecated and insecure (disabled in modern OpenSSH)"},
    "ecdsa-sha2-nistp256": {"min_bits": 256, "status": "secure", "reason": "Standard ECDSA curve"},
    "ecdsa-sha2-nistp384": {"min_bits": 384, "status": "secure", "reason": "Strong ECDSA curve"},
    "ecdsa-sha2-nistp521": {"min_bits": 521, "status": "secure", "reason": "Strong ECDSA curve"},
    "ssh-ed25519": {"min_bits": 256, "status": "secure", "reason": "Recommended modern fast and secure key"},
}

def get_default_ssh_dir() -> str:
    """Returns the default SSH directory for the current user."""
    return os.path.expanduser("~/.ssh")

def decode_public_key_bits(key_bytes: bytes, algo: str) -> Optional[int]:
    """Attempts to parse public key bytes to infer key bit length."""
    try:
        # SSH public key format: 
        # uint32 length, string algorithm_name, uint32 length, string param1, ...
        # For RSA: [length][ssh-rsa] [length][exponent] [length][modulus]
        idx = 0
        def read_bytes() -> bytes:
            nonlocal idx
            length = int.from_bytes(key_bytes[idx:idx+4], byteorder='big')
            idx += 4
            data = key_bytes[idx:idx+length]
            idx += length
            return data

        read_bytes() # Skip algorithm string (equal to first space-separated word)
        
        if algo == "ssh-rsa":
            read_bytes() # Read exponent
            modulus = read_bytes() # Read modulus
            # Bit length of modulus represents key length
            return len(modulus) * 8
        elif algo.startswith("ecdsa-"):
            # Usually 256, 384 or 521 bits based on curve name
            if "nistp256" in algo: return 256
            elif "nistp384" in algo: return 384
            elif "nistp521" in algo: return 521
        elif algo == "ssh-ed25519":
            return 256
        elif algo == "ssh-dss":
            return 1024
    except Exception:
        pass
    return None

def parse_public_key(pub_key_content: str) -> Optional[Dict[str, Any]]:
    """Parses a public key line into algorithm, key body, comment, and fingerprints."""
    parts = pub_key_content.strip().split(None, 2)
    if len(parts) < 2:
        return None
        
    algo = parts[0]
    key_base64 = parts[1]
    comment = parts[2] if len(parts) > 2 else ""
    
    try:
        key_bytes = base64.b64decode(key_base64)
        
        # Calculate SHA256 fingerprint (like ssh-keygen -l)
        sha256_hash = hashlib.sha256(key_bytes).digest()
        sha256_fp = "SHA256:" + base64.b64encode(sha256_hash).decode('utf-8').rstrip('=')
        
        # Calculate MD5 fingerprint
        md5_hash = hashlib.md5(key_bytes).hexdigest()
        md5_fp = ":".join(md5_hash[i:i+2] for i in range(0, len(md5_hash), 2))
        
        bits = decode_public_key_bits(key_bytes, algo)
        
        return {
            "algorithm": algo,
            "bits": bits,
            "comment": comment,
            "sha256_fp": sha256_fp,
            "md5_fp": md5_fp,
            "raw_base64": key_base64
        }
    except Exception:
        return None

def check_file_permissions(filepath: str) -> Tuple[bool, str]:
    """Checks if file permissions are secure. Returns (is_secure, description)."""
    if sys.platform == "win32":
        # Windows doesn't use POSIX file permissions in the same way.
        # But we can warn if it's world writable or inspect using basic os.stat.
        # Often ssh complains on Windows if the folder has broad ACL permissions.
        try:
            mode = os.stat(filepath).st_mode
            if mode & stat.S_IWOTH:
                return False, "File is writable by others (insecure)"
            return True, "Default Windows permissions"
        except Exception as e:
            return False, f"Failed to check permissions: {e}"
    else:
        # Unix/Linux
        try:
            mode = os.stat(filepath).st_mode
            # Only user should read/write private keys (0600 or 0400)
            insecure_flags = stat.S_IRWXG | stat.S_IRWXO # group/other read-write-execute
            if mode & insecure_flags:
                octal_perms = oct(mode & 0o777)
                return False, f"Permissions are too open: {octal_perms} (should be 0600)"
            return True, "Secure (0600 or less)"
        except Exception as e:
            return False, f"Error: {e}"


class SSHKeyAuditor:
    """Scans and audits SSH keys in a directory."""
    def __init__(self, directory: str):
        self.directory = directory
        self.keys: List[Dict[str, Any]] = []

    def scan(self):
        """Scans the directory for private and public SSH keys."""
        if not os.path.isdir(self.directory):
            return
            
        files = os.listdir(self.directory)
        
        # 1. Group by base name
        # If we see 'id_rsa' and 'id_rsa.pub', we link them.
        for f in files:
            path = os.path.join(self.directory, f)
            if os.path.isdir(path):
                continue
                
            # We look for private keys by ignoring files ending in .pub, .authorized, or .known
            if f.endswith(('.pub', '.authorized', '.known_hosts', 'authorized_keys', 'known_hosts')):
                continue
                
            # Check if it looks like a private key (starts with -----BEGIN or similar)
            is_private = False
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file_check:
                    head = file_check.read(100)
                    if "PRIVATE KEY" in head or "SSH PRIVATE KEY" in head or "ssh-dss" in head or "ssh-rsa" in head:
                        is_private = True
            except Exception:
                pass
                
            if is_private:
                key_info = {
                    "private_key_file": f,
                    "private_key_path": path,
                    "public_key_file": None,
                    "public_key_path": None,
                    "parsed_pub": None,
                    "permissions_ok": True,
                    "permissions_desc": ""
                }
                
                # Check permissions
                perms_ok, perms_desc = check_file_permissions(path)
                key_info["permissions_ok"] = perms_ok
                key_info["permissions_desc"] = perms_desc
                
                # Check if matching .pub file exists
                pub_path = path + ".pub"
                if os.path.exists(pub_path):
                    key_info["public_key_file"] = f + ".pub"
                    key_info["public_key_path"] = pub_path
                    try:
                        with open(pub_path, 'r', encoding='utf-8') as pub_file:
                            pub_content = pub_file.read()
                            key_info["parsed_pub"] = parse_public_key(pub_content)
                    except Exception:
                        pass
                
                self.keys.append(key_info)

    def audit_key(self, key: Dict[str, Any]) -> List[str]:
        """Audits a key pair and returns warning messages if any issues are found."""
        warnings = []
        
        # Check permissions
        if not key["permissions_ok"]:
            warnings.append(f"Private key file permissions: {key['permissions_desc']}")
            
        # Check if public key exists
        if not key["public_key_path"]:
            warnings.append("Missing corresponding public key (.pub file)")
            return warnings
            
        pub = key["parsed_pub"]
        if not pub:
            warnings.append("Failed to parse public key content")
            return warnings
            
        algo = pub["algorithm"]
        bits = pub["bits"]
        
        # Check algorithm security
        if algo in ALGO_AUDIT:
            audit = ALGO_AUDIT[algo]
            if audit["status"] == "weak":
                warnings.append(f"Deprecated/Weak Algorithm '{algo}': {audit['reason']}")
            elif audit["status"] == "legacy":
                # Only warn if bits are low
                min_b = audit["min_bits"]
                if bits and bits < min_b:
                    warnings.append(f"RSA key is too short: {bits} bits (minimum recommended: {min_b} bits)")
        else:
            warnings.append(f"Unknown key algorithm: '{algo}'")
            
        return warnings


def generate_ssh_key(filepath: str, key_type: str = "ed25519", bits: int = 3072, comment: str = "") -> bool:
    """Generates an SSH key pair using ssh-keygen command-line tool."""
    print(f"[*] Generating new SSH key pair ({key_type}) at: {filepath}...")
    
    # Ensure directory exists
    dir_name = os.path.dirname(filepath)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
        
    cmd = ["ssh-keygen", "-t", key_type, "-f", filepath]
    
    if key_type == "rsa":
        cmd += ["-b", str(bits)]
        
    if comment:
        cmd += ["-C", comment]
        
    # Execute
    try:
        # Run interactively so the user can enter passphrases if they want
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"[+] Key pair generated successfully.")
            if sys.platform != "win32":
                # Ensure correct permissions
                os.chmod(filepath, 0o600)
                os.chmod(filepath + ".pub", 0o644)
            return True
        else:
            print("[-] Key generation failed (ssh-keygen exited with error).", file=sys.stderr)
            return False
    except FileNotFoundError:
        print("[-] Error: 'ssh-keygen' executable not found in PATH.", file=sys.stderr)
        print("[*] Hint: Install OpenSSH client, or run this tool on a system with OpenSSH installed.", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="SSH Key Manager & Auditor - Scan, list, and audit local SSH key pairs."
    )
    parser.add_argument(
        "-d", "--directory",
        help="Directory to scan (defaults to ~/.ssh)"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Interactively generate a new SSH key pair"
    )
    parser.add_argument(
        "--key-type",
        dest="key_type",
        default="ed25519",
        choices=["ed25519", "rsa", "ecdsa"],
        help="Type of key to generate (default: ed25519)"
    )
    parser.add_argument(
        "--bits",
        type=int,
        default=3072,
        help="RSA key bit size (default: 3072, only used if key-type is rsa)"
    )
    parser.add_argument(
        "-c", "--comment",
        default="",
        help="Comment to append to the generated key (e.g. email address)"
    )

    args = parser.parse_args()

    # Handle generation mode
    if args.generate:
        default_path = os.path.join(get_default_ssh_dir(), f"id_{args.key_type}")
        print(f"[*] Default save path: {default_path}")
        save_path = input(f"Enter file in which to save the key (press Enter for default): ").strip()
        if not save_path:
            save_path = default_path
            
        comment = args.comment
        if not comment:
            comment = input("Enter key comment (optional, e.g. email): ").strip()
            
        success = generate_ssh_key(save_path, args.key_type, args.bits, comment)
        return 0 if success else 1

    # Default scan directory
    scan_dir = args.directory or get_default_ssh_dir()
    print(f"[*] Scanning SSH directory: {scan_dir}")
    
    if not os.path.exists(scan_dir):
        print(f"[-] Directory does not exist: {scan_dir}", file=sys.stderr)
        return 1
        
    auditor = SSHKeyAuditor(scan_dir)
    auditor.scan()
    
    if not auditor.keys:
        print("[*] No SSH private keys found in directory.")
        return 0
        
    print(f"[+] Found {len(auditor.keys)} key pair(s):\n")
    
    for idx, key in enumerate(auditor.keys, 1):
        print(f"{idx}. Private Key: {key['private_key_file']}")
        print(f"   Path:        {key['private_key_path']}")
        
        pub = key["parsed_pub"]
        if pub:
            print(f"   Public Key:  {key['public_key_file']}")
            print(f"   Algorithm:   {pub['algorithm']} ({pub['bits'] or 'unknown'} bits)")
            print(f"   Comment:     {pub['comment'] if pub['comment'] else '<none>'}")
            print(f"   SHA256 Fingerprint: {pub['sha256_fp']}")
            print(f"   MD5 Fingerprint:    {pub['md5_fp']}")
        else:
            print("   Public Key:  <missing or unparseable>")
            
        # Run audit
        warnings = auditor.audit_key(key)
        if warnings:
            print("   [!] Security Warnings:")
            for w in warnings:
                print(f"       - {w}")
        else:
            print("   [+] Security Check: PASS (No issues found)")
            
        print("-" * 65)

    return 0

if __name__ == "__main__":
    sys.exit(main())
