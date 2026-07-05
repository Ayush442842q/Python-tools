#!/usr/bin/env python3
"""
Gitignore Coverage & Audit Analyzer
-----------------------------------
Scans project workspace directories to evaluate .gitignore coverage against tracked,
untracked, build artifacts, temporary log files, and sensitive credentials.
Calculates repository ignore metrics, flags unignored sensitive/generated files,
and suggests pattern rules to improve workspace cleanliness.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import fnmatch
import json
import argparse
from typing import List, Dict, Set, Any

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Sensitive or unwanted patterns that should usually be in .gitignore
RISKY_PATTERNS = [
    ("*.env*", "Environment variable secrets file"),
    ("*.pem", "Private key file"),
    ("*.key", "Cryptographic key file"),
    ("*.log", "Log file"),
    ("__pycache__", "Python bytecode cache directory"),
    ("*.pyc", "Python compiled bytecode"),
    (".DS_Store", "macOS system metadata file"),
    ("Thumbs.db", "Windows thumbnail database"),
    ("node_modules", "Node.js dependency directory"),
    (".idea/", "JetBrains IDE workspace directory"),
    (".vscode/", "VSCode workspace directory"),
    ("*.bak", "Backup temporary file"),
    ("*.tmp", "Temporary file"),
]


def load_gitignore_rules(root_dir: str) -> List[str]:
    rules = []
    gitignore_path = os.path.join(root_dir, ".gitignore")
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        rules.append(line)
        except Exception:
            pass
    return rules


def is_ignored(rel_path: str, rules: List[str]) -> bool:
    rel_path_posix = rel_path.replace("\\", "/")
    basename = os.path.basename(rel_path)
    
    for rule in rules:
        rule_clean = rule.strip("/")
        if fnmatch.fnmatch(rel_path_posix, rule) or fnmatch.fnmatch(basename, rule_clean):
            return True
        if rule.endswith("/") and rel_path_posix.startswith(rule_clean):
            return True
    return False


def analyze_workspace(target_dir: str) -> Dict[str, Any]:
    rules = load_gitignore_rules(target_dir)
    
    total_files = 0
    ignored_files = 0
    tracked_unignored_files = 0
    total_size = 0
    ignored_size = 0
    
    risky_unignored: List[Dict[str, str]] = []
    suggested_rules: Set[str] = set()

    for root, dirs, files in os.walk(target_dir):
        # Skip .git folder
        if ".git" in dirs:
            dirs.remove(".git")

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, target_dir)
            
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
                
            total_files += 1
            total_size += size
            
            ignored = is_ignored(rel_path, rules)
            if ignored:
                ignored_files += 1
                ignored_size += size
            else:
                tracked_unignored_files += 1
                # Check for risky patterns
                for pattern, desc in RISKY_PATTERNS:
                    if fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(rel_path.replace("\\", "/"), pattern):
                        risky_unignored.append({
                            "file": rel_path,
                            "pattern": pattern,
                            "description": desc
                        })
                        suggested_rules.add(pattern)

    coverage_pct = (ignored_files / total_files * 100) if total_files > 0 else 0.0

    return {
        "target": target_dir,
        "gitignore_exists": os.path.exists(os.path.join(target_dir, ".gitignore")),
        "active_rules_count": len(rules),
        "total_files": total_files,
        "ignored_files": ignored_files,
        "unignored_files": tracked_unignored_files,
        "coverage_percentage": round(coverage_pct, 2),
        "total_size_bytes": total_size,
        "ignored_size_bytes": ignored_size,
        "risky_unignored": risky_unignored,
        "suggested_rules": sorted(list(suggested_rules))
    }


def main():
    parser = argparse.ArgumentParser(
        description="Gitignore Coverage & Audit Analyzer - Evaluate .gitignore completeness & flag risky files."
    )
    parser.add_argument("target", nargs="?", default=".", help="Target directory to analyze (default: current directory).")
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")

    args = parser.parse_args()
    target_dir = os.path.abspath(args.target)

    if not os.path.isdir(target_dir):
        print(f"{RED}Error: Directory '{target_dir}' does not exist.{RESET}")
        sys.exit(1)

    result = analyze_workspace(target_dir)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"{BOLD}{CYAN}=== Gitignore Workspace Audit & Coverage Report ==={RESET}")
    print(f"Target Directory: {result['target']}")
    print(f".gitignore Present: {GREEN if result['gitignore_exists'] else RED}{result['gitignore_exists']}{RESET}")
    print(f"Active Rules:      {result['active_rules_count']}")
    print(f"Total Files:       {result['total_files']}")
    print(f"Ignored Files:     {result['ignored_files']} ({result['coverage_percentage']}%)")
    print(f"Tracked/Unignored: {result['unignored_files']}\n")

    if result["risky_unignored"]:
        print(f"{BOLD}{RED}[!] Unignored Risky / Temporary Files Detected ({len(result['risky_unignored'])}):{RESET}")
        for item in result["risky_unignored"][:15]:
            print(f"  - {YELLOW}{item['file']}{RESET} (Matches '{item['pattern']}': {item['description']})")
        if len(result["risky_unignored"]) > 15:
            print(f"    ... and {len(result['risky_unignored']) - 15} more.")
        print()

    if result["suggested_rules"]:
        print(f"{BOLD}{GREEN}[+] Recommended Rules to add to .gitignore:{RESET}")
        for rule in result["suggested_rules"]:
            print(f"  {CYAN}{rule}{RESET}")
        print()

    if not result["risky_unignored"]:
        print(f"{GREEN}[OK] Excellent! No sensitive or temporary files found unignored.{RESET}")


if __name__ == "__main__":
    main()
