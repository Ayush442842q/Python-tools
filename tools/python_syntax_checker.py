#!/usr/bin/env python3
"""
Python Syntax Checker
Checks the syntax of one or more Python files.
"""
import argparse
import ast
import sys
import os

def check_syntax(file_path):
    """Check syntax of a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"

def main():
    parser = argparse.ArgumentParser(description='Check Python file syntax.')
    parser.add_argument('files', nargs='+', help='Python files to check')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output details for each file')
    
    args = parser.parse_args()
    
    all_passed = True
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            all_passed = False
            continue
        
        passed, error = check_syntax(file_path)
        if passed:
            if args.verbose:
                print(f"{file_path}: OK")
        else:
            all_passed = False
            print(f"{file_path}: Syntax Error - {error}", file=sys.stderr)
    
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
