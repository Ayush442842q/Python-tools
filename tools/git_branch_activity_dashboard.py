#!/usr/bin/env python3
"""
Git Branch Activity Dashboard
Aggregates activity metrics across all local git branches.
Ranks branches by stale status, calculates ahead/behind statistics,
and renders horizontal ASCII charts of commit volume.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any, Tuple

def run_git(args: List[str], cwd: str = ".") -> str:
    """Helper to run a git command and return its output."""
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
    except subprocess.CalledProcessError as e:
        # If not a git repo or git not found, return empty or raise
        raise RuntimeError(f"Git command failed: {' '.join(args)}\nError: {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("Git executable not found on system path.")

def is_git_repo(path: str) -> bool:
    """Checks if the path is inside a git repository."""
    try:
        run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return True
    except RuntimeError:
        return False

def get_default_branch(cwd: str) -> str:
    """Finds the default branch name (usually main or master)."""
    try:
        # Check remote origin head
        ref = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=cwd)
        return ref.split("/")[-1]
    except Exception:
        # Fallback to checking local branches
        branches = run_git(["branch", "--list"], cwd=cwd).split("\n")
        cleaned = [b.replace("*", "").strip() for b in branches]
        for name in ["main", "master", "develop", "trunk"]:
            if name in cleaned:
                return name
        return cleaned[0] if cleaned else "main"

def get_branches(cwd: str, include_remote: bool) -> List[str]:
    """Gets lists of local and optionally remote branches."""
    args = ["branch", "--format=%(refname:short)"]
    if include_remote:
        args.append("-a")
    
    out = run_git(args, cwd=cwd)
    if not out:
        return []
    
    # Filter out HEAD pointers like origin/HEAD -> origin/main
    branches = []
    for line in out.split("\n"):
        line = line.strip()
        if line and "->" not in line:
            branches.append(line)
    return branches

def get_branch_stats(branch: str, base_branch: str, cwd: str) -> Dict[str, Any]:
    """Fetches commit statistics for a single branch."""
    stats = {"name": branch}
    
    # Last commit time and message
    try:
        log_format = "%ct|%an|%s"
        log_data = run_git(["log", "-1", f"--format={log_format}", branch], cwd=cwd)
        parts = log_data.split("|", 2)
        if len(parts) == 3:
            stats["last_commit_timestamp"] = int(parts[0])
            stats["last_commit_author"] = parts[1]
            stats["last_commit_subject"] = parts[2]
            stats["last_commit_date"] = datetime.fromtimestamp(stats["last_commit_timestamp"])
        else:
            stats["last_commit_timestamp"] = 0
            stats["last_commit_author"] = "Unknown"
            stats["last_commit_subject"] = "N/A"
            stats["last_commit_date"] = datetime.min
    except Exception:
        stats["last_commit_timestamp"] = 0
        stats["last_commit_author"] = "Unknown"
        stats["last_commit_subject"] = "N/A"
        stats["last_commit_date"] = datetime.min

    # Commits in last 30 days
    try:
        count_30d = run_git(["rev-list", "--count", "--since=30 days ago", branch], cwd=cwd)
        stats["commits_30d"] = int(count_30d) if count_30d else 0
    except Exception:
        stats["commits_30d"] = 0

    # Total commits
    try:
        count_total = run_git(["rev-list", "--count", branch], cwd=cwd)
        stats["commits_total"] = int(count_total) if count_total else 0
    except Exception:
        stats["commits_total"] = 0

    # Ahead/Behind comparison with base branch
    try:
        if branch != base_branch and not branch.endswith(f"/{base_branch}"):
            ab = run_git(["rev-list", "--left-right", "--count", f"{base_branch}...{branch}"], cwd=cwd)
            parts = ab.split()
            if len(parts) == 2:
                stats["behind"] = int(parts[0])
                stats["ahead"] = int(parts[1])
            else:
                stats["behind"], stats["ahead"] = 0, 0
        else:
            stats["behind"], stats["ahead"] = 0, 0
    except Exception:
        stats["behind"], stats["ahead"] = 0, 0

    return stats

def draw_horizontal_bar_chart(branch_stats: List[Dict[str, Any]], metric_key: str, max_width: int = 40):
    """Draws a horizontal ASCII bar chart for branch statistics."""
    max_val = max(s[metric_key] for s in branch_stats) if branch_stats else 0
    if max_val == 0:
        max_val = 1
        
    print(f"\n[*] Branch Activity (by {metric_key.replace('_', ' ').title()}):")
    print(f"{'Branch Name':<25} | {'Metric Value':<12} | Chart")
    print("-" * 75)
    
    for s in branch_stats:
        val = s[metric_key]
        bar_len = int((val / max_val) * max_width)
        bar = "#" * bar_len
        if val > 0 and bar_len == 0:
            bar = "." # Minimum length indicator
        print(f"{s['name'][:24]:<25} | {val:<12} | {bar}")

def print_dashboard(branch_stats: List[Dict[str, Any]], base_branch: str):
    """Prints a beautiful summary dashboard table."""
    print("\n" + "=" * 100)
    print(f" GIT BRANCH ACTIVITY DASHBOARD (Base: {base_branch})")
    print("=" * 100)
    
    header = f"{'Branch Name':<25} {'Last Commit Date':<20} {'Last Author':<15} {'Ahead':<6} {'Behind':<6} {'Total Commits':<13}"
    print(header)
    print("-" * 100)
    
    now = datetime.now()
    
    for s in branch_stats:
        date_str = "N/A"
        days_ago = ""
        if s["last_commit_timestamp"] > 0:
            date_str = s["last_commit_date"].strftime("%Y-%m-%d %H:%M")
            delta = now - s["last_commit_date"]
            if delta.days == 0:
                days_ago = "(Today)"
            elif delta.days == 1:
                days_ago = "(Yesterday)"
            else:
                days_ago = f"({delta.days}d ago)"
                
        disp_date = f"{date_str} {days_ago}"[:20]
        
        name = s["name"]
        if len(name) > 24:
            name = name[:21] + "..."
            
        print(f"{name:<25} {disp_date:<20} {s['last_commit_author'][:14]:<15} {s['ahead']:<6} {s['behind']:<6} {s['commits_total']:<13}")
        
        # Print last commit message subject in subtle indented text
        subj = s["last_commit_subject"]
        if len(subj) > 70:
            subj = subj[:67] + "..."
        print(f"  └─ Last Msg: {subj}")
    print("=" * 100 + "\n")

def get_branch_details(branch: str, cwd: str):
    """Prints verbose info and recent commits for a selected branch."""
    print(f"\n[*] Detailed view for branch: {branch}")
    print("-" * 50)
    try:
        commits = run_git(["log", "-n", "5", "--format=%h - %an, %ar : %s", branch], cwd=cwd)
        print("Recent 5 Commits:")
        print(commits)
    except Exception as e:
        print(f"Error fetching logs: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Audit git branches by activity level, stale status, and structure."
    )
    parser.add_argument(
        "--path", 
        default=".", 
        help="Path to local Git repository (default: current directory)"
    )
    parser.add_argument(
        "--remote", 
        action="store_true", 
        help="Include remote branches in dashboard"
    )
    parser.add_argument(
        "--base", 
        help="Base branch to calculate ahead/behind status against (default: auto-detected main/master)"
    )
    parser.add_argument(
        "--sort", 
        choices=["date", "total", "30d", "ahead", "behind"],
        default="date",
        help="Sort branches by date, total commits, 30d commits, ahead, or behind (default: date)"
    )
    parser.add_argument(
        "--inspect",
        help="Show details and recent commits for a specific branch"
    )
    args = parser.parse_args()

    repo_path = os.path.abspath(args.path)
    
    if not is_git_repo(repo_path):
        print(f"[-] Error: Path '{repo_path}' is not inside a Git repository.")
        sys.exit(1)
        
    print(f"[*] Analyzing Git Repository at: {repo_path}")
    
    try:
        base_branch = args.base if args.base else get_default_branch(repo_path)
        branches = get_branches(repo_path, args.remote)
        
        if not branches:
            print("[-] No branches found.")
            sys.exit(0)
            
        print(f"[*] Found {len(branches)} branches. Fetching statistics...")
        
        branch_stats = []
        for b in branches:
            stats = get_branch_stats(b, base_branch, repo_path)
            branch_stats.append(stats)
            
        # Sorting
        if args.sort == "date":
            branch_stats.sort(key=lambda x: x["last_commit_timestamp"], reverse=True)
        elif args.sort == "total":
            branch_stats.sort(key=lambda x: x["commits_total"], reverse=True)
        elif args.sort == "30d":
            branch_stats.sort(key=lambda x: x["commits_30d"], reverse=True)
        elif args.sort == "ahead":
            branch_stats.sort(key=lambda x: x["ahead"], reverse=True)
        elif args.sort == "behind":
            branch_stats.sort(key=lambda x: x["behind"], reverse=True)

        # Print dashboard table
        print_dashboard(branch_stats, base_branch)
        
        # Draw horizontal commit activity chart
        draw_horizontal_bar_chart(branch_stats, "commits_30d")
        
        # If user wants to inspect a branch
        if args.inspect:
            get_branch_details(args.inspect, repo_path)
            
    except Exception as e:
        print(f"[-] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
