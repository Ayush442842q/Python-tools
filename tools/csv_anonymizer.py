#!/usr/bin/env python3
"""
Structured CSV PII Anonymizer & Masker - Scrub personal identifiers (PII) from CSV files.
Supports hashing, format-preserving masking (emails, phone numbers, IDs), static redaction,
and mock faking of names or values.
"""

import argparse
import csv
import hashlib
import os
import sys

def hash_value(val, salt=""):
    """Returns SHA-256 hex digest of the value."""
    if not val:
        return ""
    hasher = hashlib.sha256()
    hasher.update((val + salt).encode('utf-8'))
    return hasher.hexdigest()[:16] # Shortened for readability

def mask_email(email):
    """Partially masks email mailbox and domain: u***@ex***.com."""
    if not email or '@' not in email:
        return email
    parts = email.split('@', 1)
    mailbox, domain = parts[0], parts[1]
    
    # Mask mailbox
    if len(mailbox) <= 2:
        masked_mailbox = "*" * len(mailbox)
    else:
        masked_mailbox = mailbox[0] + "*" * (len(mailbox) - 2) + mailbox[-1]
        
    # Mask domain
    domain_parts = domain.rsplit('.', 1)
    if len(domain_parts) == 2:
        dom_name, dom_ext = domain_parts[0], domain_parts[1]
        if len(dom_name) <= 2:
            masked_dom = "*" * len(dom_name)
        else:
            masked_dom = dom_name[0] + "*" * (len(dom_name) - 2) + dom_name[-1]
        masked_domain = f"{masked_dom}.{dom_ext}"
    else:
        masked_domain = domain
        
    return f"{masked_mailbox}@{masked_domain}"

def mask_general(val, unmasked_suffix_len=4):
    """Replaces most characters with '*' keeping the suffix unmasked."""
    if not val:
        return ""
    val_str = str(val)
    if len(val_str) <= unmasked_suffix_len:
        return "*" * len(val_str)
    return "*" * (len(val_str) - unmasked_suffix_len) + val_str[-unmasked_suffix_len:]

def anonymize_csv(input_path, output_path, rules, salt=""):
    """
    Reads CSV and applies anonymization rules based on column headers.
    rules: dict mapping column_header -> operation ('hash', 'email', 'mask', 'redact', 'fake')
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.", file=sys.stderr)
        return False
        
    fake_counters = {}
    
    try:
        with open(input_path, 'r', newline='', encoding='utf-8', errors='replace') as infile:
            reader = csv.reader(infile)
            headers = next(reader, None)
            
            if not headers:
                print("Error: Empty CSV or missing headers.", file=sys.stderr)
                return False
                
            # Map column index to operation
            col_ops = {}
            for idx, header in enumerate(headers):
                # Match case-insensitive
                for rule_col, op in rules.items():
                    if rule_col.lower() == header.strip().lower():
                        col_ops[idx] = op
                        
            if not col_ops:
                print("Warning: No matching columns found for anonymization rules.", file=sys.stderr)
                
            # Open output
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.writer(outfile)
                writer.writerow(headers)
                
                for row_idx, row in enumerate(reader, 1):
                    new_row = list(row)
                    # Extend row if it is truncated compared to headers
                    while len(new_row) < len(headers):
                        new_row.append("")
                        
                    for col_idx, op in col_ops.items():
                        original_val = new_row[col_idx]
                        if not original_val:
                            continue
                            
                        if op == 'hash':
                            new_row[col_idx] = hash_value(original_val, salt)
                        elif op == 'email':
                            new_row[col_idx] = mask_email(original_val)
                        elif op == 'mask':
                            new_row[col_idx] = mask_general(original_val)
                        elif op == 'redact':
                            new_row[col_idx] = "[REDACTED]"
                        elif op == 'fake':
                            # Generate simple pseudo-fake item
                            fake_counters[col_idx] = fake_counters.get(col_idx, 0) + 1
                            new_row[col_idx] = f"Fake_{headers[col_idx]}_{fake_counters[col_idx]}"
                            
                    writer.writerow(new_row)
                    
        return True
    except Exception as e:
        print(f"Error during CSV processing: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Structured CSV PII Anonymizer & Masker.")
    parser.add_argument("-i", "--input", required=True, help="Input CSV file path")
    parser.add_argument("-o", "--output", required=True, help="Output CSV file path")
    parser.add_argument("--hash", help="Comma-separated column headers to hash")
    parser.add_argument("--email", help="Comma-separated column headers to partially mask as email")
    parser.add_argument("--mask", help="Comma-separated column headers to mask (keeping last 4 chars)")
    parser.add_argument("--redact", help="Comma-separated column headers to redact entirely")
    parser.add_argument("--fake", help="Comma-separated column headers to replace with dummy identifiers")
    parser.add_argument("-s", "--salt", default="pii_salt_123", help="Cryptographic salt for hashing")
    
    args = parser.parse_args()
    
    # Parse rules
    rules = {}
    
    if args.hash:
        for col in args.hash.split(','):
            rules[col.strip()] = 'hash'
    if args.email:
        for col in args.email.split(','):
            rules[col.strip()] = 'email'
    if args.mask:
        for col in args.mask.split(','):
            rules[col.strip()] = 'mask'
    if args.redact:
        for col in args.redact.split(','):
            rules[col.strip()] = 'redact'
    if args.fake:
        for col in args.fake.split(','):
            rules[col.strip()] = 'fake'
            
    if not rules:
        print("Error: No anonymization rules specified. Use --hash, --email, --mask, --redact, or --fake.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Starting CSV anonymization on '{args.input}'...")
    print(f"Rules configured for {len(rules)} columns.")
    
    success = anonymize_csv(args.input, args.output, rules, args.salt)
    if success:
        print(f"Successfully wrote anonymized dataset to '{args.output}'")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
