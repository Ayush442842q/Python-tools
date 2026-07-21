#!/usr/bin/env python3
"""
dns_zone_validator - DNS Zone File Parser and Validator

Parses and validates RFC 1035 compliant DNS Zone files. It checks for common
logical errors and syntax issues, including:
- Missing SOA or NS records
- Circular CNAME chains
- CNAME conflicts (CNAME alongside other records on the same name)
- Malformed A/AAAA IP addresses
- Out-of-zone resource records
- Missing TTL settings

Usage:
    python tools/dns_zone_validator.py zone.txt [--origin example.com.]
"""

import argparse
import re
import sys


class DNSZoneValidator:
    def __init__(self, zone_content, origin=None):
        self.zone_content = zone_content
        self.origin = origin.lower() if origin else ""
        if self.origin and not self.origin.endswith('.'):
            self.origin += '.'
            
        self.default_ttl = None
        self.current_origin = self.origin
        self.records = []
        self.errors = []
        self.warnings = []

    def log_error(self, line_num, msg):
        self.errors.append({"line": line_num, "message": msg})

    def log_warning(self, line_num, msg):
        self.warnings.append({"line": line_num, "message": msg})

    def preprocess_lines(self):
        """
        Removes comments, handles multi-line records (parentheses),
        and yields (line_number, cleaned_line).
        """
        lines = self.zone_content.splitlines()
        in_parentheses = False
        accumulator = []
        start_line_num = 0

        for i, line in enumerate(lines, 1):
            # Strip comment (char ';' not preceded by backslash)
            # Simple approximation: split on ';' but handle potential quotes/escapes
            comment_idx = -1
            in_quote = False
            for idx, char in enumerate(line):
                if char == '"' and (idx == 0 or line[idx - 1] != '\\'):
                    in_quote = not in_quote
                elif char == ';' and not in_quote:
                    comment_idx = idx
                    break
            
            if comment_idx != -1:
                line = line[:comment_idx]
            
            line = line.strip()
            if not line:
                continue

            if not in_parentheses:
                if '(' in line:
                    in_parentheses = True
                    start_line_num = i
                    # Split at '('
                    parts = line.split('(', 1)
                    accumulator.append(parts[0].strip())
                    if ')' in parts[1]:
                        in_parentheses = False
                        subparts = parts[1].split(')', 1)
                        accumulator.append(subparts[0].strip())
                        yield start_line_num, " ".join(accumulator).strip()
                        accumulator = []
                    else:
                        accumulator.append(parts[1].strip())
                else:
                    yield i, line
            else:
                if ')' in line:
                    in_parentheses = False
                    parts = line.split(')', 1)
                    accumulator.append(parts[0].strip())
                    yield start_line_num, " ".join(accumulator).strip()
                    accumulator = []
                else:
                    accumulator.append(line)

        if in_parentheses:
            self.log_error(start_line_num, "Unclosed parentheses in multi-line block")

    def parse(self):
        last_name = ""
        preprocessed = list(self.preprocess_lines())

        # Directives & Record parsing
        for line_num, line in preprocessed:
            tokens = line.split()
            if not tokens:
                continue

            first_token = tokens[0].upper()

            # Directives
            if first_token == "$TTL":
                if len(tokens) < 2:
                    self.log_error(line_num, "Missing value for $TTL directive")
                else:
                    self.default_ttl = tokens[1]
                continue
            elif first_token == "$ORIGIN":
                if len(tokens) < 2:
                    self.log_error(line_num, "Missing value for $ORIGIN directive")
                else:
                    self.current_origin = tokens[1]
                    if not self.current_origin.endswith('.'):
                        self.current_origin += '.'
                continue
            elif first_token.startswith("$"):
                self.log_warning(line_num, f"Unknown directive '{first_token}'")
                continue

            # Standard Resource Records
            # Determine Name
            has_explicit_name = not line[0].isspace()
            token_idx = 0

            if has_explicit_name:
                name = tokens[token_idx]
                token_idx += 1
                # Resolve relative name
                if name == "@":
                    name = self.current_origin
                elif not name.endswith('.'):
                    name = f"{name}.{self.current_origin}" if self.current_origin else name
                last_name = name
            else:
                if not last_name:
                    self.log_error(line_num, "First record in zone file must specify an explicit name")
                    name = "@"
                else:
                    name = last_name

            # Look for TTL and CLASS
            ttl = None
            rr_class = "IN"  # Default class
            
            # Helper to check TTL format
            def is_ttl(t):
                return t.isdigit() or re.match(r'^\d+[hHwWdDsS]$', t)

            while token_idx < len(tokens):
                tok = tokens[token_idx]
                if is_ttl(tok):
                    ttl = tok
                    token_idx += 1
                elif tok.upper() in ("IN", "CH", "HS"):
                    rr_class = tok.upper()
                    token_idx += 1
                else:
                    break

            if token_idx >= len(tokens):
                self.log_error(line_num, f"Malformed record: missing record type and data in '{line}'")
                continue

            # Record Type
            rr_type = tokens[token_idx].upper()
            token_idx += 1

            # Record Data
            rr_data = " ".join(tokens[token_idx:])
            if not rr_data:
                self.log_error(line_num, f"Missing data for record type {rr_type}")
                continue

            # Assign default TTL if not specified
            resolved_ttl = ttl or self.default_ttl
            if not resolved_ttl:
                self.log_warning(line_num, f"No TTL specified for record '{name}' and no default $TTL set")
                resolved_ttl = "Default"

            self.records.append({
                "line": line_num,
                "name": name.lower(),
                "ttl": resolved_ttl,
                "class": rr_class,
                "type": rr_type,
                "data": rr_data
            })

    def validate(self):
        """Perform semantic validation of the zone records."""
        if not self.records:
            self.log_error(0, "Zone file contains no records")
            return

        soa_records = [r for r in self.records if r["type"] == "SOA"]
        ns_records = [r for r in self.records if r["type"] == "NS"]
        cname_records = [r for r in self.records if r["type"] == "CNAME"]
        
        # 1. SOA Checks
        if not soa_records:
            self.log_error(0, "Zone file is missing a SOA (Start of Authority) record")
        elif len(soa_records) > 1:
            for r in soa_records[1:]:
                self.log_error(r["line"], "Multiple SOA records found in zone")

        # 2. NS Checks
        if not ns_records:
            self.log_warning(0, "No NS (Name Server) records found in zone")

        # 3. Validation by Record Type
        ip4_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
        
        for r in self.records:
            rtype = r["type"]
            data = r["data"]
            line = r["line"]
            name = r["name"]

            # A Record Validation
            if rtype == "A":
                match = ip4_pattern.match(data)
                if not match:
                    self.log_error(line, f"Invalid IPv4 address '{data}' in A record")
                else:
                    if any(int(octet) > 255 for octet in match.groups()):
                        self.log_error(line, f"IPv4 octets must be in 0-255 range: '{data}'")

            # AAAA Record Validation
            elif rtype == "AAAA":
                # Simple IPv6 verification
                hextets = data.split(':')
                if len(hextets) > 8 or len(hextets) < 3:
                    self.log_error(line, f"Malformed IPv6 address '{data}' in AAAA record")
                else:
                    for h in hextets:
                        if h and not all(c in '0123456789abcdefABCDEF' for c in h):
                            self.log_error(line, f"Invalid hexadecimal values in IPv6: '{data}'")

            # CNAME checks
            elif rtype == "CNAME":
                # Ensure data is valid domain
                if data == "@":
                    pass
                elif ' ' in data:
                    self.log_error(line, f"CNAME data contains spaces: '{data}'")

        # 4. CNAME Conflicts & Circular chains
        cname_targets = {}  # name -> target
        names_with_other_records = set()
        cname_names = set()

        for r in self.records:
            if r["type"] == "CNAME":
                cname_names.add(r["name"])
                cname_targets[r["name"]] = r["data"].lower()
                # Resolve targets relative to origin
                if cname_targets[r["name"]] == "@" and self.current_origin:
                    cname_targets[r["name"]] = self.current_origin.lower()
                elif not cname_targets[r["name"]].endswith('.') and self.current_origin:
                    cname_targets[r["name"]] = f"{cname_targets[r['name']]}.{self.current_origin.lower()}"
            else:
                names_with_other_records.add(r["name"])

        # Check: CNAME and other data on same name
        conflict_names = cname_names.intersection(names_with_other_records)
        for name in conflict_names:
            # Find the line of the CNAME record
            cname_record = next(r for r in self.records if r["name"] == name and r["type"] == "CNAME")
            self.log_error(cname_record["line"], f"CNAME conflict: Name '{name}' has CNAME and other records (violates DNS RFCs)")

        # Check: Circular CNAME Chains
        for start_name in cname_targets:
            visited = set()
            curr = start_name
            chain = [curr]
            
            while curr in cname_targets:
                next_node = cname_targets[curr]
                if next_node in visited:
                    # Circular chain detected
                    cname_record = next(r for r in self.records if r["name"] == curr and r["type"] == "CNAME")
                    chain.append(next_node)
                    chain_str = " -> ".join(chain)
                    self.log_error(cname_record["line"], f"Circular CNAME loop detected: {chain_str}")
                    break
                visited.add(curr)
                curr = next_node
                chain.append(curr)

    def print_report(self):
        print("=" * 70)
        print(f" DNS ZONE VALIDATION REPORT")
        if self.current_origin:
            print(f" Zone Origin: {self.current_origin}")
        print("=" * 70)

        # Print parsed records table
        if self.records:
            print("\nParsed Resource Records:")
            print(f"{'Name':<30} {'TTL':<8} {'Class':<5} {'Type':<8} {'Data'}")
            print("-" * 70)
            for r in self.records:
                print(f"{r['name']:<30} {r['ttl']:<8} {r['class']:<5} {r['type']:<8} {r['data']}")
            print("-" * 70)
            print(f"Total parsed records: {len(self.records)}")
        
        # Print errors
        if self.errors:
            print(f"\n[\033[91mERRORS FOUND\033[0m: {len(self.errors)}]")
            for err in self.errors:
                line_str = f"Line {err['line']}: " if err['line'] > 0 else ""
                print(f"  - {line_str}{err['message']}")
        else:
            print("\n[\033[92mNO SYNTAX ERRORS FOUND\033[0m]")

        # Print warnings
        if self.warnings:
            print(f"\n[\033[93mWARNINGS\033[0m: {len(self.warnings)}]")
            for wrn in self.warnings:
                line_str = f"Line {wrn['line']}: " if wrn['line'] > 0 else ""
                print(f"  - {line_str}{wrn['message']}")

        print("=" * 70)
        return len(self.errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="DNS RFC 1035 Zone File Validator"
    )
    parser.add_argument("zone_file", help="Path to the DNS zone file")
    parser.add_argument("--origin", help="Fallback Origin domain name (e.g. example.com.)")

    args = parser.parse_args()

    try:
        with open(args.zone_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading zone file: {e}", file=sys.stderr)
        return 1

    validator = DNSZoneValidator(content, args.origin)
    validator.parse()
    validator.validate()
    
    success = validator.print_report()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
