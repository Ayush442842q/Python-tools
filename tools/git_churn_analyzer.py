#!/usr/bin/env python3
"""
Git Churn Analyzer - Measure and rank code churn of files in a Git repository.

This tool runs git commands to extract modification statistics (additions,
deletions, and commit frequency) for each file in a repository, and displays
a ranked summary to identify codebase hot-spots.
"""

import os
import sys
import subprocess
import argparse
from collections import defaultdict


def run_command(cmd, cwd=None):
    """Run a system command and return stdout, or None on error."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            cwd=cwd
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None


def check_git_repo(repo_path):
    """Check if the given path is a valid Git repository."""
    if not os.path.exists(repo_path):
        return False
    # Run a simple git status command to verify
    out = run_command("git rev-parse --is-inside-work-tree", cwd=repo_path)
    return out is not None and "true" in out.strip().lower()


def analyze_churn(repo_path, max_count, since, until, author):
    """Analyze git log to calculate file churn stats."""
    # Build git log command
    cmd = "git log --numstat --pretty=format:\"commit:%h\""
    if max_count:
        cmd += f" -n {max_count}"
    if since:
        cmd += f" --since=\"{since}\""
    if until:
        cmd += f" --until=\"{until}\""
    if author:
        cmd += f" --author=\"{author}\""

    log_output = run_command(cmd, cwd=repo_path)
    if not log_output:
        return {}

    # File stats accumulator
    # file_path -> {commits, additions, deletions, churn}
    stats = defaultdict(lambda: {"commits": 0, "additions": 0, "deletions": 0, "churn": 0})
    
    current_commit = None
    commit_files = set() # Track files touched in the current commit to count unique commits per file

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("commit:"):
            current_commit = line.split(":")[1]
            commit_files = set()
            continue

        # Parse numstat line: <additions> <deletions> <filepath>
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue

        add_str, del_str, filepath = parts
        
        # Handle binary files represented by '-'
        try:
            additions = int(add_str) if add_str != "-" else 0
        except ValueError:
            additions = 0
            
        try:
            deletions = int(del_str) if del_str != "-" else 0
        except ValueError:
            deletions = 0

        # Skip directory renames or empty filepaths
        if not filepath:
            continue

        # Update stats
        if filepath not in commit_files:
            stats[filepath]["commits"] += 1
            commit_files.add(filepath)
            
        stats[filepath]["additions"] += additions
        stats[filepath]["deletions"] += deletions
        stats[filepath]["churn"] += (additions + deletions)

    return stats


def print_report(stats, limit, sort_key):
    """Print the formatted churn report to stdout."""
    if not stats:
        print("No churn statistics found matching the filters.")
        return

    # Convert to list and sort
    sorted_stats = sorted(
        stats.items(),
        key=lambda item: item[1][sort_key],
        reverse=True
    )

    # Print Header
    print("\n" + "=" * 100)
    print(f"{'GIT CODE CHURN REPORT':^100}")
    print("=" * 100)
    print(f"{'File Path':<50} | {'Commits':<8} | {'Added':<9} | {'Deleted':<9} | {'Total Churn':<11}")
    print("-" * 100)

    total_added = 0
    total_deleted = 0
    total_churn = 0

    count = 0
    for filepath, file_stats in sorted_stats:
        total_added += file_stats["additions"]
        total_deleted += file_stats["deletions"]
        total_churn += file_stats["churn"]
        
        if count < limit:
            print(f"{filepath[:50]:<50} | {file_stats['commits']:<8} | {file_stats['additions']:<9} | {file_stats['deletions']:<9} | {file_stats['churn']:<11}")
            count += 1

    if len(sorted_stats) > limit:
        print(f"... and {len(sorted_stats) - limit} more files.")

    print("-" * 100)
    print(f"{'TOTALS':<50} | {'-':<8} | {total_added:<9} | {total_deleted:<9} | {total_churn:<11}")
    print("=" * 100 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Git Churn Analyzer - Identify frequently modified hot-spots in a Git repository."
    )
    parser.add_argument(
        "-r", "--repo",
        default=".",
        help="Path to the Git repository (default: current directory)"
    )
    parser.add_argument(
        "-n", "--max-count",
        type=int,
        help="Limit the number of commits to analyze"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=15,
        help="Limit output to top N files (default: 15)"
    )
    parser.add_argument(
        "--since",
        help="Analyze commits more recent than a specific date (e.g. '2026-01-01' or '1.month.ago')"
    )
    parser.add_argument(
        "--until",
        help="Analyze commits older than a specific date"
    )
    parser.add_argument(
        "--author",
        help="Filter commits by author (name or email pattern)"
    )
    parser.add_argument(
        "--sort",
        choices=["churn", "commits", "additions", "deletions"],
        default="churn",
        help="Key to sort files by (default: churn)"
    )

    args = parser.parse_args()

    repo_abs_path = os.path.abspath(args.repo)
    if not check_git_repo(repo_abs_path):
        print(f"Error: '{repo_abs_path}' is not a valid Git repository or git is not installed.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing churn in repository: {repo_abs_path}")
    print("Running analysis... (this may take a moment for large histories)")
    
    stats = analyze_churn(
        repo_abs_path,
        max_count=args.max_count,
        since=args.since,
        until=args.until,
        author=args.author
    )

    print_report(stats, args.limit, args.sort)


if __name__ == "__main__":
    main()
