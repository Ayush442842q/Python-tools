#!/usr/bin/env python3
"""
BIND DNS Zone File Parser & Auditor

This tool parses standard BIND DNS zone files (RFC 1035) into structured JSON.
It handles $TTL and $ORIGIN directives, multi-line records (like SOA or TXT
enclosed in parentheses), relative hostname expansion, and performs static
sanity audits to catch common DNS configuration mistakes.

Requirements:
    - Pure Python 3 (no third-party dependencies)
"""

import os
import sys
import json
import re
import argparse

# ANSI Terminal Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'blue': '\033[34m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    """Wraps text in ANSI colors if output is a terminal"""
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

class DNSZoneParser:
    def __init__(self, default_origin=""):
        self.origin = default_origin
        self.default_ttl = 3600
        self.last_name = "@"
        self.records = []
        self.warnings = []

    def log_warning(self, line_num, message):
        self.warnings.append({
            "line": line_num,
            "message": message
        })

    def expand_name(self, name):
        """Expands hostnames based on current $ORIGIN"""
        if not name:
            return self.origin
        name = name.strip()
        if name == "@":
            return self.origin
        if name.endswith("."):
            return name  # Already fully qualified
        if self.origin:
            return f"{name}.{self.origin}"
        return name

    def preprocess_zone(self, content):
        """
        Preprocesses zone file by:
        1. Removing comments.
        2. Joining multi-line records enclosed in parentheses.
        """
        lines = []
        in_parentheses = False
        current_line = []
        
        for idx, line in enumerate(content.splitlines(), 1):
            # Remove inline comments (careful with escaped semicolons inside TXT, but standard BIND splits on ;)
            # Simplification: split on ';' but ignore semicolons inside quotes
            # For robustness, we do a basic state machine split on semicolon
            clean_line = ""
            in_quote = False
            for char in line:
                if char == '"':
                    in_quote = not in_quote
                elif char == ';' and not in_quote:
                    break
                clean_line += char
            
            clean_line = clean_line.strip()
            if not clean_line:
                continue
                
            # Handle parentheses
            for char in clean_line:
                if char == '(':
                    in_parentheses = True
                    current_line.append(' ')
                elif char == ')':
                    in_parentheses = False
                    current_line.append(' ')
                else:
                    current_line.append(char)
                    
            if not in_parentheses:
                joined = "".join(current_line).strip()
                # Squash whitespace
                squashed = re.sub(r'\s+', ' ', joined)
                if squashed:
                    # Keep track of original line index for debugging/warning
                    lines.append((idx, squashed))
                current_line = []
            else:
                current_line.append(' ')
                
        return lines

    def parse(self, content):
        preprocessed = self.preprocess_zone(content)
        
        # Regex to parse standard records:
        # name [ttl] [class] type value...
        # Since class (IN) and ttl can appear in any order or be omitted:
        # We parse token by token.
        for line_num, line in preprocessed:
            tokens = line.split()
            if not tokens:
                continue
                
            first_token = tokens[0].upper()
            
            # Check for directives
            if first_token == "$ORIGIN":
                if len(tokens) > 1:
                    self.origin = tokens[1]
                    if not self.origin.endswith("."):
                        self.origin += "."
                continue
            elif first_token == "$TTL":
                if len(tokens) > 1:
                    try:
                        self.default_ttl = int(tokens[1])
                    except ValueError:
                        # Could be 1d, 1h, etc.
                        self.default_ttl = self.parse_time_unit(tokens[1], line_num)
                continue
            elif first_token.startswith("$"):
                # Unknown directive
                self.log_warning(line_num, f"Unknown directive ignored: {tokens[0]}")
                continue
                
            # Normal record parsing
            # Determine if name is inherited or explicit
            if line[0].isspace():
                # Name is inherited from the last record
                name = self.last_name
                record_tokens = tokens
            else:
                name = tokens[0]
                self.last_name = name
                record_tokens = tokens[1:]
                
            # Defaults
            ttl = self.default_ttl
            rr_class = "IN"
            rr_type = None
            value_tokens = []
            
            # Parse intermediate optional fields: TTL and CLASS
            # Standard classes: IN, CH, HS
            # Standard types: A, AAAA, CNAME, MX, TXT, NS, SOA, SRV, PTR, SPF, CAA, etc.
            idx = 0
            while idx < len(record_tokens):
                tok = record_tokens[idx]
                tok_upper = tok.upper()
                
                # Check if it is a TTL
                if tok.isdigit():
                    ttl = int(tok)
                    idx += 1
                    continue
                elif self.is_time_unit(tok):
                    ttl = self.parse_time_unit(tok, line_num)
                    idx += 1
                    continue
                    
                # Check if it is a Class
                if tok_upper in ("IN", "CH", "HS"):
                    rr_class = tok_upper
                    idx += 1
                    continue
                    
                # Otherwise, it must be the record type
                rr_type = tok_upper
                value_tokens = record_tokens[idx+1:]
                break
                
            if not rr_type:
                self.log_warning(line_num, f"Could not determine record type for line: '{line}'")
                continue
                
            value = " ".join(value_tokens)
            
            # Format value specific to type
            parsed_val = self.parse_record_value(rr_type, value_tokens, line_num)
            
            self.records.append({
                "line": line_num,
                "name": self.expand_name(name),
                "ttl": ttl,
                "class": rr_class,
                "type": rr_type,
                "value": parsed_val
            })
            
        self.audit_records()
        return {
            "origin": self.origin,
            "default_ttl": self.default_ttl,
            "records": self.records,
            "warnings": self.warnings
        }

    def is_time_unit(self, val):
        return bool(re.match(r'^\d+[WwDdHhMmSs]?$', val))

    def parse_time_unit(self, val, line_num):
        match = re.match(r'^(\d+)([WwDdHhMmSs])?$', val)
        if not match:
            self.log_warning(line_num, f"Invalid time unit '{val}', defaulting to 3600s")
            return 3600
        num = int(match.group(1))
        unit = match.group(2)
        if not unit:
            return num
        unit = unit.upper()
        multipliers = {
            'S': 1,
            'M': 60,
            'H': 3600,
            'D': 86400,
            'W': 604800
        }
        return num * multipliers.get(unit, 1)

    def parse_record_value(self, rr_type, tokens, line_num):
        """Parses resource record values into structured dicts where possible"""
        val_str = " ".join(tokens)
        if rr_type == "SOA":
            # PrimaryNS AdminEmail Serial Refresh Retry Expire Minimum
            if len(tokens) >= 7:
                return {
                    "mname": self.expand_name(tokens[0]),
                    "rname": tokens[1], # email (e.g. hostmaster.example.com)
                    "serial": int(tokens[2]),
                    "refresh": int(tokens[3]),
                    "retry": int(tokens[4]),
                    "expire": int(tokens[5]),
                    "minimum": int(tokens[6])
                }
            else:
                self.log_warning(line_num, "Malformed SOA record value")
                return {"raw": val_str}
        elif rr_type == "MX":
            # Priority Target
            if len(tokens) >= 2:
                try:
                    return {
                        "preference": int(tokens[0]),
                        "exchange": self.expand_name(tokens[1])
                    }
                except ValueError:
                    self.log_warning(line_num, f"Invalid MX preference value '{tokens[0]}'")
            return {"raw": val_str}
        elif rr_type == "SRV":
            # Priority Weight Port Target
            if len(tokens) >= 4:
                try:
                    return {
                        "priority": int(tokens[0]),
                        "weight": int(tokens[1]),
                        "port": int(tokens[2]),
                        "target": self.expand_name(tokens[3])
                    }
                except ValueError:
                    self.log_warning(line_num, "Invalid SRV record integer values")
            return {"raw": val_str}
        elif rr_type in ("CNAME", "NS", "PTR"):
            return self.expand_name(val_str)
        elif rr_type == "TXT":
            # TXT can contain quotes. Merge them back
            return val_str.strip('"')
        elif rr_type == "CAA":
            # Flags Tag Value
            if len(tokens) >= 3:
                return {
                    "flags": int(tokens[0]),
                    "tag": tokens[1],
                    "value": " ".join(tokens[2:]).strip('"')
                }
            return {"raw": val_str}
        return val_str

    def audit_records(self):
        """Performs static analysis to detect common DNS configuration flaws"""
        soa_count = 0
        names_seen = set()
        cname_records = {} # name -> line
        other_records = {} # name -> list of types and lines
        
        for r in self.records:
            name = r["name"]
            rtype = r["type"]
            line = r["line"]
            
            # SOA checks
            if rtype == "SOA":
                soa_count += 1
                if soa_count > 1:
                    self.log_warning(line, "Duplicate SOA record detected. A zone must have exactly one SOA record.")
                    
            # Track CNAME and other records for collision audits
            if rtype == "CNAME":
                cname_records[name] = line
            else:
                other_records.setdefault(name, []).append((rtype, line))
                
            # MX/NS targets should end with dot (absolute) to avoid origin inheritance
            if rtype == "MX" and isinstance(r["value"], dict):
                exch = r["value"].get("exchange", "")
                if not exch.endswith("."):
                    self.log_warning(line, f"MX exchange target '{exch}' does not end with a dot. It will resolve to '{self.expand_name(exch)}'. Check if this is intended.")
            elif rtype == "NS":
                ns_target = r["value"]
                if isinstance(ns_target, str) and not ns_target.endswith("."):
                    self.log_warning(line, f"NS target server '{ns_target}' does not end with a dot. It will resolve to '{self.expand_name(ns_target)}'.")
            elif rtype == "CNAME":
                cname_target = r["value"]
                if isinstance(cname_target, str) and not cname_target.endswith("."):
                    self.log_warning(line, f"CNAME target '{cname_target}' does not end with a dot. It will resolve to '{self.expand_name(cname_target)}'.")
                    
        # Check for CNAME collision (RFC 1912: CNAME cannot coexist with other data for same label)
        for name, cname_line in cname_records.items():
            if name in other_records:
                for rtype, other_line in other_records[name]:
                    self.log_warning(cname_line, f"CNAME collision at label '{name}': coexists with {rtype} record on line {other_line}. This violates RFC 1912.")

        if soa_count == 0:
            self.warnings.append({"line": 0, "message": "Missing SOA record. Standard BIND zone files require an SOA record."})

