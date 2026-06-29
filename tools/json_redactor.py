#!/usr/bin/env python3
"""
JSON Redactor

Recursively traverses a JSON file to redact, mask, hash, or remove sensitive fields
(e.g., passwords, keys, emails, credit cards) based on key names or value regex patterns.
Useful for sanitizing database dumps or API response logs before using them in local development.

Usage:
    python tools/json_redactor.py input.json -o output.json [options]
"""

import argparse
import hashlib
import json
import re
import sys

# Default patterns for sensitive keys (case-insensitive substring matches)
DEFAULT_SENSITIVE_KEYS = {
    'password', 'passwd', 'secret', 'token', 'key', 'auth', 'ssn', 
    'credit_card', 'card', 'cvv', 'salt', 'hash', 'signature', 'private'
}

# Regexes for auto-detecting sensitive values
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
CARD_REGEX = re.compile(r'\b(?:\d[ -]*?){13,16}\b')  # 13 to 16 digit card number

def redact_value(value, strategy, key_name=None):
    """Apply a redaction strategy to a single value."""
    if not isinstance(value, (str, int, float)):
        return value
        
    val_str = str(value)
    
    if strategy == 'remove':
        return None # Note: The caller needs to handle removing the key entirely if returned None, or we just nullify it.
    elif strategy == 'hash':
        return hashlib.sha256(val_str.encode('utf-8')).hexdigest()[:16]
    elif strategy == 'mask':
        if len(val_str) <= 4:
            return '*' * len(val_str)
        return '*' * (len(val_str) - 4) + val_str[-4:]
    else: # Default: 'redact'
        return '[REDACTED]'

def check_value_regex(val_str):
    """Check if the string matches value-based sensitive patterns."""
    if EMAIL_REGEX.search(val_str):
        return 'email'
    if CARD_REGEX.search(val_str):
        return 'credit_card'
    return None

def process_node(node, sensitive_keys, strategy, regex_redact=True):
    """Recursively traverse and redact JSON node."""
    if isinstance(node, dict):
        new_dict = {}
        for k, v in node.items():
            k_lower = k.lower()
            
            # Check if key is sensitive
            is_sensitive = any(sk in k_lower for sk in sensitive_keys)
            
            if is_sensitive:
                if strategy == 'remove':
                    # Skip adding this key entirely
                    continue
                new_dict[k] = redact_value(v, strategy, k)
            else:
                # Recurse or check value regex
                if isinstance(v, (dict, list)):
                    new_dict[k] = process_node(v, sensitive_keys, strategy, regex_redact)
                else:
                    val_str = str(v)
                    matched_type = check_value_regex(val_str) if regex_redact else None
                    if matched_type:
                        new_dict[k] = redact_value(v, 'redact', k)
                    else:
                        new_dict[k] = v
        return new_dict
        
    elif isinstance(node, list):
        new_list = []
        for item in node:
            if isinstance(item, (dict, list)):
                new_list.append(process_node(item, sensitive_keys, strategy, regex_redact))
            else:
                val_str = str(item)
                matched_type = check_value_regex(val_str) if regex_redact else None
                if matched_type:
                    new_list.append(redact_value(item, 'redact'))
                else:
                    new_list.append(item)
        return new_list
        
    else:
        # Top-level scalar value
        val_str = str(node)
        matched_type = check_value_regex(val_str) if regex_redact else None
        if matched_type:
            return redact_value(node, 'redact')
        return node

def main():
    parser = argparse.ArgumentParser(
        description="Recursively redact or mask sensitive info in JSON structures."
    )
    parser.add_argument("input", nargs="?", default="-",
                        help="Input JSON file (default: stdin)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output JSON file (default: stdout)")
    parser.add_argument("-s", "--strategy", choices=["redact", "mask", "hash", "remove"], default="redact",
                        help="Redaction strategy (default: redact)")
    parser.add_argument("-k", "--keys", default=None,
                        help="Comma-separated custom sensitive key terms to check")
    parser.add_argument("--no-regex", action="store_true",
                        help="Disable auto-detection of sensitive values (emails/cards) via regex")
    parser.add_argument("-p", "--pretty", action="store_true",
                        help="Format the output JSON with indentation")
                        
    args = parser.parse_args()
    
    # Define keys to match
    sensitive_keys = DEFAULT_SENSITIVE_KEYS
    if args.keys:
        custom_keys = {k.strip().lower() for k in args.keys.split(',') if k.strip()}
        sensitive_keys = sensitive_keys.union(custom_keys)

    # Read input JSON
    try:
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON input: {e}", file=sys.stderr)
        return 1

    # Redact data
    redacted_data = process_node(
        data, 
        sensitive_keys=sensitive_keys, 
        strategy=args.strategy, 
        regex_redact=not args.no_regex
    )

    # Serialize output
    indent = 2 if args.pretty else None
    try:
        out_str = json.dumps(redacted_data, indent=indent, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_str)
                f.write("\n")
        else:
            sys.stdout.write(out_str)
            sys.stdout.write("\n")
    except Exception as e:
        print(f"Error writing JSON output: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
