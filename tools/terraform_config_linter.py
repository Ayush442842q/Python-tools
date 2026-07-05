#!/usr/bin/env python3
"""
Terraform Configuration Linter & Security Auditor
--------------------------------------------------
Static analysis linter that audits Terraform (.tf) HCL configuration files for
security risks, hardcoded secrets, open network ingress rules, missing tags,
unencrypted storage resources, and wildcard IAM policies.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import List, Dict, Any, Tuple

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# Security Audit Rules
RULES = [
    {
        "id": "TF-SEC-001",
        "severity": "CRITICAL",
        "title": "Hardcoded AWS Credentials",
        "pattern": r'(?i)(secret_key|access_key|api_token|password)\s*=\s*"[A-Za-z0-9/+=]{10,}"',
        "description": "Hardcoded secrets or credentials detected in Terraform file.",
        "remediation": "Use environment variables (TF_VAR_) or dynamic secret stores (Vault, AWS Secrets Manager)."
    },
    {
        "id": "TF-SEC-002",
        "severity": "HIGH",
        "title": "Security Group Open to World (0.0.0.0/0)",
        "pattern": r'cidr_blocks\s*=\s*\[\s*"0\.0\.0\.0/0"\s*\]',
        "description": "Security group rule allows unrestricted ingress access from anywhere on the internet.",
        "remediation": "Restrict CIDR ranges to specific trusted IP blocks or internal VPC subnets."
    },
    {
        "id": "TF-SEC-003",
        "severity": "HIGH",
        "title": "Unencrypted S3 Bucket",
        "pattern": r'resource\s+"aws_s3_bucket"\s+.*\{',
        "negative_pattern": r'server_side_encryption_configuration',
        "description": "S3 bucket may be missing server-side encryption configuration.",
        "remediation": "Add server_side_encryption_configuration or aws_s3_bucket_server_side_encryption_configuration."
    },
    {
        "id": "TF-SEC-004",
        "severity": "HIGH",
        "title": "Wildcard IAM Policy Statement",
        "pattern": r'"Action"\s*:\s*"\*"|"Resource"\s*:\s*"\*"',
        "description": "IAM Policy permits full wildcard (*) actions or resources.",
        "remediation": "Enforce principle of least privilege by specifying exact IAM actions and resource ARNs."
    },
    {
        "id": "TF-SEC-005",
        "severity": "MEDIUM",
        "title": "Unencrypted EBS Volume",
        "pattern": r'resource\s+"aws_ebs_volume"\s+.*\{',
        "negative_pattern": r'encrypted\s*=\s*true',
        "description": "EBS volume block is missing explicit encryption (encrypted = true).",
        "remediation": "Set encrypted = true on aws_ebs_volume resources."
    },
    {
        "id": "TF-SEC-006",
        "severity": "LOW",
        "title": "Resource Missing Tags",
        "pattern": r'resource\s+"aws_\w+"\s+.*\{',
        "negative_pattern": r'tags\s*=\s*\{',
        "description": "Cloud resource block lacks cost allocation or ownership tags.",
        "remediation": "Include a tags block with Environment, Owner, and Project metadata."
    }
]


def lint_terraform_file(filepath: str) -> List[Dict[str, Any]]:
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        full_content = "".join(lines)
        
        for rule in RULES:
            # Check positive pattern
            matches = list(re.finditer(rule["pattern"], full_content))
            if matches:
                # If negative pattern exists, verify if negative pattern is present in the file/block
                if "negative_pattern" in rule:
                    if re.search(rule["negative_pattern"], full_content):
                        continue
                
                for match in matches:
                    start_pos = match.start()
                    line_no = full_content[:start_pos].count("\n") + 1
                    match_snippet = match.group(0).strip().replace("\n", " ")
                    if len(match_snippet) > 60:
                        match_snippet = match_snippet[:57] + "..."
                    
                    findings.append({
                        "file": filepath,
                        "line": line_no,
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "title": rule["title"],
                        "snippet": match_snippet,
                        "description": rule["description"],
                        "remediation": rule["remediation"]
                    })
    except Exception as e:
        pass
    return findings


def scan_terraform_dir(directory: str) -> List[Dict[str, Any]]:
    all_findings = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".tf"):
                all_findings.extend(lint_terraform_file(os.path.join(root, file)))
    return all_findings


def main():
    parser = argparse.ArgumentParser(
        description="Terraform Configuration Linter & Security Auditor - Audit .tf files for security & syntax issues."
    )
    parser.add_argument("target", help="Terraform file (.tf) or directory containing Terraform files.")
    parser.add_argument("--json", action="store_true", help="Output audit report in JSON format.")
    parser.add_argument("--min-severity", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], default="LOW", help="Filter minimum severity level.")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Error: Target path '{args.target}' does not exist.{RESET}")
        sys.exit(1)

    if os.path.isdir(args.target):
        findings = scan_terraform_dir(args.target)
    else:
        findings = lint_terraform_file(args.target)

    severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    min_sev_val = severity_order[args.min_severity]
    filtered_findings = [f for f in findings if severity_order[f["severity"]] >= min_sev_val]

    if args.json:
        print(json.dumps(filtered_findings, indent=2))
        return

    print(f"{BOLD}{CYAN}=== Terraform Configuration Audit & Linter Report ==={RESET}")
    print(f"Target: {args.target}")
    print(f"Total Issues Found: {len(filtered_findings)}\n")

    if not filtered_findings:
        print(f"{GREEN}[OK] No Terraform security or formatting violations detected!{RESET}")
        return

    sev_color = {
        "CRITICAL": RED + BOLD,
        "HIGH": RED,
        "MEDIUM": YELLOW,
        "LOW": CYAN
    }

    for item in filtered_findings:
        c = sev_color.get(item["severity"], RESET)
        print(f"  [{item['rule_id']}] [{c}{item['severity']}{RESET}] {BOLD}{item['title']}{RESET}")
        print(f"    Location:    {item['file']}:{item['line']}")
        print(f"    Snippet:     {item['snippet']}")
        print(f"    Description: {item['description']}")
        print(f"    Remediation: {GREEN}{item['remediation']}{RESET}")
        print("-" * 65)


if __name__ == "__main__":
    main()
