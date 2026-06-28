#!/usr/bin/env python3
"""
dns_security_auditor.py - Comprehensive DNS & Domain Security Auditor
Performs DNS record queries (A, AAAA, MX, TXT, NS, SOA, CAA, DNSSEC/DS) using a pure Python DNS client
running over UDP (no third-party dependencies). Audits email security (SPF, DMARC), CAA, and DNSSEC policies,
providing a security scorecard and structured Markdown/JSON reports.
"""

import sys
import socket
import struct
import argparse
import json
import re

# Record Type mapping
TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5
TYPE_SOA = 6
TYPE_MX = 15
TYPE_TXT = 16
TYPE_AAAA = 28
TYPE_DS = 43
TYPE_CAA = 257

TYPE_NAMES = {
    TYPE_A: "A",
    TYPE_NS: "NS",
    TYPE_CNAME: "CNAME",
    TYPE_SOA: "SOA",
    TYPE_MX: "MX",
    TYPE_TXT: "TXT",
    TYPE_AAAA: "AAAA",
    TYPE_DS: "DS",
    TYPE_CAA: "CAA"
}

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

# Pure Python DNS Query Implementation
def build_dns_query(domain, record_type):
    """Builds a raw DNS query packet."""
    transaction_id = 0x1234
    flags = 0x0100  # Standard query with recursion desired
    qdcount = 1     # One question
    ancount = 0
    nscount = 0
    arcount = 0
    
    header = struct.pack("!HHHHHH", transaction_id, flags, qdcount, ancount, nscount, arcount)
    
    # Encode domain name
    qname = b""
    for part in domain.split("."):
        if not part:
            continue
        qname += bytes([len(part)]) + part.encode("utf-8")
    qname += b"\x00"
    
    question = qname + struct.pack("!HH", record_type, 1)  # Type, Class (1 = IN)
    return header + question

def parse_dns_name(packet, offset):
    """Parses a DNS name at offset, supporting compression pointers."""
    labels = []
    original_offset = offset
    jumped = False
    
    while True:
        length = packet[offset]
        if length == 0:
            offset += 1
            break
            
        if (length & 0xC0) == 0xC0:
            # Pointer compression
            pointer = struct.unpack("!H", packet[offset:offset+2])[0] & 0x3FFF
            if not jumped:
                original_offset = offset + 2
                jumped = True
            offset = pointer
            continue
            
        offset += 1
        labels.append(packet[offset:offset+length].decode("utf-8", errors="replace"))
        offset += length
        
    return ".".join(labels), (original_offset if jumped else offset)

def parse_dns_response(packet, record_type):
    """Parses a raw DNS response packet and extracts records of record_type."""
    if len(packet) < 12:
        return []
        
    header = packet[:12]
    transaction_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", header)
    
    # Check RCODE (error code in last 4 bits of flags)
    rcode = flags & 0x000F
    if rcode != 0:
        return []
        
    offset = 12
    # Skip questions section
    for _ in range(qdcount):
        _, offset = parse_dns_name(packet, offset)
        offset += 4  # Type (2 bytes), Class (2 bytes)
        
    records = []
    # Parse answers section
    for _ in range(ancount):
        name, offset = parse_dns_name(packet, offset)
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", packet[offset:offset+10])
        offset += 10
        
        rdata_bytes = packet[offset:offset+rdlength]
        
        # Parse based on record type
        rdata_parsed = None
        if rtype == TYPE_A and rdlength == 4:
            rdata_parsed = socket.inet_ntop(socket.AF_INET, rdata_bytes)
        elif rtype == TYPE_AAAA and rdlength == 16:
            rdata_parsed = socket.inet_ntop(socket.AF_INET6, rdata_bytes)
        elif rtype == TYPE_CNAME or rtype == TYPE_NS:
            rdata_parsed, _ = parse_dns_name(packet, offset)
        elif rtype == TYPE_MX:
            preference = struct.unpack("!H", rdata_bytes[:2])[0]
            exchange, _ = parse_dns_name(packet, offset + 2)
            rdata_parsed = f"{preference} {exchange}"
        elif rtype == TYPE_TXT:
            # TXT record can have multiple character strings
            strings = []
            txt_offset = 0
            while txt_offset < rdlength:
                str_len = rdata_bytes[txt_offset]
                txt_offset += 1
                strings.append(rdata_bytes[txt_offset:txt_offset+str_len].decode("utf-8", errors="replace"))
                txt_offset += str_len
            rdata_parsed = "".join(strings)
        elif rtype == TYPE_CAA:
            flags_caa = rdata_bytes[0]
            tag_len = rdata_bytes[1]
            tag = rdata_bytes[2:2+tag_len].decode("utf-8", errors="replace")
            value = rdata_bytes[2+tag_len:].decode("utf-8", errors="replace")
            rdata_parsed = f"{flags_caa} {tag} \"{value}\""
        elif rtype == TYPE_DS:
            if rdlength >= 4:
                key_tag, algo, digest_type = struct.unpack("!HBB", rdata_bytes[:4])
                digest = rdata_bytes[4:].hex()
                rdata_parsed = f"{key_tag} {algo} {digest_type} {digest}"
            else:
                rdata_parsed = rdata_bytes.hex()
        else:
            rdata_parsed = rdata_bytes.hex()
            
        if rtype == record_type:
            records.append({
                "name": name,
                "type": TYPE_NAMES.get(rtype, str(rtype)),
                "ttl": ttl,
                "data": rdata_parsed
            })
            
        offset += rdlength
        
    return records

