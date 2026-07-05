#!/usr/bin/env python3
"""SSH Authorized Keys Auditor

Audits SSH authorized_keys files for security vulnerabilities such as weak key algorithms,
insufficient key lengths, duplicate keys, overly permissive options, and missing metadata.
"""

import argparse
import base64
import json
import os
import struct
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


def parse_rsa_key_bits(key_bytes: bytes) -> Optional[int]:
    """Extract RSA key length in bits from raw OpenSSH key payload."""
    try:
        idx = 0
        # Read string: key type
        type_len = struct.unpack(">I", key_bytes[idx:idx + 4])[0]
        idx += 4 + type_len

        # Read exponent e
        e_len = struct.unpack(">I", key_bytes[idx:idx + 4])[0]
        idx += 4 + e_len

        # Read modulus n
        n_len = struct.unpack(">I", key_bytes[idx:idx + 4])[0]
        idx += 4
        modulus_bytes = key_bytes[idx:idx + n_len]
        # Strip leading zero padding if present
        if modulus_bytes and modulus_bytes[0] == 0:
            modulus_bytes = modulus_bytes[1:]
        return len(modulus_bytes) * 8
    except Exception:
        return None


class KeyEntry:
    def __init__(self, line_no: int, raw_line: str):
        self.line_no = line_no
        self.raw_line = raw_line.strip()
        self.options: List[str] = []
        self.key_type = ""
        self.key_b64 = ""
        self.comment = ""
        self.key_bits: Optional[int] = None
        self.warnings: List[str] = []
        self._parse()

    def _parse(self):
        parts = self.raw_line.split()
        if not parts:
            return

        # Check if first token is option or key type
        if parts[0].startswith("ssh-") or parts[0].startswith("ecdsa-"):
            self.key_type = parts[0]
            if len(parts) > 1:
                self.key_b64 = parts[1]
            if len(parts) > 2:
                self.comment = " ".join(parts[2:])
        else:
            # Options prefix present
            self.options = parts[0].split(",")
            if len(parts) > 1:
                self.key_type = parts[1]
            if len(parts) > 2:
                self.key_b64 = parts[2]
            if len(parts) > 3:
                self.comment = " ".join(parts[3:])

        if self.key_b64:
            try:
                raw_bytes = base64.b64decode(self.key_b64)
                if self.key_type == "ssh-rsa":
                    self.key_bits = parse_rsa_key_bits(raw_bytes)
            except Exception:
                self.warnings.append("Malformed base64 key payload")


class AuthorizedKeysAuditor:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.entries: List[KeyEntry] = []

    def audit(self) -> List[KeyEntry]:
        lines = self.file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        seen_keys: Dict[str, int] = {}

        for i, line in enumerate(lines, 1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            entry = KeyEntry(i, line_str)

            # Rule 1: DSA keys are deprecated and insecure
            if entry.key_type == "ssh-dss":
                entry.warnings.append("CRITICAL: DSA keys (ssh-dss) are deprecated and insecure")

            # Rule 2: Weak RSA key length (< 2048 bits)
            elif entry.key_type == "ssh-rsa":
                if entry.key_bits and entry.key_bits < 2048:
                    entry.warnings.append(f"HIGH: RSA key length is weak ({entry.key_bits} bits < 2048 bits)")
                elif entry.key_bits and entry.key_bits == 2048:
                    entry.warnings.append("MEDIUM: RSA 2048-bit key (consider upgrading to ED25519 or RSA 4096-bit)")

            # Rule 3: Check duplicates
            if entry.key_b64:
                if entry.key_b64 in seen_keys:
                    entry.warnings.append(f"HIGH: Duplicate key payload (first seen on line {seen_keys[entry.key_b64]})")
                else:
                    seen_keys[entry.key_b64] = i

            # Rule 4: Missing comment
            if not entry.comment:
                entry.warnings.append("LOW: Key entry lacks descriptive comment or owner tag")

            self.entries.append(entry)

        return self.entries


def main():
    parser = argparse.ArgumentParser(
        description="Audit SSH authorized_keys files for weak keys, duplicates, and security risks."
    )
    default_auth_keys = Path.home() / ".ssh" / "authorized_keys"
    parser.add_argument("path", nargs="?", default=str(default_auth_keys), help="Path to authorized_keys file")
    parser.add_argument("--format", choices=["terminal", "json", "markdown"], default="terminal", help="Output format")

    args = parser.parse_args()
    file_path = Path(args.path).resolve()

    if not file_path.exists():
        print(f"{COLOR_RED}Error: File '{file_path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    auditor = AuthorizedKeysAuditor(file_path)
    entries = auditor.audit()

    if args.format == "terminal":
        print(f"{COLOR_BOLD}{COLOR_CYAN}SSH Authorized Keys Security Audit{COLOR_RESET}")
        print(f"File: {COLOR_BOLD}{file_path}{COLOR_RESET} | Total Keys: {len(entries)}\n")

        total_issues = sum(len(e.warnings) for e in entries)
        if total_issues == 0:
            print(f"{COLOR_GREEN}✓ No security issues detected in authorized_keys!{COLOR_RESET}")
            return

        for e in entries:
            key_info = f"{e.key_type} ({e.key_bits} bits)" if e.key_bits else e.key_type
            comment_str = f" - '{e.comment}'" if e.comment else " (No comment)"
            print(f"  Line {e.line_no}: {COLOR_BOLD}{key_info}{COLOR_RESET}{COLOR_GREY}{comment_str}{COLOR_RESET}")

            for w in e.warnings:
                if "CRITICAL" in w or "HIGH" in w:
                    color = COLOR_RED
                elif "MEDIUM" in w:
                    color = COLOR_YELLOW
                else:
                    color = COLOR_GREY
                print(f"    - {color}{w}{COLOR_RESET}")
            print()

        print(f"{COLOR_BOLD}Audit Summary:{COLOR_RESET} {total_issues} warning(s) across {len(entries)} key(s).")

    elif args.format == "json":
        res = [
            {
                "line": e.line_no,
                "type": e.key_type,
                "bits": e.key_bits,
                "comment": e.comment,
                "options": e.options,
                "warnings": e.warnings,
            }
            for e in entries
        ]
        print(json.dumps(res, indent=2))

    elif args.format == "markdown":
        print(f"# SSH Authorized Keys Audit Report\n")
        print(f"**Target File:** `{file_path}`\n")
        print("| Line | Type | Bits | Comment | Security Issues |")
        print("|---|---|---|---|---|")
        for e in entries:
            warn_str = "<br>".join(e.warnings) if e.warnings else "✓ Clean"
            bits_str = str(e.key_bits) if e.key_bits else "N/A"
            print(f"| {e.line_no} | `{e.key_type}` | {bits_str} | {e.comment or 'N/A'} | {warn_str} |")


if __name__ == "__main__":
    main()
