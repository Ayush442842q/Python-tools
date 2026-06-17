#!/usr/bin/env python3
"""
Environment Variable Manager
Compares .env files with .env.example files to verify consistency, identifies missing variables, and helps keep them in sync.
"""

import sys
import os
import argparse

def parse_env_file(file_path):
    """
    Parse a .env style file and return a dictionary of keys to their line numbers,
    and a list of all parsed keys.
    """
    env_data = {}
    if not os.path.exists(file_path):
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                    
                key = line.split('=', 1)[0].strip()
                # Validate key name (simple check)
                if not key.isidentifier() and not (key.replace('_', '').isalnum()):
                    continue
                env_data[key] = {
                    'line_num': idx,
                    'raw': line
                }
        return env_data
    except Exception as e:
        print(f"Error reading '{file_path}': {e}", file=sys.stderr)
        return None

def sync_example_file(env_path, example_path):
    """
    Append missing keys from env_path to example_path as empty placeholders.
    """
    env_keys = parse_env_file(env_path)
    example_keys = parse_env_file(example_path)
    
    if env_keys is None:
        print(f"Error: Source file '{env_path}' does not exist or could not be read.", file=sys.stderr)
        return False
        
    if example_keys is None:
        # Create example file if it doesn't exist
        example_keys = {}
        try:
            with open(example_path, 'w', encoding='utf-8') as f:
                f.write("# Environment Variables Example\n\n")
        except Exception as e:
            print(f"Error creating '{example_path}': {e}", file=sys.stderr)
            return False

    missing_keys = [k for k in env_keys if k not in example_keys]
    
    if not missing_keys:
        print(f"'{example_path}' is already in sync with '{env_path}'.")
        return True
        
    try:
        with open(example_path, 'a', encoding='utf-8') as f:
            f.write("\n# Added automatically by Env Manager\n")
            for key in sorted(missing_keys):
                f.write(f"{key}=\n")
        print(f"Added {len(missing_keys)} missing key(s) to '{example_path}'")
        return True
    except Exception as e:
        print(f"Error updating '{example_path}': {e}", file=sys.stderr)
        return False

def init_env_file(example_path, env_path, overwrite=False):
    """
    Initialize a new .env file from .env.example.
    """
    if os.path.exists(env_path) and not overwrite:
        print(f"Error: Target file '{env_path}' already exists. Use --force to overwrite.", file=sys.stderr)
        return False
        
    if not os.path.exists(example_path):
        print(f"Error: Example file '{example_path}' does not exist.", file=sys.stderr)
        return False
        
    try:
        with open(example_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully initialized '{env_path}' from '{example_path}'")
        return True
    except Exception as e:
        print(f"Error initializing '{env_path}': {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Environment Variable Manager - Check consistency and sync .env files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env", default=".env", help="Path to the .env file (default: .env)")
    parser.add_argument("--example", default=".env.example", help="Path to the example file (default: .env.example)")
    parser.add_argument("--verify", action="store_true", help="Exit with error code if keys are missing from .env")
    parser.add_argument("--sync", action="store_true", help="Sync missing keys from .env to .env.example")
    parser.add_argument("--init", action="store_true", help="Initialize a new .env file from .env.example")
    parser.add_argument("--force", action="store_true", help="Force overwrite when initializing")
    
    args = parser.parse_args()
    
    if args.init:
        success = init_env_file(args.example, args.env, args.force)
        return 0 if success else 1
        
    if args.sync:
        success = sync_example_file(args.env, args.example)
        return 0 if success else 1
        
    # Default behavior: compare files
    env_exists = os.path.exists(args.env)
    example_exists = os.path.exists(args.example)
    
    if not env_exists and not example_exists:
        print("Error: Neither the .env file nor the .env.example file was found.", file=sys.stderr)
        return 1
        
    env_keys = parse_env_file(args.env) if env_exists else {}
    example_keys = parse_env_file(args.example) if example_exists else {}
    
    if env_exists and env_keys is None:
        return 1
    if example_exists and example_keys is None:
        return 1
        
    has_issues = False
    
    print("=== Environment Variable Status ===")
    print(f"Local .env status: {'Found' if env_exists else 'Not Found'}")
    print(f"Template .env.example status: {'Found' if example_exists else 'Not Found'}")
    print()
    
    if env_exists and example_exists:
        # Check for missing keys in .env
        missing = [k for k in example_keys if k not in env_keys]
        if missing:
            print("❌ Missing keys in .env (defined in .env.example):")
            for k in missing:
                print(f"  - {k} (line {example_keys[k]['line_num']} in .env.example)")
            has_issues = True
        else:
            print("✓ No keys missing from .env")
            
        # Check for extra keys in .env (undocumented in .env.example)
        extra = [k for k in env_keys if k not in example_keys]
        if extra:
            print("\n⚠️  Undocumented keys in .env (not in .env.example):")
            for k in extra:
                print(f"  - {k} (line {env_keys[k]['line_num']} in .env)")
        else:
            print("✓ All keys in .env are documented in .env.example")
            
    elif not env_exists:
        print(f"Template .env.example lists {len(example_keys)} variables.")
        print(f"Run 'python tools/env_manager.py --init' to generate your local .env file.")
        has_issues = True
        
    elif not example_exists:
        print(f"Local .env lists {len(env_keys)} variables.")
        print(f"Run 'python tools/env_manager.py --sync' to generate the .env.example file.")
        
    if args.verify and has_issues:
        sys.exit(1)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
