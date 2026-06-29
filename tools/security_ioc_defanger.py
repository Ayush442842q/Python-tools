#!/usr/bin/env python3
"""
security_ioc_defanger.py - Security IOC Defanger & Refanger

A utility to defang (make safe to share) and refang indicators of compromise
(IOCs) including URLs, domain names, IPv4/IPv6 addresses, and email addresses.
Supports bulk file processing and colorized terminal output.

Requirements:
    - Python 3.6+ (No external dependencies)
"""

import sys
import os
import re
import argparse

# ANSI Escape Sequences for Color Output
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"

def has_color_support():
    """Checks if the output stream supports ANSI colors."""
    if os.name == 'nt':
        # Enable virtual terminal processing on Windows 10+
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return sys.stdout.isatty()

# Common Defanging Patterns
# URLs: http(s) -> hxxp(s)
# Domains: domain.com -> domain[.]com
# IPv4: 1.2.3.4 -> 1.2.3[.]4
# Email: test@test.com -> test[at]test[.]com

def defang_url(text, use_color=False):
    """Defangs HTTP and HTTPS protocols."""
    # Find http:// or https:// or ftp://
    def repl(match):
        proto = match.group(1)
        # replace t with x
        defanged_proto = proto.replace('t', 'x').replace('T', 'X')
        if use_color:
            return f"{COLOR_RED}{defanged_proto}{COLOR_RESET}://"
        return f"{defanged_proto}://"
        
    return re.sub(r'\b(https?|ftp)://', repl, text, flags=re.IGNORECASE)

def defang_ips(text, use_color=False):
    """Defangs IPv4 addresses."""
    # Matches standard IPv4 addresses
    ipv4_pattern = r'\b((?:\d{1,3}\.){3})\b(\d{1,3})'
    
    def repl(match):
        first_part = match.group(1)
        last_octet = match.group(2)
        # replace the last dot with [.] or [.]colored
        first_part_defanged = first_part[:-1] # Remove trailing dot
        dot = "[.]"
        if use_color:
            dot = f"{COLOR_YELLOW}[.]{COLOR_RESET}"
        return f"{first_part_defanged}{dot}{last_octet}"
        
    return re.sub(ipv4_pattern, repl, text)

def defang_emails(text, use_color=False):
    """Defangs email addresses by replacing @ with [at]."""
    # Simple email pattern
    email_pattern = r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    
    def repl(match):
        username = match.group(1)
        domain = match.group(2)
        at_symbol = "[at]"
        if use_color:
            at_symbol = f"{COLOR_CYAN}[at]{COLOR_RESET}"
        # Also defang the domain part
        domain_defanged = defang_domain_simple(domain, use_color)
        return f"{username}{at_symbol}{domain_defanged}"
        
    return re.sub(email_pattern, repl, text)

def defang_domain_simple(domain, use_color=False):
    """Helper to defang a domain name string."""
    parts = domain.split('.')
    if len(parts) > 1:
        dot = "[.]"
        if use_color:
            dot = f"{COLOR_YELLOW}[.]{COLOR_RESET}"
        # Defang the last dot before TLD
        return '.'.join(parts[:-1]) + dot + parts[-1]
    return domain

def defang_domains(text, use_color=False):
    """Defangs domain names in generic text, ignoring already defanged/processed ones."""
    # We want to match domains (e.g. google.com, sub.domain.co.uk) but avoid matching numbers (IPs) or inside protocols
    # Matches words with dots, ending with a 2-6 letter TLD
    domain_pattern = r'\b([a-zA-Z0-9-]+\.)+([a-zA-Z]{2,6})\b'
    
    def repl(match):
        full_match = match.group(0)
        # Skip if it's part of an email username (handled separately)
        # Skip if it is preceded by hxxp or http (handled by URL defang)
        # If it's just a raw domain:
        return defang_domain_simple(full_match, use_color)
        
    # We use a custom parser or regex to only touch domains not inside URL/Email
    # For safety in generic text, we can run this after URL and email defangers
    # but only on segments that don't contain protocols or @ symbols
    return re.sub(domain_pattern, repl, text)

