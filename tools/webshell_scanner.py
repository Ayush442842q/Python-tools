#!/usr/bin/env python3
"""
Web Shell & Backdoor Scanner

Recursively scans web application files (PHP, JS, Python, ASPX, etc.) for malicious signatures,
suspicious functions, dynamic execution calls, and abnormally high entropy (obfuscated code).

Usage:
    python tools/webshell_scanner.py /var/www/html/
    python tools/webshell_scanner.py . --entropy-threshold 6.2
"""

import os
import sys
import math
import re
import argparse
from typing import List, Dict, Tuple, Any

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Signatures for various languages
SIGNATURES = {
    "php": [
        (re.compile(r"\beval\s*\("), "eval() - Dynamic code execution"),
        (re.compile(r"\bassert\s*\("), "assert() - Dynamic code evaluation"),
        (re.compile(r"\bsystem\s*\("), "system() - Shell execution"),
        (re.compile(r"\bshell_exec\s*\("), "shell_exec() - Shell execution"),
        (re.compile(r"\bpassthru\s*\("), "passthru() - Shell execution"),
        (re.compile(r"\bexec\s*\("), "exec() - Shell execution"),
        (re.compile(r"\bpopen\s*\("), "popen() - Process execution"),
        (re.compile(r"\bproc_open\s*\("), "proc_open() - Process execution"),
        (re.compile(r"\bbase64_decode\s*\("), "base64_decode() - Often used to obfuscate code"),
        (re.compile(r"\bstr_rot13\s*\("), "str_rot13() - Obfuscation"),
        (re.compile(r"\bgzuncompress\s*\("), "gzuncompress() - Compressed payload execution"),
        (re.compile(r"\bcreate_function\s*\("), "create_function() - Deprecated code execution"),
        (re.compile(r"\b\$\_(POST|GET|REQUEST|COOKIE)\s*\[\s*\$\_"), "Nested superglobals (variable variables)"),
        (re.compile(r"\b(include|require)(_once)?\s*\(\s*\$\_"), "Dynamic file inclusion"),
    ],
    "js": [
        (re.compile(r"\beval\s*\("), "eval() - Dynamic code execution"),
        (re.compile(r"\bchild_process\b"), "child_process module - Process execution"),
        (re.compile(r"\bexec\s*\(\s*['\"`]"), "shell execution"),
        (re.compile(r"\bspawn\s*\("), "spawn() - Process execution"),
        (re.compile(r"\bnew\s+Function\s*\("), "new Function() - Dynamic function generation"),
        (re.compile(r"\\x[0-9a-fA-F]{2}"), "Hex encoded characters - Potential obfuscation"),
        (re.compile(r"\\u[0-9a-fA-F]{4}"), "Unicode escapes - Potential obfuscation"),
    ],
    "python": [
        (re.compile(r"\beval\s*\("), "eval() - Dynamic evaluation"),
        (re.compile(r"\bexec\s*\("), "exec() - Dynamic execution"),
        (re.compile(r"\bsubprocess\.(Popen|run|call|check_output)"), "subprocess execution"),
        (re.compile(r"\bos\.(system|popen)"), "os.system/popen shell execution"),
        (re.compile(r"\bpty\.spawn"), "pty.spawn() - Interactive shell access"),
        (re.compile(r"\bimport\s+socket\b.*\bconnect\s*\("), "socket reverse shell pattern"),
        (re.compile(r"\bctypes\.CDLL"), "ctypes loading - Low level binary access"),
    ]
}

def calculate_entropy(data: bytes) -> float:
    """Calculate the Shannon entropy of file data to detect encrypted/compressed content."""
    if not data:
        return 0.0
    entropy = 0.0
    # Create frequency map
    frequency = [0] * 256
    for byte in data:
        frequency[byte] += 1
    
    # Calculate probabilities and entropy
    total_bytes = len(data)
    for count in frequency:
        if count > 0:
            p = count / total_bytes
            entropy -= p * math.log2(p)
    return entropy

