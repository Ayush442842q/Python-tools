#!/usr/bin/env python3
"""
GPG Keyring Auditor

A standalone utility to audit GnuPG (GPG) cryptographic keys and configuration files.
Performs:
1. Programmatic keyring analysis by querying `gpg --with-colons` (stable format).
2. Key strength audits: warns about weak RSA sizes (<2048), deprecated DSA keys,
   expired keys, or keys lacking expiration dates.
3. Security config audit: inspects local `gpg.conf` files for cryptographic
   best practices (algorithm preferences, hash algorithms, keyserver config).

Usage:
    python gpg_keyring_auditor.py
"""

import sys
import os
import argparse
import subprocess
import time
from datetime import datetime

# Algorithm lookup mapping according to OpenPGP standards (RFC 4880)
ALGO_NAMES = {
    1: "RSA (Encrypt/Sign)",
    2: "RSA Encrypt-Only",
    3: "RSA Sign-Only",
    16: "Elgamal Encrypt-Only",
    17: "DSA (Sign)",
    18: "ECDH (Encrypt)",
    19: "ECDSA (Sign)",
    22: "EdDSA (Sign)"
}

def run_gpg_command(args):
    """Executes a gpg command and returns stdout, returning None if gpg is missing."""
    try:
        res = subprocess.run(
            ['gpg'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

def parse_colons_output(output_str):
    """Parses colon-separated gpg --list-keys output."""
    keys = []
    current_key = None
    
    for line in output_str.splitlines():
        line = line.strip()
        if not line:
            continue
            
        parts = line.split(':')
        record_type = parts[0]
        
        # pub: public key, sec: secret key
        if record_type in ('pub', 'sec'):
            current_key = {
                'type': record_type,
                'validity': parts[1],
                'length': int(parts[2]) if parts[2].isdigit() else 0,
                'algo': int(parts[3]) if parts[3].isdigit() else 0,
                'id': parts[4],
                'created': int(parts[5]) if parts[5].isdigit() else 0,
                'expires': int(parts[6]) if parts[6].isdigit() else 0,
                'uids': [],
                'subkeys': [],
                'fingerprint': ''
            }
            keys.append(current_key)
        elif record_type in ('sub', 'ssb') and current_key:
            subkey = {
                'type': record_type,
                'length': int(parts[2]) if parts[2].isdigit() else 0,
                'algo': int(parts[3]) if parts[3].isdigit() else 0,
                'id': parts[4],
                'created': int(parts[5]) if parts[5].isdigit() else 0,
                'expires': int(parts[6]) if parts[6].isdigit() else 0,
            }
            current_key['subkeys'].append(subkey)
        elif record_type == 'uid' and current_key:
            uid_str = parts[9]
            current_key['uids'].append(uid_str)
        elif record_type == 'fpr' and current_key:
            # fingerprint record is outputted after the key record
            current_key['fingerprint'] = parts[9]
            
    return keys

def audit_gpg_conf():
    """Inspects GPG config file for security settings."""
    warnings = []
    recommendations = []
    
    # Locate gpg.conf
    home = os.path.expanduser('~')
    gpg_conf_paths = [
        os.path.join(home, '.gnupg', 'gpg.conf'),
        os.path.join(home, 'AppData', 'Roaming', 'gnupg', 'gpg.conf') # Windows
    ]
    
    conf_path = None
    for path in gpg_conf_paths:
        if os.path.exists(path):
            conf_path = path
            break
            
    if not conf_path:
        return None, ["Could not locate ~/.gnupg/gpg.conf. Using default system GPG config."], []

    with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Check for recommended settings
    if "personal-digest-preferences SHA512" not in content:
        recommendations.append("Add 'personal-digest-preferences SHA512 SHA384 SHA256' for stronger hashing.")
    if "cert-digest-algo SHA512" not in content:
        recommendations.append("Add 'cert-digest-algo SHA512' to sign keys using SHA512.")
    if "no-emit-version" not in content:
        recommendations.append("Add 'no-emit-version' to hide GPG version headers in signatures/messages.")
    if "require-cross-certification" not in content:
        recommendations.append("Add 'require-cross-certification' to protect against signature spoofing on subkeys.")
        
    return conf_path, warnings, recommendations

def main():
    parser = argparse.ArgumentParser(
        description="Audit GPG keyrings and configuration profiles for cryptographic compliance.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    args = parser.parse_args()

    print("GPG Keyring Auditor")
    print("=" * 70)

    # 1. Audit GPG Config File
    conf_path, conf_warn, conf_recs = audit_gpg_conf()
    if conf_path:
        print(f"GPG Config Path  : {conf_path}")
    for w in conf_warn:
        print(f"  [!] {w}")
    print("-" * 70)

    # 2. Query GPG Keys
    raw_keys_out = run_gpg_command(['--list-keys', '--with-colons'])
    
    if raw_keys_out is None:
        print("\033[93mGnuPG CLI ('gpg') command not found or not installed in PATH.\033[0m")
        print("Skipping keyring analysis. Setup GnuPG to manage PGP keys.")
        print("-" * 70)
        # Output config recommendations only
        if conf_recs:
            print("\nGPG Configuration Best Practice Recommendations:")
            for rec in conf_recs:
                print(f"  - {rec}")
        return 0

    keys = parse_colons_output(raw_keys_out)
    
    if not keys:
        print("No public GPG keys found in local keyring database.")
        print("-" * 70)
        return 0

    print(f"Auditing {len(keys)} primary key entries...")
    print("-" * 70)

    now_epoch = int(time.time())
    total_issues = 0

    for key in keys:
        issues = []
        
        # Audit algorithms & key length
        algo_name = ALGO_NAMES.get(key['algo'], f"Unknown ({key['algo']})")
        if key['algo'] in (1, 2, 3):  # RSA
            if key['length'] < 2048:
                issues.append(f"CRITICAL: Weak RSA key length: {key['length']} bits (unsafe, should be >= 2048).")
            elif key['length'] < 3072:
                issues.append(f"Warning: Moderate RSA key length: {key['length']} bits (3072+ recommended).")
        elif key['algo'] == 17:  # DSA
            issues.append("CRITICAL: Deprecated DSA algorithm (unsafe).")

        # Expiration check
        if key['expires'] > 0:
            exp_date = datetime.fromtimestamp(key['expires']).strftime('%Y-%m-%d')
            if key['expires'] < now_epoch:
                issues.append(f"CRITICAL: Key EXPIRED on {exp_date}.")
            elif key['expires'] - now_epoch < (30 * 86400):  # 30 days
                issues.append(f"Warning: Key is expiring soon on {exp_date}.")
        else:
            issues.append("Warning: Primary key has NO expiration date configured.")

        # Subkeys audit
        for sub in key['subkeys']:
            if sub['algo'] in (1, 2, 3) and sub['length'] < 2048:
                issues.append(f"CRITICAL: Weak subkey ({sub['id'][:8]}) length: {sub['length']} bits.")
            if sub['expires'] > 0 and sub['expires'] < now_epoch:
                issues.append(f"Warning: Subkey ({sub['id'][:8]}) is EXPIRED.")

        # Print Key details
        uid_label = key['uids'][0] if key['uids'] else "No UID"
        print(f"\nKey ID: \033[1m{key['id'][-16:]}\033[0m ({uid_label})")
        print(f"  Fingerprint   : {key['fingerprint']}")
        print(f"  Key Size/Type : {key['length']} bits | {algo_name}")
        
        created_str = datetime.fromtimestamp(key['created']).strftime('%Y-%m-%d')
        expires_str = datetime.fromtimestamp(key['expires']).strftime('%Y-%m-%d') if key['expires'] > 0 else "Never"
        print(f"  Validity      : Created: {created_str} | Expires: {expires_str}")
        print(f"  Subkeys Count : {len(key['subkeys'])}")

        if issues:
            total_issues += len(issues)
            print("  \033[91mAudit Findings:\033[0m")
            for iss in issues:
                print(f"    - [!] {iss}")
        else:
            try:
                print("  \033[92m[✓] Key configuration is healthy.\033[0m")
            except UnicodeEncodeError:
                print("  \033[92m[ok] Key configuration is healthy.\033[0m")

    print("\n" + "=" * 70)
    print("AUDIT RESULT SUMMARY")
    print(f"  Total Keys Audited : {len(keys)}")
    print(f"  Total Key Issues   : {total_issues}")
    print("=" * 70)

    if conf_recs:
        print("\nGPG Configuration Best Practice Recommendations:")
        for rec in conf_recs:
            print(f"  - {rec}")
            
    return 1 if total_issues > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
