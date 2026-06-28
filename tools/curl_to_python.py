#!/usr/bin/env python3
"""
cURL to Python Converter

Parses a raw cURL command (e.g., copied from browser DevTools) and converts
it into a clean, runnable Python script using standard 'urllib' or 'requests'.

Usage:
    # Convert a curl command via stdin
    echo 'curl -X POST "https://httpbin.org/post" -H "accept: application/json"' | python tools/curl_to_python.py
    
    # Convert a curl command from a text file
    python tools/curl_to_python.py -f curl_command.txt --lib requests
"""

import sys
import re
import shlex
import argparse
from typing import Dict, List, Tuple, Optional

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_colored(text: str, color: str):
    """Print text to stderr with ANSI color."""
    sys.stderr.write(f"{color}{text}{RESET}\n")

def parse_curl(curl_str: str) -> Tuple[str, str, Dict[str, str], Optional[str], Optional[Tuple[str, str]], List[str]]:
    """
    Parses a curl command line string.
    Returns: (url, method, headers, data, auth, cookies)
    """
    # Clean up multi-line curls
    curl_str = curl_str.replace("\\\n", " ").replace("\\\r\n", " ")
    
    # Tokenize shell style
    try:
        tokens = shlex.split(curl_str)
    except ValueError as e:
        # Fallback to simple split if shell parsing fails due to unmatched quotes
        print_colored(f"[!] Warning: Shell tokenization failed ({e}). Falling back to whitespace split.", YELLOW)
        tokens = curl_str.split()

    if not tokens:
        raise ValueError("Empty command")

    if tokens[0].lower() != "curl":
        # Find index of curl in case there are environment variables or prefix
        curl_idx = -1
        for i, tok in enumerate(tokens):
            if tok.lower() == "curl":
                curl_idx = i
                break
        if curl_idx != -1:
            tokens = tokens[curl_idx:]
        else:
            raise ValueError("Command does not appear to start with 'curl'")

    url = ""
    method = "GET"
    headers = {}
    data = None
    auth = None
    cookies = []

    # Simple state machine to parse options
    i = 1
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        
        # Method / Request Type
        if tok in ("-X", "--request") and i + 1 < n:
            method = tokens[i+1].upper()
            i += 2
        
        # Headers
        elif tok in ("-H", "--header") and i + 1 < n:
            header_val = tokens[i+1]
            if ":" in header_val:
                key, val = header_val.split(":", 1)
                headers[key.strip()] = val.strip()
            i += 2
            
        # Data / Body
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode") and i + 1 < n:
            data = tokens[i+1]
            # cURL defaults to POST when data is sent, unless method is explicitly set
            if method == "GET":
                method = "POST"
            i += 2
            
        # User / Auth
        elif tok in ("-u", "--user") and i + 1 < n:
            user_auth = tokens[i+1]
            if ":" in user_auth:
                u, p = user_auth.split(":", 1)
                auth = (u, p)
            else:
                auth = (user_auth, "")
            i += 2
            
        # Cookies
        elif tok in ("-b", "--cookie") and i + 1 < n:
            cookie_val = tokens[i+1]
            # Cookies can be key=val; pairs or files
            if "=" in cookie_val:
                cookies.append(cookie_val)
            i += 2
            
        # URL (any positional argument not starting with -)
        elif not tok.startswith("-"):
            # Check if this token looks like a URL
            if not url:
                url = tok
            i += 1
        else:
            # Skip unknown switches/options (many switches don't take values)
            # If the next token doesn't look like a switch, check if we need to skip it
            if tok in ("--compressed", "-k", "--insecure", "-L", "--location", "-s", "--silent"):
                i += 1
            elif i + 1 < n and not tokens[i+1].startswith("-"):
                # If it's a switch that usually takes a parameter, skip parameter too
                i += 2
            else:
                i += 1

    # Check headers for cookies
    if "Cookie" in headers:
        cookies.append(headers["Cookie"])
        del headers["Cookie"]

    return url, method, headers, data, auth, cookies

