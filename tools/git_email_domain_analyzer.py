#!/usr/bin/env python3
"""
Git Email Domain Analyzer - Analyze commit statistics and contributions grouped by email domains.
"""

import argparse
import sys
import subprocess
from collections import defaultdict
from datetime import datetime
import math

# ANSI escape codes for styling
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_UNDERLINE = "\033[4m"

def run_git_command(args):
    """Executes a git command and returns the output lines"""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{COLOR_RED}Error running git command: {e}{COLOR_RESET}", file=sys.stderr)
        return []

def get_git_commits():
    """Gathers all commits with format: 'Author Email | Timestamp (Unix)'"""
    # %ae is author email, %at is author date unix timestamp
    return run_git_command(["log", "--all", "--format=%ae|%at"])

def parse_domain(email):
    """Extracts the domain part from an email address"""
    if not email or "@" not in email:
        return "unknown"
    return email.split("@")[-1].lower()

def print_bar_chart(value, max_value, width=30, color=COLOR_CYAN):
    """Generates a simple terminal bar chart"""
    if max_value == 0:
        return ""
    filled_length = int(round(width * value / max_value))
    bar = "█" * filled_length + "░" * (width - filled_length)
    return f"{color}{bar}{COLOR_RESET}"

def main():
    parser = argparse.ArgumentParser(
        description="Git Email Domain Analyzer - Analyze git contributions grouped by email domain."
    )
    parser.add_argument(
        "--path", default=".", help="Path to the git repository (default: current directory)"
    )
    parser.add_argument(
        "--limit", type=int, default=15, help="Number of domains to show in the detailed breakdown"
    )
    parser.add_argument(
        "--since", help="Show commits more recent than a specific date (e.g. '2023-01-01')"
    )
    parser.add_argument(
        "--until", help="Show commits older than a specific date (e.g. '2023-12-31')"
    )
    parser.add_argument(
        "--csv", action="store_true", help="Output breakdown in CSV format"
    )
    args = parser.parse_args()

    # Verify directory is a git repository
    import os
    if not os.path.exists(os.path.join(args.path, ".git")):
        print(f"{COLOR_RED}Error: '{args.path}' is not a valid Git repository root.{COLOR_RESET}")
        sys.exit(1)

    # Change directory to the target git repository path
    original_cwd = os.getcwd()
    os.chdir(args.path)

    try:
        # Build filter options
        git_log_args = ["log", "--all", "--format=%ae|%at|%an"]
        if args.since:
            git_log_args.append(f"--since={args.since}")
        if args.until:
            git_log_args.append(f"--until={args.until}")

        log_lines = run_git_command(git_log_args[1:])
        if not log_lines:
            print(f"{COLOR_YELLOW}No commits found in the specified range.{COLOR_RESET}")
            return

        domain_commits = defaultdict(int)
        domain_authors = defaultdict(set)
        author_commits = defaultdict(int)
        
        earliest_timestamp = float('inf')
        latest_timestamp = 0
        total_commits = 0

        for line in log_lines:
            parts = line.split("|")
            if len(parts) < 2:
                continue
            email = parts[0]
            timestamp = int(parts[1])
            author_name = parts[2] if len(parts) > 2 else email

            domain = parse_domain(email)
            domain_commits[domain] += 1
            domain_authors[domain].add(email)
            author_commits[email] += 1
            total_commits += 1

            if timestamp < earliest_timestamp:
                earliest_timestamp = timestamp
            if timestamp > latest_timestamp:
                latest_timestamp = timestamp

        # Sort domains by number of commits
        sorted_domains = sorted(domain_commits.items(), key=lambda x: x[1], reverse=True)

        if args.csv:
            print("Domain,Commits,Percentage,Unique_Authors")
            for domain, count in sorted_domains:
                pct = (count / total_commits) * 100
                unique_authors = len(domain_authors[domain])
                print(f"{domain},{count},{pct:.2f}%,{unique_authors}")
            return

        earliest_date = datetime.fromtimestamp(earliest_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        latest_date = datetime.fromtimestamp(latest_timestamp).strftime('%Y-%m-%d %H:%M:%S')

        # Print header dashboard
        print("=" * 80)
        print(f"{COLOR_BOLD}{COLOR_HEADER}GIT EMAIL DOMAIN CONTRIBUTIONS REPORT{COLOR_RESET}")
        print("=" * 80)
        print(f"Repository Path : {COLOR_BOLD}{args.path}{COLOR_RESET}")
        print(f"Analysis Period : {COLOR_BLUE}{earliest_date}{COLOR_RESET} to {COLOR_BLUE}{latest_date}{COLOR_RESET}")
        print(f"Total Commits   : {COLOR_GREEN}{total_commits}{COLOR_RESET}")
        print(f"Unique Domains  : {COLOR_YELLOW}{len(domain_commits)}{COLOR_RESET}")
        print(f"Unique Authors  : {COLOR_YELLOW}{len(author_commits)}{COLOR_RESET}")
        print("=" * 80)
        print()

        # Breakdown section
        print(f"{COLOR_BOLD}Top {args.limit} Domains by Commit Count:{COLOR_RESET}")
        print("-" * 80)
        print(f"{'Domain':<30} | {'Commits':<8} | {'Share (%)':<9} | {'Authors':<7} | {'Visual Distribution'}")
        print("-" * 80)

        max_commits = sorted_domains[0][1] if sorted_domains else 0
        for domain, count in sorted_domains[:args.limit]:
            pct = (count / total_commits) * 100
            unique_authors = len(domain_authors[domain])
            bar = print_bar_chart(count, max_commits, width=25)
            # Categorize domain color
            if domain in ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com", "me.com", "icloud.com"]:
                dom_display = f"{COLOR_YELLOW}{domain}{COLOR_RESET}"
            elif domain == "users.noreply.github.com":
                dom_display = f"{COLOR_BLUE}{domain}{COLOR_RESET}"
            else:
                dom_display = f"{COLOR_GREEN}{domain}{COLOR_RESET}"

            print(f"{dom_display:<39} | {count:<8} | {pct:.1f}%     | {unique_authors:<7} | {bar}")

        # Summary of remaining domains if any
        if len(sorted_domains) > args.limit:
            other_commits = sum(count for _, count in sorted_domains[args.limit:])
            other_pct = (other_commits / total_commits) * 100
            other_authors = sum(len(domain_authors[domain]) for domain, _ in sorted_domains[args.limit:])
            other_bar = print_bar_chart(other_commits, max_commits, width=25, color=COLOR_BLUE)
            print(f"{COLOR_BOLD}{'Other (' + str(len(sorted_domains) - args.limit) + ' domains)':<30}{COLOR_RESET} | {other_commits:<8} | {other_pct:.1f}%     | {other_authors:<7} | {other_bar}")

        print("-" * 80)
        print(f"Legend: {COLOR_GREEN}Corporate/Org Domain{COLOR_RESET} | {COLOR_YELLOW}Public Webmail{COLOR_RESET} | {COLOR_BLUE}GitHub Noreply / System{COLOR_RESET}")
        print("=" * 80)
        print()

        # Categorize contributions: Personal (webmail) vs Corporate (custom domains) vs Unknown/Noreply
        webmails = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com", "me.com", "icloud.com", "aol.com", "mail.com", "gmx.com", "zoho.com"}
        corp_commits = 0
        personal_commits = 0
        system_commits = 0

        for domain, count in sorted_domains:
            if domain in webmails:
                personal_commits += count
            elif "noreply" in domain or domain == "unknown" or "local" in domain:
                system_commits += count
            else:
                corp_commits += count

        corp_pct = (corp_commits / total_commits) * 100 if total_commits > 0 else 0
        pers_pct = (personal_commits / total_commits) * 100 if total_commits > 0 else 0
        syst_pct = (system_commits / total_commits) * 100 if total_commits > 0 else 0

        print(f"{COLOR_BOLD}Contribution Type Classification:{COLOR_RESET}")
        print(f"  {COLOR_GREEN}Corporate / Organization Domains : {corp_commits:<6} ({corp_pct:.1f}%){COLOR_RESET}")
        print(f"  {COLOR_YELLOW}Public Webmail Accounts          : {personal_commits:<6} ({pers_pct:.1f}%){COLOR_RESET}")
        print(f"  {COLOR_BLUE}GitHub Noreply / System Emails   : {system_commits:<6} ({syst_pct:.1f}%){COLOR_RESET}")
        print("=" * 80)
        
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    main()
