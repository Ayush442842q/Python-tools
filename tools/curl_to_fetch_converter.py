#!/usr/bin/env python3
"""
cURL Command to JS fetch() & Python Code Converter
Parses cURL command lines and generates equivalent JavaScript fetch() API or Python requests code.

Features:
- Parses cURL flags: -X / --request, -H / --header, -d / --data / --data-raw, -u / --user, --url.
- Generates clean JavaScript fetch() code snippets (async/await or standard Promise).
- Generates Python `requests` or `httpx` code snippets.
- Supports CLI input, file input, or stdin.
"""

import sys
import os
import re
import shlex
import json
import argparse
from typing import Dict, Any, Tuple

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def parse_curl_command(curl_str: str) -> Dict[str, Any]:
    """Parses a cURL command string into structured components."""
    # Remove leading bash line continuations (\)
    curl_str = re.sub(r"\\\s*\n", " ", curl_str)
    
    try:
        tokens = shlex.split(curl_str)
    except Exception as e:
        print(f"Error parsing shell tokens: {e}", file=sys.stderr)
        tokens = curl_str.split()

    url = ""
    method = "GET"
    headers: Dict[str, str] = {}
    data: str = ""
    auth: Tuple[str, str] = ("", "")

    idx = 0
    if tokens and tokens[0].lower() in ("curl", "curl.exe"):
        idx = 1

    while idx < len(tokens):
        token = tokens[idx]

        if token in ("-X", "--request") and idx + 1 < len(tokens):
            method = tokens[idx + 1].upper()
            idx += 2
        elif token in ("-H", "--header") and idx + 1 < len(tokens):
            header_str = tokens[idx + 1]
            if ":" in header_str:
                k, v = header_str.split(":", 1)
                headers[k.strip()] = v.strip()
            idx += 2
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode") and idx + 1 < len(tokens):
            data = tokens[idx + 1]
            if method == "GET":
                method = "POST"
            idx += 2
        elif token in ("-u", "--user") and idx + 1 < len(tokens):
            user_pass = tokens[idx + 1]
            if ":" in user_pass:
                u, p = user_pass.split(":", 1)
                auth = (u, p)
            else:
                auth = (user_pass, "")
            idx += 2
        elif token == "--url" and idx + 1 < len(tokens):
            url = tokens[idx + 1]
            idx += 2
        elif token.startswith("http://") or token.startswith("https://"):
            url = token
            idx += 1
        else:
            idx += 1

    if auth[0]:
        import base64
        b64_auth = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {b64_auth}"

    return {
        "url": url,
        "method": method,
        "headers": headers,
        "data": data,
    }


def generate_js_fetch(parsed: Dict[str, Any], async_await: bool = True) -> str:
    """Generates JavaScript fetch() code."""
    url = parsed["url"] or "https://api.example.com/endpoint"
    method = parsed["method"]
    headers = parsed["headers"]
    data = parsed["data"]

    options: Dict[str, Any] = {"method": method}
    if headers:
        options["headers"] = headers
    if data:
        options["body"] = data

    options_json = json.dumps(options, indent=2)

    if async_await:
        return f"""async function makeRequest() {{
  const response = await fetch("{url}", {options_json});
  const data = await response.json();
  console.log(data);
  return data;
}}

makeRequest();"""
    else:
        return f"""fetch("{url}", {options_json})
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));"""


def generate_python_requests(parsed: Dict[str, Any]) -> str:
    """Generates Python requests code."""
    url = parsed["url"] or "https://api.example.com/endpoint"
    method = parsed["method"].lower()
    headers = parsed["headers"]
    data = parsed["data"]

    lines = ["import requests", ""]
    if headers:
        lines.append(f"headers = {json.dumps(headers, indent=2)}")
    
    if data:
        # Check if JSON
        try:
            json_obj = json.loads(data)
            lines.append(f"payload = {json.dumps(json_obj, indent=2)}")
            data_arg = "json=payload"
        except Exception:
            lines.append(f"payload = {json.dumps(data)}")
            data_arg = "data=payload"
    else:
        data_arg = ""

    args = [f'"{url}"']
    if headers:
        args.append("headers=headers")
    if data_arg:
        args.append(data_arg)

    args_str = ", ".join(args)
    lines.append(f"response = requests.{method}({args_str})")
    lines.append("print(response.status_code)")
    lines.append("print(response.text)")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert cURL command lines to JS fetch() or Python code.")
    parser.add_argument("curl_cmd", nargs="?", type=str, help="cURL command string or file path containing cURL command.")
    parser.add_argument("-t", "--target", choices=["js", "js-promise", "python"], default="js", help="Target output language (default: js).")
    parser.add_argument("-o", "--output", type=str, help="Output file path.")

    args = parser.parse_args()

    content = ""
    if args.curl_cmd:
        if os.path.exists(args.curl_cmd):
            with open(args.curl_cmd, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = args.curl_cmd
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        content = sys.stdin.read()

    parsed = parse_curl_command(content)

    if args.target == "js":
        code = generate_js_fetch(parsed, async_await=True)
    elif args.target == "js-promise":
        code = generate_js_fetch(parsed, async_await=False)
    elif args.target == "python":
        code = generate_python_requests(parsed)
    else:
        code = ""

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        print(f"Successfully exported {args.target} code to {args.output}")
    else:
        print(code)


if __name__ == "__main__":
    main()
