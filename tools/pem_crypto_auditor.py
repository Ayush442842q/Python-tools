#!/usr/bin/env python3
"""
PEM Certificate & Crypto Auditor

A standalone, zero-dependency auditor for PEM-encoded certificates and keys.
Natively parses ASN.1/DER structures to extract subjects, issuers, validity periods,
public key parameters, and checks for weak/expired keys (e.g., RSA < 2048, SHA-1).

Usage:
    python pem_crypto_auditor.py [path_to_pem_file]
"""

import sys
import os
import argparse
import base64
import re
from datetime import datetime

# Common OIDs mapped to text names
OIDS = {
    "2.5.4.3": "Common Name (CN)",
    "2.5.4.6": "Country (C)",
    "2.5.4.7": "Locality (L)",
    "2.5.4.8": "State/Province (ST)",
    "2.5.4.10": "Organization (O)",
    "2.5.4.11": "Organizational Unit (OU)",
    "1.2.840.113549.1.1.1": "RSA Encryption",
    "1.2.840.113549.1.1.5": "SHA-1 with RSA",
    "1.2.840.113549.1.1.11": "SHA-256 with RSA",
    "1.2.840.10045.2.1": "EC Public Key",
    "1.2.840.10045.3.1.7": "ECDSA P-256"
}

def parse_asn1_length(data, offset):
    """Parses DER length octets, returning (length, next_offset)."""
    if offset >= len(data):
        return 0, offset
    byte = data[offset]
    if byte & 0x80 == 0:
        return byte, offset + 1
    num_octets = byte & 0x7F
    if offset + 1 + num_octets > len(data):
        return 0, len(data)
    val = 0
    for i in range(num_octets):
        val = (val << 8) | data[offset + 1 + i]
    return val, offset + 1 + num_octets

def parse_asn1_oid(data):
    """Decodes a DER OID into its dot-separated string representation."""
    if not data:
        return ""
    # First byte encodes first two components: val = first * 40 + second
    first = data[0] // 40
    second = data[0] % 40
    parts = [str(first), str(second)]
    
    val = 0
    for byte in data[1:]:
        val = (val << 7) | (byte & 0x7F)
        if byte & 0x80 == 0:
            parts.append(str(val))
            val = 0
    return ".".join(parts)

def parse_asn1_tlv(data, offset=0):
    """Decodes a single DER TLV field, returning (tag, value, next_offset)."""
    if offset >= len(data):
        return None, None, offset
    tag = data[offset]
    length, val_offset = parse_asn1_length(data, offset + 1)
    value = data[val_offset:val_offset + length]
    return tag, value, val_offset + length

def parse_asn1_sequence(data):
    """Walks list of TLVs in a SEQUENCE body."""
    offset = 0
    children = []
    while offset < len(data):
        tag, value, next_offset = parse_asn1_tlv(data, offset)
        if tag is None:
            break
        children.append((tag, value))
        offset = next_offset
    return children

def parse_name(sequence_data):
    """Parses X.509 RelativeDistinguishedName SET structure."""
    parts = []
    # A Name is a SEQUENCE of SETs, each containing an AttributeTypeAndValue SEQUENCE
    sets = parse_asn1_sequence(sequence_data)
    for tag_set, val_set in sets:
        if tag_set == 0x31:  # SET
            items = parse_asn1_sequence(val_set)
            for tag_item, val_item in items:
                if tag_item == 0x30:  # SEQUENCE
                    sub_items = parse_asn1_sequence(val_item)
                    if len(sub_items) >= 2:
                        # item 0: OID, item 1: String type
                        oid_str = parse_asn1_oid(sub_items[0][1])
                        val_str = sub_items[1][1].decode('utf-8', errors='ignore')
                        oid_label = OIDS.get(oid_str, oid_str)
                        parts.append(f"{oid_label}={val_str}")
    return ", ".join(parts)

def parse_time(time_bytes, tag):
    """Decodes UTCTime (0x17) or GeneralizedTime (0x18) fields."""
    time_str = time_bytes.decode('ascii', errors='ignore')
    # UTCTime format is YYMMDDHHMMSSZ, GeneralizedTime is YYYYMMDDHHMMSSZ
    if tag == 0x17:
        year = int(time_str[:2])
        year_prefix = "20" if year < 50 else "19"
        time_str = year_prefix + time_str
    
    try:
        # Standardize format
        dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return time_str

