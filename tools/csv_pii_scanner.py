#!/usr/bin/env python3
"""
CSV Sensitive Data & PII (Personally Identifiable Information) Scanner

Scans CSV datasets to detect sensitive data patterns (Emails, Phone numbers, SSNs,
Credit Cards, IP Addresses, API Keys/JWTs, Passwords, etc.), computes column-level
risk scores, and optionally outputs a masked/anonymized copy of the dataset.

Usage:
    python csv_pii_scanner.py [csv_file] [options]
"""

import os
import sys
import csv
import re
import argparse
import json
from typing import Dict, List, Tuple

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Regex PII patterns
PII_PATTERNS = {
    "Email": (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), 0.9, "*****@***.***"),
    "Phone_Number": (re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), 0.8, "***-***-****"),
    "SSN": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 1.0, "XXX-XX-XXXX"),
    "Credit_Card": (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), 1.0, "****-****-****-****"),
    "IPv4": (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"), 0.6, "***.***.***.***"),
    "API_Key": (re.compile(r"\b(sk_live_[0-9a-zA-Z]{24}|AKIA[0-9A-Z]{16}|api[_-]?key[_-]?[0-9a-zA-Z]{16,})\b", re.IGNORECASE), 1.0, "[REDACTED_API_KEY]"),
    "JWT_Token": (re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"), 0.95, "[REDACTED_JWT]"),
    "US_ZipCode": (re.compile(r"\b\d{5}(-\d{4})?\b"), 0.4, "XXXXX"),
}


def mask_string(val: str, pattern_key: str) -> str:
    """Masks value based on detected pattern key."""
    if pattern_key in PII_PATTERNS:
        regex, _, mask_template = PII_PATTERNS[pattern_key]
        return regex.sub(mask_template, val)
    return "[REDACTED]"


def scan_csv_file(file_path: str, max_rows: int = 10000) -> Tuple[List[str], Dict[str, Dict[str, float]], List[Dict]]:
    """
    Scans CSV and returns (headers, column_stats, sample_matches).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{file_path}' not found.")

    headers = []
    column_matches: Dict[str, Dict[str, int]] = {}
    row_count = 0
    sample_matches = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return [], {}, []

        column_matches = {h: {p: 0 for p in PII_PATTERNS} for h in headers}

        for row_idx, row in enumerate(reader, 1):
            row_count += 1
            if row_count > max_rows:
                break

            for col_idx, val in enumerate(row):
                if col_idx >= len(headers):
                    continue
                col_name = headers[col_idx]
                val_str = str(val).strip()

                if not val_str:
                    continue

                for ptype, (regex, weight, _) in PII_PATTERNS.items():
                    if regex.search(val_str):
                        column_matches[col_name][ptype] += 1
                        if len(sample_matches) < 20:
                            sample_matches.append({
                                "row": row_idx,
                                "column": col_name,
                                "type": ptype,
                                "original": val_str[:30] + ("..." if len(val_str) > 30 else ""),
                                "masked": mask_string(val_str, ptype)[:30]
                            })

    # Compute risk scores
    column_stats = {}
    for col_name in headers:
        col_type_counts = column_matches[col_name]
        total_pii_hits = sum(col_type_counts.values())
        
        # Risk score calculation based on hit density and pattern weights
        score = 0.0
        if row_count > 0:
            weighted_hits = sum(count * PII_PATTERNS[ptype][1] for ptype, count in col_type_counts.items())
            score = min(100.0, round((weighted_hits / row_count) * 100, 2))

        column_stats[col_name] = {
            "risk_score": score,
            "total_hits": total_pii_hits,
            "patterns": {p: cnt for p, cnt in col_type_counts.items() if cnt > 0}
        }

    return headers, column_stats, sample_matches


def generate_masked_csv(input_path: str, output_path: str):
    """Generates anonymized CSV copy with PII masked."""
    with open(input_path, "r", encoding="utf-8", errors="ignore") as infile, \
         open(output_path, "w", newline="", encoding="utf-8") as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        try:
            headers = next(reader)
            writer.writerow(headers)
        except StopIteration:
            return

        for row in reader:
            masked_row = []
            for val in row:
                masked_val = str(val)
                for ptype in PII_PATTERNS:
                    masked_val = mask_string(masked_val, ptype)
                masked_row.append(masked_val)
            writer.writerow(masked_row)

    print(f"{GREEN}Masked output saved to '{output_path}'.{RESET}")


def main():
    parser = argparse.ArgumentParser(description="CSV Sensitive Data & PII (Personally Identifiable Information) Scanner")
    parser.add_argument("csv_file", help="Path to CSV file to scan")
    parser.add_argument("--max-rows", type=int, default=10000, help="Maximum rows to scan (default: 10000)")
    parser.add_argument("--mask-output", "-m", help="Output path to save masked CSV dataset")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")

    args = parser.parse_args()

    try:
        headers, column_stats, sample_matches = scan_csv_file(args.csv_file, args.max_rows)
    except Exception as e:
        print(f"{RED}Error scanning CSV file: {e}{RESET}")
        sys.exit(1)

    if args.json:
        data = {
            "file": args.csv_file,
            "columns": column_stats,
            "sample_matches": sample_matches
        }
        print(json.dumps(data, indent=2))
        sys.exit(0)

    print(f"\n{BOLD}{CYAN}=== CSV PII & Sensitive Data Scan Report ==={RESET}")
    print(f"File: {BOLD}{args.csv_file}{RESET}\n")

    print(f"{'Column Name':<30} | {'Risk Score':<12} | {'PII Patterns Found'}")
    print("-" * 75)

    high_risk_found = False
    for col in headers:
        stats = column_stats[col]
        score = stats["risk_score"]
        patterns_str = ", ".join(f"{p}:{cnt}" for p, cnt in stats["patterns"].items()) or "None"

        if score >= 50.0:
            score_str = f"{RED}{score:>5.1f}% HIGH{RESET}"
            high_risk_found = True
        elif score > 0:
            score_str = f"{YELLOW}{score:>5.1f}% MED {RESET}"
        else:
            score_str = f"{GREEN}  0.0% CLEAN{RESET}"

        print(f"{col[:30]:<30} | {score_str:<21} | {patterns_str}")

    if sample_matches:
        print(f"\n{BOLD}{YELLOW}Sample PII Detections ({len(sample_matches)}):{RESET}")
        for match in sample_matches[:5]:
            print(f"  Row {match['row']} [{match['column']}] ({match['type']}): '{match['original']}' -> '{match['masked']}'")

    print()
    if high_risk_found:
        print(f"{RED}WARNING: Sensitive PII detected in dataset! Consider masking before sharing.{RESET}")

    if args.mask_output:
        generate_masked_csv(args.csv_file, args.mask_output)


if __name__ == "__main__":
    main()
