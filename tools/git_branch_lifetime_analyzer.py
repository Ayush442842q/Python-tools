#!/usr/bin/env python3
"""
Git Branch Lifetime & Merge Latency Analyzer - Computes development duration,
active commit count, contributor count, and review/merge latency from git merge history.
Outputs a detailed report and ASCII stats.
"""

import os
import re
import sys
import subprocess
import argparse
from datetime import datetime, timedelta

# ANSI color codes for TUI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_RESET = "\033[0m"

def log_success(message):
    print(f"{COLOR_GREEN}[✓] {message}{COLOR_RESET}")

def log_warn(message):
    print(f"{COLOR_YELLOW}[!] {message}{COLOR_RESET}")

def log_error(message):
    print(f"{COLOR_RED}[✗] {message}{COLOR_RESET}", file=sys.stderr)

def log_info(message):
    print(f"{COLOR_BLUE}[i] {message}{COLOR_RESET}")

def run_git_command(args, cwd=None):
    """Safely runs a git command and returns output as string, or None if errors occur."""
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=cwd
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

def format_duration(seconds):
    """Converts duration in seconds to human readable string."""
    if seconds < 0:
        return "N/A"
    
    td = timedelta(seconds=seconds)
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
        
    return " ".join(parts)

def parse_merge_subject(subject):
    """Extracts a branch name from common merge commit subject structures."""
    # Match: Merge pull request #123 from user/branch-name
    pr_match = re.search(r'Merge pull request #\d+ from [^/]+/([^\s\']+)', subject)
    if pr_match:
        return pr_match.group(1)
        
    # Match: Merge branch 'branch-name'
    branch_match = re.search(r"Merge branch '([^']+)'", subject)
    if branch_match:
        return branch_match.group(1)
        
    # Match: Merge branch 'branch-name' of ...
    of_match = re.search(r"Merge branch '([^']+)' of", subject)
    if of_match:
        return of_match.group(1)
        
    # Match GitHub squash commits or simpler merges: Merge pull request #123 from branch-name
    sim_pr = re.search(r'Merge pull request #\d+ from ([^\s\']+)', subject)
    if sim_pr:
        return sim_pr.group(1)
        
    return None

def analyze_git_branches(repo_path, max_merges=100, target_branch="HEAD"):
    """Walks the merge history and analyzes branch lifetimes."""
    # Verify it is a git repo
    is_repo = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    if not is_repo:
        log_error(f"Directory '{repo_path}' is not a Git repository.")
        return None
        
    log_info(f"Scanning up to {max_merges} merge commits on '{target_branch}'...")
    
    # Get merges on target branch
    # Format: hash|committer_timestamp|subject
    log_format = "%H|%ct|%s"
    merges_output = run_git_command(
        ["log", "--merges", f"--max-count={max_merges}", f"--format={log_format}", target_branch],
        cwd=repo_path
    )
    
    if not merges_output:
        log_warn("No merge commits found in this repository.")
        return []
        
    analysis_results = []
    lines = merges_output.splitlines()
    
    for idx, line in enumerate(lines):
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
            
        m_hash, m_time_str, m_subject = parts
        m_timestamp = int(m_time_str)
        
        branch_name = parse_merge_subject(m_subject)
        if not branch_name:
            # Fallback if subject name couldn't be extracted, e.g. "Merge pull request #X"
            branch_name = f"branch-merged-at-{m_hash[:8]}"
            
        # Get parents of the merge commit
        parents_str = run_git_command(["show", "--no-patch", "--format=%P", m_hash], cwd=repo_path)
        if not parents_str:
            continue
            
        parents = parents_str.split()
        if len(parents) < 2:
            # Not a standard 2-parent merge (could be octopus merge or squash commit representation)
            continue
            
        parent1, parent2 = parents[0], parents[1]
        
        # Get merge base (fork point) between parent1 (main branch line) and parent2 (feature branch)
        m_base = run_git_command(["merge-base", parent1, parent2], cwd=repo_path)
        if not m_base:
            continue
            
        # First commit timestamp on feature branch (first commit after merge base)
        first_commit_time_str = run_git_command(
            ["log", "--reverse", "--format=%ct", f"{m_base}..{parent2}", "-n", "1"],
            cwd=repo_path
        )
        
        if first_commit_time_str:
            first_commit_timestamp = int(first_commit_time_str)
        else:
            # If no commits in list, fallback to merge-base timestamp
            m_base_time = run_git_command(["show", "-s", "--format=%ct", m_base], cwd=repo_path)
            first_commit_timestamp = int(m_base_time) if m_base_time else m_timestamp
            
        # Last commit timestamp on feature branch (tip of feature branch before merge)
        last_commit_time_str = run_git_command(
            ["log", "-n", "1", "--format=%ct", parent2],
            cwd=repo_path
        )
        last_commit_timestamp = int(last_commit_time_str) if last_commit_time_str else m_timestamp
        
        # Commit count
        commit_count_str = run_git_command(
            ["rev-list", "--count", f"{m_base}..{parent2}"],
            cwd=repo_path
        )
        commit_count = int(commit_count_str) if commit_count_str else 1
        
        # Unique contributors
        contributors_str = run_git_command(
            ["log", "--format=%an", f"{m_base}..{parent2}"],
            cwd=repo_path
        )
        contributors = list(set(contributors_str.splitlines())) if contributors_str else ["Unknown"]
        
        # Math Calculations
        # 1. Lifetime: From first commit to actual merge
        lifetime_secs = m_timestamp - first_commit_timestamp
        # 2. Merge Latency: Time between last code push and merge
        latency_secs = m_timestamp - last_commit_timestamp
        
        # Normalize negative results from clock skew/rebase issues
        lifetime_secs = max(0, lifetime_secs)
        latency_secs = max(0, latency_secs)
        
        analysis_results.append({
            "hash": m_hash[:8],
            "branch": branch_name,
            "subject": m_subject,
            "merge_time": datetime.fromtimestamp(m_timestamp),
            "lifetime_secs": lifetime_secs,
            "latency_secs": latency_secs,
            "commit_count": commit_count,
            "contributors": contributors
        })
        
    return analysis_results

