#!/usr/bin/env python3
"""
Dotenv Validator

Compares a configuration .env file with an example .env.example template file to find missing, extra, or empty environment variables.

Usage:
    python tools/dotenv_validator.py --env .env --example .env.example
"""

import argparse
import os
import sys

def parse_env_file(filepath):
    variables = {}
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            if '=' not in line:
                continue
                
            key, val = line.split('=', 1)
            variables[key.strip()] = {
                'value': val.strip(),
                'line': line_num
            }
    return variables

def main():
    parser = argparse.ArgumentParser(description="Dotenv Validator - Compare and validate .env against a template/example")
    parser.add_argument('--env', default='.env', help='Path to target .env file (default: .env)')
    parser.add_argument('--example', default='.env.example', help='Path to template .env.example file (default: .env.example)')
    parser.add_argument('--strict', action='store_true', help='Treat empty values in .env as errors')
    
    args = parser.parse_args()

    if not os.path.exists(args.example):
        print(f"Error: Template file '{args.example}' does not exist.")
        return 1
        
    if not os.path.exists(args.env):
        print(f"Error: Configuration file '{args.env}' does not exist.")
        return 1

    env_vars = parse_env_file(args.env)
    example_vars = parse_env_file(args.example)

    if env_vars is None:
        print(f"Error reading configuration file '{args.env}'.")
        return 1
    if example_vars is None:
        print(f"Error reading template file '{args.example}'.")
        return 1

    missing = []
    empty = []
    extra = []

    # Check for missing variables
    for key in example_vars:
        if key not in env_vars:
            missing.append(key)
        elif not env_vars[key]['value']:
            empty.append(key)

    # Check for extra variables (in .env but not in .env.example)
    for key in env_vars:
        if key not in example_vars:
            extra.append(key)

    # Print results
    has_issues = False
    
    print(f"Auditing config: '{args.env}' against template: '{args.example}'\n")

    if missing:
        has_issues = True
        print("Missing Variables (defined in template but not in config):")
        for key in missing:
            print(f"  - {key}")
        print()

    if empty:
        if args.strict:
            has_issues = True
        label = "[Error]" if args.strict else "[Warning]"
        print(f"{label} Empty Variables (defined but have no value):")
        for key in empty:
            print(f"  - {key} (line {env_vars[key]['line']})")
        print()

    if extra:
        print("Extra Variables (defined in config but not in template):")
        for key in extra:
            print(f"  - {key} (line {env_vars[key]['line']})")
        print()

    if not missing and (not empty or not args.strict):
        print("[PASS] Validation passed! Configuration file matches the template.")
        return 0
    else:
        print("[FAIL] Validation failed with errors.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
