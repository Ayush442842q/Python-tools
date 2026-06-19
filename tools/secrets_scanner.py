#!/usr/bin/env python3
"""
Source Code Secrets & API Key Scanner

Scans codebase directories recursively for hardcoded secrets, API keys, 
private keys, and high-entropy strings, using predefined pattern matching and 
Shannon entropy analysis. Masks detected secrets to prevent log leakage.

Usage:
    python tools/secrets_scanner.py <target_path> [options]

Example:
    python tools/secrets_scanner.py . --entropy 4.3 --exclude-dirs node_modules,.git,venv
"""

import argparse
import math
import os
import re
import sys
from collections import Counter
from typing import Dict, List, Set, Tuple

# Predefined Regex Signatures for common secrets
SECRET_PATTERNS = {
    'AWS Access Key ID': re.compile(r'\b(?:AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b'),
    'AWS Secret Access Key': re.compile(r'\b[A-Za-z0-9/+=]{40}\b'),
    'GitHub Personal Access Token': re.compile(r'\b(?:gh[pous]_[a-zA-Z0-9]{36,255}|github_pat_[a-zA-Z0-9]{82})\b'),
    'Slack Webhook URL': re.compile(r'https://hooks\.slack\.com/services/[T|A][A-Z0-9]{8}/[B][A-Z0-9]{8}/[A-Za-z0-9]{24}'),
    'Slack Token': re.compile(r'\bxox[baprs]-[0-9]{12}-[a-zA-Z0-9]{24,48}\b'),
    'Google API Key': re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'),
    'Stripe API Key': re.compile(r'\b[rs]k_(?:live|test)_[0-9a-zA-Z]{24,34}\b'),
    'Private Key Header': re.compile(r'-----BEGIN [A-Z0-9_ ]+ PRIVATE KEY-----'),
    'Generic Password Parameter': re.compile(r'\b(?:password|passwd|secret|api_key|apikey|db_pass|database_pass|client_secret)\s*=\s*[\'"]([^\'"]{8,64})[\'"]', re.IGNORECASE)
}

# Directories and extensions to ignore by default
DEFAULT_EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', '.idea', '.vscode', 'dist', 'build'}
DEFAULT_EXCLUDE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3', '.woff', '.woff2', '.ttf', '.eot', '.exe', '.dll', '.so', '.dylib', '.pyc'}

def calculate_entropy(text: str) -> float:
    """Calculates the Shannon entropy of a string (higher means more random/complex)."""
    if not text:
        return 0.0
    length = len(text)
    counts = Counter(text)
    entropy = 0.0
    for count in counts.values():
        p_x = count / length
        entropy -= p_x * math.log2(p_x)
    return entropy

def mask_secret(secret: str) -> str:
    """Masks a secret string leaving only the start and end visible."""
    if len(secret) <= 8:
        return '*' * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"