def query_dns(domain, record_type, dns_server="1.1.1.1"):
    """Sends a DNS query over UDP and returns parsed records."""
    query = build_dns_query(domain, record_type)
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.5)
            s.sendto(query, (dns_server, 53))
            response, _ = s.recvfrom(4096)
            return parse_dns_response(response, record_type)
    except (socket.timeout, OSError):
        return []

# Security Auditing Logics
def audit_spf(spf_record):
    """Audits SPF record for configuration vulnerabilities."""
    score_penalty = 0
    warnings = []
    
    if not spf_record:
        return 25, ["SPF record is missing. Senders cannot be validated, increasing spoofing risk."]
        
    if "+all" in spf_record:
        score_penalty += 25
        warnings.append("Critical: SPF has '+all' directive, allowing anyone in the world to spoof email from this domain.")
    elif "?all" in spf_record:
        score_penalty += 10
        warnings.append("Low: SPF has '?all' (neutral) policy. It is recommended to use '~all' (softfail) or '-all' (hardfail).")
    elif "~all" in spf_record:
        pass # Softfail is common and acceptable with DMARC
    elif "-all" in spf_record:
        pass # Hardfail is the most secure
    else:
        score_penalty += 10
        warnings.append("Warning: SPF record lacks an explicit 'all' directive at the end (e.g. -all or ~all).")
        
    # Check lookup count limits (DNS SPF lookup limit is 10)
    lookups = spf_record.count("include:") + spf_record.count("mx") + spf_record.count("a") + spf_record.count("exists") + spf_record.count("redirect")
    if lookups > 10:
        score_penalty += 15
        warnings.append(f"Warning: SPF record requires {lookups} DNS lookups, which exceeds the RFC limit of 10. Resolvers may ignore it.")
        
    return max(0, 100 - score_penalty), warnings

def audit_dmarc(dmarc_record):
    """Audits DMARC record for security strength."""
    score_penalty = 0
    warnings = []
    
    if not dmarc_record:
        return 0, ["Critical: DMARC record is missing. No policy defined for handling spoofed emails."]
        
    # Parse tags
    tags = {}
    for item in dmarc_record.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            tags[k.strip().lower()] = v.strip().lower()
            
    policy = tags.get("p")
    if not policy:
        score_penalty += 40
        warnings.append("Critical: DMARC record missing the policy ('p=') tag.")
    elif policy == "none":
        score_penalty += 20
        warnings.append("Medium: DMARC policy is set to 'p=none' (monitoring only). Change to 'quarantine' or 'reject' to block spoofed emails.")
    elif policy == "quarantine":
        # Safe quarantine policy
        pass
    elif policy == "reject":
        # Strongest reject policy
        pass
        
    # Check reporting
    if "rua" not in tags:
        score_penalty += 10
        warnings.append("Low: DMARC aggregate reports destination ('rua=') tag is missing. You will not receive activity reports.")
        
    return max(0, 100 - score_penalty), warnings

