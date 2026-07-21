#!/usr/bin/env python3

"""
Password Strength Analyzer - Analyze and evaluate the strength of passwords
"""

import re
import sys
import argparse

def analyze_password_strength(password):
    """Analyze the strength of a password and provide detailed feedback"""
    
    # Basic password information
    print(f"Password Analysis for: {password}")
    print("=" * 40)
    
    # Password length
    length_score = len(password)
    print(f"Length: {length_score} characters")
    
    # Character variety analysis
    has_lower = bool(re.search(r"[a-z]", password))
    has_upper = bool(re.search(r"[A-Z]", password))
    has_digit = bool(re.search(r"[0-9]", password))
    has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password))
    
    char_types = []
    if has_lower:
        char_types.append("Lowercase letters")
    if has_upper:
        char_types.append("Uppercase letters")
    if has_digit:
        char_types.append("Numbers")
    if has_special:
        char_types.append("Special characters")
    
    print(f"Character types used: {', '.join(char_types) if char_types else 'None'}")
    
    # Check for common patterns
    common_patterns = check_common_patterns(password)
    if common_patterns:
        print(f"Warning: {common_patterns}")
    
    # Calculate password strength score
    score = calculate_strength_score(password, has_lower, has_upper, has_digit, has_special)
    print(f"Strength Score: {score}/100")
    
    # Provide feedback based on score
    if score >= 80:
        print("Feedback: Very Strong Password")
    elif score >= 60:
        print("Feedback: Strong Password")
    elif score >= 40:
        print("Feedback: Medium Strength Password")
        print("Suggestions: Add more character types or increase length")
    elif score >= 20:
        print("Feedback: Weak Password")
        print("Suggestions: Add uppercase letters, numbers, and special characters")
    else:
        print("Feedback: Very Weak Password")
        print("Suggestions: Increase length and add different character types")

def check_common_patterns(password):
    """Check for common weak password patterns"""
    common_patterns = [
        (r'(?i)password', "Contains 'password'"),
        (r'12345', "Sequential numbers"),
        (r'qwerty', "QWERTY keyboard pattern"),
        (r'abc', "Sequential letters"),
        (r'xyz', "Sequential letters")
    ]
    
    for pattern, description in common_patterns:
        if re.search(pattern, password):
            return description
    return None

def calculate_strength_score(password, has_lower, has_upper, has_digit, has_special):
    """Calculate a password strength score out of 100"""
    score = 0
    
    # Length contributes up to 50 points
    length = len(password)
    score += min(length * 2, 50)
    
    # Character variety contributes up to 50 points
    char_variety = sum([has_lower, has_upper, has_digit, has_special])
    score += char_variety * 12.5
    
    # Bonus for longer passwords with good variety
    if length > 12 and char_variety >= 3:
        score += 10
    
    return min(int(score), 100)

def main():
    parser = argparse.ArgumentParser(description="Analyze password strength")
    parser.add_argument("password", nargs='?', help="Password to analyze")
    parser.add_argument("--password", dest="pwd_arg", help="Password to analyze (alternative argument)")
    parser.add_argument("-f", "--file", help="File containing passwords to analyze", default=None)
    
    args = parser.parse_args()
    
    if args.file:
        # Read passwords from file
        try:
            with open(args.file, 'r') as f:
                passwords = f.read().splitlines()
        except FileNotFoundError:
            print("Error: File not found")
            return
    elif args.pwd_arg:
        passwords = [args.pwd_arg]
    elif args.password:
        passwords = [args.password]
    else:
        # Interactive mode
        password = input("Enter password to analyze: ")
        passwords = [password]
    
    for i, pwd in enumerate(passwords):
        if i > 0:
            print("\n" + "-" * 50 + "\n")
        analyze_password_strength(pwd)

if __name__ == "__main__":
    main()