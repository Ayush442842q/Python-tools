#!/usr/bin/env python3
"""
cURL Command Sanitizer & Formatter

Parses cURL commands from text or files, redacting sensitive authentication headers,
tokens, passwords, and URL parameters. Normalizes flags, formats multi-line syntax,
and outputs clean cURL commands safe for sharing and documentation.
"""

import os
import sys
import re
import json
import argparse
import shlex

# Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Sensitive Header patterns (case-insensitive key match)
SENSITIVE_HEADERS = {
    'authorization', 'auth', 'x-api-key', 'api-key', 'x-auth-token', 
    'cookie', 'set-cookie', 'x-csrf-token', 'x-secret', 'bearer'
}

# Sensitive URL query parameter patterns
SENSITIVE_PARAMS = {
    'key', 'api_key', 'token', 'access_token', 'secret', 'password', 'pwd', 'auth'
}


def sanitize_header(header_line, mask_token="[REDACTED]"):
    """Sanitizes header string of format 'Header-Name: Value'."""
    if ':' not in header_line:
        return header_line
    key, val = header_line.split(':', 1)
    key_strip = key.strip().lower()

    if key_strip in SENSITIVE_HEADERS:
        if key_strip == 'authorization':
            val_lower = val.strip().lower()
            if val_lower.startswith('bearer'):
                return f"{key.strip()}: Bearer {mask_token}"
            elif val_lower.startswith('basic'):
                return f"{key.strip()}: Basic {mask_token}"
        return f"{key.strip()}: {mask_token}"
    return header_line


def sanitize_url(url, mask_token="[REDACTED]"):
    """Masks sensitive query parameters in a URL."""
    if '?' not in url:
        return url
    base, query = url.split('?', 1)
    params = query.split('&')
    new_params = []

    for p in params:
        if '=' in p:
            k, v = p.split('=', 1)
            if k.lower() in SENSITIVE_PARAMS:
                new_params.append(f"{k}={mask_token}")
            else:
                new_params.append(p)
        else:
            new_params.append(p)

    return f"{base}?{'&'.join(new_params)}"


def parse_curl_command(curl_str):
    """
    Parses a curl command string into a dictionary containing method,
    url, headers, data, and extra args.
    """
    # Clean up multi-line backslashes
    clean_str = re.sub(r'\\\s*\n', ' ', curl_str).strip()
    
    try:
        tokens = shlex.split(clean_str)
    except Exception:
        # Fallback split if shlex fails on malformed input
        tokens = clean_str.split()

    if not tokens or tokens[0].lower() != 'curl':
        # Search for 'curl' token index if embedded in extra text
        try:
            curl_idx = next(i for i, t in enumerate(tokens) if t.lower() == 'curl')
            tokens = tokens[curl_idx:]
        except StopIteration:
            raise ValueError("Input string does not contain a valid 'curl' command.")

    parsed = {
        'method': 'GET',
        'url': '',
        'headers': [],
        'data': None,
        'extra_args': []
    }

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token in ('-X', '--request') and i + 1 < len(tokens):
            parsed['method'] = tokens[i + 1].upper()
            i += 2
        elif token in ('-H', '--header') and i + 1 < len(tokens):
            parsed['headers'].append(tokens[i + 1])
            i += 2
        elif token in ('-d', '--data', '--data-raw', '--data-binary') and i + 1 < len(tokens):
            parsed['data'] = tokens[i + 1]
            if parsed['method'] == 'GET':
                parsed['method'] = 'POST'
            i += 2
        elif token.startswith('http://') or token.startswith('https://'):
            parsed['url'] = token
            i += 1
        else:
            if not parsed['url'] and not token.startswith('-'):
                parsed['url'] = token
            else:
                parsed['extra_args'].append(token)
            i += 1

    return parsed


def format_curl_output(parsed, mode='multiline', shell='bash', mask_token="[REDACTED]"):
    """Formats parsed curl command dictionary into safe curl output."""
    sanitized_url = sanitize_url(parsed['url'], mask_token)
    sanitized_headers = [sanitize_header(h, mask_token) for h in parsed['headers']]
    
    cont_char = '`' if shell == 'powershell' else '\\'

    if mode == 'json':
        return json.dumps({
            'method': parsed['method'],
            'url': sanitized_url,
            'headers': {h.split(':', 1)[0].strip(): h.split(':', 1)[1].strip() for h in sanitized_headers if ':' in h},
            'data': parsed['data']
        }, indent=2)

    lines = []
    lines.append(f"curl -X {parsed['method']} \"{sanitized_url}\"")

    for h in sanitized_headers:
        lines.append(f"  -H \"{h}\"")

    if parsed['data']:
        # Sanitize sensitive data fields in JSON if applicable
        data_str = parsed['data']
        try:
            json_obj = json.loads(data_str)
            if isinstance(json_obj, dict):
                for k in json_obj:
                    if k.lower() in SENSITIVE_PARAMS or k.lower() in SENSITIVE_HEADERS:
                        json_obj[k] = mask_token
                data_str = json.dumps(json_obj)
        except Exception:
            pass
        lines.append(f"  --data '{data_str}'")

    for extra in parsed['extra_args']:
        lines.append(f"  {extra}")

    if mode == 'single-line':
        return " ".join([l.strip() for l in lines])
    else:
        return f" {cont_char}\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="cURL Command Sanitizer - Redact secrets and format cURL commands for documentation."
    )
    parser.add_argument("input", nargs="?", help="cURL command string or file path (reads stdin if omitted)")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    parser.add_argument("-m", "--mode", choices=['multiline', 'single-line', 'json'], default='multiline', help="Output format mode")
    parser.add_argument("-s", "--shell", choices=['bash', 'powershell'], default='bash', help="Target shell for multiline continuation")
    parser.add_argument("-t", "--token", default="[REDACTED]", help="Custom mask string for sensitive values")

    args = parser.parse_args()

    # Read input source
    curl_input = ""
    if args.input:
        if os.path.exists(args.input):
            with open(args.input, 'r', encoding='utf-8') as f:
                curl_input = f.read()
        else:
            curl_input = args.input
    else:
        if not sys.stdin.isatty():
            curl_input = sys.stdin.read()

    if not curl_input.strip():
        print(f"{RED}[ERROR]{RESET} No cURL command provided.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    try:
        parsed = parse_curl_command(curl_input)
        result = format_curl_output(parsed, mode=args.mode, shell=args.shell, mask_token=args.token)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result + "\n")
            print(f"{GREEN}[SUCCESS]{RESET} Sanitized cURL saved to '{args.output}'.")
        else:
            print(result)

    except Exception as e:
        print(f"{RED}[ERROR]{RESET} {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
