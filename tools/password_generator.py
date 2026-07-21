#!/usr/bin/env python3
"""
Password Generator - Generate secure passwords with various options.

This tool generates strong, random passwords with customizable length,
character sets, and complexity requirements.
"""

import argparse
import secrets
import string
import sys
from typing import List


def generate_password(
    length: int = 16,
    use_uppercase: bool = True,
    use_lowercase: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = False,
) -> str:
    """
    Generate a secure random password.
    
    Args:
        length: Length of the password
        use_uppercase: Include uppercase letters
        use_lowercase: Include lowercase letters
        use_digits: Include digits
        use_symbols: Include symbols
        exclude_ambiguous: Exclude ambiguous characters (0O1lI)
        
    Returns:
        Generated password string
    """
    # Define character sets
    uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lowercase = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?/"
    
    # Remove ambiguous characters if requested
    if exclude_ambiguous:
        ambiguous = set("0O1lI")
        uppercase = "".join(c for c in uppercase if c not in ambiguous)
        lowercase = "".join(c for c in lowercase if c not in ambiguous)
        digits = "".join(c for c in digits if c not in ambiguous)
        # Note: symbols already don't contain 0, O, 1, l, I
    
    # Build the character set
    charset = ""
    if use_uppercase:
        charset += uppercase
    if use_lowercase:
        charset += lowercase
    if use_digits:
        charset += digits
    if use_symbols:
        charset += symbols
    
    if not charset:
        raise ValueError("At least one character set must be selected")
    
    # Generate password
    password = ''.join(secrets.choice(charset) for _ in range(length))
    
    # Ensure at least one character from each selected set (if length allows)
    if length >= 4:
        attempts = 0
        while attempts < 100:  # Prevent infinite loop
            # Check if password meets requirements
            meets_requirements = True
            
            if use_uppercase and not any(c in uppercase for c in password):
                meets_requirements = False
            if use_lowercase and not any(c in lowercase for c in password):
                meets_requirements = False
            if use_digits and not any(c in digits for c in password):
                meets_requirements = False
            if use_symbols and not any(c in symbols for c in password):
                meets_requirements = False
            
            if meets_requirements:
                break
                
            # Regenerate if requirements not met
            password = ''.join(secrets.choice(charset) for _ in range(length))
            attempts += 1
    
    return password


def main():
    """Main entry point for the password generator."""
    parser = argparse.ArgumentParser(
        description="Generate secure passwords",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Generate 16-character password
  %(prog)s -l 32              # Generate 32-character password
  %(prog)s -l 20 -s           # 20 chars with symbols
  %(prog)s -l 12 --no-digits  # 12 chars without digits
  %(prog)s -l 24 --exclude-ambiguous  # Exclude 0O1lI
        """
    )
    
    parser.add_argument(
        '-l', '--length',
        type=int,
        default=16,
        help='Length of the password (default: 16)'
    )
    
    parser.add_argument(
        '--no-uppercase',
        action='store_true',
        help='Exclude uppercase letters'
    )
    
    parser.add_argument(
        '--no-lowercase',
        action='store_true',
        help='Exclude lowercase letters'
    )
    
    parser.add_argument(
        '--no-digits',
        action='store_true',
        help='Exclude digits'
    )
    
    parser.add_argument(
        '--no-symbols',
        action='store_true',
        help='Exclude symbols'
    )
    
    parser.add_argument(
        '--exclude-ambiguous',
        action='store_true',
        help='Exclude ambiguous characters (0O1lI)'
    )
    
    parser.add_argument(
        '-n', '--count',
        type=int,
        default=1,
        help='Number of passwords to generate (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.length < 1:
        print("Error: Password length must be at least 1", file=sys.stderr)
        sys.exit(1)
    
    if args.count < 1:
        print("Error: Count must be at least 1", file=sys.stderr)
        sys.exit(1)
    
    # Check that at least one character type is selected
    if all([args.no_uppercase, args.no_lowercase, args.no_digits, args.no_symbols]):
        print("Error: At least one character type must be selected", file=sys.stderr)
        sys.exit(1)
    
    # Generate passwords
    try:
        for i in range(args.count):
            password = generate_password(
                length=args.length,
                use_uppercase=not args.no_uppercase,
                use_lowercase=not args.no_lowercase,
                use_digits=not args.no_digits,
                use_symbols=not args.no_symbols,
                exclude_ambiguous=args.exclude_ambiguous,
            )
            print(password)
            
    except Exception as e:
        print(f"Error generating password: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()