def audit_cert(der_data):
    """Audits X.509 TBSCertificate structure inside the outer SEQUENCE."""
    tag, tbs_data, next_offset = parse_asn1_tlv(der_data, 0)
    if tag != 0x30:
        return None, "Not a valid X.509 SEQUENCE structure."
        
    children = parse_asn1_sequence(tbs_data)
    if not children:
        return None, "Empty certificate SEQUENCE."
        
    # First child is TBSCertificate
    tbs_tag, tbs_val = children[0]
    if tbs_tag != 0x30:
        return None, "Invalid TBSCertificate structure."
        
    tbs_children = parse_asn1_sequence(tbs_val)
    idx = 0
    
    # Optional Explicit Version [0]
    version = 1
    if tbs_children[idx][0] == 0xA0:
        val_children = parse_asn1_sequence(tbs_children[idx][1])
        if val_children:
            # ASN.1 INTEGER is tag 0x02
            version = int.from_bytes(val_children[0][1], 'big') + 1
        idx += 1
        
    # Serial Number (INTEGER)
    serial = tbs_children[idx][1].hex().upper()
    idx += 1
    
    # Signature Algorithm
    sig_algo_children = parse_asn1_sequence(tbs_children[idx][1])
    sig_oid = parse_asn1_oid(sig_algo_children[0][1]) if sig_algo_children else "N/A"
    sig_name = OIDS.get(sig_oid, sig_oid)
    idx += 1
    
    # Issuer
    issuer = parse_name(tbs_children[idx][1])
    idx += 1
    
    # Validity (SEQUENCE)
    validity_children = parse_asn1_sequence(tbs_children[idx][1])
    not_before = "Unknown"
    not_after = "Unknown"
    if len(validity_children) >= 2:
        not_before = parse_time(validity_children[0][1], validity_children[0][0])
        not_after = parse_time(validity_children[1][1], validity_children[1][0])
    idx += 1
    
    # Subject
    subject = parse_name(tbs_children[idx][1])
    idx += 1
    
    # SubjectPublicKeyInfo
    spki_children = parse_asn1_sequence(tbs_children[idx][1])
    key_size_bits = 0
    key_type = "Unknown"
    
    if len(spki_children) >= 2:
        algo_seq = parse_asn1_sequence(spki_children[0][1])
        if algo_seq:
            key_oid = parse_asn1_oid(algo_seq[0][1])
            key_type = OIDS.get(key_oid, key_oid)
            
        # Parse public key bit string
        pub_key_bytes = spki_children[1][1]
        # Ignore leading padding bits count (first byte)
        if len(pub_key_bytes) > 1 and key_type == "RSA Encryption":
            # The BIT STRING wraps a SEQUENCE containing the modulus and public exponent
            inner_tag, inner_val, _ = parse_asn1_tlv(pub_key_bytes, 1)
            if inner_tag == 0x30:
                rsa_children = parse_asn1_sequence(inner_val)
                if rsa_children:
                    # Modulus INTEGER is the first child
                    modulus = rsa_children[0][1]
                    # RSA size in bits is size of modulus excluding leading sign byte
                    mod_bytes = len(modulus)
                    if modulus[0] == 0:
                        mod_bytes -= 1
                    key_size_bits = mod_bytes * 8
                    
    # Generate audit recommendations
    audit_notes = []
    
    # 1. Expired check
    try:
        end_dt = datetime.strptime(not_after.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() > end_dt:
            audit_notes.append("\033[91m[-] ALERT: Certificate is EXPIRED!\033[0m")
    except Exception:
        pass
        
    # 2. Signature algorithm check
    if "SHA-1" in sig_name:
        audit_notes.append("\033[91m[-] WARNING: Weak signature algorithm (SHA-1) detected.\033[0m")
        
    # 3. Key size check
    if key_type == "RSA Encryption" and key_size_bits < 2048:
        audit_notes.append(f"\033[91m[-] ALERT: Weak RSA key length ({key_size_bits} bits). Minimum 2048 required.\033[0m")
    elif key_type == "RSA Encryption" and key_size_bits >= 2048:
        audit_notes.append("\033[92m[✓] Key length is secure.\033[0m")
            
    return {
        'version': version,
        'serial': serial,
        'issuer': issuer,
        'subject': subject,
        'not_before': not_before,
        'not_after': not_after,
        'signature_algorithm': sig_name,
        'key_type': key_type,
        'key_size': f"{key_size_bits} bits" if key_size_bits else "N/A",
        'audit': audit_notes
    }, None

def main():
    parser = argparse.ArgumentParser(
        description="Audit PEM certificates, public keys, and cryptographic structures natively.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pem_file", help="Path to the PEM encoded file.")
    args = parser.parse_args()

    if not os.path.exists(args.pem_file):
        print(f"Error: File '{args.pem_file}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(args.pem_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # Extract PEM base64 body
    match = re.search(r'-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----', content, re.DOTALL)
    if not match:
        print("Error: File does not contain a valid PEM CERTIFICATE block.", file=sys.stderr)
        return 1

    try:
        b64_data = match.group(1).replace('\n', '').replace('\r', '')
        der_data = base64.b64decode(b64_data)
    except Exception as e:
        print(f"Error decoding PEM base64 block: {e}", file=sys.stderr)
        return 1

    res, err = audit_cert(der_data)
    if err:
        print(f"Error auditing certificate: {err}", file=sys.stderr)
        return 1

    print("PEM Crypto Certificate Auditor")
    print("=" * 70)
    print(f"File Path : {args.pem_file}")
    print(f"Version   : v{res['version']}")
    print(f"Serial    : {res['serial']}")
    print(f"Signature : {res['signature_algorithm']}")
    print(f"Key Type  : {res['key_type']}")
    print(f"Key Size  : {res['key_size']}")
    print("-" * 70)
    print(f"Issuer    : {res['issuer']}")
    print(f"Subject   : {res['subject']}")
    print("-" * 70)
    print(f"Validity  : {res['not_before']} to {res['not_after']}")
    print("=" * 70)
    
    if res['audit']:
        print("Audit Findings:")
        for note in res['audit']:
            try:
                print(f"  {note}")
            except UnicodeEncodeError:
                clean_note = note.replace('[✓]', '[ok]')
                print(f"  {clean_note}")
    else:
        try:
            print("\033[92m[✓] Certificate security check passed successfully.\033[0m")
        except UnicodeEncodeError:
            print("[ok] Certificate security check passed successfully.")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
