#!/usr/bin/env python3
"""
Git Repository Summarizer - Generate activity and contribution reports

This utility runs Git commands via subprocess to analyze the local repository.
It reports key metrics such as total commits, commit activity trends by day/hour,
top contributors, and files with the highest change frequencies.

Usage:
    python tools/git_repo_summarizer.py [--path REPO_PATH] [--limit LIMIT]

Example:
    python tools/git_repo_summarizer.py --limit 500
"""

import argparse
import collections
import os
import subprocess
import sys
from typing import Dict, List, Tuple

def run_git_cmd(args: List[str], cwd: str) -> Tuple[bool, str]:
    """Execute a git command and return success status and output/error."""
    try:
        # Prevent git from asking for credentials or paging
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["PAGER"] = "cat"
        
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            check=True
        )
        return True, result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        err_msg = ""
        if isinstance(e, subprocess.CalledProcessError):
            err_msg = e.stderr.strip()
        else:
            err_msg = "Git executable not found in system PATH."
        return False, err_msg

def is_git_repo(path: str) -> bool:
    """Check if the path is inside a git work tree."""
    success, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], path)
    return success

def get_total_commits(path: str) -> int:
    """Get total commit count across all branches."""
    success, output = run_git_cmd(["rev-list", "--all", "--count"], path)
    if success and output.isdigit():
        return int(output)
    return 0

def get_contributors(path: str) -> List[Tuple[str, int]]:
    """Get list of contributors with commit counts."""
    success, output = run_git_cmd(["shortlog", "HEAD", "-s", "-n"], path)
    if not success:
        # Fallback to all commits if HEAD is not unborn
        success, output = run_git_cmd(["shortlog", "-s", "-n", "--all"], path)
        
    contributors = []
    if success and output:
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                count_str, name = parts
                if count_str.isdigit():
                    contributors.append((name, int(count_str)))
    return contributors

def analyze_commit_activity(path: str, limit: int) -> Tuple[Dict[str, int], Dict[int, int]]:
    """Analyze the day-of-week and hour distribution of commits."""
    # Day numbers: 0=Sunday, 1=Monday... 6=Saturday
    # Format: "%w %H" (day_of_week hour)
    success, output = run_git_cmd(
        ["log", "--all", f"-n{limit}", "--pretty=format:%ad", "--date=format:%w %H"],
        path
    )
    
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    day_counts = collections.defaultdict(int)
    hour_counts = collections.defaultdict(int)
    
    if success and output:
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) == 2:
                day_idx, hour_str = parts
                if day_idx.isdigit() and hour_str.isdigit():
                    day_name = days[int(day_idx)]
                    day_counts[day_name] += 1
                    hour_counts[int(hour_str)] += 1
                    
    return day_counts, hour_counts

def get_frequent_files(path: str, limit: int) -> List[Tuple[str, int]]:
    """Identify frequently modified files in recent commits."""
    success, output = run_git_cmd(
        ["log", "--all", f"-n{limit}", "--name-only", "--pretty=format:"],
        path
    )
    
    file_counter = collections.Counter()
    if success and output:
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            file_counter[line] += 1
            
    return file_counter.most_common(5)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize local Git repository activity and stats."
    )
    parser.add_argument(
        "--path", "-p",
        default=".",
        help="Path to local Git repository (default: current directory)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=500,
        help="Number of recent commits to analyze for activity trends (default: 500)"
    )
    
    args = parser.parse_args()
    repo_path = os.path.abspath(args.path)
    
    if not os.path.exists(repo_path):
        print(f"Error: Path '{repo_path}' does not exist.", file=sys.stderr)
        return 1
        
    if not is_git_repo(repo_path):
        print(f"Error: '{repo_path}' is not a Git repository.", file=sys.stderr)
        return 1
        
    print("=" * 60)
    print(f"Git Repository Summary: {repo_path}")
    print("=" * 60)
    
    # Total commits
    total_commits = get_total_commits(repo_path)
    print(f"Total Commits (All branches): {total_commits}")
    
    # Top Contributors
    contributors = get_contributors(repo_path)
    print(f"\nTop Contributors:")
    print("-" * 30)
    for name, count in contributors[:5]:
        percentage = (count / total_commits * 100) if total_commits > 0 else 0
        print(f"  {name:<18} : {count:>4} commits ({percentage:.1f}%)")
        
    # Activity Analysis
    day_counts, hour_counts = analyze_commit_activity(repo_path, args.limit)
    
    print(f"\nWeekly Commit Activity Distribution (Last {args.limit} commits):")
    print("-" * 50)
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    max_day_val = max(day_counts.values()) if day_counts else 1
    for day in days_order:
        count = day_counts.get(day, 0)
        bar_len = int((count / max_day_val) * 20) if count > 0 else 0
        bar = "#" * bar_len
        print(f"  {day:<9} : {count:>4} {bar}")
        
    print(f"\nHourly Commit Activity Peaks (Last {args.limit} commits):")
    print("-" * 50)
    # Print hours in blocks of 4 (00-03, 04-07, etc.)
    hourly_ranges = [
        ("Night (00-05)", range(0, 6)),
        ("Morning (06-11)", range(6, 12)),
        ("Afternoon (12-17)", range(12, 18)),
        ("Evening (18-23)", range(18, 24))
    ]
    for name, r in hourly_ranges:
        count = sum(hour_counts.get(h, 0) for h in r)
        print(f"  {name:<18} : {count:>4} commits")
        
    # Hotspot Files
    hotspots = get_frequent_files(repo_path, args.limit)
    print(f"\nTop Hotspot Files (Most changed in last {args.limit} commits):")
    print("-" * 50)
    for filepath, count in hotspots:
        print(f"  {filepath:<35} : {count:>3} modifications")
        
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
