#!/usr/bin/env python3
"""
api_code_generator - HTTP Request Snippet Generator

Given a URL, HTTP method, headers, and request body, this utility generates
equivalent, copy-pasteable code snippets for curl, Python (requests),
JavaScript (fetch), and Go (net/http).

Usage:
    python tools/api_code_generator.py https://api.github.com/repos/psf/requests \
        -X GET \
        -H "Accept: application/vnd.github.v3+json" \
        -H "User-Agent: my-app"

    python tools/api_code_generator.py https://httpbin.org/post \
        -X POST \
        --json-body '{"key": "value", "num": 42}'
"""

import argparse
import json
import sys
from urllib.parse import urlparse, parse_qsl


def generate_curl(url, method, headers, body):
    """Generates curl command snippet."""
    parts = ["curl"]
    if method != "GET":
        parts.append(f"-X {method}")
    
    for h, v in headers.items():
        parts.append(f'-H "{h}: {v}"')
        
    if body:
        # Escape double quotes for shell compatibility
        escaped_body = body.replace('"', '\\"')
        parts.append(f'-d "{escaped_body}"')
        
    parts.append(f'"{url}"')
    return " \\\n  ".join(parts)


def generate_python_requests(url, method, headers, body):
    """Generates Python requests snippet."""
    lines = ["import requests", ""]
    
    # URL parsing
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    query_params = dict(parse_qsl(parsed.query))

    lines.append(f'url = "{base_url}"')
    
    # Headers
    if headers:
        headers_str = json.dumps(headers, indent=4)
        # Indent it correctly
        headers_str = headers_str.replace("\n", "\n    ")
        lines.append(f"headers = {headers_str}")
    else:
        lines.append("headers = {}")

    # Query params
    if query_params:
        params_str = json.dumps(query_params, indent=4)
        params_str = params_str.replace("\n", "\n    ")
        lines.append(f"params = {params_str}")
    else:
        lines.append("params = {}")

    # Body
    if body:
        try:
            # Check if JSON
            json_obj = json.loads(body)
            body_str = json.dumps(json_obj, indent=4)
            body_str = body_str.replace("\n", "\n    ")
            lines.append(f"json_data = {body_str}")
            payload_arg = "json=json_data"
        except json.JSONDecodeError:
            # Treat as raw data
            lines.append(f'data = """{body}"""')
            payload_arg = "data=data"
    else:
        payload_arg = None

    # Request execution
    args = ["url", "headers=headers", "params=params"]
    if payload_arg:
        args.append(payload_arg)
        
    lines.append(f"response = requests.{method.lower()}({', '.join(args)})")
    lines.append("")
    lines.append("print(response.status_code)")
    lines.append("print(response.text)")
    
    return "\n".join(lines)


def generate_js_fetch(url, method, headers, body):
    """Generates JS fetch snippet."""
    lines = []
    options = {
        "method": method
    }
    
    if headers:
        options["headers"] = headers

    if body:
        try:
            # Validate JSON
            json.loads(body)
            options["body"] = "JSON.stringify(payload)"
            lines.append(f"const payload = {body};")
            lines.append("")
        except json.JSONDecodeError:
            # Treat as raw string
            options["body"] = "bodyData"
            lines.append(f"const bodyData = `{body}`;")
            lines.append("")

    options_json = json.dumps(options, indent=4)
    # Unquote the function/variable calls in options_json if they were strings
    options_json = options_json.replace('"JSON.stringify(payload)"', 'JSON.stringify(payload)')
    options_json = options_json.replace('"bodyData"', 'bodyData')
    
    lines.append(f"fetch('{url}', {options_json})")
    lines.append("  .then(response => {")
    lines.append("    console.log(`Status: ${response.status}`);")
    lines.append("    return response.text();")
    lines.append("  })")
    lines.append("  .then(data => console.log(data))")
    lines.append("  .catch(err => console.error(err));")

    return "\n".join(lines)


def generate_go_http(url, method, headers, body):
    """Generates Go net/http snippet."""
    lines = [
        "package main",
        "",
        "import (",
        '\t"fmt"',
        '\t"io"',
        '\t"net/http"',
    ]
    if body:
        lines.append('\t"strings"')
    lines.append(")")
    lines.append("")
    lines.append("func main() {")
    
    if body:
        # Escape double quotes and backslashes for Go multiline raw string
        escaped_body = body.replace('`', '` + "`" + `')
        lines.append(f'\tpayload := strings.NewReader(`{escaped_body}`)\n')
        lines.append(f'\treq, err := http.NewRequest("{method}", "{url}", payload)')
    else:
        lines.append(f'\treq, err := http.NewRequest("{method}", "{url}", nil)')
        
    lines.append("\tif err != nil {")
    lines.append("\t\tpanic(err)")
    lines.append("\t}")
    lines.append("")
    
    for h, v in headers.items():
        lines.append(f'\treq.Header.Add("{h}", "{v}")')
    
    if headers:
        lines.append("")

    lines.append("\tclient := &http.Client{}")
    lines.append("\tres, err := client.Do(req)")
    lines.append("\tif err != nil {")
    lines.append("\t\tpanic(err)")
    lines.append("\t}")
    lines.append("\tdefer res.Body.Close()")
    lines.append("")
    lines.append("\tbody, err := io.ReadAll(res.Body)")
    lines.append("\tif err != nil {")
    lines.append("\t\tpanic(err)")
    lines.append("\t}")
    lines.append("")
    lines.append('\tfmt.Println("Response Status:", res.Status)')
    lines.append('\tfmt.Println(string(body))')
    lines.append("}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="HTTP Request Snippet Generator"
    )
    parser.add_argument("url", help="Target request URL")
    parser.add_argument("-X", "--method", default="GET", help="HTTP Method (GET, POST, etc.)")
    parser.add_argument("-H", "--header", action="append", help="HTTP headers (e.g. 'Content-Type: application/json')")
    parser.add_argument("-d", "--data", help="Raw data payload body")
    parser.add_argument("--json-body", help="JSON data payload body (auto-adds 'Content-Type: application/json')")
    parser.add_argument("-o", "--output", help="Write generated output to a file instead of stdout")

    args = parser.parse_args()

    # Parse headers
    headers = {}
    if args.header:
        for item in args.header:
            if ":" in item:
                k, v = item.split(":", 1)
                headers[k.strip()] = v.strip()
            else:
                print(f"Warning: Invalid header format '{item}'. Header should be Key: Value", file=sys.stderr)

    body = None
    if args.json_body:
        body = args.json_body
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
    elif args.data:
        body = args.data

    method = args.method.upper()

    # Generate snippets
    curl_snippet = generate_curl(args.url, method, headers, body)
    python_snippet = generate_python_requests(args.url, method, headers, body)
    js_snippet = generate_js_fetch(args.url, method, headers, body)
    go_snippet = generate_go_http(args.url, method, headers, body)

    output_content = f"""# HTTP Request Code Snippets
Target URL: {args.url}
HTTP Method: {method}

## 1. curl Command
```bash
{curl_snippet}
```

## 2. Python (requests)
```python
{python_snippet}
```

## 3. JavaScript (fetch API)
```javascript
{js_snippet}
```

## 4. Go (net/http)
```go
{go_snippet}
```
"""

    if args.output:
        try:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(output_content)
            print(f"Code snippets successfully written to {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
