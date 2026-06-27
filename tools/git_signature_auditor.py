#!/usr/bin/env python3
"""
Git Commit Signature Auditor

Audits a local Git repository's commit logs to check GPG, SSH, or S/MIME signatures.
Flags unsigned commits, bad signatures, or unknown key IDs, providing a comprehensive
security compliance report.

Usage:
    python tools/git_signature_auditor.py [options]
"""

import sys
import os
import argparse
import subprocess
import re
from collections import Counter, defaultdict

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# Git signature codes mapping
SIGNATURE_CODES = {
    'G': ('Good', GREEN),
    'B': ('Bad Signature', RED),
    'U': ('Good (Untrusted Key)', YELLOW),
    'X': ('Good (Expired Key)', YELLOW),
    'Y': ('Good (Revoked Key)', RED),
    'R': ('Good (Expired Key Signature)', YELLOW),
    'E': ('Verification Error', RED),
    'N': ('Unsigned', RED)
}

def print_banner():
    banner = f"""
{BLUE}{BOLD}=========================================================
     🔒   GIT COMMIT SIGNATURE AUDITOR & COMPLIANCE   🔒
========================================================={RESET}
"""
    print(banner)

def is_git_repo():
    """Checks if the current directory or parent is a git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return res.stdout.strip() == "true"
    except Exception:
        return False

def audit_signatures(limit=100, branch="HEAD"):
    """Audits the signatures of the last N commits in the specified branch."""
    # format: hash | author_email | signature_status | key_id | committer_name | date
    git_format = "%h|%ae|%G?|%GK|%cn|%cd"
    
    cmd = ["git", "log", f"-n {limit}", f"--pretty=format:{git_format}", branch]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error executing git log: {e.stderr.strip()}{RESET}", file=sys.stderr)
        return None

    log_lines = result.stdout.strip().split('\n')
    if not log_lines or log_lines == ['']:
        return []

    audit_results = []
    for line in log_lines:
        parts = line.split('|', 5)
        if len(parts) < 6:
            continue
            
        commit_hash, author_email, sig_status, key_id, committer, date = parts
        
        # Git sets sig_status to empty or N for unsigned
        if not sig_status:
            sig_status = 'N'
            
        audit_results.append({
            "hash": commit_hash,
            "author_email": author_email,
            "status_code": sig_status,
            "key_id": key_id if key_id else "N/A",
            "committer": committer,
            "date": date
        })
        
    return audit_results

def print_audit_report(results, show_unsigned=False):
    """Parses audit results and generates a console report."""
    if not results:
        print(f"{YELLOW}No commits scanned or git log is empty.{RESET}")
        return

    total = len(results)
    status_counts = Counter(r["status_code"] for r in results)
    author_counts = defaultdict(lambda: Counter())
    key_usage = Counter()

    for r in results:
        author_counts[r["author_email"]][r["status_code"]] += 1
        if r["key_id"] != "N/A":
            key_usage[r["key_id"]] += 1

    signed_count = total - status_counts['N']
    compliance_pct = (signed_count / total) * 100 if total > 0 else 0.0

    print(f"\n{BOLD}📋 Repository Summary:{RESET}")
    print(f"  Total Commits Scanned : {total}")
    print(f"  Total Signed Commits  : {signed_count}")
    
    compliance_color = GREEN if compliance_pct > 90 else (YELLOW if compliance_pct > 50 else RED)
    print(f"  Signature Compliance  : {compliance_color}{compliance_pct:.1f}%{RESET}")

    print(f"\n{BOLD}🔍 Signature Status Breakdown:{RESET}")
    for code, (label, color) in SIGNATURE_CODES.items():
        count = status_counts[code]
        pct = (count / total) * 100 if total > 0 else 0.0
        if count > 0:
            print(f"  • [{code}] {color}{label:<30}{RESET}: {count} ({pct:.1f}%)")

    # Author compliance
    print(f"\n{BOLD}👥 Developer Compliance Table:{RESET}")
    print(f"  {BOLD}{'Author Email':<35} | {'Signed':<8} | {'Total':<8} | {'Rate':<8}{RESET}")
    print("  " + "-" * 67)
    
    for email, counts in sorted(author_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total_author = sum(counts.values())
        signed_author = total_author - counts['N']
        pct_author = (signed_author / total_author) * 100
        rate_color = GREEN if pct_author > 90 else (YELLOW if pct_author > 50 else RED)
        print(f"  {email:<35} | {signed_author:<8} | {total_author:<8} | {rate_color}{pct_author:.1f}%{RESET}")

    # Active keys
    if key_usage:
        print(f"\n{BOLD}🔑 Active Signature Keys used:{RESET}")
        for key, count in key_usage.most_common(5):
            print(f"  • Key ID {CYAN}{key}{RESET} : {count} commits signed")

    # Show unsigned details if requested or if compliance is low
    if show_unsigned or compliance_pct < 100:
        print(f"\n{BOLD}⚠️  Detailed Audit Alerts (Unsigned/Flagged Commits):{RESET}")
        flagged_count = 0
        for r in results:
            if r["status_code"] != 'G' and r["status_code"] != 'U':
                label, color = SIGNATURE_CODES.get(r["status_code"], ("Unknown", YELLOW))
                print(f"  • {CYAN}{r['hash']}{RESET} | {color}{label:<15}{RESET} | {r['author_email']} | {r['date']}")
                flagged_count += 1
                if flagged_count >= 15:
                    print(f"  ... and {total - flagged_count} more flagged commits.")
                    break
        if flagged_count == 0:
            print(f"  {GREEN}No issues found. All scanned commits have valid signatures!{RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Git Commit Signature Auditor - Audit GPG/SSH commit signatures for repository compliance.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", "-n", type=int, default=100, help="Number of recent commits to scan (default: 100)")
    parser.add_argument("--branch", "-b", default="HEAD", help="Git branch/revision to audit (default: HEAD)")
    parser.add_argument("--show-unsigned", "-u", action="store_true", help="Always show detailed list of unsigned commits")
    
    args = parser.parse_args()
    print_banner()

    if not is_git_repo():
        print(f"{RED}Error: The directory is not a Git repository.{RESET}", file=sys.stderr)
        return 1

    print(f"Auditing signatures on {BOLD}{args.branch}{RESET} (scanning last {args.limit} commits)...")
    results = audit_signatures(args.limit, args.branch)
    
    if results is None:
        return 1
        
    print_audit_report(results, args.show_unsigned)
    return 0

if __name__ == "__main__":
    sys.exit(main())