def perform_audit(domain, dns_server="1.1.1.1"):
    """Runs a complete DNS audit on the target domain."""
    results = {}
    
    print(f"Auditing domain: {BOLD}{domain}{RESET} using resolver {dns_server}...")
    
    # 1. Fetch records
    results["A"] = query_dns(domain, TYPE_A, dns_server)
    results["AAAA"] = query_dns(domain, TYPE_AAAA, dns_server)
    results["MX"] = query_dns(domain, TYPE_MX, dns_server)
    results["TXT"] = query_dns(domain, TYPE_TXT, dns_server)
    results["NS"] = query_dns(domain, TYPE_NS, dns_server)
    results["SOA"] = query_dns(domain, TYPE_SOA, dns_server)
    results["CAA"] = query_dns(domain, TYPE_CAA, dns_server)
    results["DS"] = query_dns(domain, TYPE_DS, dns_server)
    
    # DMARC query on _dmarc sub-domain
    results["DMARC"] = query_dns(f"_dmarc.{domain}", TYPE_TXT, dns_server)
    
    # 2. Extract specific records
    # Find SPF record in TXT
    spf_rec = None
    for r in results["TXT"]:
        if r["data"].startswith("v=spf1"):
            spf_rec = r["data"]
            break
            
    dmarc_rec = None
    for r in results["DMARC"]:
        if r["data"].startswith("v=DMARC1"):
            dmarc_rec = r["data"]
            break
            
    # 3. Analyze Security Components
    spf_score, spf_warns = audit_spf(spf_rec)
    dmarc_score, dmarc_warns = audit_dmarc(dmarc_rec)
    
    dnssec_enabled = len(results["DS"]) > 0
    caa_configured = len(results["CAA"]) > 0
    mx_configured = len(results["MX"]) > 0
    
    # Overall Score Calculation
    total_score = 0
    score_weights = {
        "spf": (spf_score, 0.30),
        "dmarc": (dmarc_score, 0.40),
        "dnssec": (100 if dnssec_enabled else 30, 0.15),
        "caa": (100 if caa_configured else 50, 0.10),
        "mx": (100 if mx_configured else 0, 0.05)
    }
    
    for _, (score, weight) in score_weights.items():
        total_score += score * weight
        
    audit_data = {
        "domain": domain,
        "score": int(total_score),
        "dnssec_enabled": dnssec_enabled,
        "caa_configured": caa_configured,
        "mx_configured": mx_configured,
        "spf": {
            "record": spf_rec,
            "score": spf_score,
            "warnings": spf_warns
        },
        "dmarc": {
            "record": dmarc_rec,
            "score": dmarc_score,
            "warnings": dmarc_warns
        },
        "records": {
            "A": [r["data"] for r in results["A"]],
            "AAAA": [r["data"] for r in results["AAAA"]],
            "MX": [r["data"] for r in results["MX"]],
            "NS": [r["data"] for r in results["NS"]],
            "TXT": [r["data"] for r in results["TXT"]],
            "CAA": [r["data"] for r in results["CAA"]],
            "DS": [r["data"] for r in results["DS"]],
            "SOA": [r["data"] for r in results["SOA"]]
        }
    }
    
    return audit_data

def print_audit_report(data):
    """Outputs the audit data to the terminal with beautiful formatting."""
    print("=" * 60)
    print(f"{BOLD}{CYAN}DNS Security Audit Report for: {data['domain']}{RESET}")
    print("=" * 60)
    
    # Print Score
    score = data["score"]
    if score >= 90:
        color = GREEN
        grade = "A (Excellent)"
    elif score >= 75:
        color = YELLOW
        grade = "B (Good)"
    elif score >= 50:
        color = YELLOW
        grade = "C (Fair)"
    else:
        color = RED
        grade = "F (Poor/Vulnerable)"
        
    print(f"Overall Security Score: {BOLD}{color}{score}/100{RESET} - Grade: {BOLD}{color}{grade}{RESET}\n")
    
    # DNSSEC & CAA Checks
    print(f"DNSSEC (Domain Signer DS):   {GREEN}ENABLED{RESET}" if data["dnssec_enabled"] else f"DNSSEC (Domain Signer DS):   {RED}DISABLED{RESET} (Vulnerable to cache poisoning/spoofing)")
    print(f"CAA Records Configured:      {GREEN}YES{RESET}" if data["caa_configured"] else f"CAA Records Configured:      {YELLOW}NO{RESET} (Any CA can issue certificates for this domain)")
    print(f"MX (Mail Server) Records:    {GREEN}YES{RESET}" if data["mx_configured"] else f"MX (Mail Server) Records:    {YELLOW}NO{RESET} (No mail servers configured)")
    print("-" * 60)
    
    # SPF Section
    print(f"{BOLD}1. Sender Policy Framework (SPF):{RESET}")
    if data["spf"]["record"]:
        print(f"   Record: {CYAN}{data['spf']['record']}{RESET}")
        print(f"   Score:  {data['spf']['score']}/100")
        for w in data["spf"]["warnings"]:
            print(f"   {YELLOW}[WARNING]{RESET} {w}")
    else:
        print(f"   {RED}[VULNERABLE]{RESET} SPF record is missing.")
    print()
    
    # DMARC Section
    print(f"{BOLD}2. Domain-based Message Authentication (DMARC):{RESET}")
    if data["dmarc"]["record"]:
        print(f"   Record: {CYAN}{data['dmarc']['record']}{RESET}")
        print(f"   Score:  {data['dmarc']['score']}/100")
        for w in data["dmarc"]["warnings"]:
            print(f"   {YELLOW}[WARNING]{RESET} {w}")
    else:
        print(f"   {RED}[VULNERABLE]{RESET} DMARC record is missing.")
    print()
    
    # Raw Records Summary
    print(f"{BOLD}3. Query Record Counts:{RESET}")
    for rtype, records in data["records"].items():
        if records:
            print(f"   - {rtype:<5}: {len(records)} records found")
            for r in records[:3]:  # Show first 3 for spacing
                print(f"     * {r}")
            if len(records) > 3:
                print(f"     * ... ({len(records) - 3} more)")
                
    print("=" * 60)

