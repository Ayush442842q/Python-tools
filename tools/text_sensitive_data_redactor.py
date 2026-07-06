#!/usr/bin/env python3
"""
Text Sensitive Data Redactor & Auditor
Scans text files or streams for sensitive PII (emails, IP addresses, credit cards, SSNs, phone numbers, API keys)
and redacts or masks them using labels, asterisks, or cryptographic hashes.
"""

import argparse
import hashlib
import re
import sys

# Define sensitive data regex patterns
PATTERNS = {
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "IPV4": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "MAC_ADDRESS": r"\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b",
    "API_KEY": r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{16,})['\"]?\b",
    "BEARER_TOKEN": r"(?i)Bearer\s+([A-Za-z0-9\-._~+/]+=*)",
}

def luhn_check(card_str):
    """Validate credit card number using Luhn algorithm to avoid false positives."""
    digits = [int(c) for c in card_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for idx, digit in enumerate(reverse_digits):
        if idx % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0

def mask_match(match_str, pattern_type, style="label", hash_salt=""):
    """Format the replacement string for a matched sensitive pattern."""
    if style == "label":
        return f"[REDACTED:{pattern_type}]"
    elif style == "asterisk":
        if len(match_str) <= 4:
            return "*" * len(match_str)
        # Preserve first and last character
        return match_str[0] + ("*" * (len(match_str) - 2)) + match_str[-1]
    elif style == "hash":
        # Cryptographic anonymization to preserve correlation in log files
        digest = hashlib.sha256((hash_salt + match_str).encode('utf-8')).hexdigest()[:10]
        return f"[{pattern_type}_HASH:{digest}]"
    return "[REDACTED]"

def redact_text(text, active_patterns, style="label", hash_salt="", stats_counter=None):
    """Process text and replace sensitive matches."""
    result = text
    
    for pattern_name, regex_pattern in active_patterns.items():
        compiled_regex = re.compile(regex_pattern)
        
        def replace_func(match):
            matched_val = match.group(0)
            
            # Additional validation for credit cards to avoid false positives
            if pattern_name == "CREDIT_CARD":
                cleaned = re.sub(r"[^\d]", "", matched_val)
                if not luhn_check(cleaned):
                    return matched_val
                    
            if stats_counter is not None:
                stats_counter[pattern_name] = stats_counter.get(pattern_name, 0) + 1
                
            return mask_match(matched_val, pattern_name, style, hash_salt)
            
        result = compiled_regex.sub(replace_func, result)
        
    return result

def main():
    parser = argparse.ArgumentParser(description="Text Sensitive Data Redactor & Auditor")
    
    parser.add_argument("input", nargs="?", help="Input text file path (reads from stdin if omitted)")
    parser.add_argument("-o", "--output", help="Output file path (writes to stdout by default)")
    
    parser.add_argument("-s", "--style", choices=["label", "asterisk", "hash"], default="label",
                        help="Masking style: 'label' ([REDACTED:TYPE]), 'asterisk' (m****h), or 'hash' ([TYPE_HASH:abc123])")
    parser.add_argument("--salt", default="", help="Salt string for 'hash' masking style to secure log correlation")
    
    parser.add_argument("-c", "--custom-regex", help="Custom regex pattern to redact (labeled as CUSTOM)")
    parser.add_argument("--stats", action="store_true", help="Print statistical summary of detected sensitive fields")
    
    # Flags to disable specific patterns if desired
    parser.add_argument("--skip-ip", action="store_true", help="Skip IPv4 redaction")
    parser.add_argument("--skip-email", action="store_true", help="Skip Email redaction")

    args = parser.parse_args()

    # Prepare active patterns dictionary
    active_patterns = PATTERNS.copy()
    if args.skip_ip:
        active_patterns.pop("IPV4", None)
    if args.skip_email:
        active_patterns.pop("EMAIL", None)
        
    if args.custom_regex:
        active_patterns["CUSTOM"] = args.custom_regex

    # Read input
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            print("Error: No input data provided. Specify a file path or pipe text into stdin.", file=sys.stderr)
            parser.print_usage()
            sys.exit(1)

    stats_counter = {} if args.stats else None
    redacted_content = redact_text(content, active_patterns, style=args.style, hash_salt=args.salt, stats_counter=stats_counter)

    # Output statistics if requested
    if args.stats:
        print("====================================================", file=sys.stderr)
        print("            SENSITIVE DATA AUDIT REPORT             ", file=sys.stderr)
        print("====================================================", file=sys.stderr)
        if not stats_counter:
            print("✓ No sensitive fields detected.", file=sys.stderr)
        else:
            for pattern_name, count in sorted(stats_counter.items()):
                print(f"  {pattern_name:15}: {count:5d} match(es) redacted", file=sys.stderr)
        print("====================================================\n", file=sys.stderr)

    # Write output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(redacted_content)
            print(f"✓ Redacted content written to '{args.output}'", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output file '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(redacted_content)

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    main()
