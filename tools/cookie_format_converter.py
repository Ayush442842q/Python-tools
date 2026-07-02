#!/usr/bin/env python3
"""
Cookie Format Converter

Convert cookies between Netscape format (used by curl, wget, cookies.txt)
and JSON format (used by browser extensions like EditThisCookie, Puppeteer, Playwright, etc.).
Allows validating and pruning expired cookies.

Usage:
    python tools/cookie_format_converter.py cookies.txt -o cookies.json
    python tools/cookie_format_converter.py cookies.json -o cookies.txt

Requirements:
    - Python 3.6+
"""

import os
import sys
import json
import time
import argparse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}", file=sys.stderr)
    else:
        print(text, file=sys.stderr)

def parse_netscape(lines, use_color=True):
    """Parse Netscape/Mozilla cookie file lines."""
    cookies = []
    current_time = time.time()
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        # Skip empty lines or standard comment lines
        if not line or (line.startswith('#') and not line.startswith('#HttpOnly_')):
            continue
            
        is_httponly = False
        if line.startswith('#HttpOnly_'):
            is_httponly = True
            line = line[len('#HttpOnly_'):] # Strip the prefix
            
        parts = line.split('\t')
        # Netscape format requires exactly 7 fields
        if len(parts) < 7:
            # Try splitting by multiple spaces if tabs aren't used
            parts = [p for p in line.split() if p]
            if len(parts) < 7:
                print_colored(f"Warning: Line {line_num} does not have 7 fields, skipping: {line}", YELLOW, use_color)
                continue
                
        domain = parts[0]
        # Flag indicating if all machines under domain can access (true/false)
        flag = parts[1].upper() == 'TRUE'
        path = parts[2]
        secure = parts[3].upper() == 'TRUE'
        
        try:
            expiration = int(parts[4])
        except ValueError:
            print_colored(f"Warning: Line {line_num} has invalid expiration time, skipping.", YELLOW, use_color)
            continue
            
        name = parts[5]
        # Some cookies might have an empty value
        value = parts[6] if len(parts) > 6 else ""
        
        cookie_obj = {
            "domain": domain,
            "hostOnly": not flag,
            "path": path,
            "secure": secure,
            "expirationDate": expiration,
            "name": name,
            "value": value,
            "httpOnly": is_httponly
        }
        cookies.append(cookie_obj)
        
    return cookies

def parse_json(json_str, use_color=True):
    """Parse JSON cookie format."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as jde:
        print_colored(f"Error: Invalid JSON format: {jde}", RED, use_color)
        return None
        
    if not isinstance(data, list):
        # Could be a single cookie object
        if isinstance(data, dict):
            data = [data]
        else:
            print_colored("Error: JSON must be a list of cookie objects.", RED, use_color)
            return None
            
    cookies = []
    # Standardize field names from common extensions (EditThisCookie/Playwright)
    for idx, c in enumerate(data):
        if not isinstance(c, dict):
            continue
            
        domain = c.get("domain") or c.get("host")
        name = c.get("name")
        value = c.get("value", "")
        path = c.get("path", "/")
        
        # Determine secure and httpOnly
        secure = c.get("secure", False)
        # Handle cases where secure is a string
        if isinstance(secure, str):
            secure = secure.upper() == "TRUE"
            
        httponly = c.get("httpOnly", c.get("httponly", False))
        if isinstance(httponly, str):
            httponly = httponly.upper() == "TRUE"
            
        # Handle expiration (could be expirationDate, expires, or sessions)
        expiration = c.get("expirationDate") or c.get("expires")
        if expiration is None:
            # If no expiration date, set standard session cookie duration or distant future
            # 0 or negative often represents session cookie
            expiration = 0
        else:
            try:
                # Could be float
                expiration = int(float(expiration))
            except (ValueError, TypeError):
                expiration = 0
                
        if not domain or not name:
            print_colored(f"Warning: Cookie at index {idx} is missing 'domain' or 'name', skipping.", YELLOW, use_color)
            continue
            
        cookies.append({
            "domain": domain,
            "hostOnly": c.get("hostOnly", False),
            "path": path,
            "secure": secure,
            "expirationDate": expiration,
            "name": name,
            "value": value,
            "httpOnly": httponly
        })
        
    return cookies

def to_netscape_string(cookies):
    """Generate Netscape/cookies.txt format string."""
    lines = [
        "# Netscape HTTP Cookie File",
        "# This file was generated by cookie_format_converter.py",
        "# http://curl.haxx.se/rfc/cookie_spec.html",
        "# This is a generated file! Do not edit.",
        ""
    ]
    
    for c in cookies:
        domain = c["domain"]
        httponly_prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        
        # flag: TRUE if domain starts with a dot, else FALSE (indicates subdomain matching)
        # In Netscape: hostOnly=false -> flag=TRUE, hostOnly=true -> flag=FALSE
        flag = "FALSE" if c.get("hostOnly") else "TRUE"
        
        path = c["path"]
        secure = "TRUE" if c["secure"] else "FALSE"
        expiration = str(c["expirationDate"])
        name = c["name"]
        value = c["value"]
        
        line = f"{httponly_prefix}{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}"
        lines.append(line)
        
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(
        description="Convert cookies between Netscape format (cookies.txt) and JSON format.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", help="Path to input cookie file (detects format based on content)")
    parser.add_argument("-o", "--output", help="Path to output file (if omitted, writes to stdout)")
    parser.add_argument("--clean-expired", action="store_true", help="Remove cookies that have already expired")
    parser.add_argument("--no-color", action="store_true", help="Disable colored CLI stderr diagnostics")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stderr.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    if not os.path.exists(args.input):
        print_colored(f"Error: Input file not found: {args.input}", RED, use_color)
        return 1
        
    try:
        with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print_colored(f"Error reading input file: {e}", RED, use_color)
        return 1

    # Detect format
    is_json = False
    stripped_content = content.strip()
    if (stripped_content.startswith('[') and stripped_content.endswith(']')) or \
       (stripped_content.startswith('{') and stripped_content.endswith('}')):
        is_json = True
        
    print_colored(f"Detected input format: {'JSON' if is_json else 'Netscape/cookies.txt'}", BLUE, use_color)
    
    if is_json:
        cookies = parse_json(content, use_color)
    else:
        cookies = parse_netscape(content.splitlines(), use_color)
        
    if cookies is None or len(cookies) == 0:
        print_colored("No cookies successfully parsed.", RED, use_color)
        return 1

    total_parsed = len(cookies)
    
    # Optional clean-expired
    if args.clean_expired:
        current_time = int(time.time())
        # keep if expirationDate is 0 (session) or in the future
        cookies = [c for c in cookies if c["expirationDate"] == 0 or c["expirationDate"] > current_time]
        cleaned_count = total_parsed - len(cookies)
        if cleaned_count > 0:
            print_colored(f"Cleaned {cleaned_count} expired cookie(s).", YELLOW, use_color)

    # Format output opposite of input
    output_content = ""
    target_format = "Netscape" if is_json else "JSON"
    
    if is_json:
        output_content = to_netscape_string(cookies)
    else:
        output_content = json.dumps(cookies, indent=2)

    # Write output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content)
            print_colored(f"Successfully converted {len(cookies)} cookies and saved to '{args.output}' ({target_format} format).", GREEN, use_color)
        except Exception as e:
            print_colored(f"Error writing output file: {e}", RED, use_color)
            return 1
    else:
        print(output_content)
        print_colored(f"\n--- Converted {len(cookies)} cookies to stdout ---", GREEN, use_color)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
