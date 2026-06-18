#!/usr/bin/env python3
"""
Password Breach Checker
Checks if a password has been compromised in data breaches using the Have I Been Pwned API.
Uses the K-Anonymity model to guarantee privacy (only the first 5 characters of the SHA-1 hash are sent).

Usage:
    python tools/password_breach_checker.py
    python tools/password_breach_checker.py -p "my_secret_password"
    python tools/password_breach_checker.py --check-file passwords.txt
"""

import argparse
import getpass
import hashlib
import json
import sys
import urllib.request
from urllib.error import URLError, HTTPError

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def get_breach_count(password):
    """
    Checks the Have I Been Pwned API to see if the password has been breached.
    Returns the count of breaches, or 0 if it has not been found.
    """
    # Calculate SHA-1 hash of the password
    sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1[:5]
    suffix = sha1[5:]

    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Python-Tools-Collection/1.0 (Password Breach Checker)'}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                print(f"{RED}[ERROR] API returned status code {response.status}{RESET}", file=sys.stderr)
                return None
            
            # Read and parse lines
            lines = response.read().decode('utf-8').splitlines()
            for line in lines:
                h_suffix, count = line.split(':')
                if h_suffix == suffix:
                    return int(count)
            return 0
    except HTTPError as e:
        print(f"{RED}[ERROR] HTTP error occurred: {e.code} - {e.reason}{RESET}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"{RED}[ERROR] Network/Connection error: {e.reason}{RESET}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"{RED}[ERROR] Unexpected error: {e}{RESET}", file=sys.stderr)
        return None

def analyze_strength(password):
    """Simple password strength analyzer."""
    length = len(password)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    score = 0
    feedback = []

    if length >= 8:
        score += 1
    else:
        feedback.append("Length is less than 8 characters.")

    if length >= 12:
        score += 1

    if has_upper and has_lower:
        score += 1
    else:
        feedback.append("Missing mix of uppercase and lowercase letters.")

    if has_digit:
        score += 1
    else:
        feedback.append("Missing numeric digits.")

    if has_special:
        score += 1
    else:
        feedback.append("Missing special characters (e.g. @, #, $, etc.).")

    return score, feedback

def print_result(password, count, verbose):
    """Displays the security check results for a single password."""
    score, feedback = analyze_strength(password)
    
    print("-" * 60)
    print(f"{BOLD}Password Integrity Analysis{RESET}")
    print("-" * 60)
    
    # Breach status
    if count is None:
        print(f"Breach Check Status: {YELLOW}UNKNOWN (API/Network Error){RESET}")
    elif count > 0:
        print(f"Breach Status: {RED}{BOLD}COMPROMISED!{RESET}")
        print(f"This password was found in {RED}{count:,}{RESET} data breaches.")
        print(f"{RED}[WARNING] Stop using this password immediately!{RESET}")
    else:
        print(f"Breach Status: {GREEN}SECURE (Not found in known breaches){RESET}")
        print("This password has not been detected in any public data leaks.")

    # Strength evaluation
    strength_labels = {
        0: f"{RED}Very Weak{RESET}",
        1: f"{RED}Weak{RESET}",
        2: f"{YELLOW}Moderate{RESET}",
        3: f"{GREEN}Strong{RESET}",
        4: f"{GREEN}Very Strong{RESET}",
        5: f"{GREEN}Excellent / Secure{RESET}"
    }
    
    print(f"Local Strength Rating: {strength_labels[score]} ({score}/5)")
    if verbose and feedback:
        print(f"{BOLD}Suggestions to improve password strength:{RESET}")
        for item in feedback:
            print(f" - {item}")
    print("-" * 60)

def main():
    parser = argparse.ArgumentParser(
        description="Check if your passwords have been leaked in data breaches securely."
    )
    parser.add_argument("-p", "--password", help="Password to check. (Leave empty for secure terminal input)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose password strength suggestions")
    parser.add_argument("-f", "--file", help="File containing list of passwords to check (one per line)")
    
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
            
            print(f"Checking {len(passwords)} passwords from '{args.file}'...")
            compromised_count = 0
            
            for idx, pwd in enumerate(passwords, 1):
                count = get_breach_count(pwd)
                mask = pwd[0] + "*" * (len(pwd) - 2) + pwd[-1] if len(pwd) > 2 else "***"
                if count is None:
                    print(f"[{idx}/{len(passwords)}] {mask}: {YELLOW}API error{RESET}")
                elif count > 0:
                    print(f"[{idx}/{len(passwords)}] {mask}: {RED}COMPROMISED ({count:,} times){RESET}")
                    compromised_count += 1
                else:
                    print(f"[{idx}/{len(passwords)}] {mask}: {GREEN}OK{RESET}")
            
            print("-" * 60)
            print(f"Scan complete. {compromised_count} out of {len(passwords)} passwords were compromised.")
            
        except FileNotFoundError:
            print(f"{RED}[ERROR] File '{args.file}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        # Single password check
        if args.password:
            password = args.password
        else:
            password = getpass.getpass("Enter the password to check (input is hidden): ")
            if not password:
                print(f"{RED}[ERROR] Password cannot be empty.{RESET}", file=sys.stderr)
                sys.exit(1)
        
        print("\nQuerying Have I Been Pwned database securely...")
        count = get_breach_count(password)
        print_result(password, count, args.verbose)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(1)
