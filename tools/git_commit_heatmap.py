#!/usr/bin/env python3
"""
Git Commit Heatmap & Statistics Generator
Generates a GitHub-style ASCII/Unicode contribution calendar heatmap for commits 
in a local Git repository, with customizable dates, colors, and statistics.
"""

import argparse
import collections
import datetime
import os
import subprocess
import sys
from typing import Dict, List, Tuple, Set

# ANSI Color escapes for block output
COLOR_SCHEMES = {
    "green": [
        "\033[38;5;236m░\033[0m",  # 0 commits
        "\033[38;5;107m▒\033[0m",  # L1
        "\033[38;5;114m▓\033[0m",  # L2
        "\033[38;5;120m█\033[0m",  # L3
        "\033[38;5;156m█\033[0m",  # L4+
    ],
    "blue": [
        "\033[38;5;236m░\033[0m",
        "\033[38;5;24m▒\033[0m",
        "\033[38;5;32m▓\033[0m",
        "\033[38;5;39m█\033[0m",
        "\033[38;5;81m█\033[0m",
    ],
    "purple": [
        "\033[38;5;236m░\033[0m",
        "\033[38;5;54m▒\033[0m",
        "\033[38;5;91m▓\033[0m",
        "\033[38;5;128m█\033[0m",
        "\033[38;5;165m█\033[0m",
    ],
    "orange": [
        "\033[38;5;236m░\033[0m",
        "\033[38;5;130m▒\033[0m",
        "\033[38;5;166m▓\033[0m",
        "\033[38;5;202m█\033[0m",
        "\033[38;5;214m█\033[0m",
    ],
    "mono": [
        "░", "▒", "▓", "█", "█"
    ]
}

import re

