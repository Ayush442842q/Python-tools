#!/usr/bin/env python3
"""
DNS SPF & DMARC Policy Inspector
--------------------------------
Parses, validates, and audits SPF (Sender Policy Framework) and DMARC (Domain-based Message
Authentication, Reporting, and Conformance) DNS records for syntax compliance, security risks,
lookup limits, and enforcement policies.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# SPF Mechanisms that require DNS lookups
LOOKUP_MECHANISMS = {'include', 'a', 'mx', 'ptr', 'exists', 'redirect'}


class SPFValidator:
    def __init__(self, spf_record: str):
        self.raw_record = spf_record.strip()
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.lookup_count = 0
        self.mechanisms: List[Dict[str, str]] = []

    def parse_and_validate(self) -> Dict[str, Any]:
        record = self.raw_record.strip()
        if (record.startswith('"') and record.endswith('"')) or (record.startswith("'") and record.endswith("'")):
            record = record[1:-1]

        if not record.startswith("v=spf1"):
            self.errors.append("SPF record must start with 'v=spf1'")
            self.valid = False
            return self._result()

        tokens = record.split()
        version_token = tokens[0]
        mechanism_tokens = tokens[1:]

        has_all = False
        all_qualifier = None

        for token in mechanism_tokens:
            qualifier = "+"
            term = token
            if token[0] in ['+', '-', '~', '?']:
                qualifier = token[0]
                term = token[1:]

            if term == "all":
                has_all = True
                all_qualifier = qualifier
                if qualifier == "+":
                    self.errors.append("Critical Security Risk: '+all' allows ANY IP address to send email on your domain!")
                    self.valid = False
                elif qualifier == "?":
                    self.warnings.append("Weak Policy: '?all' (Neutral) provides no protection against spoofing.")
                elif qualifier == "~":
                    self.warnings.append("SoftFail Policy: '~all' marks unauthorized mail as softfail. Consider '-all' (HardFail) for strict enforcement.")
                elif qualifier == "-":
                    self.info.append("Strict HardFail Policy: '-all' rejects unauthorized mail sender IPs.")

            # Check mechanisms requiring DNS lookups
            mech_name = term.split(':')[0].split('=')[0].lower()
            if mech_name in LOOKUP_MECHANISMS:
                self.lookup_count += 1
                self.mechanisms.append({"type": mech_name, "qualifier": qualifier, "target": term})

        if not has_all:
            self.warnings.append("Missing 'all' mechanism at end of SPF record (e.g. '-all' or '~all').")

        if self.lookup_count > 10:
            self.errors.append(f"DNS Lookup Limit Exceeded: Record requires {self.lookup_count} DNS lookups (RFC 7208 maximum is 10).")
            self.valid = False
        elif self.lookup_count > 7:
            self.warnings.append(f"High DNS Lookups: Record uses {self.lookup_count}/10 allowed DNS lookups.")

        return self._result()

    def _result(self) -> Dict[str, Any]:
        return {
            "record": self.raw_record,
            "valid": self.valid,
            "dns_lookups": self.lookup_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


class DMARCValidator:
    def __init__(self, dmarc_record: str):
        self.raw_record = dmarc_record.strip()
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.tags: Dict[str, str] = {}

    def parse_and_validate(self) -> Dict[str, Any]:
        record = self.raw_record.strip()
        if (record.startswith('"') and record.endswith('"')) or (record.startswith("'") and record.endswith("'")):
            record = record[1:-1]

        tokens = [t.strip() for t in record.split(';') if t.strip()]
        if not tokens:
            self.errors.append("Empty DMARC record")
            self.valid = False
            return self._result()

        if not tokens[0].startswith("v=DMARC1"):
            self.errors.append("DMARC record must start with 'v=DMARC1'")
            self.valid = False

        for token in tokens:
            if '=' in token:
                k, v = token.split('=', 1)
                self.tags[k.strip().lower()] = v.strip()

        # Check required tag 'p' (Policy)
        if 'p' not in self.tags:
            self.errors.append("Missing required 'p' (Policy) tag in DMARC record.")
            self.valid = False
        else:
            policy = self.tags['p'].lower()
            if policy == "none":
                self.warnings.append("Monitoring-Only Policy: 'p=none' gathers reports but does NOT block or quarantine spoofed emails.")
            elif policy == "quarantine":
                self.info.append("Quarantine Policy: 'p=quarantine' routes suspicious mail to spam/junk folders.")
            elif policy == "reject":
                self.info.append("Strict Reject Policy: 'p=reject' instructs receivers to block unauthorized email.")
            else:
                self.errors.append(f"Invalid policy value 'p={policy}'. Must be 'none', 'quarantine', or 'reject'.")
                self.valid = False

        # Check aggregate reporting
        if 'rua' not in self.tags:
            self.warnings.append("Missing 'rua' tag: Aggregate DMARC reports will not be received.")
        else:
            self.info.append(f"Aggregate Reports Target: {self.tags['rua']}")

        # Check alignment mode
        aspf = self.tags.get('aspf', 'r').lower()
        if aspf == 's':
            self.info.append("Strict SPF alignment configured (aspf=s).")
        adkim = self.tags.get('adkim', 'r').lower()
        if adkim == 's':
            self.info.append("Strict DKIM alignment configured (adkim=s).")

        return self._result()

    def _result(self) -> Dict[str, Any]:
        return {
            "record": self.raw_record,
            "valid": self.valid,
            "tags": self.tags,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def generate_recommended_spf(domain: str, includes: List[str], ip4s: List[str], hardfail: bool = True) -> str:
    """Generate recommended SPF record string."""
    parts = ["v=spf1"]
    for ip in ip4s:
        parts.append(f"ip4:{ip}")
    for inc in includes:
        parts.append(f"include:{inc}")
    parts.append("-all" if hardfail else "~all")
    return " ".join(parts)


def generate_recommended_dmarc(domain: str, email: str, policy: str = "quarantine") -> str:
    """Generate recommended DMARC record string."""
    return f"v=DMARC1; p={policy}; rua=mailto:{email}; ruf=mailto:{email}; fo=1; adkim=r; aspf=r;"


def print_report(title: str, res: Dict[str, Any]):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")
    print(f"Record: {BOLD}{res['record']}{RESET}")
    
    if res['valid']:
        print(f"Status: {GREEN}✓ VALID{RESET}")
    else:
        print(f"Status: {RED}✗ INVALID{RESET}")

    if "dns_lookups" in res:
        print(f"DNS Lookups: {res['dns_lookups']}/10")

    for err in res['errors']:
        print(f"  {RED}✘ Error:{RESET} {err}")

    for warn in res['warnings']:
        print(f"  {YELLOW}⚠ Warning:{RESET} {warn}")

    for info in res['info']:
        print(f"  {BLUE}ℹ Info:{RESET} {info}")


def main():
    parser = argparse.ArgumentParser(
        description="DNS SPF & DMARC Policy Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python tools/dns_spf_dmarc_validator.py --spf "v=spf1 include:_spf.google.com ~all"
  python tools/dns_spf_dmarc_validator.py --dmarc "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"
  python tools/dns_spf_dmarc_validator.py --generate --domain example.com --email dmarc@example.com --include _spf.google.com
"""
    )
    
    parser.add_argument("--spf", help="SPF record string to validate")
    parser.add_argument("--dmarc", help="DMARC record string to validate")
    parser.add_argument("--generate", action="store_true", help="Generate recommended SPF & DMARC records")
    parser.add_argument("--domain", default="example.com", help="Domain for policy generation")
    parser.add_argument("--email", default="dmarc@example.com", help="Email for DMARC reporting")
    parser.add_argument("--include", action="append", default=[], help="SPF include domains (can be specified multiple times)")

    args = parser.parse_args()

    if args.generate:
        print(f"\n{BOLD}{CYAN}=== Generated Compliant Policies for {args.domain} ==={RESET}\n")
        rec_spf = generate_recommended_spf(args.domain, args.include or ["_spf.google.com"], ["192.0.2.1"])
        rec_dmarc = generate_recommended_dmarc(args.domain, args.email)
        print(f"{BOLD}SPF TXT Record:{RESET}\n  {GREEN}{rec_spf}{RESET}\n")
        print(f"{BOLD}DMARC TXT Record (_dmarc.{args.domain}):{RESET}\n  {GREEN}{rec_dmarc}{RESET}\n")
        return

    if not args.spf and not args.dmarc:
        # Default demo if no parameters supplied
        demo_spf = "v=spf1 include:_spf.google.com include:mailgun.org ip4:192.0.2.1 ~all"
        demo_dmarc = "v=DMARC1; p=none; rua=mailto:reports@example.com; ruf=mailto:reports@example.com"
        
        val_spf = SPFValidator(demo_spf).parse_and_validate()
        print_report("SPF Record Inspection (Demo)", val_spf)

        val_dmarc = DMARCValidator(demo_dmarc).parse_and_validate()
        print_report("DMARC Record Inspection (Demo)", val_dmarc)
        return

    if args.spf:
        val_spf = SPFValidator(args.spf).parse_and_validate()
        print_report("SPF Record Inspection", val_spf)

    if args.dmarc:
        val_dmarc = DMARCValidator(args.dmarc).parse_and_validate()
        print_report("DMARC Record Inspection", val_dmarc)


if __name__ == "__main__":
    main()