def defang_text(text, use_color=False):
    """Applies all defanging rules to the text."""
    # Order matters:
    # 1. Defang Emails (handles internal domains too)
    # 2. Defang URLs (handles protocol)
    # 3. Defang IPs
    # 4. Defang remaining raw domains
    text = defang_emails(text, use_color)
    text = defang_url(text, use_color)
    text = defang_ips(text, use_color)
    
    # Simple regex to target standard domains not already defanged
    # e.g., matching google.com but not google[.]com
    # Must not be preceded by / or @ or [at]
    text = re.sub(
        r'(?<![a-zA-Z0-9@/.\-])\b([a-zA-Z0-9\-]+\.)+([a-zA-Z]{2,6})\b(?![.\]a-zA-Z])',
        lambda m: defang_domain_simple(m.group(0), use_color),
        text
    )
    return text


# Refanging Patterns (Reversing the defanging process)
def refang_text(text):
    """Converts defanged IOCs back into their live/active formats."""
    # Replace hxxp/hxxps/ftp with http/https/ftp
    text = re.sub(r'\b(hxxps?|hXXPs?|fxp)://', lambda m: m.group(1).replace('x', 't').replace('X', 'T') + "://", text, flags=re.IGNORECASE)
    
    # Replace [.] , (.) , {.} , [.] with .
    text = re.sub(r'\[\.\]|\(\.\)|\{\.\}|\[\.\]', '.', text)
    
    # Replace [at] , (at) , {at} , [at] with @
    text = re.sub(r'\[at\]|\(at\)|\{at\}|\[AT\]', '@', text, flags=re.IGNORECASE)
    
    return text

def process_io_streams(input_stream, output_stream, action_func, use_color=False):
    """Reads lines from input_stream, applies action_func, and writes to output_stream."""
    for line in input_stream:
        processed = action_func(line, use_color) if use_color else action_func(line)
        output_stream.write(processed)
        output_stream.flush()

def main():
    parser = argparse.ArgumentParser(description="Defang or Refang Security Indicators of Compromise (IOCs).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--defang", action="store_true", help="Defang the input IOCs (default)")
    group.add_argument("-r", "--refang", action="store_true", help="Refang the input IOCs (restore active links/IPs)")
    
    parser.add_argument("-i", "--input", help="Path to input file (reads from stdin if not specified)")
    parser.add_argument("-o", "--output", help="Path to output file (writes to stdout if not specified)")
    parser.add_argument("--no-color", action="store_true", help="Disable color formatting in stdout")
    
    args = parser.parse_args()
    
    # Determine operation
    is_defang_op = not args.refang
    
    # Determine color usage
    use_color = not args.no_color and has_color_support() and args.output is None
    
    # Open input stream
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
            sys.exit(1)
        try:
            input_file = open(args.input, "r", encoding="utf-8")
        except IOError as e:
            print(f"Error: Cannot open input file. {e}", file=sys.stderr)
            sys.exit(1)
    else:
        input_file = sys.stdin
        # Print interactive mode prompt if stdin is a terminal
        if sys.stdin.isatty():
            print(f"{COLOR_CYAN}--- IOC Defanger Interactive Mode ---{COLOR_RESET}")
            print("Paste your IOCs / logs below. Press Ctrl+D (or Ctrl+Z on Windows) followed by Enter to process:")

    # Open output stream
    if args.output:
        try:
            output_file = open(args.output, "w", encoding="utf-8")
        except IOError as e:
            print(f"Error: Cannot open output file for writing. {e}", file=sys.stderr)
            if args.input:
                input_file.close()
            sys.exit(1)
    else:
        output_file = sys.stdout

    try:
        if is_defang_op:
            if use_color:
                process_io_streams(input_file, output_file, defang_text, use_color=True)
            else:
                process_io_streams(input_file, output_file, lambda x: defang_text(x, False))
        else:
            # Refanging doesn't use colors since we are recreating live strings
            process_io_streams(input_file, output_file, lambda x, c=False: refang_text(x), use_color=False)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
    finally:
        if args.input:
            input_file.close()
        if args.output:
            output_file.close()

if __name__ == "__main__":
    main()