# Try to reconfigure stdout to support utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def safe_print(text: str):
    """Print text, falling back to ASCII character sets if encoding error occurs."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback to plain ASCII characters if encoding is restricted (e.g. cp1252 on Windows)
        ascii_text = text
        ascii_text = ascii_text.replace("░", ".")
        ascii_text = ascii_text.replace("▒", "-")
        ascii_text = ascii_text.replace("▓", "=")
        ascii_text = ascii_text.replace("█", "#")
        # Strip ANSI escape codes
        ansi_pattern = re.compile(r'\033\[[0-9;]*m')
        ascii_text = ansi_pattern.sub('', ascii_text)
        try:
            print(ascii_text)
        except UnicodeEncodeError:
            try:
                print(text.encode('ascii', errors='replace').decode('ascii'))
            except Exception:
                pass

def run_git_cmd(args: List[str], cwd: str) -> Tuple[bool, str]:
    """Execute a git command and return success status and stdout/stderr."""
    try:
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
        err = e.stderr.strip() if isinstance(e, subprocess.CalledProcessError) else str(e)
        return False, err


def check_git_repo(path: str) -> bool:
    """Verify if path is inside a Git repository work tree."""
    success, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], path)
    return success

def get_commits(path: str, author_filter: str = None) -> List[datetime.date]:
    """Retrieve all commit dates from the git log."""
    args = ["log", "--all", "--pretty=format:%ad", "--date=format:%Y-%m-%d"]
    if author_filter:
        args.append(f"--author={author_filter}")
        
    success, output = run_git_cmd(args, path)
    if not success or not output:
        return []
        
    dates = []
    for line in output.splitlines():
        line = line.strip()
        if line:
            try:
                dt = datetime.datetime.strptime(line, "%Y-%m-%d").date()
                dates.append(dt)
            except ValueError:
                continue
    return dates

def calculate_streaks(commit_dates_set: Set[datetime.date]) -> Tuple[int, int]:
    """Calculate the current and longest commit streaks (consecutive days)."""
    if not commit_dates_set:
        return 0, 0
        
    sorted_dates = sorted(list(commit_dates_set))
    longest_streak = 0
    current_streak = 0
    
    # Calculate streaks
    temp_streak = 0
    prev_date = None
    
    for d in sorted_dates:
        if prev_date is None:
            temp_streak = 1
        elif (d - prev_date).days == 1:
            temp_streak += 1
        elif (d - prev_date).days > 1:
            if temp_streak > longest_streak:
                longest_streak = temp_streak
            temp_streak = 1
        prev_date = d
        
    if temp_streak > longest_streak:
        longest_streak = temp_streak
        
    # Current streak calculation (ends today or yesterday)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    if today in commit_dates_set:
        check_date = today
        current_streak = 0
        while check_date in commit_dates_set:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)
    elif yesterday in commit_dates_set:
        check_date = yesterday
        current_streak = 0
        while check_date in commit_dates_set:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)
    else:
        current_streak = 0
        
    return current_streak, longest_streak

def render_heatmap(commit_counts: Dict[datetime.date, int], year: int, scheme_name: str, no_color: bool):
    """Render a GitHub-style grid of weeks for the specified year."""
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)
    
    # Align to start on the Sunday before or on Jan 1
    # start_date.weekday(): Monday=0, Sunday=6
    offset = start_date.weekday()
    if offset != 6:  # If not Sunday
        start_date -= datetime.timedelta(days=offset + 1)
        
    # Make sure we cover all of the year, align end_date to Saturday
    end_offset = 5 - end_date.weekday()  # Monday=0 -> Saturday=5
    if end_offset >= 0 and end_date.weekday() != 6:
        end_date += datetime.timedelta(days=end_offset + 1)
    elif end_date.weekday() == 6:
        end_date += datetime.timedelta(days=6)
        
    # Get color palette
    palette = COLOR_SCHEMES["mono"] if (no_color or scheme_name not in COLOR_SCHEMES) else COLOR_SCHEMES[scheme_name]
    
    # Group dates by day of week (row) and week (column)
    total_days = (end_date - start_date).days + 1
    weeks = []
    current_week = [None] * 7
    
    day_pointer = start_date
    for i in range(total_days):
        weekday_idx = day_pointer.weekday()
        # Map weekday index to Sunday-first: Sunday=0, Monday=1 ... Saturday=6
        sf_idx = (weekday_idx + 1) % 7
        
        current_week[sf_idx] = day_pointer
        
        if sf_idx == 6 or i == total_days - 1:
            weeks.append(current_week)
            current_week = [None] * 7
            
        day_pointer += datetime.timedelta(days=1)
        
    # Row headers (Sun, Tue, Thu, Sat)
    row_headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    # Print Month Headers
    month_headers = []
    prev_month = None
    for w_idx, week in enumerate(weeks):
        # Check first non-None day in week to find month name
        valid_day = next((d for d in week if d is not None), None)
        if valid_day and valid_day.year == year:
            curr_month = valid_day.strftime("%b")
            if curr_month != prev_month:
                month_headers.append((w_idx, curr_month))
                prev_month = curr_month
                
    # Render Month line
    header_str = "    "  # padding for row header
    last_pos = 0
    for w_idx, m_name in month_headers:
        spaces = (w_idx - last_pos) * 2
        header_str += " " * (spaces - len(m_name) if spaces > len(m_name) else 1) + m_name
        last_pos = w_idx
    safe_print(header_str)
    
    # Render grid rows (days)
    for day_idx in range(7):
        # Print day label for alternate days (Sun, Tue, Thu, Sat)
        if day_idx in [0, 2, 4, 6]:
            row_str = f"{row_headers[day_idx]:<4}"
        else:
            row_str = "    "
            
        for week in weeks:
            d = week[day_idx]
            if d is None or d.year != year:
                row_str += "  "
            else:
                count = commit_counts.get(d, 0)
                if count == 0:
                    symbol = palette[0]
                elif count <= 2:
                    symbol = palette[1]
                elif count <= 5:
                    symbol = palette[2]
                elif count <= 10:
                    symbol = palette[3]
                else:
                    symbol = palette[4]
                row_str += symbol + " "
        safe_print(row_str)
        
    # Render legend
    legend_str = "\n    Less "
    for sym in palette:
        legend_str += sym + " "
    legend_str += "More"
    safe_print(legend_str)

def main():
    parser = argparse.ArgumentParser(
        description="Git Commit Heatmap & Statistics Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--path", default=".", help="Path to local Git repository (default: current directory)"
    )
    parser.add_argument(
        "--author", help="Filter commits by author name/email regex pattern"
    )
    parser.add_argument(
        "--year", type=int, default=datetime.date.today().year,
        help="Year to display heatmap for (default: current year)"
    )
    parser.add_argument(
        "--scheme", default="green", choices=list(COLOR_SCHEMES.keys()),
        help="Color scheme for heatmap blocks (default: green)"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output (plain ASCII mode)"
    )
    args = parser.parse_args()
    
    repo_path = os.path.abspath(args.path)
    
    if not check_git_repo(repo_path):
        print(f"Error: '{repo_path}' is not a valid Git repository.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Analyzing Git repository at: {repo_path}")
    if args.author:
        print(f"Filtering commits by author pattern: {args.author}")
        
    commit_dates = get_commits(repo_path, args.author)
    if not commit_dates:
        print("No commits found matching the criteria.")
        sys.exit(0)
        
    commit_counts = collections.Counter(commit_dates)
    unique_dates = set(commit_dates)
    
    total_commits = len(commit_dates)
    active_days_count = len(unique_dates)
    avg_commits_per_active = total_commits / active_days_count if active_days_count else 0
    max_commits = max(commit_counts.values()) if commit_counts else 0
    max_commit_days = [d for d, c in commit_counts.items() if c == max_commits]
    
    current_streak, longest_streak = calculate_streaks(unique_dates)
    
    # Filter counts for specified year
    year_counts = {d: c for d, c in commit_counts.items() if d.year == args.year}
    year_total = sum(year_counts.values())
    
    print(f"\n--- Git Contribution Calendar ({args.year}) ---")
    render_heatmap(year_counts, args.year, args.scheme, args.no_color)
    
    print("\n--- Repository Summary Statistics ---")
    print(f"Total Commits (All-Time):      {total_commits}")
    print(f"Commits in {args.year}:             {year_total}")
    print(f"Total Active Days (All-Time):  {active_days_count}")
    print(f"Avg Commits / Active Day:      {avg_commits_per_active:.2f}")
    if max_commits > 0:
        max_day_sample = sorted(max_commit_days)[0].strftime('%Y-%m-%d')
        suffix = " and others" if len(max_commit_days) > 1 else ""
        print(f"Max Commits in a Single Day:   {max_commits} ({max_day_sample}{suffix})")
    print(f"Current Streak:                {current_streak} days")
    print(f"Longest Streak:                {longest_streak} days")
    print("--------------------------------------")

if __name__ == "__main__":
    main()
