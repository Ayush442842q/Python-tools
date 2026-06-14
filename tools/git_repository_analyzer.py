#!/usr/bin/env python3
"""
Git Repository Analyzer

A command-line tool that scans a local Git repository, parses Git log history, and
generates detailed statistics and insights (top contributors, hourly/daily activity,
most frequently modified files) with inline ASCII visual graphs.

Usage:
    python tools/git_repository_analyzer.py [path/to/repo] [--limit 500]
"""

import argparse
import sys
import subprocess
import collections
from datetime import datetime
import shutil

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def print(*args, **kwargs):
    import builtins
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                cleaned = arg.replace('█', '#').replace('│', '|').replace('═', '=').replace('─', '-')
                new_args.append(cleaned.encode('ascii', errors='replace').decode('ascii'))
            else:
                new_args.append(arg)
        builtins.print(*new_args, **kwargs)

def get_terminal_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def run_git_command(args, cwd=None):
    """Runs a git command and returns the stdout string, or None on error."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=cwd,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def is_git_repo(path):
    """Checks if the given path is a valid git repository."""
    out = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return out == "true"

def draw_ascii_bar(val, max_val, max_width=40, color_code="cyan"):
    """Draws a simple horizontal progress bar."""
    if max_val <= 0:
        return ""
    width = int((val / max_val) * max_width)
    bar = "█" * width
    color = COLORS.get(color_code, COLORS["cyan"])
    return f"{color}{bar}{COLORS['reset']}"

def analyze_repository(repo_path, commit_limit=None):
    if not is_git_repo(repo_path):
        print(f"{COLORS['red']}Error: '{repo_path}' is not inside a Git repository.{COLORS['reset']}", file=sys.stderr)
        return False

    print(f"Analyzing Git repository at: {COLORS['bold']}{repo_path}{COLORS['reset']}")
    
    # Get current branch
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path) or "Unknown"
    
    # Run git log
    log_args = ["log"]
    if commit_limit:
        log_args.append(f"-n {commit_limit}")
    log_args.append('--format=%an|%ae|%at')
    
    log_data = run_git_command(log_args, cwd=repo_path)
    if not log_data:
        print(f"{COLORS['yellow']}No commits found or unable to read git log.{COLORS['reset']}")
        return False
    
    lines = log_data.split('\n')
    total_commits = len(lines)
    
    authors = collections.Counter()
    emails = {}  # Author Name -> Email
    weekdays = collections.Counter()  # Monday = 0, Sunday = 6
    hours = collections.Counter()     # 0 to 23
    dates = collections.Counter()     # YYYY-MM-DD
    
    for line in lines:
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 3:
            continue
        author, email, timestamp_str = parts[0], parts[1], parts[2]
        
        authors[author] += 1
        emails[author] = email
        
        try:
            dt = datetime.fromtimestamp(int(timestamp_str))
            weekdays[dt.weekday()] += 1
            hours[dt.hour] += 1
            dates[dt.strftime('%Y-%m-%d')] += 1
        except Exception:
            pass

    # Get file modification counts
    # Using git log --name-only to find most changed files
    file_args = ["log"]
    if commit_limit:
        file_args.append(f"-n {commit_limit}")
    file_args.extend(["--name-only", "--format="])
    file_data = run_git_command(file_args, cwd=repo_path)
    
    changed_files = collections.Counter()
    if file_data:
        for f_line in file_data.split('\n'):
            f_line = f_line.strip()
            if f_line:  # Ignore empty lines (commit info lines are ignored because of --format=)
                changed_files[f_line] += 1

    term_width = get_terminal_width()
    print("\n" + "=" * term_width)
    print(f" GIT ANALYZER REPORT: {branch.upper()} BRANCH ".center(term_width, "═"))
    print("=" * term_width)

    # General Stats
    print(f"\n{COLORS['bold']}General Statistics:{COLORS['reset']}")
    print(f"  Total Commits Analyzed: {COLORS['green']}{total_commits}{COLORS['reset']}")
    print(f"  Unique Contributors:    {COLORS['green']}{len(authors)}{COLORS['reset']}")
    if dates:
        active_days = len(dates)
        print(f"  Active Days spanned:   {COLORS['green']}{active_days}{COLORS['reset']} days")
        print(f"  Avg Commits per Day:   {COLORS['green']}{total_commits / active_days:.2f}{COLORS['reset']}")

    # Top Contributors
    print(f"\n{COLORS['bold']}Top Contributors (by commit count):{COLORS['reset']}")
    top_authors = authors.most_common(10)
    max_author_commits = top_authors[0][1] if top_authors else 0
    max_author_len = max(len(a) for a, _ in top_authors) if top_authors else 10
    
    for author, count in top_authors:
        pct = (count / total_commits) * 100
        bar = draw_ascii_bar(count, max_author_commits, max_width=30, color_code="cyan")
        email_disp = f"<{emails[author]}>"
        print(f"  {author.ljust(max_author_len)} {email_disp.ljust(25)} │ {count:4d} ({pct:5.1f}%) │ {bar}")

    # Commit Distribution by Weekday
    print(f"\n{COLORS['bold']}Commit Activity by Weekday:{COLORS['reset']}")
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    max_weekday_commits = max(weekdays.values()) if weekdays else 0
    
    for i, name in enumerate(weekday_names):
        count = weekdays[i]
        bar = draw_ascii_bar(count, max_weekday_commits, max_width=30, color_code="green")
        print(f"  {name.ljust(9)} │ {count:4d} │ {bar}")

    # Commit Distribution by Hour
    print(f"\n{COLORS['bold']}Commit Activity by Hour (24h):{COLORS['reset']}")
    max_hour_commits = max(hours.values()) if hours else 0
    # Group hours into 2-hour slots for more compact rendering
    for h_slot in range(0, 24, 2):
        count = hours[h_slot] + hours[h_slot + 1]
        bar = draw_ascii_bar(count, max_hour_commits * 2, max_width=30, color_code="yellow")
        print(f"  {h_slot:02d}:00-{h_slot+1:02d}:59 │ {count:4d} │ {bar}")

    # Top Modified Files
    if changed_files:
        print(f"\n{COLORS['bold']}Top 10 Most Modified Files:{COLORS['reset']}")
        top_files = changed_files.most_common(10)
        max_file_changes = top_files[0][1] if top_files else 0
        max_file_len = max(len(f) for f, _ in top_files) if top_files else 20
        max_file_len = min(max_file_len, term_width - 55)  # Make sure it fits
        
        for filepath, count in top_files:
            # Truncate filename if it's too long
            disp_path = filepath
            if len(disp_path) > max_file_len:
                disp_path = "..." + disp_path[-(max_file_len - 3):]
            bar = draw_ascii_bar(count, max_file_changes, max_width=25, color_code="magenta")
            print(f"  {disp_path.ljust(max_file_len)} │ {count:4d} modifications │ {bar}")

    print("\n" + "=" * term_width + "\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="Analyze a Git repository log and generate insights.")
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("--limit", type=int, help="Limit the number of commits to analyze (default: all commits)")
    args = parser.parse_args()
    
    success = analyze_repository(args.repo_path, args.limit)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
