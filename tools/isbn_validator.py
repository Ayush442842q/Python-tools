#!/usr/bin/env python3
"""
ISBN Validator & Converter - Validate, format, and convert ISBN-10 and ISBN-13 codes.
"""

import sys
import re
import argparse

def clean_isbn(isbn_str):
    """Remove hyphens, spaces, and other delimiters from the ISBN string."""
    return re.sub(r'[- ]', '', isbn_str).strip()

def calculate_isbn10_checksum(digits):
    """Compute the check digit for the first 9 digits of an ISBN-10."""
    total = 0
    for idx, d in enumerate(digits[:9]):
        total += (10 - idx) * int(d)
    rem = (11 - (total % 11)) % 11
    return 'X' if rem == 10 else str(rem)

def calculate_isbn13_checksum(digits):
    """Compute the check digit for the first 12 digits of an ISBN-13."""
    total = 0
    for idx, d in enumerate(digits[:12]):
        weight = 3 if idx % 2 == 1 else 1
        total += weight * int(d)
    rem = (10 - (total % 10)) % 10
    return str(rem)

def validate_isbn10(clean_code):
    """Validates an ISBN-10 code."""
    if len(clean_code) != 10:
        return False
        
    if not re.match(r'^\d{9}[\dX]$', clean_code, re.IGNORECASE):
        return False
        
    expected_check = calculate_isbn10_checksum(clean_code)
    return clean_code[-1].upper() == expected_check

def validate_isbn13(clean_code):
    """Validates an ISBN-13 code."""
    if len(clean_code) != 13:
        return False
        
    if not re.match(r'^\d{13}$', clean_code):
        return False
        
    expected_check = calculate_isbn13_checksum(clean_code)
    return clean_code[-1] == expected_check

def convert_isbn10_to_isbn13(isbn10_clean):
    """Convert an ISBN-10 to ISBN-13 format."""
    if not validate_isbn10(isbn10_clean):
        return None
        
    # Prepend 978 and drop the ISBN-10 check digit
    base = "978" + isbn10_clean[:9]
    check = calculate_isbn13_checksum(base)
    return base + check

def format_isbn(clean_code):
    """
    Format clean ISBNs with standard hyphens.
    Note: Full publisher group ranges are highly complex.
    We apply a heuristic format representing standard layout divisions:
    ISBN-10: G-PP-TTTTT-C (Group-Publisher-Title-Check)
    ISBN-13: EAN-G-PP-TTTTT-C
    """
    if len(clean_code) == 10:
        return f"{clean_code[0]}-{clean_code[1:3]}-{clean_code[3:8]}-{clean_code[8:9]}-{clean_code[9]}"
    elif len(clean_code) == 13:
        return f"{clean_code[0:3]}-{clean_code[3:4]}-{clean_code[4:6]}-{clean_code[6:11]}-{clean_code[11:12]}-{clean_code[12]}"
    return clean_code

def inspect_isbn(clean_code):
    """Deconstruct and explain the segments of an ISBN."""
    if len(clean_code) == 10 and validate_isbn10(clean_code):
        return {
            "Type": "ISBN-10",
            "Valid": True,
            "Formatted": format_isbn(clean_code),
            "Segments": {
                "Group/Country ID": clean_code[0],
                "Publisher Prefix": clean_code[1:3],
                "Title Identifier": clean_code[3:9],
                "Check Digit": clean_code[9].upper()
            },
            "Convertible to ISBN-13": convert_isbn10_to_isbn13(clean_code)
        }
    elif len(clean_code) == 13 and validate_isbn13(clean_code):
        return {
            "Type": "ISBN-13",
            "Valid": True,
            "Formatted": format_isbn(clean_code),
            "Segments": {
                "EAN Prefix": clean_code[0:3],
                "Group/Country ID": clean_code[3:4],
                "Publisher Prefix": clean_code[4:6],
                "Title Identifier": clean_code[6:12],
                "Check Digit": clean_code[12]
            }
        }
    else:
        return {
            "Type": "Unknown/Malformed",
            "Valid": False,
            "Formatted": clean_code,
            "Segments": {}
        }

def main():
    parser = argparse.ArgumentParser(
        description="ISBN Validator & Converter - Check and manage ISBN-10 and ISBN-13 book identifier codes."
    )
    parser.add_argument("isbn", nargs="?", help="ISBN code to validate/format")
    parser.add_argument(
        "-f", "--file", help="Path to file containing a list of ISBNs (one per line) to batch validate"
    )
    parser.add_argument(
        "-c", "--convert", action="store_true",
        help="Attempt to convert ISBN-10 inputs to ISBN-13"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # File batch mode
        try:
            with open(args.file, 'r') as f:
                codes = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
            
        print(f"{'Raw Input':<20} | {'Type':<8} | {'Status':<7} | {'Formatted / Conversion':<25}")
        print("-" * 70)
        for code in codes:
            clean = clean_isbn(code)
            is_v10 = validate_isbn10(clean)
            is_v13 = validate_isbn13(clean)
            
            status = "VALID" if (is_v10 or is_v13) else "INVALID"
            type_str = "ISBN-10" if is_v10 else ("ISBN-13" if is_v13 else "UNKNOWN")
            
            target = format_isbn(clean)
            if args.convert and is_v10:
                target = f"-> {format_isbn(convert_isbn10_to_isbn13(clean))}"
                
            print(f"{code:<20} | {type_str:<8} | {status:<7} | {target:<25}")
            
    elif args.isbn:
        # Single code validation
        clean = clean_isbn(args.isbn)
        details = inspect_isbn(clean)
        
        print(f"Input Code: {args.isbn}")
        print(f"Cleaned   : {clean}")
        print(f"Type      : {details['Type']}")
        
        if details["Valid"]:
            print("\033[92m[OK] Status: Valid Code\033[0m")
            print(f"Formatted : {details['Formatted']}")
            print("\nSegments:")
            for k, v in details["Segments"].items():
                print(f"  - {k}: {v}")
                
            if "Convertible to ISBN-13" in details and details["Convertible to ISBN-13"]:
                conv = details["Convertible to ISBN-13"]
                print(f"\nISBN-13 Equivalent: {format_isbn(conv)} ({conv})")
        else:
            print("\033[91m[FAIL] Status: Invalid ISBN Code\033[0m")
            sys.exit(1)
    else:
        # Interactive loop
        print("=" * 60)
        print(" ISBN Validator & Converter - Interactive Mode")
        print(" Enter an ISBN code to inspect. Type 'exit' to quit.")
        print("=" * 60)
        
        while True:
            try:
                val = input("\nEnter ISBN: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                break
                
            if val.lower() in ('exit', 'quit'):
                break
                
            if not val:
                continue
                
            clean = clean_isbn(val)
            details = inspect_isbn(clean)
            
            print(f"Type: {details['Type']}")
            if details["Valid"]:
                print("\033[92m[OK] Valid\033[0m")
                print(f"Formatted: {details['Formatted']}")
                if "Convertible to ISBN-13" in details and details["Convertible to ISBN-13"]:
                    print(f"ISBN-13  : {format_isbn(details['Convertible to ISBN-13'])}")
            else:
                print("\033[91m[FAIL] Invalid\033[0m")

if __name__ == "__main__":
    main()
