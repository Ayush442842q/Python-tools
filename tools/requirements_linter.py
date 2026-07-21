#!/usr/bin/env python3
"""
Requirements Linter
Lint requirements.txt for common issues like unpinned packages, insecure URLs, etc.
"""
import argparse
import re
import sys
import os

def lint_requirements(file_path):
    """Lint a requirements.txt file."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    for i, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Check for inline comments
        if '#' in line:
            line = line.split('#')[0].strip()
        
        # Check for -r, -e, etc.
        if line.startswith('-r ') or line.startswith('--requirement ') or line.startswith('-e ') or line.startswith('--editable '):
            issues.append(f"Line {i}: Use of {line.split()[0]} is not recommended for linting; consider using separate files.")
            continue
        
        # Check for URL dependencies
        if re.match(r'^[a-zA-Z][a-zA-Z0-9]*(+[a-zA-Z0-9]+)?://', line):
            issues.append(f"Line {i}: Direct URL dependency can be insecure and not reproducible. Consider using a version-controlled package.")
            continue
        
        # Check for missing version pin
        # Pattern: package_name [==|>=|<=|>|<|~=|!=] version
        if not re.search(r'[=<>!~]', line):
            issues.append(f"Line {i}: Package '{line}' is not version-pinned. Consider specifying a version.")
            continue
        
        # Check for insecure protocols in URL (if any)
        if 'http://' in line:
            issues.append(f"Line {i}: Insecure HTTP URL used. Use HTTPS if possible.")
    
    return issues

def main():
    parser = argparse.ArgumentParser(description='Lint requirements.txt files.')
    parser.add_argument('files', nargs='+', help='Requirements files to lint')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output details for each file')
    
    args = parser.parse_args()
    
    all_issues = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            all_issues.append(f"File not found: {file_path}")
            continue
        
        issues = lint_requirements(file_path)
        if issues:
            all_issues.extend([f"{file_path}: {issue}" for issue in issues])
            if args.verbose:
                for issue in issues:
                    print(f"{file_path}: {issue}")
        else:
            if args.verbose:
                print(f"{file_path}: No issues found")
    
    if all_issues:
        print("Linting issues found:", file=sys.stderr)
        for issue in all_issues:
            print(issue, file=sys.stderr)
        sys.exit(1)
    else:
        if not args.verbose:
            print("No linting issues found.")
        sys.exit(0)

if __name__ == '__main__':
    main()
