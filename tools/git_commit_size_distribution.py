#!/usr/bin/env python3
"""Git Commit Size Distribution Analyzer

Analyzes Git commit history statistics (lines added, deleted, files changed),
categorizes commits into size distribution buckets, computes percentiles (p50, p75, p90, p99),
detects commit size outliers, and displays ASCII histograms in the terminal.
"""

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

STAT_LINE_PATTERN = re.compile(
    r"^\s*(\d+)\s+file[s]?\s+changed(?:,\s+(\d+)\s+insertion[s]?\(\+\))?(?:,\s+(\d+)\s+deletion[s]?\(\-\))?"
)


class CommitStat:
    def __init__(self, commit_hash: str, author: str, date: str, subject: str):
        self.hash = commit_hash
        self.author = author
        self.date = date
        self.subject = subject
        self.files_changed = 0
        self.insertions = 0
        self.deletions = 0

    @property
    def total_changes(self) -> int:
        return self.insertions + self.deletions


def run_git_log(repo_path: Path, max_count: int, author: Optional[str] = None, since: Optional[str] = None) -> str:
    """Executes git log --shortstat to retrieve commit metadata and line delta statistics."""
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        f"-n{max_count}",
        "--format=COMMIT|%h|%an|%ad|%s",
        "--shortstat",
        "--date=short",
    ]
    if author:
        cmd.append(f"--author={author}")
    if since:
        cmd.append(f"--since={since}")

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding="utf-8")
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"{COLOR_RED}Error running Git command: {e.stderr.strip()}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)


def parse_git_log_output(output: str) -> List[CommitStat]:
    """Parses git log shortstat output into CommitStat objects."""
    commits: List[CommitStat] = []
    current_commit: Optional[CommitStat] = None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("COMMIT|"):
            parts = line.split("|", 4)
            if len(parts) >= 5:
                current_commit = CommitStat(parts[1], parts[2], parts[3], parts[4])
                commits.append(current_commit)
            continue

        if current_commit:
            match = STAT_LINE_PATTERN.match(line)
            if match:
                files = int(match.group(1)) if match.group(1) else 0
                insertions = int(match.group(2)) if match.group(2) else 0
                deletions = int(match.group(3)) if match.group(3) else 0

                current_commit.files_changed = files
                current_commit.insertions = insertions
                current_commit.deletions = deletions

    return commits


def compute_percentile(sorted_data: List[int], p: float) -> float:
    """Computes percentile value from sorted list of numbers."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    idx = (n - 1) * (p / 100.0)
    floor_idx = int(math.floor(idx))
    ceil_idx = int(math.ceil(idx))
    if floor_idx == ceil_idx:
        return float(sorted_data[floor_idx])
    d0 = sorted_data[floor_idx] * (ceil_idx - idx)
    d1 = sorted_data[ceil_idx] * (idx - floor_idx)
    return d0 + d1


def render_histogram(buckets: Dict[str, int], total: int, width: int = 30) -> None:
    """Renders ANSI ASCII bar graph of size categories."""
    max_count = max(buckets.values()) if buckets else 1
    for label, count in buckets.items():
        pct = (count / total * 100) if total > 0 else 0.0
        bar_len = int((count / max_count) * width) if max_count > 0 else 0
        bar = "#" * bar_len
        print(f" {label:<20} | {COLOR_CYAN}{bar:<{width}}{COLOR_RESET} | {count:4d} ({pct:5.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Git commit size distribution and line delta metrics."
    )
    parser.add_argument(
        "-C", "--cwd", default=".", help="Path to target Git repository (default: current directory)."
    )
    parser.add_argument(
        "-n", "--max-count", type=int, default=500, help="Maximum number of commits to analyze (default: 500)."
    )
    parser.add_argument("--author", help="Filter commits by specific author name or email.")
    parser.add_argument("--since", help="Filter commits since date (e.g. '2025-01-01', '1 month ago').")
    parser.add_argument(
        "--outliers", type=int, default=5, help="Number of top monster commits to list (default: 5)."
    )

    args = parser.parse_args()
    repo_path = Path(args.cwd).resolve()

    if not (repo_path / ".git").exists():
        print(f"{COLOR_RED}Error: '{repo_path}' is not a valid Git repository directory.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    raw_output = run_git_log(repo_path, args.max_count, args.author, args.since)
    commits = parse_git_log_output(raw_output)

    if not commits:
        print(f"{COLOR_YELLOW}No commits found matching the criteria.{COLOR_RESET}")
        return

    changes = sorted(c.total_changes for c in commits)
    insertions = [c.insertions for c in commits]
    deletions = [c.deletions for c in commits]
    files = [c.files_changed for c in commits]

    # Size categories
    buckets = {
        "Micro (<10 lines)": 0,
        "Small (10-49)": 0,
        "Medium (50-249)": 0,
        "Large (250-999)": 0,
        "Mega (1000+)": 0,
    }

    for c in commits:
        ch = c.total_changes
        if ch < 10:
            buckets["Micro (<10 lines)"] += 1
        elif ch < 50:
            buckets["Small (10-49)"] += 1
        elif ch < 250:
            buckets["Medium (50-249)"] += 1
        elif ch < 1000:
            buckets["Large (250-999)"] += 1
        else:
            buckets["Mega (1000+)"] += 1

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Git Commit Size Distribution Analysis ==={COLOR_RESET}\n")
    print(f"Repository: {COLOR_BOLD}{repo_path.name}{COLOR_RESET}")
    print(f"Commits Analyzed: {len(commits)}\n")

    print(f"{COLOR_BOLD}Commit Size Distribution (Lines Changed):{COLOR_RESET}")
    render_histogram(buckets, len(commits))

    print(f"\n{COLOR_BOLD}Statistical Summary (Delta Lines):{COLOR_RESET}")
    print(f" * Average Changes/Commit : {sum(changes)/len(changes):.1f} lines")
    print(f" * Median (P50)           : {compute_percentile(changes, 50):.0f} lines")
    print(f" * P75                    : {compute_percentile(changes, 75):.0f} lines")
    print(f" * P90                    : {compute_percentile(changes, 90):.0f} lines")
    print(f" * P99                    : {compute_percentile(changes, 99):.0f} lines")
    print(f" * Total Insertions       : {sum(insertions):,} lines ({COLOR_GREEN}+{sum(insertions)}{COLOR_RESET})")
    print(f" * Total Deletions        : {sum(deletions):,} lines ({COLOR_RED}-{sum(deletions)}{COLOR_RESET})")
    print(f" * Average Files Touched  : {sum(files)/len(files):.1f} files/commit")

    if args.outliers > 0:
        monster_commits = sorted(commits, key=lambda c: c.total_changes, reverse=True)[: args.outliers]
        print(f"\n{COLOR_BOLD}Top {len(monster_commits)} Largest 'Monster' Commits:{COLOR_RESET}")
        for mc in monster_commits:
            print(
                f" * [{COLOR_YELLOW}{mc.hash}{COLOR_RESET}] {COLOR_BOLD}{mc.total_changes:,} lines{COLOR_RESET} "
                f"({COLOR_GREEN}+{mc.insertions}{COLOR_RESET}/{COLOR_RED}-{mc.deletions}{COLOR_RESET}) in {mc.files_changed} files "
                f"by {mc.author} ({mc.date}): {COLOR_GREY}{mc.subject[:40]}{COLOR_RESET}"
            )
    print()


if __name__ == "__main__":
    main()
