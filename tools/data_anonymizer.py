#!/usr/bin/env python3
"""
Data PII Anonymizer

Scans files (CSV, JSON, or plain text) for Personally Identifiable Information (PII)
such as emails, phone numbers, credit card numbers, and IP addresses, replacing
them with masked values, hashes, or synthetic mock values.

Usage:
    python tools/data_anonymizer.py input.csv -o output.csv -m email,phone,name
    python tools/data_anonymizer.py log.txt -o log_anonymized.txt
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys

# ANSI Escape Sequences
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

# Regular expressions for PII detection
REGEX_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
REGEX_PHONE = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
REGEX_CREDIT_CARD = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
REGEX_IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

class Anonymizer:
    def __init__(self, salt="anonymizer_salt_123", use_hash=False, fields_to_mask=None):
        self.salt = salt
        self.use_hash = use_hash
        self.fields_to_mask = [f.lower().strip() for f in fields_to_mask] if fields_to_mask else []
        self.stats = {
            "emails": 0,
            "phones": 0,
            "cards": 0,
            "ips": 0,
            "fields": 0
        }

    def _hash_val(self, val):
        if not val:
            return val
        hasher = hashlib.sha256(f"{val}{self.salt}".encode('utf-8'))
        return hasher.hexdigest()[:12]

    def anonymize_email(self, email):
        self.stats["emails"] += 1
        if self.use_hash:
            return f"{self._hash_val(email)}@example.com"
        
        parts = email.split('@')
        if len(parts) == 2:
            name, domain = parts
            if len(name) <= 2:
                masked_name = name[0] + "*"
            else:
                masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
            return f"{masked_name}@{domain}"
        return "[email_redacted]"

    def anonymize_phone(self, phone):
        self.stats["phones"] += 1
        if self.use_hash:
            return f"phone-{self._hash_val(phone)}"
        
        # Remove non-digits
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 4:
            return f"+{digits[:-4]}****" if phone.startswith('+') else f"***-***-{digits[-4:]}"
        return "[phone_redacted]"

    def anonymize_credit_card(self, card):
        self.stats["cards"] += 1
        if self.use_hash:
            return f"card-{self._hash_val(card)}"
        
        # Keep last 4 digits
        digits = re.sub(r'\D', '', card)
        if len(digits) >= 4:
            return f"xxxx-xxxx-xxxx-{digits[-4:]}"
        return "[card_redacted]"

    def anonymize_ip(self, ip):
        self.stats["ips"] += 1
        if self.use_hash:
            return f"ip-{self._hash_val(ip)}"
        
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.x.x"
        return "[ip_redacted]"

    def anonymize_text(self, text):
        """Perform regex replacement on raw text string."""
        if not isinstance(text, str):
            return text

        # Match and replace credit cards
        def cc_repl(m):
            return self.anonymize_credit_card(m.group(0))
        text = REGEX_CREDIT_CARD.sub(cc_repl, text)

        # Match and replace emails
        def email_repl(m):
            return self.anonymize_email(m.group(0))
        text = REGEX_EMAIL.sub(email_repl, text)

        # Match and replace phones
        def phone_repl(m):
            return self.anonymize_phone(m.group(0))
        text = REGEX_PHONE.sub(phone_repl, text)

        # Match and replace IPs
        def ip_repl(m):
            return self.anonymize_ip(m.group(0))
        text = REGEX_IPV4.sub(ip_repl, text)

        return text

    def anonymize_value(self, key_name, value):
        """Anonymizes a single structured value based on field name or value patterns."""
        if not isinstance(value, str):
            return value
            
        key_lower = key_name.lower()
        
        # Check explicit field name matches
        if self.fields_to_mask and any(f in key_lower for f in self.fields_to_mask):
            self.stats["fields"] += 1
            if self.use_hash:
                return self._hash_val(value)
            return f"[redacted_{key_name}]"

        # Check heuristics based on key names
        if "email" in key_lower:
            return self.anonymize_email(value)
        elif "phone" in key_lower or "mobile" in key_lower:
            return self.anonymize_phone(value)
        elif "card" in key_lower or "cc_num" in key_lower:
            return self.anonymize_credit_card(value)
        elif "ip_address" in key_lower or "ipaddress" in key_lower:
            return self.anonymize_ip(value)
        elif "ssn" in key_lower or "social_security" in key_lower:
            self.stats["fields"] += 1
            if self.use_hash:
                return self._hash_val(value)
            return "[ssn_redacted]"

        # Default: check content patterns
        return self.anonymize_text(value)

    def process_csv(self, input_path, output_path):
        """Processes and anonymizes a CSV file."""
        with open(input_path, 'r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []

            rows = []
            for row in reader:
                rows.append(row)

        anonymized_headers = [self.anonymize_text(h) for h in headers]
        anonymized_rows = []

        for row_idx, row in enumerate(rows):
            new_row = []
            for col_idx, cell in enumerate(row):
                header_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                new_row.append(self.anonymize_value(header_name, cell))
            anonymized_rows.append(new_row)

        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            if anonymized_headers:
                writer.writerow(anonymized_headers)
            writer.writerows(anonymized_rows)

    def process_json(self, input_path, output_path):
        """Processes and anonymizes a JSON file recursively."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        def recurse_json(obj, parent_key=""):
            if isinstance(obj, dict):
                return {k: recurse_json(v, k) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [recurse_json(item, parent_key) for item in obj]
            elif isinstance(obj, str):
                return self.anonymize_value(parent_key, obj)
            else:
                return obj

        anonymized_data = recurse_json(data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(anonymized_data, f, indent=4)

    def process_text(self, input_path, output_path):
        """Processes and anonymizes plain text line by line."""
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:
            for line in infile:
                outfile.write(self.anonymize_text(line))


def main():
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI color escape sequences on Windows

    parser = argparse.ArgumentParser(
        description="Data PII Anonymizer - Redact, mask, and hash sensitive details in datasets and text files"
    )
    parser.add_argument("input", help="Path to the input file (CSV, JSON, or text)")
    parser.add_argument("-o", "--output", required=True, help="Path to save the anonymized output file")
    parser.add_argument("-m", "--mask", help="Comma-separated list of field/column names to explicitly mask")
    parser.add_argument("--hash", action="store_true", help="Replace values with hashes instead of masking templates")
    parser.add_argument("-s", "--salt", default="anonymizer_salt_123", help="Custom salt for hashing algorithms")
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.input):
        print(f"{CLR_RED}Error: Input file '{args.input}' does not exist.{CLR_RESET}")
        return 1

    mask_fields = args.mask.split(',') if args.mask else None
    anonymizer = Anonymizer(salt=args.salt, use_hash=args.hash, fields_to_mask=mask_fields)

    print("=" * 60)
    print(f"{CLR_GREEN}{CLR_BOLD}DATA PII ANONYMIZER{CLR_RESET}")
    print("=" * 60)
    print(f"Input File:  {args.input}")
    print(f"Output File: {args.output}")
    print(f"Mode:        {'Hashing' if args.hash else 'Masking'}")
    if mask_fields:
        print(f"Custom Mask: {mask_fields}")
    print("-" * 60)

    ext = os.path.splitext(args.input.lower())[1]

    try:
        if ext == '.csv':
            print("Detected CSV format. Processing table...")
            anonymizer.process_csv(args.input, args.output)
        elif ext == '.json':
            print("Detected JSON format. Processing structured objects...")
            anonymizer.process_json(args.input, args.output)
        else:
            print("Detected Plain Text format. Processing lines...")
            anonymizer.process_text(args.input, args.output)

        print(f"\n{CLR_GREEN}{CLR_BOLD}Anonymization complete!{CLR_RESET}")
        print("Summary of Redacted Elements:")
        print(f"  Emails Redacted      : {CLR_YELLOW}{anonymizer.stats['emails']}{CLR_RESET}")
        print(f"  Phone Numbers Redact : {CLR_YELLOW}{anonymizer.stats['phones']}{CLR_RESET}")
        print(f"  Credit Cards Redact  : {CLR_YELLOW}{anonymizer.stats['cards']}{CLR_RESET}")
        print(f"  IP Addresses Redact  : {CLR_YELLOW}{anonymizer.stats['ips']}{CLR_RESET}")
        print(f"  Custom Masked Fields : {CLR_YELLOW}{anonymizer.stats['fields']}{CLR_RESET}")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"{CLR_RED}An error occurred during processing: {e}{CLR_RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
