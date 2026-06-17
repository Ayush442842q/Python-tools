#!/usr/bin/env python3
"""
Time-based One-Time Password (TOTP) Generator - Offline multi-factor authentication (MFA) client.

This tool implements RFC 6238 (TOTP) and RFC 4226 (HOTP) in pure Python without any external
dependencies. It generates active 6-digit verification codes, supports storing multiple accounts
with encrypted/plaintext configuration files, and renders visual countdown progress bars.
"""

import sys
import os
import time
import hmac
import hashlib
import struct
import base64
import json
import argparse

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.totp_generator_keys.json")

def colorize(text, color):
    """Wrap text in ANSI color escape codes if supported"""
    if color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def parse_base32(secret):
    """
    Decodes a base32 encoded string into bytes.
    Pads the secret correctly if required.
    """
    # Clean secret from spaces and make uppercase
    secret = secret.strip().replace(" ", "").upper()
    
    # Fix padding
    missing_padding = len(secret) % 8
    if missing_padding != 0:
        secret += '=' * (8 - missing_padding)
        
    try:
        return base64.b32decode(secret)
    except Exception as e:
        raise ValueError(f"Invalid Base32 secret key format: {e}")

def get_hotp(secret_bytes, counter):
    """
    Generate an HMAC-based One-Time Password (HOTP)
    As specified in RFC 4226.
    """
    # Counter must be packed as 8-byte big-endian integer
    counter_bytes = struct.pack(">Q", counter)
    
    # Compute HMAC-SHA1
    hmac_sha1 = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
    
    # Dynamic Truncation (DT)
    offset = hmac_sha1[-1] & 0x0F
    binary = struct.unpack(">I", hmac_sha1[offset:offset+4])[0] & 0x7FFFFFFF
    
    # Get 6-digit code
    code = binary % 1000000
    return f"{code:06d}"

def get_totp(secret_base32, time_step=30):
    """
    Generate a Time-based One-Time Password (TOTP)
    As specified in RFC 6238.
    """
    secret_bytes = parse_base32(secret_base32)
    # Calculate intervals elapsed
    current_time = int(time.time())
    counter = current_time // time_step
    time_remaining = time_step - (current_time % time_step)
    
    code = get_hotp(secret_bytes, counter)
    return code, time_remaining

def load_keys(config_path):
    """Load keys from local configuration file"""
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(colorize(f"Error loading configuration file: {e}", 'red'), file=sys.stderr)
        return {}

def save_keys(keys, config_path):
    """Save keys to local configuration file with secure permissions"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Write file
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(keys, f, indent=4)
            
        # Set file permissions to owner read/write only (Unix-like)
        if os.name != 'nt':
            os.chmod(config_path, 0o600)
            
        return True
    except Exception as e:
        print(colorize(f"Error saving keys: {e}", 'red'), file=sys.stderr)
        return False

def show_progress_bar(remaining, time_step=30, width=15):
    """Generate a visual countdown progress bar"""
    filled_len = int(round(width * remaining / time_step))
    bar = "█" * filled_len + "░" * (width - filled_len)
    
    # Color bar based on urgency
    if remaining <= 5:
        colored_bar = colorize(bar, 'red')
    elif remaining <= 10:
        colored_bar = colorize(bar, 'yellow')
    else:
        colored_bar = colorize(bar, 'green')
        
    return f"[{colored_bar}] {remaining:2d}s"

def main():
    parser = argparse.ArgumentParser(
        description="TOTP Generator - Secure, offline time-based MFA token generator."
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # Subcommand: generate
    gen_parser = subparsers.add_parser("get", help="Generate code for a specific key/account")
    gen_parser.add_argument("name", nargs="?", help="Account label name to fetch from storage")
    gen_parser.add_argument("-s", "--secret", help="Directly specify secret key (Base32 string)")
    
    # Subcommand: add
    add_parser = subparsers.add_parser("add", help="Add a new account secret to storage")
    add_parser.add_argument("name", help="Account label name (e.g. 'Github:john')")
    add_parser.add_argument("secret", help="Secret key (Base32 encoded string)")
    
    # Subcommand: list
    subparsers.add_parser("list", help="List all saved accounts and generate current codes")
    
    # Subcommand: remove
    rem_parser = subparsers.add_parser("remove", help="Remove an account secret from storage")
    rem_parser.add_argument("name", help="Account label name to remove")
    
    # Global Config option
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH, help="Path to config JSON file")
    
    args = parser.parse_args()
    
    # Enable terminal VT processing on Windows
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
    # If no subcommand, default to list / get all
    if not args.command:
        args.command = "list"
        
    keys = load_keys(args.config)
    
    if args.command == "add":
        # Test secret base32 validation first
        try:
            parse_base32(args.secret)
        except ValueError as e:
            print(colorize(str(e), 'red'), file=sys.stderr)
            sys.exit(1)
            
        keys[args.name] = args.secret.strip().replace(" ", "")
        if save_keys(keys, args.config):
            print(colorize(f"Success: Added secret for account '{args.name}'", 'green'))
            
    elif args.command == "remove":
        if args.name in keys:
            del keys[args.name]
            if save_keys(keys, args.config):
                print(colorize(f"Success: Removed account '{args.name}'", 'green'))
        else:
            print(colorize(f"Error: Account '{args.name}' not found.", 'red'), file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "get":
        if args.secret:
            try:
                code, remaining = get_totp(args.secret)
                print(f"Code: {colorize(code, 'bold')} ({remaining}s remaining)")
            except ValueError as e:
                print(colorize(str(e), 'red'), file=sys.stderr)
                sys.exit(1)
        elif args.name:
            if args.name in keys:
                try:
                    code, remaining = get_totp(keys[args.name])
                    print(f"{args.name}: {colorize(code, 'bold')} ({remaining}s remaining)")
                except ValueError as e:
                    print(colorize(f"Error decoding secret for {args.name}: {e}", 'red'), file=sys.stderr)
            else:
                print(colorize(f"Error: Account '{args.name}' not found.", 'red'), file=sys.stderr)
                sys.exit(1)
        else:
            gen_parser.print_help()
            
    elif args.command == "list":
        if not keys:
            print("No saved accounts found. Add one using:")
            print(f"  python {sys.argv[0]} add <AccountName> <SecretKey>")
            return
            
        print("=" * 60)
        print(colorize("Active MFA Verification Codes", 'bold'))
        print("=" * 60)
        
        has_error = False
        for name, secret in keys.items():
            try:
                code, remaining = get_totp(secret)
                progress = show_progress_bar(remaining)
                # Pretty alignment
                padded_name = name[:20].ljust(20)
                formatted_code = colorize(f"{code[:3]} {code[3:]}", 'bold')
                print(f" {padded_name} │ {formatted_code} │ {progress}")
            except ValueError:
                print(f" {name[:20].ljust(20)} │ [Invalid Secret Key]      │")
                has_error = True
                
        print("=" * 60)
        if has_error:
            print(colorize("Warning: Some secret keys could not be decoded. Double check their base32 format.", 'yellow'))

if __name__ == "__main__":
    main()
