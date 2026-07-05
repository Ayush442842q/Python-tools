#!/usr/bin/env python3
"""Git Commit Streak Tracker

Analyze git repository log history to calculate daily commit streaks, longest streak,
activity heatmaps, and terminal contribution matrix.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


def get_git_commits(repo_path: Path, author: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None) -> List[Tuple[date, datetime]]:
    cmd = ["git", "-C", str(repo_path), "log", "--no-merges", '--format=%ad', '--date=iso-strict']
    if author:
        cmd.append(f"--author={author}")
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return []

    commits: List[Tuple[date, datetime]] = []
    for line in res.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            # Handle ISO formats
            dt = datetime.fromisoformat(line)
            commits.append((dt.date(), dt))
        except ValueError:
            continue
    return commits


def calculate_streaks(commit_dates: Set[date]) -> Tuple[int, int, Optional[date], Optional[date]]:
    if not commit_dates:
        return 0, 0, None, None

    sorted_dates = sorted(commit_dates)
    longest_streak = 1
    current_temp_streak = 1

    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
            current_temp_streak += 1
            if current_temp_streak > longest_streak:
                longest_streak = current_temp_streak
        elif sorted_dates[i] > sorted_dates[i - 1] + timedelta(days=1):
            current_temp_streak = 1

    # Current streak calculation relative to today/yesterday
    today = date.today()
    yesterday = today - timedelta(days=1)

    current_streak = 0
    check_day = today if today in commit_dates else (yesterday if yesterday in commit_dates else None)

    if check_day:
        current_streak = 1
        curr = check_day - timedelta(days=1)
        while curr in commit_dates:
            current_streak += 1
            curr -= timedelta(days=1)

    return current_streak, longest_streak, sorted_dates[0], sorted_dates[-1]


def render_ascii_calendar(daily_counts: Dict[date, int], weeks: int = 16) -> str:
    today = date.today()
    # Align to previous Sunday or Monday
    start_date = today - timedelta(days=(weeks * 7) + today.weekday())

    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    grid: List[List[str]] = [[] for _ in range(7)]

    curr = start_date
    while curr <= today:
        cnt = daily_counts.get(curr, 0)
        if cnt == 0:
            symbol = f"{COLOR_GREY}·{COLOR_RESET}"
        elif cnt <= 2:
            symbol = f"{COLOR_GREEN}░{COLOR_RESET}"
        elif cnt <= 5:
            symbol = f"{COLOR_GREEN}▒{COLOR_RESET}"
        else:
            symbol = f"{COLOR_BOLD}{COLOR_GREEN}█{COLOR_RESET}"

        grid[curr.weekday()].append(symbol)
        curr += timedelta(days=1)

    lines = []
    lines.append(f"{COLOR_BOLD}Commit Activity Grid (Last {weeks} Weeks):{COLOR_RESET}")
    for idx, day_name in enumerate(days_of_week):
        row_str = " ".join(grid[idx])
        lines.append(f"  {COLOR_CYAN}{day_name}{COLOR_RESET} {row_str}")

    return "\n".join(lines)


def run_tests():
    """Self-test for git_commit_streak_tracker."""
    today = date.today()
    dates = {
        today - timedelta(days=4),
        today - timedelta(days=3),
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    }
    curr, longest, start, end = calculate_streaks(dates)
    assert curr == 5, f"Expected current streak 5, got {curr}"
    assert longest == 5, f"Expected longest streak 5, got {longest}"

    # Discontinuous dates
    dates2 = {
        today - timedelta(days=10),
        today - timedelta(days=9),
        today - timedelta(days=8),
        today - timedelta(days=1),
        today,
    }
    curr2, longest2, _, _ = calculate_streaks(dates2)
    assert curr2 == 2, f"Expected current streak 2, got {curr2}"
    assert longest2 == 3, f"Expected longest streak 3, got {longest2}"

    print(f"{COLOR_GREEN}All tests passed successfully!{COLOR_RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze git repository log history to calculate daily commit streaks and visual activity grid."
    )
    parser.add_argument("repo", nargs="?", default=".", help="Path to git repository (default: current directory)")
    parser.add_argument("--author", help="Filter commits by author name or email")
    parser.add_argument("--since", help="Filter commits since date (e.g. 2026-01-01)")
    parser.add_argument("--until", help="Filter commits until date")
    parser.add_argument("--weeks", type=int, default=16, help="Number of weeks to render in ASCII grid (default: 16)")
    parser.add_argument("--json", action="store_true", help="Output stats in JSON format")
    parser.add_argument("--test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return 0

    repo_path = Path(args.repo)
    if not (repo_path / ".git").exists() and not repo_path.is_file():
        # Check if git command works in dir
        pass

    commits = get_git_commits(repo_path, author=args.author, since=args.since, until=args.until)

    daily_counts: Dict[date, int] = defaultdict(int)
    dow_counts: Dict[str, int] = defaultdict(int)

    for commit_date, dt in commits:
        daily_counts[commit_date] += 1
        dow_counts[dt.strftime("%A")] += 1

    commit_dates = set(daily_counts.keys())
    curr_streak, longest_streak, first_date, last_date = calculate_streaks(commit_dates)

    stats = {
        "repository": str(repo_path.resolve()),
        "total_commits": len(commits),
        "active_days": len(commit_dates),
        "current_streak_days": curr_streak,
        "longest_streak_days": longest_streak,
        "first_commit_date": str(first_date) if first_date else None,
        "last_commit_date": str(last_date) if last_date else None,
        "day_of_week_distribution": dict(dow_counts),
    }

    if args.json:
        print(json.dumps(stats, indent=2))
        return 0

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Git Commit Streak Tracker ==={COLOR_RESET}")
    print(f"Repository: {COLOR_BOLD}{repo_path.resolve()}{COLOR_RESET}\n")

    if not commits:
        print(f"{COLOR_YELLOW}No commits found matching criteria.{COLOR_RESET}\n")
        return 0

    print(f"  ▸ Total Commits:    {COLOR_BOLD}{COLOR_GREEN}{len(commits)}{COLOR_RESET}")
    print(f"  ▸ Active Days:      {COLOR_BOLD}{len(commit_dates)}{COLOR_RESET}")
    print(f"  ▸ Current Streak:   {COLOR_BOLD}{COLOR_CYAN}{curr_streak} days{COLOR_RESET}")
    print(f"  ▸ Longest Streak:   {COLOR_BOLD}{COLOR_YELLOW}{longest_streak} days{COLOR_RESET}")
    print(f"  ▸ First Commit:     {first_date}")
    print(f"  ▸ Last Commit:      {last_date}\n")

    print(render_ascii_calendar(daily_counts, weeks=args.weeks))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
