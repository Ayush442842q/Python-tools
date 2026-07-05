#!/usr/bin/env python3
"""
INI & CFG Configuration Linter & Security Auditor
--------------------------------------------------
Lints, security audits, and converts standard INI/CFG configuration files.
Scans for duplicate section keys, syntax violations, insecure protocol URLs
(HTTP, FTP), plain-text secrets, and converts INI configs to JSON or YAML.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import configparser
import argparse
from typing import List, Dict, Any, Tuple

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def lint_ini_file(filepath: str) -> Dict[str, Any]:
    findings = []
    sections_count = 0
    keys_count = 0

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Check raw line issues
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            line_str = line.strip()
            # Check for plaintext password or secret key
            if re.search(r'(?i)(password|secret|api_key|access_token)\s*=\s*["\']?[A-Za-z0-9_!@#$%^&*()]{6,}', line_str):
                if not re.search(r'(?i)(env|vault|placeholder|EXAMPLE|CHANGE_ME)', line_str):
                    findings.append({
                        "line": i,
                        "severity": "HIGH",
                        "issue": "Plaintext secret/password detected in configuration key",
                        "snippet": line_str[:60]
                    })
            # Check for unencrypted HTTP/FTP URLs
            if re.search(r'=\s*(http|ftp)://', line_str):
                findings.append({
                    "line": i,
                    "severity": "MEDIUM",
                    "issue": "Insecure unencrypted URL protocol (http:// or ftp://)",
                    "snippet": line_str[:60]
                })

        # Parse with ConfigParser
        config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        config.read_string(content, source=filepath)
        
        sections_count = len(config.sections())
        for sec in config.sections():
            for key, val in config.items(sec):
                keys_count += 1

    except configparser.DuplicateSectionError as e:
        findings.append({
            "line": 0,
            "severity": "HIGH",
            "issue": f"Duplicate section error: {e.section}",
            "snippet": str(e)
        })
    except configparser.DuplicateOptionError as e:
        findings.append({
            "line": 0,
            "severity": "HIGH",
            "issue": f"Duplicate key/option '{e.option}' in section [{e.section}]",
            "snippet": str(e)
        })
    except configparser.Error as e:
        findings.append({
            "line": 0,
            "severity": "CRITICAL",
            "issue": f"INI Syntax Parse Error: {str(e)}",
            "snippet": ""
        })
    except Exception as e:
        findings.append({
            "line": 0,
            "severity": "CRITICAL",
            "issue": f"File read error: {str(e)}",
            "snippet": ""
        })

    return {
        "file": filepath,
        "valid_ini": len([f for f in findings if f["severity"] == "CRITICAL"]) == 0,
        "sections_count": sections_count,
        "keys_count": keys_count,
        "findings": findings
    }


def ini_to_json(filepath: str) -> str:
    config = configparser.ConfigParser()
    config.read(filepath, encoding="utf-8")
    data = {sec: dict(config.items(sec)) for sec in config.sections()}
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="INI & CFG Configuration Linter & Security Auditor - Audit and convert INI configuration files."
    )
    parser.add_argument("target", help="INI/CFG file or directory to scan.")
    parser.add_argument("--json", action="store_true", help="Output audit report in JSON.")
    parser.add_argument("--to-json", action="store_true", help="Convert valid INI file to JSON output.")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Error: Target path '{args.target}' does not exist.{RESET}")
        sys.exit(1)

    if args.to_json and os.path.isfile(args.target):
        print(ini_to_json(args.target))
        return

    results = []
    if os.path.isdir(args.target):
        for root, _, files in os.walk(args.target):
            for file in files:
                if file.endswith((".ini", ".cfg", ".conf")):
                    results.append(lint_ini_file(os.path.join(root, file)))
    else:
        results.append(lint_ini_file(args.target))

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"{BOLD}{CYAN}=== INI / CFG Configuration Linter Report ==={RESET}")
    print(f"Target: {args.target}")
    print(f"Files Processed: {len(results)}\n")

    for res in results:
        status_str = f"{GREEN}[VALID]{RESET}" if res["valid_ini"] else f"{RED}[INVALID]{RESET}"
        print(f"File: {BOLD}{res['file']}{RESET} {status_str}")
        print(f"  Sections: {res['sections_count']}, Keys: {res['keys_count']}")
        
        if not res["findings"]:
            print(f"  {GREEN}[OK] Clean configuration! No security or syntax issues found.{RESET}\n")
        else:
            for item in res["findings"]:
                sev_color = RED if item["severity"] in ("HIGH", "CRITICAL") else YELLOW
                print(f"    Line {item['line']}: [{sev_color}{item['severity']}{RESET}] {item['issue']}")
                if item["snippet"]:
                    print(f"      Snippet: {item['snippet']}")
            print()


if __name__ == "__main__":
    main()
