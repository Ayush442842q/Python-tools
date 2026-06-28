#!/usr/bin/env python3
"""
API Security Fuzzer
A command-line utility to perform security fuzzing on HTTP/REST API endpoints,
identifying potential SQL injection, XSS, path traversal, and unhandled exception vulnerabilities.
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

# Default security fuzzing payloads
DEFAULT_PAYLOADS = [
    # SQL Injection
    "' OR '1'='1",
    "' UNION SELECT NULL, NULL--",
    "admin'--",
    "1' OR 1=1 --",
    "1; DROP TABLE users--",
    # Cross-Site Scripting (XSS)
    "<script>alert(1)</script>",
    "\"><script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    # Path Traversal
    "../../../../etc/passwd",
    "..\\..\\..\\..\\windows\\win.ini",
    "/etc/passwd\0",
    "....//....//etc/passwd",
    # Command Injection
    "; cat /etc/passwd",
    "| dir",
    "`id`",
    "$(whoami)",
    # Format Strings & Boundary Values
    "%s%s%s%s%s",
    "0",
    "-1",
    "999999999999999999999999999999999",
    "NaN",
    "null",
    "undefined",
    "[]",
    "{}",
]

# Signatures for database error leakage or system exceptions
ERROR_SIGNATURES = [
    r"SQL syntax",
    r"mysql_fetch",
    r"sqlite3\.OperationalError",
    r"PostgreSQL query failed",
    r"Microsoft OLE DB Provider",
    r"syntax error at or near",
    r"Uncaught Exception",
    r"Traceback \(most recent call\)",
    r"ZeroDivisionError",
    r"NullPointerException",
    r"FileNotFoundException",
    r"Permission denied",
    r"Fatal error",
]

def print_color(text, color):
    """Print text with ANSI color if supported."""
    print(f"{color}{text}{COLOR_RESET}")

def make_request(url, method, headers, data, timeout=5):
    """Send an HTTP request and return (status, body, duration, err_msg)."""
    req_headers = {
        "User-Agent": "APIFuzzer/1.0",
        "Accept": "*/*"
    }
    if headers:
        for k, v in headers.items():
            req_headers[k] = v

    # Disable SSL certificate verification for local/testing convenience
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req_data = None
    if data:
        if isinstance(data, (dict, list)):
            req_data = json.dumps(data).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
        else:
            req_data = data.encode("utf-8")

    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            duration = time.time() - start_time
            body = response.read().decode("utf-8", errors="ignore")
            return response.status, body, duration, None
    except urllib.error.HTTPError as e:
        duration = time.time() - start_time
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return e.code, body, duration, str(e)
    except Exception as e:
        duration = time.time() - start_time
        return 0, "", duration, str(e)

def fuzz_parameter(url, method, headers, data, param_type, target_key, payload):
    """Fuzzes a specific parameter target with a payload."""
    fuzzed_url = url
    fuzzed_headers = dict(headers) if headers else {}
    fuzzed_data = None

    if param_type == "url":
        # Replace parameter value in URL query string
        # e.g. target_key="id", replace id=value with id=payload
        pattern = re.compile(rf"([?&]){re.escape(target_key)}=([^&]*)")
        if pattern.search(url):
            fuzzed_url = pattern.sub(rf"\1{target_key}={urllib.parse.quote(payload)}", url)
        else:
            connector = "&" if "?" in url else "?"
            fuzzed_url = f"{url}{connector}{target_key}={urllib.parse.quote(payload)}"
    elif param_type == "header":
        fuzzed_headers[target_key] = payload
    elif param_type == "json":
        # Data is assumed to be dict
        if isinstance(data, dict):
            # Nested parameter resolution simplified
            fuzzed_data = dict(data)
            fuzzed_data[target_key] = payload
        else:
            fuzzed_data = payload
    elif param_type == "form":
        # Data assumed to be urlencoded query format
        params = urllib.parse.parse_qs(data or "")
        params[target_key] = [payload]
        fuzzed_data = urllib.parse.urlencode(params, doseq=True)

    status, body, duration, err = make_request(fuzzed_url, method, fuzzed_headers, fuzzed_data)
    return payload, status, len(body), duration, body, err

def analyze_response(status, body, duration, err, baseline_len, baseline_time):
    """Determine if the fuzzed response is anomalous or indicates vulnerability."""
    anomalies = []
    severity = "INFO"

    # Status anomaly
    if status == 500:
        anomalies.append("HTTP 500 Internal Server Error (Unhandled Exception)")
        severity = "HIGH"
    elif status == 0:
        anomalies.append(f"Connection Failed / Timeout ({err})")
        severity = "MEDIUM"

    # Error signature leakage
    for sig in ERROR_SIGNATURES:
        if re.search(sig, body, re.IGNORECASE):
            anomalies.append(f"Sensitive Error Signature Leakage: '{sig}'")
            severity = "HIGH"

    # Length anomaly (deviation of more than 50% from baseline)
    if baseline_len > 0 and abs(len(body) - baseline_len) / baseline_len > 0.8:
        anomalies.append(f"Response size deviation ({len(body)} bytes vs baseline {baseline_len} bytes)")
        if severity == "INFO":
            severity = "LOW"

    # Time anomaly (response time more than 3x baseline and > 2s)
    if baseline_time > 0 and duration > 3 * baseline_time and duration > 2.0:
        anomalies.append(f"Response delay anomaly ({duration:.2f}s vs baseline {baseline_time:.2f}s) - Possible Time-Based Injection/DoS")
        if severity != "HIGH":
            severity = "MEDIUM"

    return severity, anomalies

def main():
    parser = argparse.ArgumentParser(
        description="API Security Fuzzer - Fuzz endpoints for security vulnerabilities.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="Target API URL (e.g. http://localhost:8000/api/users)")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST", "PUT", "DELETE"], help="HTTP Method (default: GET)")
    parser.add_argument("-H", "--header", action="append", help="HTTP Headers (Format: 'Name: Value')")
    parser.add_argument("-d", "--data", help="HTTP Request Body Data (JSON or urlencoded form format)")
    parser.add_argument("-p", "--parameter", required=True, help="Parameter key to fuzz (e.g. 'id', 'search')")
    parser.add_argument("-t", "--type", default="url", choices=["url", "header", "json", "form"], help="Where to find parameter (default: url)")
    parser.add_argument("-w", "--wordlist", help="Path to custom wordlist of payloads")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Number of concurrent fuzzing threads (default: 5)")
    parser.add_argument("-o", "--output", help="Save results summary to a JSON file")
    
    args = parser.parse_args()

    # Parse headers
    headers = {}
    if args.header:
        for h in args.header:
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()

    # Parse body data
    data_payload = args.data
    if args.type == "json" and args.data:
        try:
            data_payload = json.loads(args.data)
        except json.JSONDecodeError:
            print_color("Error: Provided request body is not valid JSON, but parameter type is set to json.", COLOR_RED)
            return 1

    # Load payloads
    payloads = DEFAULT_PAYLOADS
    if args.wordlist:
        try:
            with open(args.wordlist, "r", encoding="utf-8") as f:
                payloads = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"[*] Loaded {len(payloads)} payloads from custom wordlist: {args.wordlist}")
        except Exception as e:
            print_color(f"[-] Failed to load wordlist: {e}. Using default payloads instead.", COLOR_YELLOW)

    print_color(f"[*] Starting API Fuzzer on {args.url} [{args.method}]", COLOR_BOLD + COLOR_BLUE)
    print(f"[*] Target parameter: '{args.parameter}' in {args.type}")
    print(f"[*] Sending baseline request to establish reference response...")
    
    # Establish baseline
    base_status, base_body, base_time, base_err = make_request(args.url, args.method, headers, data_payload)
    if base_status == 0:
        print_color(f"[-] Failed baseline request: {base_err}. Cannot proceed safely.", COLOR_RED)
        return 1
    
    print(f"[+] Baseline: Status={base_status}, Length={len(base_body)} bytes, Response Time={base_time:.3f}s")
    print_color(f"[*] Fuzzing with {len(payloads)} payloads using {args.concurrency} threads...\n", COLOR_CYAN)

    results = []
    anomalies_found = []

    # Run ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(
                fuzz_parameter, args.url, args.method, headers, data_payload, args.type, args.parameter, payload
            ): payload for payload in payloads
        }
        
        # Table Header
        print(f"{COLOR_BOLD}{'PAYLOAD':<35} | {'STATUS':<6} | {'SIZE':<8} | {'TIME':<6} | {'SEVERITY':<8} | {'ANOMALIES/WARNINGS'}{COLOR_RESET}")
        print("-" * 110)

        for future in as_completed(futures):
            payload, status, length, duration, body, err = future.result()
            severity, anomalies = analyze_response(status, body, duration, err, len(base_body), base_time)
            
            # Format payload for printing
            display_payload = repr(payload)[1:-1]
            if len(display_payload) > 33:
                display_payload = display_payload[:30] + "..."
                
            color = COLOR_RESET
            if severity == "HIGH":
                color = COLOR_RED
            elif severity == "MEDIUM":
                color = COLOR_YELLOW
            elif severity == "LOW":
                color = COLOR_BLUE
            elif severity == "INFO" and status != base_status:
                color = COLOR_CYAN
                
            anomaly_desc = ", ".join(anomalies) if anomalies else "None"
            
            print(f"{color}{display_payload:<35} | {status:<6} | {length:<8} | {duration:>5.2f}s | {severity:<8} | {anomaly_desc}{COLOR_RESET}")
            
            result_item = {
                "payload": payload,
                "status": status,
                "length": length,
                "duration": duration,
                "severity": severity,
                "anomalies": anomalies,
                "error": err
            }
            results.append(result_item)
            if anomalies:
                anomalies_found.append(result_item)

    print("\n" + "=" * 50)
    print_color("[*] Fuzzing Completed Summary:", COLOR_BOLD + COLOR_BLUE)
    print(f"Total Requests Sent: {len(results)}")
    print(f"Anomalous/Suspect Responses Found: {len(anomalies_found)}")
    
    # Save output if requested
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump({
                    "target": {
                        "url": args.url,
                        "method": args.method,
                        "parameter": args.parameter,
                        "type": args.type
                    },
                    "baseline": {
                        "status": base_status,
                        "length": len(base_body),
                        "time": base_time
                    },
                    "summary": {
                        "total_requests": len(results),
                        "anomalies_count": len(anomalies_found)
                    },
                    "anomalies": anomalies_found,
                    "all_results": results
                }, f, indent=4)
            print_color(f"[+] Detailed reports written to: {args.output}", COLOR_GREEN)
        except Exception as e:
            print_color(f"[-] Failed to write report: {e}", COLOR_RED)

    return 0 if not anomalies_found else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_color("\n[-] Fuzzing aborted by user.", COLOR_RED)
        sys.exit(1)