def save_markdown_report(data, filename):
    """Exports audit report as a clean Markdown file."""
    score = data["score"]
    status_str = "Clean" if score >= 90 else ("Warn" if score >= 60 else "Vulnerable")
    
    md_content = f"""# DNS Security Audit Report: {data['domain']}

Generated on: {data['records']['SOA'][0].split()[1] if data['records']['SOA'] else 'N/A'}
Security Score: **{score}/100** ({status_str})

## Summary
- **DNSSEC**: {"Enabled" if data["dnssec_enabled"] else "Disabled (Recommended to enable at registrar)"}
- **CAA Configured**: {"Yes" if data["caa_configured"] else "No (Recommended to set up CAA to restrict certificate issuance)"}
- **MX Redundancy**: {"Yes" if data["mx_configured"] else "No"}

## SPF Security Auditing
- **Record**: `{data['spf']['record'] if data['spf']['record'] else 'Missing'}`
- **Score**: {data['spf']['score']}/100
### Findings
"""
    if data['spf']['warnings']:
        for w in data['spf']['warnings']:
            md_content += f"- ⚠️ {w}\n"
    else:
        md_content += "- ✅ SPF record configuration is secure.\n"
        
    md_content += f"""
## DMARC Security Auditing
- **Record**: `{data['dmarc']['record'] if data['dmarc']['record'] else 'Missing'}`
- **Score**: {data['dmarc']['score']}/100
### Findings
"""
    if data['dmarc']['warnings']:
        for w in data['dmarc']['warnings']:
            md_content += f"- ⚠️ {w}\n"
    else:
        md_content += "- ✅ DMARC record configuration is secure.\n"

    md_content += "\n## Discovered DNS Records\n"
    for rtype, records in data["records"].items():
        if records:
            md_content += f"### {rtype} Records ({len(records)})\n"
            for r in records:
                md_content += f"- `{r}`\n"
            md_content += "\n"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"Saved Markdown report to: {filename}")
    except Exception as e:
        print(f"Error saving Markdown: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="DNS security audit tool mapping SPF, DMARC, DNSSEC, and CAA configurations."
    )
    parser.add_argument("domain", help="Target domain name to audit (e.g. google.com)")
    parser.add_argument(
        "-s", "--server", 
        default="1.1.1.1", 
        help="DNS resolver server IP to query (default: 1.1.1.1)"
    )
    parser.add_argument(
        "--json", 
        help="Export results as JSON file"
    )
    parser.add_argument(
        "--markdown", 
        help="Export results as Markdown report file"
    )
    
    args = parser.parse_args()
    
    # Perform audit
    try:
        data = perform_audit(args.domain, args.server)
    except Exception as e:
        print(f"Audit failed: {e}", file=sys.stderr)
        sys.exit(1)
        
    print_audit_report(data)
    
    if args.json:
        try:
            with open(args.json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Saved JSON data to: {args.json}")
        except Exception as e:
            print(f"Error saving JSON: {e}", file=sys.stderr)
            
    if args.markdown:
        save_markdown_report(data, args.markdown)

if __name__ == "__main__":
    main()