def main():
    parser = argparse.ArgumentParser(description="Parse standard DNS BIND zone files and audit them for errors.")
    parser.add_argument("zone_file", help="Path to the BIND zone file")
    parser.add_argument("-o", "--origin", default="", help="Fallback or default $ORIGIN domain (e.g. example.com.)")
    parser.add_argument("-j", "--json", action="store_true", help="Output raw parsed JSON data")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.zone_file):
        print(colorize(f"Error: File not found: {args.zone_file}", 'red'), file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.zone_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(colorize(f"Error reading file: {e}", 'red'), file=sys.stderr)
        sys.exit(1)
        
    dns_parser = DNSZoneParser(default_origin=args.origin)
    result = dns_parser.parse(content)
    
    if args.json:
        print(json.dumps(result, indent=2))
        return
        
    # Pretty-print CLI summary
    print(colorize(f"=== DNS Zone File Report: {args.zone_file} ===", 'bold'))
    print(f"Origin:       {colorize(result['origin'] or '(not defined)', 'cyan')}")
    print(f"Default TTL:  {colorize(str(result['default_ttl']) + 's', 'cyan')}")
    print(f"Total Records: {colorize(len(result['records']), 'green')}")
    print()
    
    print(colorize("--- Records List ---", 'bold'))
    # Print formatted table
    print(f"{'Line':<6} {'Name':<30} {'Type':<6} {'TTL':<8} {'Value'}")
    print("-" * 80)
    for r in result["records"]:
        val = r["value"]
        if isinstance(val, dict):
            val_str = ", ".join(f"{k}={v}" for k, v in val.items())
        else:
            val_str = str(val)
        print(f"{r['line']:<6} {r['name']:<30} {r['type']:<6} {r['ttl']:<8} {val_str}")
        
    print()
    if result["warnings"]:
        print(colorize(f"--- Sanity Audit Warnings ({len(result['warnings'])}) ---", 'red'))
        for w in result["warnings"]:
            line_str = f"Line {w['line']}:" if w['line'] > 0 else "Global:"
            print(f"{colorize(line_str, 'yellow')} {w['message']}")
    else:
        print(colorize("--- Sanity Audit: Pass (0 warnings) ---", 'green'))

if __name__ == "__main__":
    main()
