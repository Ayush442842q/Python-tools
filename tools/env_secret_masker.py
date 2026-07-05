#!/usr/bin/env python3
"""
Environment Variable & Secret Masker / Redactor Tool

Scans environment files (.env), configuration files, source code, or log files to detect
sensitive secrets (AWS credentials, GitHub tokens, passwords, private keys, JWTs, connection URIs)
and redacts them using customizable pattern matching and Shannon entropy analysis.
"""

import os
import sys
import re
import math
import argparse
from typing import List, Tuple, Dict, Any, Optional

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r'\b(AKIA[0-9A-Z]{16})\b')),
    ("AWS Secret Key", re.compile(r'\b[0-9a-zA-Z/+]{40}\b')),
    ("GitHub Token", re.compile(r'\b(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b')),
    ("Generic API Key", re.compile(r'(?i)\b(api[_-]?key|secret|token|password|auth_token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?')),
    ("JWT Token", re.compile(r'\beyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b')),
    ("Private Key", re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ("Database URI Password", re.compile(r'(?i)\b([a-z0-9+]+://[^:]+:)([^@]+)(@[^/]+)')),
    ("Slack Token", re.compile(r'\bxox[baprs]-[0-9a-zA-Z]{10,48}\b')),
]


def calculate_shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy of a string to detect high-entropy keys."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in set(data):
        p_x = float(data.count(x)) / len(data)
        entropy -= p_x * math.log2(p_x)
    return entropy


class SecretMasker:
    def __init__(self, mask_symbol: str = "*", entropy_threshold: float = 4.5, min_length: int = 16):
        self.mask_symbol = mask_symbol
        self.entropy_threshold = entropy_threshold
        self.min_length = min_length
        self.detections: List[Dict[str, Any]] = []

    def mask_string(self, secret: str) -> str:
        """Mask a secret leaving only initial/final characters visible if long enough."""
        if len(secret) <= 6:
            return self.mask_symbol * len(secret)
        return secret[:2] + (self.mask_symbol * (len(secret) - 4)) + secret[-2:]

    def process_content(self, content: str, filename: str = "stream") -> Tuple[str, int]:
        masked_content = content
        count = 0

        # Pattern-based matching
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(content):
                full_match = match.group(0)
                # If group 2 exists (e.g. key=val pair or uri), target key value specifically
                if len(match.groups()) >= 2:
                    secret_val = match.group(2)
                    if len(secret_val) >= 4:
                        redacted_val = self.mask_string(secret_val)
                        masked_content = masked_content.replace(secret_val, redacted_val)
                        count += 1
                        self.detections.append({
                            'file': filename, 'type': label, 'original': secret_val, 'masked': redacted_val
                        })
                else:
                    redacted = self.mask_string(full_match)
                    masked_content = masked_content.replace(full_match, redacted)
                    count += 1
                    self.detections.append({
                        'file': filename, 'type': label, 'original': full_match, 'masked': redacted
                    })

        # High entropy string scanning for assignment values
        for line_num, line in enumerate(content.splitlines(), start=1):
            if '=' in line or ':' in line:
                parts = re.split(r'[:=]', line, maxsplit=1)
                if len(parts) == 2:
                    key, val = parts[0].strip(), parts[1].strip().strip('"\'')
                    if len(val) >= self.min_length and not val.startswith('[REDACTED'):
                        ent = calculate_shannon_entropy(val)
                        if ent >= self.entropy_threshold and not any(d['original'] == val for d in self.detections):
                            redacted = self.mask_string(val)
                            masked_content = masked_content.replace(val, redacted)
                            count += 1
                            self.detections.append({
                                'file': filename, 'type': f"High Entropy ({ent:.2f})", 'original': val, 'masked': redacted
                            })

        return masked_content, count


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Scan and redact sensitive secrets from configuration/log files.")
    parser.add_argument("files", nargs="+", help="File(s) or directory paths to process")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify files in-place with redacted output")
    parser.add_argument("-o", "--output", help="Output file path (for single file processing)")
    parser.add_argument("--entropy", type=float, default=4.5, help="Entropy threshold for secret detection (default: 4.5)")
    parser.add_argument("--dry-run", action="store_true", help="Report detected secrets without writing modifications")

    args = parser.parse_args()
    masker = SecretMasker(entropy_threshold=args.entropy)

    total_secrets = 0
    for target_path in args.files:
        if os.path.isfile(target_path):
            with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            masked, count = masker.process_content(content, target_path)
            total_secrets += count

            if not args.dry_run:
                if args.in_place:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(masked)
                    print(f"{GREEN}✓ Redacted secrets in-place: '{target_path}'{RESET}")
                elif args.output:
                    with open(args.output, 'w', encoding='utf-8') as f:
                        f.write(masked)
                    print(f"{GREEN}✓ Redacted output saved to: '{args.output}'{RESET}")
                else:
                    if len(args.files) == 1:
                        print(masked)
        elif os.path.isdir(target_path):
            for root, _, filenames in os.walk(target_path):
                for fname in filenames:
                    fpath = os.path.join(root, fname)
                    if fname.endswith(('.env', '.json', '.yaml', '.yml', '.log', '.py', '.js', '.txt', '.conf')):
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        masked, count = masker.process_content(content, fpath)
                        total_secrets += count
                        if args.in_place and not args.dry_run and count > 0:
                            with open(fpath, 'w', encoding='utf-8') as f:
                                f.write(masked)

    print(f"\n{BOLD}{CYAN}=== Secret Masking Report ==={RESET}", file=sys.stderr)
    print(f"Total Secrets Detected : {RED if total_secrets > 0 else GREEN}{total_secrets}{RESET}", file=sys.stderr)

    if masker.detections:
        print(f"\n{BOLD}Detections Detail:{RESET}", file=sys.stderr)
        for d in masker.detections:
            print(f"  [{YELLOW}{d['type']}{RESET}] File: {d['file']} -> {d['masked']}", file=sys.stderr)


if __name__ == '__main__':
    main()
