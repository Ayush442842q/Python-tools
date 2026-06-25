#!/usr/bin/env python3
"""
Luhn Validator & Mock Card/IMEI Generator

Validates credit cards, IMEIs, and other identifiers using the Luhn algorithm.
Identifies card networks (Visa, Mastercard, Amex, etc.) and generates valid test
numbers.
"""

import argparse
import random
import re
import sys
from typing import Dict, Optional, Tuple

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass

# ANSI colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

# Card network regex rules: (Name, Prefix, Possible Lengths)
CARD_NETWORKS = [
    ("Visa", r"^4", [13, 16]),
    ("Mastercard", r"^(5[1-5]|222[1-9]|22[3-9]|2[3-6]|27[0-1]|2720)", [16]),
    ("American Express", r"^3[47]", [15]),
    ("Discover", r"^(6011|622(12[6-9]|1[3-9][0-9]|[2-8][0-9]{2}|9[0-1][0-9]|92[0-5])|64[4-9]|65)", [16, 19]),
    ("Diners Club", r"^(30[0-5]|36|38|39)", [14]),
    ("JCB", r"^35(2[89]|[3-8][0-9])", [16]),
    ("UnionPay", r"^62", [16, 17, 18, 19]),
]

def check_luhn(number: str) -> bool:
    """Verifies a number string against the Luhn algorithm checklist."""
    cleaned = re.sub(r"\D", "", number)
    if not cleaned:
        return False
        
    total = 0
    num_digits = len(cleaned)
    oddeven = num_digits & 1
    
    for i in range(num_digits):
        digit = int(cleaned[i])
        
        # Double every second digit from the right
        if not ((i & 1) ^ oddeven):
            digit *= 2
            if digit > 9:
                digit -= 9
                
        total += digit
        
    return (total % 10) == 0

def identify_card_network(card_number: str) -> str:
    """Identifies the credit card network based on prefix rules."""
    cleaned = re.sub(r"\D", "", card_number)
    for name, regex, lengths in CARD_NETWORKS:
        if re.match(regex, cleaned):
            if len(cleaned) in lengths:
                return name
            else:
                return f"{name} (Invalid Length: {len(cleaned)})"
    return "Unknown Network"

def generate_luhn(prefix: str, length: int) -> str:
    """Generates a random valid Luhn number starting with prefix of given length."""
    # Convert prefix to list of digits
    digits = [int(c) for c in prefix if c.isdigit()]
    
    # Fill up to length - 1
    while len(digits) < length - 1:
        digits.append(random.randint(0, 9))
        
    # Calculate check digit
    total = 0
    num_digits = length
    oddeven = num_digits & 1
    
    for i in range(len(digits)):
        digit = digits[i]
        if not ((i & 1) ^ oddeven):
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
        
    check_digit = (10 - (total % 10)) % 10
    digits.append(check_digit)
    
    return "".join(map(str, digits))

def format_card(card_number: str) -> str:
    """Formats credit card numbers nicely with space delimiters based on length."""
    cleaned = re.sub(r"\D", "", card_number)
    if len(cleaned) == 15:  # Amex: 4-6-5 format
        return f"{cleaned[0:4]} {cleaned[4:10]} {cleaned[10:15]}"
    elif len(cleaned) == 14:  # Diners Club: 4-6-4 format
        return f"{cleaned[0:4]} {cleaned[4:10]} {cleaned[10:14]}"
    else:  # Standard 4-4-4-4... format
        return " ".join(cleaned[i:i+4] for i in range(0, len(cleaned), 4))

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Luhn Validator & Generator - Validate credit cards/IMEIs and generate test values.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Mutually exclusive actions
    group = parser.add_mutually_exclusive_group()
    group.add_argument("number", nargs="?", help="The number to validate (credit card or IMEI)")
    group.add_argument("-g", "--generate", choices=["visa", "mastercard", "amex", "discover", "diners", "jcb", "unionpay", "imei", "generic"], help="Generate a valid Luhn number")
    
    parser.add_argument("-l", "--length", type=int, help="Specify length for generated number")
    
    args = parser.parse_args()
    
    # 1. Generation Mode
    if args.generate:
        prefix = ""
        length = args.length
        
        target = args.generate.lower()
        if target == "visa":
            prefix = "4"
            length = length or 16
        elif target == "mastercard":
            prefix = str(random.choice([51, 52, 53, 54, 55, 2221]))
            length = length or 16
        elif target == "amex":
            prefix = str(random.choice([34, 37]))
            length = length or 15
        elif target == "discover":
            prefix = "6011"
            length = length or 16
        elif target == "diners":
            prefix = str(random.choice([300, 36, 38]))
            length = length or 14
        elif target == "jcb":
            prefix = "3528"
            length = length or 16
        elif target == "unionpay":
            prefix = "62"
            length = length or 16
        elif target == "imei":
            # IMEI starts with arbitrary Reporting Body Identifier prefixes (e.g. 35, 86, etc.)
            prefix = str(random.choice([35, 86, 44, 99]))
            length = length or 15
        else: # Generic
            prefix = str(random.randint(1, 9))
            length = length or 16
            
        generated_num = generate_luhn(prefix, length)
        
        # Display Generated Info
        print(f"\n{COLOR_GREEN}[+] Generated Valid {args.generate.upper()} Number:{COLOR_RESET}")
        print(f"  Raw       : {generated_num}")
        if target != "imei" and target != "generic":
            print(f"  Formatted : {format_card(generated_num)}")
        print(f"  Checksum  : Valid (Luhn Check Digit: {generated_num[-1]})")
        return 0
        
    # 2. Validation Mode
    number = args.number
    if not number:
        # Prompt if run without arguments
        try:
            number = input(f"{COLOR_YELLOW}[?]{COLOR_RESET} Enter credit card or IMEI number to validate: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[-] Cancelled.")
            return 1
            
    cleaned = re.sub(r"\D", "", number)
    if not cleaned:
        print(f"{COLOR_RED}[-] Error: Input must contain numeric digits.{COLOR_RESET}", file=sys.stderr)
        return 1
        
    is_valid = check_luhn(cleaned)
    
    print(f"\n{COLOR_CYAN}{COLOR_BOLD}--- Validation Results ---{COLOR_RESET}")
    print(f"  Input Value : {number}")
    print(f"  Cleaned Dig : {cleaned}")
    print(f"  Length      : {len(cleaned)} digits")
    
    # Identify type
    if len(cleaned) == 15 and (cleaned.startswith("35") or cleaned.startswith("86") or cleaned.startswith("44") or cleaned.startswith("99")):
        # Probably IMEI
        print(f"  Inferred Typ: IMEI (International Mobile Equipment Identity)")
    elif 13 <= len(cleaned) <= 19:
        network = identify_card_network(cleaned)
        print(f"  Inferred Typ: Credit Card ({network})")
        if not network.startswith("Unknown") and "Invalid Length" not in network:
            print(f"  Formatted   : {format_card(cleaned)}")
    else:
        print(f"  Inferred Typ: Generic Identification Number")
        
    if is_valid:
        print(f"  Luhn Check  : {COLOR_GREEN}✓ VALID Checksum{COLOR_RESET}")
        print(f"  Check Digit : {cleaned[-1]} (Correct)")
        return 0
    else:
        print(f"  Luhn Check  : {COLOR_RED}✗ INVALID Checksum (Luhn mismatch){COLOR_RESET}")
        print(f"  Check Digit : {cleaned[-1]} (Incorrect)")
        return 2

if __name__ == "__main__":
    sys.exit(main())