def generate_urllib_code(url: str, method: str, headers: Dict[str, str], data: Optional[str], auth: Optional[Tuple[str, str]], cookies: List[str]) -> str:
    """Generate Python code using standard urllib."""
    lines = [
        "import urllib.request",
        "import urllib.parse",
        "import json",
        ""
    ]
    
    # URL definition
    lines.append(f"url = {repr(url)}")
    
    # Headers
    clean_headers = dict(headers)
    if cookies:
        clean_headers["Cookie"] = "; ".join(cookies)
        
    lines.append("headers = {")
    for k, v in clean_headers.items():
        lines.append(f"    {repr(k)}: {repr(v)},")
    lines.append("}")
    lines.append("")
    
    # Data handling
    if data is not None:
        lines.append(f"payload = {repr(data)}")
        # Check if JSON
        if data.strip().startswith("{") or data.strip().startswith("["):
            lines.append("data = payload.encode('utf-8')")
            if "Content-Type" not in clean_headers:
                lines.append("headers['Content-Type'] = 'application/json'")
        else:
            lines.append("data = urllib.parse.urlencode(json.loads(payload)).encode('utf-8') # or payload.encode('utf-8')")
    else:
        lines.append("data = None")
    lines.append("")
    
    # Authentication (urllib uses a password manager)
    if auth:
        username, password = auth
        lines.extend([
            "password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()",
            f"password_manager.add_password(None, url, {repr(username)}, {repr(password)})",
            "auth_handler = urllib.request.HTTPBasicAuthHandler(password_manager)",
            "opener = urllib.request.build_opener(auth_handler)",
            "urllib.request.install_opener(opener)",
            ""
        ])

    # Request builder
    lines.extend([
        "req = urllib.request.Request(url, data=data, headers=headers, method=" + repr(method) + ")",
        "",
        "try:",
        "    with urllib.request.urlopen(req) as response:",
        "        print(f'Status Code: {response.status}')",
        "        response_body = response.read().decode('utf-8')",
        "        try:",
        "            # Try formatting as JSON",
        "            parsed_json = json.loads(response_body)",
        "            print(json.dumps(parsed_json, indent=4))",
        "        except json.JSONDecodeError:",
        "            print(response_body)",
        "except urllib.error.HTTPError as e:",
        "    print(f'HTTP Error {e.code}: {e.reason}')",
        "    print(e.read().decode('utf-8'))",
        "except Exception as e:",
        "    print(f'Error: {e}')"
    ])
    
    return "\n".join(lines)

def generate_requests_code(url: str, method: str, headers: Dict[str, str], data: Optional[str], auth: Optional[Tuple[str, str]], cookies: List[str]) -> str:
    """Generate Python code using requests library."""
    lines = [
        "import requests",
        "import json",
        ""
    ]
    
    lines.append(f"url = {repr(url)}")
    
    # Headers
    lines.append("headers = {")
    for k, v in headers.items():
        lines.append(f"    {repr(k)}: {repr(v)},")
    lines.append("}")
    lines.append("")
    
    # Cookies
    if cookies:
        cookie_dict = {}
        for cookie_str in cookies:
            for part in cookie_str.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookie_dict[k.strip()] = v.strip()
        lines.append(f"cookies = {repr(cookie_dict)}")
    else:
        lines.append("cookies = None")
        
    # Auth
    if auth:
        lines.append(f"auth = {repr(auth)}")
    else:
        lines.append("auth = None")
    lines.append("")
    
    # Request call
    method_lower = method.lower()
    req_args = ["url", "headers=headers", "cookies=cookies", "auth=auth"]
    
    if data is not None:
        if data.strip().startswith("{") or data.strip().startswith("["):
            lines.append(f"json_data = json.loads({repr(data)})")
            req_args.append("json=json_data")
        else:
            req_args.append(f"data={repr(data)}")
            
    lines.extend([
        f"response = requests.{method_lower}(" + ", ".join(req_args) + ")",
        "",
        "print(f'Status Code: {response.status_code}')",
        "try:",
        "    print(json.dumps(response.json(), indent=4))",
        "except json.JSONDecodeError:",
        "    print(response.text)"
    ])
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Convert cURL commands to Python script code.")
    parser.add_argument("-f", "--file", help="Path to file containing raw cURL command")
    parser.add_argument("-l", "--lib", choices=["urllib", "requests"], default="urllib", help="Target python library (default: urllib)")
    parser.add_argument("-o", "--output", help="Write output to a specified Python file instead of printing")
    
    args = parser.parse_args()
    
    curl_command = ""
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                curl_command = f.read()
        except Exception as e:
            print_colored(f"[-] Error reading file: {e}", RED)
            sys.exit(1)
    else:
        # Read from stdin if no file is provided
        if not sys.stdin.isatty():
            curl_command = sys.stdin.read()
        else:
            print_colored("[*] Paste your cURL command below and press Ctrl+D (Ctrl+Z on Windows) followed by Enter:", BLUE)
            try:
                curl_command = sys.stdin.read()
            except KeyboardInterrupt:
                print_colored("\n[!] Exiting...", YELLOW)
                sys.exit(0)
                
    curl_command = curl_command.strip()
    if not curl_command:
        print_colored("[-] Error: No cURL command provided.", RED)
        sys.exit(1)
        
    try:
        url, method, headers, data, auth, cookies = parse_curl(curl_command)
        
        if not url:
            print_colored("[-] Error: Could not extract target URL from cURL command.", RED)
            sys.exit(1)
            
        if args.lib == "urllib":
            py_code = generate_urllib_code(url, method, headers, data, auth, cookies)
        else:
            py_code = generate_requests_code(url, method, headers, data, auth, cookies)
            
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(py_code)
            print_colored(f"[+] Successfully converted cURL and saved to: {args.output}", GREEN)
        else:
            print(py_code)
            
    except Exception as e:
        print_colored(f"[-] Error converting cURL command: {e}", RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