def print_text_report(results):
    """Outputs the branch analysis results in a clean formatted report."""
    if not results:
        return
        
    print("\n" + "="*80)
    print(f" {COLOR_MAGENTA}GIT BRANCH LIFETIME & MERGE LATENCY REPORT{COLOR_RESET} ".center(90, "="))
    print("="*80)
    
    # Calculate stats
    total_lifetime = 0
    total_latency = 0
    total_commits = 0
    max_lifetime = -1
    max_lifetime_branch = ""
    max_latency = -1
    max_latency_branch = ""
    
    all_contributors = set()
    
    print(f"\n{'Merge Date':<11} | {'Hash':<8} | {'Branch Name':<25} | {'Commits':<7} | {'Lifetime':<10} | {'Latency':<10}")
    print("-"*80)
    
    for r in results:
        lifetime_str = format_duration(r["lifetime_secs"])
        latency_str = format_duration(r["latency_secs"])
        date_str = r["merge_time"].strftime("%Y-%m-%d")
        
        # Limit branch name size for display
        b_name = r["branch"]
        if len(b_name) > 25:
            b_name = b_name[:22] + "..."
            
        print(f"{date_str:<11} | {r['hash']:<8} | {b_name:<25} | {r['commit_count']:<7} | {lifetime_str:<10} | {latency_str:<10}")
        
        total_lifetime += r["lifetime_secs"]
        total_latency += r["latency_secs"]
        total_commits += r["commit_count"]
        all_contributors.update(r["contributors"])
        
        if r["lifetime_secs"] > max_lifetime:
            max_lifetime = r["lifetime_secs"]
            max_lifetime_branch = r["branch"]
            
        if r["latency_secs"] > max_latency:
            max_latency = r["latency_secs"]
            max_latency_branch = r["branch"]
            
    num_branches = len(results)
    avg_lifetime = total_lifetime / num_branches
    avg_latency = total_latency / num_branches
    avg_commits = total_commits / num_branches
    
    print("="*80)
    print(f"{COLOR_GREEN}Summary Statistics (Based on {num_branches} Merges):{COLOR_RESET}")
    print(f"  • Average Branch Lifetime:        {format_duration(int(avg_lifetime))}")
    print(f"  • Average Merge/Review Latency:   {format_duration(int(avg_latency))}")
    print(f"  • Average Commits per Branch:     {avg_commits:.1f}")
    print(f"  • Unique Contributors Analyzed:   {len(all_contributors)}")
    print(f"  • Longest Living Branch:          {format_duration(max_lifetime)} ({max_lifetime_branch})")
    print(f"  • Highest Merge Delay (Latency):  {format_duration(max_latency)} ({max_latency_branch})")
    print("="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Analyze Git branch lifetimes and merge latencies.")
    parser.add_argument("repo", nargs="?", default=".", help="Path to local Git repository (default: current directory).")
    parser.add_argument("-n", "--count", type=int, default=30, help="Number of merge commits to analyze (default: 30).")
    parser.add_argument("-b", "--branch", default="HEAD", help="Target branch to run log against (default: HEAD).")
    parser.add_argument("-o", "--output", help="Path to save output report as a CSV file.")
    
    args = parser.parse_args()
    
    log_info(f"Initializing Git Branch Lifetime Analyzer on repository: {os.path.abspath(args.repo)}")
    
    results = analyze_git_branches(args.repo, max_merges=args.count, target_branch=args.branch)
    
    if results is None:
        sys.exit(1)
        
    if not results:
        sys.exit(0)
        
    print_text_report(results)
    
    # Save to CSV if requested
    if args.output:
        import csv
        try:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Merge Date", "Merge Commit Hash", "Branch Name", "Subject", "Commits Count", "Lifetime (seconds)", "Merge Latency (seconds)", "Contributors"])
                for r in results:
                    writer.writerow([
                        r["merge_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        r["hash"],
                        r["branch"],
                        r["subject"],
                        r["commit_count"],
                        r["lifetime_secs"],
                        r["latency_secs"],
                        ", ".join(r["contributors"])
                    ])
            log_success(f"CSV report successfully saved to: {args.output}")
        except Exception as e:
            log_error(f"Failed to save CSV file: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