def scan_file(file_path: str, min_entropy: float, check_entropy: bool) -> List[Dict[str, Any]]:
    """Scans a single file for secret signatures and high-entropy words."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        # Ignore files we cannot read
        return findings

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # 1. Regex Pattern Matching
        for name, pattern in SECRET_PATTERNS.items():
            matches = pattern.findall(line_stripped)
            for match in matches:
                # If match is a tuple (e.g. from generic password capturing group), extract the secret
                secret = match[0] if isinstance(match, tuple) else match
                
                # Filter false positives: ignore if empty or too short
                if not secret or len(secret.strip()) < 6:
                    continue
                    
                findings.append({
                    'type': 'Pattern Match',
                    'detector': name,
                    'line_number': line_num,
                    'matched_string': secret,
                    'masked_string': mask_secret(secret),
                    'line_snippet': line_stripped[:120]
                })

        # 2. Shannon Entropy Analysis for potential random keys/passwords
        if check_entropy:
            # Tokenize words using alphanumeric characters plus common base64/hex symbols
            words = re.findall(r'\b[A-Za-z0-9/+=_-]{16,64}\b', line_stripped)
            for word in words:
                # Ignore if it's already caught by regex detectors to avoid duplicate findings
                already_caught = False
                for f in findings:
                    if f['line_number'] == line_num and word in f['matched_string']:
                        already_caught = True
                        break
                if already_caught:
                    continue
                    
                # Skip simple strings (e.g., repeating characters or common programming terms)
                if len(set(word)) < 5:
                    continue
                    
                entropy = calculate_entropy(word)
                if entropy >= min_entropy:
                    # Double check if it looks like a hex string, base64, or pure random key
                    findings.append({
                        'type': 'High Entropy String',
                        'detector': f'Entropy ({entropy:.2f})',
                        'line_number': line_num,
                        'matched_string': word,
                        'masked_string': mask_secret(word),
                        'line_snippet': line_stripped[:120]
                    })
                    
    return findings

def main() -> int:
    parser = argparse.ArgumentParser(description="Scan project files for hardcoded secrets and API keys.")
    parser.add_argument("path", nargs="?", default=".", help="Directory or file path to scan (default: '.')")
    parser.add_argument("-e", "--entropy", type=float, default=4.5, help="Entropy threshold for random keys detection (default: 4.5)")
    parser.add_argument("--no-entropy", action="store_true", help="Disable Shannon entropy scanning (only check regex patterns)")
    parser.add_argument("--exclude-dirs", help="Comma-separated list of additional directories to ignore")
    parser.add_argument("--exclude-exts", help="Comma-separated list of additional file extensions to ignore")
    parser.add_argument("-o", "--output", help="Save the scan report to a file (JSON or text)")
    
    args = parser.parse_args()
    
    target_path = os.path.abspath(args.path)
    if not os.path.exists(target_path):
        print(f"Error: Target path '{target_path}' does not exist.", file=sys.stderr)
        return 1
        
    # Configure exclusions
    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()
    if args.exclude_dirs:
        exclude_dirs.update(d.strip() for d in args.exclude_dirs.split(','))
        
    exclude_exts = DEFAULT_EXCLUDE_EXTS.copy()
    if args.exclude_exts:
        exclude_exts.update(e.strip() if e.startswith('.') else f".{e.strip()}" for e in args.exclude_exts.split(','))
        
    all_findings: Dict[str, List[Dict[str, Any]]] = {}
    total_files_scanned = 0
    total_secrets_found = 0
    
    print(f"Scanning target: {target_path}")
    print(f"Excluding directories: {', '.join(sorted(list(exclude_dirs)))}")
    if not args.no_entropy:
        print(f"Entropy Threshold: {args.entropy}")
        
    # Gather files
    files_to_scan = []
    if os.path.isfile(target_path):
        files_to_scan.append(target_path)
    else:
        for root, dirs, files in os.walk(target_path):
            # Prune directory walk list
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_exts:
                    continue
                files_to_scan.append(os.path.join(root, file))
                
    # Run scan
    for file_path in files_to_scan:
        rel_path = os.path.relpath(file_path, target_path)
        # Skip this script itself and other tools if we run locally (prevent self-detection on test patterns)
        if os.path.basename(file_path) == "secrets_scanner.py":
            continue
            
        file_findings = scan_file(file_path, args.entropy, not args.no_entropy)
        if file_findings:
            all_findings[rel_path] = file_findings
            total_secrets_found += len(file_findings)
        total_files_scanned += 1
        
    # Render Report
    print("\n" + "=" * 80)
    print(f"SECRETS SCAN REPORT")
    print("=" * 80)
    print(f"Files scanned:    {total_files_scanned}")
    print(f"Secrets detected: {total_secrets_found}")
    print("-" * 80)
    
    if total_secrets_found > 0:
        for file, findings in all_findings.items():
            print(f"\n📂 File: {file}")
            print("-" * 50)
            for f in findings:
                print(f"  Line {f['line_number']:<4} | Type: {f['type']:<15} | Detector: {f['detector']}")
                print(f"  Snippet:   {f['line_snippet']}")
                print(f"  Match:     \033[91m{f['masked_string']}\033[0m")
                print("-" * 30)
        print("\n\033[91mWARNING: Hardcoded secrets found. Never commit credentials to version control!\033[0m")
    else:
        print("\n\033[92mSUCCESS: No hardcoded secrets or high-entropy tokens detected.\033[0m")
        
    print("=" * 80)
    
    # Save output if requested
    if args.output:
        try:
            import json
            with open(args.output, 'w', encoding='utf-8') as f:
                if args.output.endswith('.json'):
                    json.dump({
                        'summary': {
                            'files_scanned': total_files_scanned,
                            'secrets_found': total_secrets_found
                        },
                        'findings': all_findings
                    }, f, indent=4)
                else:
                    # Write plain text format
                    f.write(f"Secrets Scan Summary\n")
                    f.write(f"Files Scanned: {total_files_scanned}\n")
                    f.write(f"Secrets Found: {total_secrets_found}\n\n")
                    for file, findings in all_findings.items():
                        f.write(f"File: {file}\n")
                        for fn in findings:
                            f.write(f"  Line {fn['line_number']} [{fn['type']} - {fn['detector']}]: {fn['masked_string']}\n")
            print(f"Report saved to {args.output}")
        except Exception as e:
            print(f"Error saving report to {args.output}: {e}", file=sys.stderr)
            
    # Exit with code 1 if secrets found (useful for CI/CD checks)
    return 1 if total_secrets_found > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
