#!/usr/bin/env python3
"""
Simple Security Checker
Checks Python files for common security issues.
"""
import argparse
import re
import sys
import os

# Patterns for potential security issues
PATTERNS = [
    (r'eval\s*\(', "Use of eval() can be dangerous"),
    (r'exec\s*\(', "Use of exec() can be dangerous"),
    (r'pickle\.loads?\s*', "Pickle can execute arbitrary code, use with caution"),
    (r'os\.system\s*\(', "os.system() is dangerous, use subprocess module"),
    (r'subprocess\.call\s*[^,]*shell\s*=\s*True', "subprocess with shell=True is dangerous"),
    (r"open\s*[^)]*['\"]w['\"]", "Opening file in write mode without checking path can be risky"),
    (r'r\s*=\s*requests\.get\s*\([^)]*\)\s*\.text', "Consider using .content for binary data or check for HTTPS"),
]

def check_file(file_path):
    """Check a single Python file for security issues."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    lines = content.split('\n')
    for i, line in enumerate(lines, start=1):
        for pattern, message in PATTERNS:
            if re.search(pattern, line):
                issues.append(f"Line {i}: {message}")
    
    return issues

def main():
    parser = argparse.ArgumentParser(description='Check Python files for common security issues.')
    parser.add_argument('files', nargs='+', help='Python files to check')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output details for each file')
    
    args = parser.parse_args()
    
    all_issues = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            all_issues.append(f"File not found: {file_path}")
            continue
        
        issues = check_file(file_path)
        if issues:
            all_issues.extend([f"{file_path}: {issue}" for issue in issues])
            if args.verbose:
                for issue in issues:
                    print(f"{file_path}: {issue}")
        else:
            if args.verbose:
                print(f"{file_path}: No issues found")
    
    if all_issues:
        print("Security issues found:", file=sys.stderr)
        for issue in all_issues:
            print(issue, file=sys.stderr)
        sys.exit(1)
    else:
        if not args.verbose:
            print("No security issues found.")
        sys.exit(0)

if __name__ == '__main__':
    main()
