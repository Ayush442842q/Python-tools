#!/usr/bin/env python3
"""
Git Commit Timezone Analyzer

Analyzes git history to extract timezone offsets and commit hour distributions,
providing insights into geographical spread and working hour patterns of contributors.

Usage:
    python tools/git_commit_timezone_analyzer.py [options]
"""

import argparse
import collections
import os
import subprocess
import sys

def run_git_log(repo_path, max_count=None):
    """Run git log command and return the output lines."""
    cmd = ["git", "log", '--pretty=format:%ai %an']
    if max_count:
        cmd.extend(["-n", str(max_count)])
        
    try:
        # Run with cwd set to repo_path
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=repo_path
        )
        return result.stdout.splitlines()
    except subprocess.SubprocessError as e:
        print(f"Error running git: {e}", file=sys.stderr)
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Git error output: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Error: 'git' command line tool not found in PATH.", file=sys.stderr)
        return None

def analyze_commits(log_lines):
    """Parse commit details from log lines and aggregate statistics."""
    # Log format: YYYY-MM-DD HH:MM:SS TZ_OFFSET Author Name
    # Example: 2026-06-29 15:01:08 +0530 Ayush442842q
    
    tz_counter = collections.Counter()
    hour_counter = collections.Counter()
    author_tzs = collections.defaultdict(collections.Counter)
    total_commits = 0
    
    for line in log_lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split(" ", 3)
        if len(parts) < 4:
            continue
            
        date_str, time_str, tz_offset, author = parts
        
        # Verify tz_offset pattern (starts with + or - and is 4 digits)
        if not (len(tz_offset) == 5 and tz_offset[0] in ('+', '-') and tz_offset[1:].isdigit()):
            continue
            
        total_commits += 1
        tz_counter[tz_offset] += 1
        
        # Extract hour
        try:
            hour = int(time_str.split(":")[0])
            hour_counter[hour] += 1
        except (ValueError, IndexError):
            pass
            
        author_tzs[author][tz_offset] += 1
        
    return {
        "total_commits": total_commits,
        "tz_distribution": tz_counter.most_common(),
        "hour_distribution": hour_counter,
        "author_timezones": {author: tzs.most_common(2) for author, tzs in author_tzs.items()}
    }

def print_ascii_bar(label, count, max_count, max_bar_width=40):
    """Print a single line with a label and a visual text-based progress bar."""
    if max_count == 0:
        bar = ""
    else:
        bar_len = int((count / max_count) * max_bar_width)
        bar = "█" * bar_len
    print(f"  {label:<10} | {count:>5} | {bar}")

def print_report(repo_path, results):
    """Print the final timezone analysis report with ASCII charts."""
    print("=" * 60)
    print(" GIT COMMIT TIMEZONE & HOUR ANALYZER")
    print("=" * 60)
    print(f"Repository Path: {os.path.abspath(repo_path)}")
    print(f"Total Commits Analyzed: {results['total_commits']}")
    print("-" * 60)
    
    if results['total_commits'] == 0:
        print("No commits found or unable to parse history.")
        return
        
    print("Timezone Offset Distribution:")
    max_tz_count = max(count for tz, count in results['tz_distribution']) if results['tz_distribution'] else 0
    for tz, count in results['tz_distribution']:
        pct = (count / results['total_commits']) * 100
        label = f"{tz} ({pct:0.1f}%)"
        print_ascii_bar(label, count, max_tz_count)
        
    print("-" * 60)
    print("Commit Distribution by Hour of Day (Local Time):")
    hour_dist = results['hour_distribution']
    max_hour_count = max(hour_dist.values()) if hour_dist else 0
    for h in range(24):
        label = f"{h:02d}:00"
        count = hour_dist.get(h, 0)
        print_ascii_bar(label, count, max_hour_count)
        
    print("-" * 60)
    print("Top Contributors and their Primary Timezones:")
    # Sort authors by total commits
    sorted_authors = sorted(
        results['author_timezones'].items(),
        key=lambda x: sum(count for tz, count in x[1]),
        reverse=True
    )
    
    for author, tzs in sorted_authors[:15]:
        total_author_commits = sum(count for tz, count in tzs)
        tz_info = ", ".join(f"{tz} ({cnt})" for tz, cnt in tzs)
        print(f"  {author:<25} : {total_author_commits:<5} commits (TZs: {tz_info})")
    if len(sorted_authors) > 15:
        print(f"  ... and {len(sorted_authors) - 15} more contributors.")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Git Commit Timezone and Work Hours Analyzer")
    parser.add_argument("-d", "--dir", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("-n", "--limit", type=int, default=None, help="Limit analysis to last N commits")
    
    args = parser.parse_args()
    
    # Check if .git directory exists
    git_dir = os.path.join(args.dir, ".git")
    if not os.path.exists(git_dir) and not os.path.exists(os.path.join(args.dir, "HEAD")):
        # Could be a bare repository or we are not in repo
        # Let's run git rev-parse to check
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                cwd=args.dir
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            print(f"Error: Directory '{args.dir}' is not a git repository.", file=sys.stderr)
            return 1
            
    print(f"Scanning git history in '{args.dir}'...")
    log_lines = run_git_log(args.dir, args.limit)
    if log_lines is None:
        return 1
        
    results = analyze_commits(log_lines)
    print_report(args.dir, results)
    return 0

if __name__ == "__main__":
    sys.exit(main())
