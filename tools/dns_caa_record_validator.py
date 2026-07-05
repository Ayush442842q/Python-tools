#!/usr/bin/env python3
"""
DNS CAA Record Validator & Policy Generator
-------------------------------------------
Validates DNS Certification Authority Authorization (CAA) records, evaluates security posture against
major Certificate Authorities (Let's Encrypt, DigiCert, Sectigo, ZeroSSL, AWS Certificate Manager, Google Trust Services),
and generates compliant CAA zone file entries and multi-provider security policies.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import List, Dict, Any, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

KNOWN_CAS = {
    "letsencrypt.org": "Let's Encrypt",
    "digicert.com": "DigiCert",
    "sectigo.com": "Sectigo",
    "zerossl.com": "ZeroSSL",
    "amazon.com": "AWS Certificate Manager",
    "pki.goog": "Google Trust Services",
    "globalsign.com": "GlobalSign",
    "godaddy.com": "GoDaddy",
    "buypass.com": "Buypass",
    "entrust.net": "Entrust",
}

VALID_TAGS = {"issue", "issuewild", "iodef", "contactemail", "contactphone", "accounturi"}

CAA_PATTERN = re.compile(
    r'^(?P<domain>\S+)\s+(?:(?P<ttl>\d+)\s+)?(?:IN\s+)?CAA\s+(?P<flags>\d+)\s+(?P<tag>\w+)\s+"(?P<value>[^"]+)"$',
    re.IGNORECASE
)

RAW_CAA_LINE = re.compile(
    r'^(?P<flags>\d+)\s+(?P<tag>\w+)\s+"?(?P<value>[^"\s]+)"?$',
    re.IGNORECASE
)


class CAARecord:
    def __init__(self, domain: str, flags: int, tag: str, value: str, ttl: Optional[int] = 300):
        self.domain = domain
        self.flags = flags
        self.tag = tag.lower()
        self.value = value.strip()
        self.ttl = ttl

    @property
    def is_critical(self) -> bool:
        return bool(self.flags & 128)

    def to_zone_format(self) -> str:
        ttl_str = f"{self.ttl}\t" if self.ttl else ""
        return f"{self.domain}.\t{ttl_str}IN\tCAA\t{self.flags}\t{self.tag}\t\"{self.value}\""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "flags": self.flags,
            "critical": self.is_critical,
            "tag": self.tag,
            "value": self.value,
            "ttl": self.ttl,
        }


def parse_caa_line(line: str, default_domain: str = "example.com") -> Optional[CAARecord]:
    line = line.strip()
    if not line or line.startswith(";") or line.startswith("#"):
        return None

    match = CAA_PATTERN.match(line)
    if match:
        domain = match.group("domain").rstrip(".")
        ttl = int(match.group("ttl")) if match.group("ttl") else 300
        flags = int(match.group("flags"))
        tag = match.group("tag")
        value = match.group("value")
        return CAARecord(domain, flags, tag, value, ttl)

    match_raw = RAW_CAA_LINE.match(line)
    if match_raw:
        flags = int(match_raw.group("flags"))
        tag = match_raw.group("tag")
        value = match_raw.group("value")
        return CAARecord(default_domain, flags, tag, value)

    return None


def validate_caa_records(records: List[CAARecord]) -> Tuple[List[str], List[str], List[str]]:
    errors = []
    warnings = []
    info = []

    if not records:
        warnings.append("No CAA records provided. Any Certificate Authority can issue certificates for this domain.")
        return errors, warnings, info

    issue_present = False
    issuewild_present = False
    iodef_present = False
    allowed_cas = []

    for r in records:
        if r.flags not in (0, 128):
            warnings.append(f"Non-standard CAA flag '{r.flags}' for tag '{r.tag}'. Typically flags are 0 (non-critical) or 128 (critical).")

        if r.tag not in VALID_TAGS:
            if r.is_critical:
                errors.append(f"Critical CAA record (flag 128) uses unknown tag '{r.tag}'. CA must refuse issuance!")
            else:
                warnings.append(f"Unknown non-critical CAA tag '{r.tag}'. CAs will ignore this tag.")

        if r.tag == "issue":
            issue_present = True
            if r.value == ";":
                info.append("CAA issue ';' explicitly forbids all CAs from issuing single-name / SAN certificates.")
            else:
                ca_domain = r.value.split(";")[0].strip()
                ca_name = KNOWN_CAS.get(ca_domain, f"Custom CA ({ca_domain})")
                allowed_cas.append(f"{ca_name} ({ca_domain})")

        elif r.tag == "issuewild":
            issuewild_present = True
            if r.value == ";":
                info.append("CAA issuewild ';' explicitly forbids issuance of wildcard certificates.")
            else:
                ca_domain = r.value.split(";")[0].strip()
                ca_name = KNOWN_CAS.get(ca_domain, f"Custom CA ({ca_domain})")
                allowed_cas.append(f"Wildcard CA: {ca_name} ({ca_domain})")

        elif r.tag == "iodef":
            iodef_present = True
            if not (r.value.startswith("mailto:") or r.value.startswith("http://") or r.value.startswith("https://")):
                errors.append(f"Invalid iodef URL '{r.value}'. Must begin with mailto:, http://, or https://.")

        elif r.tag == "contactemail":
            if "@" not in r.value:
                errors.append(f"Invalid contactemail '{r.value}'.")

        elif r.tag == "accounturi":
            if not r.value.startswith("https://"):
                warnings.append(f"Account URI '{r.value}' should be an https:// URL.")

    if issue_present and not issuewild_present:
        info.append("No 'issuewild' record found. CAs will fall back to using 'issue' rules for wildcard certificates.")

    if not iodef_present:
        warnings.append("No 'iodef' reporting endpoint defined. Unwanted issuance requests will not trigger automated security reports.")

    return errors, warnings, info


def generate_caa_policy(domain: str, cas: List[str], allow_wildcard: bool = True, forbid_wildcard: bool = False, iodef: Optional[str] = None, account_uri: Optional[str] = None) -> List[CAARecord]:
    records = []
    domain = domain.rstrip(".")

    if not cas and not forbid_wildcard:
        records.append(CAARecord(domain, 0, "issue", ";"))
    else:
        for ca in cas:
            records.append(CAARecord(domain, 0, "issue", ca))

    if forbid_wildcard:
        records.append(CAARecord(domain, 0, "issuewild", ";"))
    elif allow_wildcard and cas:
        pass

    if iodef:
        records.append(CAARecord(domain, 0, "iodef", iodef))

    if account_uri and cas:
        for ca in cas:
            records.append(CAARecord(domain, 0, "issue", f"{ca}; accounturi={account_uri}"))

    return records


def main():
    parser = argparse.ArgumentParser(description="DNS CAA Record Validator & Policy Generator")
    parser.add_argument("--domain", "-d", default="example.com", help="Target domain name")
    parser.add_argument("--file", "-f", help="Read CAA records from a file (one record per line or zone file format)")
    parser.add_argument("--record", "-r", action="append", help="Pass CAA record line directly (e.g. '0 issue \"letsencrypt.org\"')")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate recommended CAA records")
    parser.add_argument("--ca", action="append", choices=list(KNOWN_CAS.keys()), help="Specify CAs to permit for generation")
    parser.add_argument("--no-wildcard", action="store_true", help="Explicitly forbid wildcard certificate issuance")
    parser.add_argument("--iodef", help="Reporting mailto: or https:// endpoint for CAA violations")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    records: List[CAARecord] = []

    if args.generate:
        cas = args.ca if args.ca else ["letsencrypt.org"]
        records = generate_caa_policy(
            domain=args.domain,
            cas=cas,
            forbid_wildcard=args.no_wildcard,
            iodef=args.iodef
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in records], indent=2))
            return

        print(f"\n{BOLD}{CYAN}=== Generated CAA Records for {args.domain} ==={RESET}\n")
        for r in records:
            print(f"  {GREEN}{r.to_zone_format()}{RESET}")
        print("\n" + "=" * 50 + "\n")
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                r = parse_caa_line(line, default_domain=args.domain)
                if r:
                    records.append(r)

    if args.record:
        for r_str in args.record:
            r = parse_caa_line(r_str, default_domain=args.domain)
            if r:
                records.append(r)

    if not records and not args.generate:
        print(f"{YELLOW}No records passed via --file or --record. Interactive Demo Mode:{RESET}\n")
        records = [
            CAARecord(args.domain, 0, "issue", "letsencrypt.org"),
            CAARecord(args.domain, 0, "issue", "amazon.com"),
            CAARecord(args.domain, 0, "issuewild", ";"),
            CAARecord(args.domain, 0, "iodef", "mailto:security@example.com"),
        ]

    errors, warnings, info = validate_caa_records(records)

    if args.json:
        result = {
            "domain": args.domain,
            "records": [r.to_dict() for r in records],
            "errors": errors,
            "warnings": warnings,
            "info": info,
        }
        print(json.dumps(result, indent=2))
        return

    print(f"\n{BOLD}{BLUE}=== DNS CAA Record Audit for {args.domain} ==={RESET}\n")
    print(f"{BOLD}Parsed Records ({len(records)}):{RESET}")
    for r in records:
        crit = f" {RED}[CRITICAL]{RESET}" if r.is_critical else ""
        print(f"  - Tag: {CYAN}{r.tag:<12}{RESET} Value: {BOLD}{r.value}{RESET}{crit}")
        print(f"    Zone Format: {r.to_zone_format()}")

    print(f"\n{BOLD}Security Audit Results:{RESET}")
    if errors:
        print(f"\n{RED}{BOLD}Errors ({len(errors)}):{RESET}")
        for e in errors:
            print(f"  {RED}✖ {e}{RESET}")

    if warnings:
        print(f"\n{YELLOW}{BOLD}Warnings ({len(warnings)}):{RESET}")
        for w in warnings:
            print(f"  {YELLOW}⚠ {w}{RESET}")

    if info:
        print(f"\n{GREEN}{BOLD}Information ({len(info)}):{RESET}")
        for i in info:
            print(f"  {GREEN}ℹ {i}{RESET}")

    if not errors and not warnings:
        print(f"\n{GREEN}{BOLD}✔ CAA policy configuration is strong and fully compliant!{RESET}\n")


if __name__ == "__main__":
    main()
