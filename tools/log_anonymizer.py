#!/usr/bin/env python3
"""
Log Anonymizer & PII Masker - Redacts, masks, or hashes sensitive information (PII, IPs, keys) from log files.
Provides options for placeholder substitution, character masking, and SHA-256 token hashing.
"""

import argparse
import hashlib
import os
import re
import sys

# Default patterns for identifying sensitive information
PATTERNS = {
    'email': (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', '[EMAIL_REDACTED]'),
    'ipv4': (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IPV4_REDACTED]'),
    'ipv6': (r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b', '[IPV6_REDACTED]'),
    'phone': (r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b', '[PHONE_REDACTED]'),
    'ssn': (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
    'credit_card': (r'\b(?:\d[ -]*?){13,16}\b', '[CARD_REDACTED]'),
    # Matches key/password patterns like api_key = "abc123xyz" or "password": "my_secret"
    'credential': (r'(?i)\b(password|pass|passwd|api_key|secret|token|private_key|auth)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.\~]{8,})["\']?', '[CREDENTIAL_REDACTED]')
}

def get_hash(val, salt=""):
    """Returns a deterministic SHA-256 hash of the value to preserve correlation."""
    hasher = hashlib.sha256()
    hasher.update((val + salt).encode('utf-8'))
    return f"[HASH:{hasher.hexdigest()[:12]}]"

def apply_mask(val, item_type):
    """Partially masks the characters of the value depending on its type."""
    if item_type == 'email':
        if '@' in val:
            local, domain = val.split('@', 1)
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1] if len(local) > 2 else "*" * len(local)
            masked_domain = domain[0] + "*" * (len(domain) - 4) + domain[-2:] if len(domain) > 4 else "*" * len(domain)
            return f"{masked_local}@{masked_domain}"
    elif item_type in ('ipv4', 'ipv6'):
        parts = val.split('.') if item_type == 'ipv4' else val.split(':')
        if len(parts) > 2:
            # Mask middle parts
            return parts[0] + "." + ".".join(["***"] * (len(parts) - 2)) + "." + parts[-1] if item_type == 'ipv4' else parts[0] + ":" + ":".join(["****"] * (len(parts) - 2)) + ":" + parts[-1]
    elif item_type == 'credit_card':
        clean = re.sub(r'\D', '', val)
        return "*" * (len(clean) - 4) + clean[-4:] if len(clean) > 4 else "*" * len(val)
    elif item_type == 'phone':
        clean = re.sub(r'\D', '', val)
        return "*" * (len(clean) - 4) + clean[-4:] if len(clean) > 4 else "*" * len(val)
    
    # Generic mask fallback
    return val[0] + "*" * (len(val) - 2) + val[-1] if len(val) > 2 else "*" * len(val)

def process_line(line, rules, mode, salt=""):
    """Applies anonymization rules to a single line of text."""
    for name, (pattern, placeholder) in rules.items():
        # Credentials require grouping handling because they match key + value
        if name == 'credential':
            def cred_replacer(match):
                key = match.group(1)
                val = match.group(2)
                if mode == 'redact':
                    repl = placeholder
                elif mode == 'hash':
                    repl = get_hash(val, salt)
                else:  # mask
                    repl = apply_mask(val, 'credential')
                # Preserve formatting around the key
                matched_str = match.group(0)
                # Locate start of val in matched string
                val_start_idx = matched_str.index(val)
                return matched_str[:val_start_idx] + repl + matched_str[val_start_idx + len(val):]
            line = re.sub(pattern, cred_replacer, line)
        else:
            def general_replacer(match):
                val = match.group(0)
                if mode == 'redact':
                    return placeholder
                elif mode == 'hash':
                    return get_hash(val, salt)
                else:  # mask
                    return apply_mask(val, name)
            line = re.sub(pattern, general_replacer, line)
            
    return line

def main():
    parser = argparse.ArgumentParser(
        description="Log Anonymizer & PII Masker: Safely scrub secrets and PII from logs and text files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", help="Path to input log or text file (use '-' for stdin)")
    parser.add_argument("-o", "--output", help="Path to output file (writes to console by default)")
    parser.add_argument("-m", "--mode", choices=['redact', 'mask', 'hash'], default='redact',
                        help="Anonymization mode. redact: full placeholder replace; mask: keep outer chars; hash: SHA256 hash (default: redact)")
    parser.add_argument("-s", "--salt", default="", help="Salt string for hash modes (default: empty)")
    parser.add_argument("-i", "--inplace", action="store_true", help="Modify the input file in-place (cannot use with stdout/stdin)")
    parser.add_argument("-t", "--types", help="Comma-separated types to anonymize (default: all). Options: email, ipv4, ipv6, phone, ssn, credit_card, credential")
    parser.add_argument("-p", "--pattern", action="append", nargs=2, metavar=("NAME", "REGEX"),
                        help="Add custom search regex. Requires two args: name and pattern. E.g. -p token '[A-Z]{10}'")

    args = parser.parse_args()

    # Determine rules to run
    active_types = [t.strip().lower() for t in args.types.split(',')] if args.types else list(PATTERNS.keys())
    
    rules = {}
    for t in active_types:
        if t in PATTERNS:
            rules[t] = PATTERNS[t]
        else:
            print(f"[!] Warning: Unknown type '{t}' ignored.", file=sys.stderr)

    # Process custom patterns
    if args.pattern:
        for name, pattern in args.pattern:
            rules[name] = (pattern, f"[{name.upper()}_REDACTED]")

    # Validate output options
    if args.inplace:
        if args.input == '-':
            print("[!] Error: Cannot write in-place when reading from stdin.", file=sys.stderr)
            sys.exit(1)
        if args.output:
            print("[!] Error: Cannot use --inplace and --output together.", file=sys.stderr)
            sys.exit(1)

    # Read content
    if args.input == '-':
        lines = sys.stdin.readlines()
    else:
        if not os.path.exists(args.input):
            print(f"[!] Error: Input file '{args.input}' does not exist.", file=sys.stderr)
            sys.exit(1)
        with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

    # Process content
    output_lines = []
    for line in lines:
        output_lines.append(process_line(line, rules, args.mode, args.salt))

    # Write output
    if args.inplace:
        with open(args.input, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
        print(f"[+] Successfully anonymized '{args.input}' in-place.")
    elif args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
        print(f"[+] Successfully saved anonymized log to '{args.output}'.")
    else:
        # Standard print
        for line in output_lines:
            sys.stdout.write(line)

if __name__ == "__main__":
    main()
