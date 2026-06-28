#!/usr/bin/env python3
"""
HTTP Cookie Analyzer - Parse and analyze HTTP cookies for security best practices.

Usage:
    python tools/http_cookie_analyzer.py -c "sessionid=xyz123; theme=dark"
    python tools/http_cookie_analyzer.py -f cookies.txt
"""

import sys
import os
import json
import time
import argparse
from urllib.parse import unquote

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Sensitive cookie keywords
SENSITIVE_KEYWORDS = {"session", "sid", "token", "jwt", "auth", "login", "sec", "key", "passwd", "password", "csrf"}

def parse_cookie_header(cookie_str):
    """Parse standard Cookie header string (name=value; name2=value2)"""
    cookies = []
    pairs = cookie_str.split(';')
    for pair in pairs:
        if '=' not in pair:
            continue
        name, val = pair.split('=', 1)
        cookies.append({
            "name": name.strip(),
            "value": val.strip(),
            "domain": "N/A",
            "path": "N/A",
            "secure": None, # Undefined in Cookie header
            "httpOnly": None,
            "sameSite": "N/A",
            "expires": "N/A"
        })
    return cookies

def parse_set_cookie_header(set_cookie_str):
    """Parse Set-Cookie header string"""
    parts = set_cookie_str.split(';')
    if not parts or '=' not in parts[0]:
        return None
    
    first_part = parts[0].strip()
    name, val = first_part.split('=', 1)
    
    cookie = {
        "name": name.strip(),
        "value": val.strip(),
        "domain": "Any",
        "path": "/",
        "secure": False,
        "httpOnly": False,
        "sameSite": "None",
        "expires": "Session"
    }
    
    for part in parts[1:]:
        part = part.strip()
        part_lower = part.lower()
        if not part:
            continue
        
        if part_lower == "httponly":
            cookie["httpOnly"] = True
        elif part_lower == "secure":
            cookie["secure"] = True
        elif part_lower.startswith("samesite="):
            cookie["sameSite"] = part.split('=', 1)[1].capitalize()
        elif part_lower.startswith("domain="):
            cookie["domain"] = part.split('=', 1)[1]
        elif part_lower.startswith("path="):
            cookie["path"] = part.split('=', 1)[1]
        elif part_lower.startswith("expires="):
            cookie["expires"] = part.split('=', 1)[1]
        elif part_lower.startswith("max-age="):
            try:
                seconds = int(part.split('=', 1)[1])
                cookie["expires"] = f"Max-Age: {seconds}s"
            except ValueError:
                pass
                
    return cookie

def parse_netscape_file(content):
    """Parse Netscape/curl cookie file format"""
    cookies = []
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 7:
            continue
            
        domain, _, path, secure_str, expires_ts, name, val = parts[:7]
        
        # Expiry timestamp conversion
        try:
            ts = int(expires_ts)
            if ts == 0:
                expires = "Session"
            else:
                expires = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(ts))
        except ValueError:
            expires = expires_ts
            
        cookies.append({
            "name": name,
            "value": val,
            "domain": domain,
            "path": path,
            "secure": secure_str.upper() == "TRUE",
            "httpOnly": domain.startswith("#HttpOnly_"), # Standard Netscape encoding
            "sameSite": "N/A",
            "expires": expires
        })
    return cookies

def parse_json_cookies(content):
    """Parse JSON cookies array exported from browsers"""
    try:
        data = json.loads(content)
    except Exception:
        return []
    
    if not isinstance(data, list):
        # Could be single cookie
        if isinstance(data, dict) and "name" in data:
            data = [data]
        else:
            return []
            
    cookies = []
    for c in data:
        if "name" not in c:
            continue
        
        # Try to resolve expiry
        expires = "Session"
        if c.get("session") is False or c.get("expirationDate"):
            exp_date = c.get("expirationDate")
            if exp_date:
                try:
                    expires = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(float(exp_date)))
                except ValueError:
                    expires = str(exp_date)
                    
        cookies.append({
            "name": c.get("name"),
            "value": c.get("value", ""),
            "domain": c.get("domain", "N/A"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": c.get("sameSite", "Lax"),
            "expires": expires
        })
    return cookies

def analyze_cookie(c):
    """Perform security checks on a single cookie"""
    issues = []
    name_lower = c["name"].lower()
    
    is_sensitive = any(keyword in name_lower for keyword in SENSITIVE_KEYWORDS)
    
    # 1. Check HttpOnly
    if c["httpOnly"] is False:
        if is_sensitive:
            issues.append(("ERROR", f"Sensitive cookie '{c['name']}' is missing HttpOnly flag, making it vulnerable to XSS token theft."))
        elif c["httpOnly"] is not None:
            issues.append(("WARNING", f"Cookie '{c['name']}' is missing HttpOnly flag."))
            
    # 2. Check Secure
    if c["secure"] is False:
        if is_sensitive:
            issues.append(("ERROR", f"Sensitive cookie '{c['name']}' is missing Secure flag; will be sent over unencrypted HTTP."))
        elif c["secure"] is not None:
            issues.append(("WARNING", f"Cookie '{c['name']}' is missing Secure flag."))

    # 3. SameSite flags
    if c["sameSite"] in ("None", "N/A", "None", ""):
        # SameSite=None must be Secure
        if c["sameSite"] == "None" and c["secure"] is False:
            issues.append(("ERROR", f"Cookie '{c['name']}' has SameSite=None but is not Secure (browsers will reject this)."))
        elif is_sensitive:
            issues.append(("WARNING", f"Sensitive cookie '{c['name']}' SameSite attribute is missing or None. Potential CSRF risk."))

    # 4. Check for URL encoding issues
    if '%' in c["value"]:
        decoded = unquote(c["value"])
        if decoded != c["value"]:
            # Informational
            pass

    return issues, is_sensitive

def print_cookie_table(cookies):
    """Draw a clean text table of cookies"""
    if not cookies:
        return
    
    headers = ["Name", "Value (Truncated)", "Domain", "Secure", "HttpOnly", "SameSite", "Expires"]
    col_widths = [len(h) for h in headers]
    
    # Format rows
    rows = []
    for c in cookies:
        val_str = c["value"]
        if len(val_str) > 20:
            val_str = val_str[:17] + "..."
            
        sec_str = "✓" if c["secure"] else ("✗" if c["secure"] is False else "N/A")
        ho_str = "✓" if c["httpOnly"] else ("✗" if c["httpOnly"] is False else "N/A")
        
        row = [
            c["name"],
            val_str,
            c["domain"],
            sec_str,
            ho_str,
            c["sameSite"] or "N/A",
            c["expires"]
        ]
        rows.append(row)
        for i in range(len(row)):
            col_widths[i] = max(col_widths[i], len(row[i]))
            
    # Draw header separator
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    print(sep)
    
    # Draw header titles
    header_line = "|" + "|".join(f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))) + "|"
    print(header_line)
    print(sep)
    
    # Draw rows
    for row in rows:
        row_line = "|" + "|".join(f" {row[i].ljust(col_widths[i])} " for i in range(len(row))) + "|"
        print(row_line)
    print(sep)

