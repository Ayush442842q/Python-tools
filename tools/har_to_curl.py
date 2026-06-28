#!/usr/bin/env python3
"""
HAR to cURL Generator

Extracts requests from a browser HTTP Archive (.har) file and outputs them
as formatted, executable shell cURL commands. Useful for reproducing/debugging
web API requests locally in the terminal.

Usage:
    python tools/har_to_curl.py archive.har
    python tools/har_to_curl.py archive.har --filter "/api/v1/" --limit 5
"""

import os
import sys
import json
import argparse
import shlex
from typing import List, Dict, Any

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_colored(text: str, color: str):
    """Print text with ANSI color."""
    sys.stderr.write(f"{color}{text}{RESET}\n")

def escape_shell_arg(arg: str) -> str:
    """Escapes strings for command line execution."""
    return shlex.quote(arg)

def entry_to_curl(entry: Dict[str, Any]) -> str:
    """Converts a single HAR log entry to a cURL command."""
    request = entry.get("request", {})
    if not request:
        return ""

    method = request.get("method", "GET")
    url = request.get("url", "")
    
    parts = ["curl"]
    
    # Method
    if method != "GET":
        parts.append(f"-X {method}")
        
    # Headers
    headers = request.get("headers", [])
    for h in headers:
        name = h.get("name", "")
        value = h.get("value", "")
        
        # Skip browser pseudo-headers or auto-generated connection properties if needed,
        # but generally keep all request headers to preserve authenticity.
        if name.startswith(":"):
            continue
        parts.append(f'-H "{name}: {value}"')

    # Cookies
    cookies = request.get("cookies", [])
    if cookies:
        cookie_strs = []
        for c in cookies:
            cookie_strs.append(f"{c.get('name')}={c.get('value')}")
        parts.append(f'-b "{"; ".join(cookie_strs)}"')

    # Query parameters
    # The URL in HAR usually contains query parameters already.
    # We will verify and check if we need to format/output them.
    
    # Post Data
    post_data = request.get("postData", {})
    if post_data:
        text = post_data.get("text", "")
        if text:
            # Escape the body data
            parts.append(f"--data-raw {escape_shell_arg(text)}")

    # Add Target URL
    parts.append(escape_shell_arg(url))
    
    return " ".join(parts)

def parse_har(har_path: str, filter_str: str = "", limit: int = 0) -> List[str]:
    """Parses the HAR file and extracts requests matching criteria."""
    try:
        with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except Exception as e:
        print_colored(f"[-] Failed to parse HAR file: {e}", RED)
        sys.exit(1)

    log = data.get("log", {})
    entries = log.get("entries", [])
    
    curl_commands = []
    count = 0
    
    for entry in entries:
        request = entry.get("request", {})
        url = request.get("url", "")
        
        if filter_str and filter_str not in url:
            continue
            
        curl_cmd = entry_to_curl(entry)
        if curl_cmd:
            curl_commands.append(curl_cmd)
            count += 1
            if limit > 0 and count >= limit:
                break
                
    return curl_commands

def main():
    parser = argparse.ArgumentParser(description="Convert HTTP Archive (.har) logs to runnable cURL commands.")
    parser.add_argument("har_file", help="Path to the HAR log file")
    parser.add_argument("-f", "--filter", default="", help="Sub-string filter matching URLs to export")
    parser.add_argument("-l", "--limit", type=int, default=0, help="Maximum number of cURL commands to extract")
    parser.add_argument("-o", "--output", help="Save the cURL commands to a script file (.sh or .bat)")
    
    args = parser.parse_args()

    if not os.path.exists(args.har_file):
        print_colored(f"[-] File not found: {args.har_file}", RED)
        sys.exit(1)

    print_colored(f"[*] Reading HAR archive: {args.har_file}...", BLUE)
    commands = parse_har(args.har_file, args.filter, args.limit)
    
    if not commands:
        print_colored("[!] No matching requests found in HAR archive.", YELLOW)
        return

    print_colored(f"[+] Extracted {len(commands)} requests.", GREEN)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n\n")
                for cmd in commands:
                    f.write(f"{cmd}\n\n")
            print_colored(f"[+] Successfully exported script: {args.output}", GREEN)
        except Exception as e:
            print_colored(f"[-] Failed to write script file: {e}", RED)
            sys.exit(1)
    else:
        for idx, cmd in enumerate(commands, 1):
            print_colored(f"\n# Request #{idx}", CYAN)
            print(cmd)

if __name__ == "__main__":
    main()