def check_file(filepath: str, min_entropy: float) -> Dict[str, Any]:
    """Inspects a file for suspicious patterns, line lengths, and high entropy."""
    ext = filepath.split(".")[-1].lower()
    
    # Map extensions to languages
    lang = None
    if ext in ("php", "php4", "php5", "phtml"):
        lang = "php"
    elif ext in ("js", "ts", "jsx", "tsx"):
        lang = "js"
    elif ext in ("py", "pyw"):
        lang = "python"
    elif ext in ("aspx", "ascx", "ashx", "asmx", "asp"):
        lang = "php"  # reuse PHP command execution rules as many match ASP as well
    
    try:
        with open(filepath, "rb") as f:
            raw_data = f.read()
    except Exception:
        return {}

    # Calculate entropy
    entropy = calculate_entropy(raw_data)
    
    # Decode to text
    try:
        content = raw_data.decode("utf-8", errors="ignore")
    except Exception:
        content = ""

    lines = content.splitlines()
    matches = []
    
    # Run signatures
    if lang and lang in SIGNATURES:
        for pattern, desc in SIGNATURES[lang]:
            # Scan line by line to get line numbers
            for idx, line in enumerate(lines, 1):
                if pattern.search(line):
                    # Exclude common false positives
                    if "scanner" in filepath or "webshell_scanner" in filepath:
                        continue
                    matches.append({"line": idx, "pattern": desc, "content": line.strip()[:60]})

    # Check for long lines (often base64 payloads)
    long_lines = 0
    for idx, line in enumerate(lines, 1):
        if len(line) > 1000:
            # Skip minified files (usually JavaScript libraries)
            if ext in ("js", "min.js", "css"):
                continue
            long_lines += 1
            matches.append({"line": idx, "pattern": f"Abnormally long line ({len(line)} chars)", "content": line[:60] + "..."})
            if long_lines >= 5: # Cap findings for long lines
                break

    # Determine risk score
    score = len(matches) * 2.0
    if entropy > min_entropy:
        score += 3.0
        
    risk = "LOW"
    if score >= 6.0:
        risk = "HIGH"
    elif score >= 3.0:
        risk = "MEDIUM"

    return {
        "filepath": filepath,
        "entropy": entropy,
        "matches": matches,
        "risk": risk,
        "score": score
    }

def print_colored(text: str, color: str):
    sys.stdout.write(f"{color}{text}{RESET}\n")

def main():
    parser = argparse.ArgumentParser(description="Scan directories for web shells and backdoor scripts.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-e", "--entropy-threshold", type=float, default=6.0, help="Entropy threshold to flag obfuscated files (0.0 - 8.0, default 6.0)")
    parser.add_argument("-a", "--all-files", action="store_true", help="Scan all files instead of just source code files")
    
    args = parser.parse_args()

    target_dir = args.directory
    if not os.path.exists(target_dir):
        print_colored(f"[-] Path does not exist: {target_dir}", RED)
        sys.exit(1)

    print_colored(f"[*] Starting Web Shell scan in '{target_dir}'...", BLUE)
    print_colored(f"[*] Entropy threshold: {args.entropy_threshold}", BLUE)
    
    scanned_count = 0
    findings = []
    
    source_exts = {".php", ".phtml", ".js", ".py", ".pyw", ".aspx", ".asp", ".jsp", ".sh", ".pl"}

    for root, _, files in os.walk(target_dir):
        for file in files:
            filepath = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            # Skip this script
            if file == "webshell_scanner.py":
                continue
                
            if not args.all_files and ext.lower() not in source_exts:
                continue

            scanned_count += 1
            res = check_file(filepath, args.entropy_threshold)
            if res and (res["matches"] or res["entropy"] > args.entropy_threshold):
                findings.append(res)

    # Sort findings by risk score desc
    findings.sort(key=lambda x: x["score"], reverse=True)

    print_colored(f"\n[+] Scan Complete. Scanned {scanned_count} files.", GREEN)
    
    if not findings:
        print_colored("[+] No suspicious files found.", GREEN)
        return

    print_colored(f"[!] Found {len(findings)} files with potential warnings/risks.\n", YELLOW)

    for f in findings:
        risk_color = RED if f["risk"] == "HIGH" else (YELLOW if f["risk"] == "MEDIUM" else GREEN)
        print_colored(f"============================================================", CYAN)
        print(f"File: {f['filepath']}")
        print_colored(f"Risk: {f['risk']} (Score: {f['score']})", risk_color)
        print(f"Entropy: {f['entropy']:.3f}")
        
        if f["matches"]:
            print("Matched Rules:")
            for m in f["matches"]:
                print(f"  - Line {m['line']}: {m['pattern']}")
                print(f"    Snippet: {m['content']}")
        print()

if __name__ == "__main__":
    main()