def main():
    parser = argparse.ArgumentParser(
        description="HTTP Cookie Analyzer - Security compliance and scorecard scanner for HTTP cookies."
    )
    parser.add_argument("-c", "--cookie", help="Cookie header string (e.g. 'sid=123; user=john').")
    parser.add_argument("-s", "--set-cookie", help="Set-Cookie header string.")
    parser.add_argument("-f", "--file", help="Path to cookie export file (Netscape text format or browser JSON).")
    args = parser.parse_args()

    # Enable Windows ANSI escape codes support
    if sys.platform == "win32":
        import os
        os.system("color")

    cookies = []
    
    if args.cookie:
        cookies = parse_cookie_header(args.cookie)
    elif args.set_cookie:
        parsed = parse_set_cookie_header(args.set_cookie)
        if parsed:
            cookies = [parsed]
    elif args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' not found.{RESET}", file=sys.stderr)
            return 1
            
        with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Try JSON parsing
        cookies = parse_json_cookies(content)
        # Try Netscape parsing
        if not cookies:
            cookies = parse_netscape_file(content)
            
        # Fallback to header format
        if not cookies:
            cookies = parse_cookie_header(content)
    else:
        # Check if stdin is empty
        if not sys.stdin.isatty():
            content = sys.stdin.read()
            cookies = parse_json_cookies(content)
            if not cookies:
                cookies = parse_netscape_file(content)
            if not cookies:
                cookies = parse_cookie_header(content)
        else:
            parser.print_help()
            return 0

    if not cookies:
        print(f"{RED}Error: No valid cookies detected. Ensure inputs conform to header strings or file formats.{RESET}", file=sys.stderr)
        return 1

    print(f"\n{BOLD}{BLUE}Detected Cookies List ({len(cookies)}):{RESET}")
    print_cookie_table(cookies)
    
    print(f"\n{BOLD}{BLUE}Security Analysis Reports:{RESET}")
    
    all_issues = []
    sensitive_count = 0
    error_count = 0
    warning_count = 0
    
    for c in cookies:
        issues, is_sensitive = analyze_cookie(c)
        if is_sensitive:
            sensitive_count += 1
            
        for severity, msg in issues:
            all_issues.append((severity, msg))
            if severity == "ERROR":
                error_count += 1
            else:
                warning_count += 1

    if not all_issues:
        print(f"  {GREEN}✓ Outstanding! All cookies adhere to security best practices.{RESET}")
    else:
        for severity, msg in all_issues:
            color = RED if severity == "ERROR" else YELLOW
            print(f"  {color}[{severity}]{RESET} {msg}")
            
    # Calculate simple security score
    score = 100
    score -= error_count * 20
    score -= warning_count * 5
    score = max(0, score)
    
    score_color = GREEN if score >= 80 else (YELLOW if score >= 50 else RED)
    
    print(f"\n{BOLD}{BLUE}Security Scorecard:{RESET}")
    print(f"  • Sensitive Cookies: {BOLD}{sensitive_count}{RESET}")
    print(f"  • Compliance Score:  {BOLD}{score_color}{score}/100{RESET}")
    print(f"  • Issues Detected:   {RED if error_count else GREEN}{error_count} Errors{RESET}, {YELLOW if warning_count else GREEN}{warning_count} Warnings{RESET}\n")

    return 1 if error_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
