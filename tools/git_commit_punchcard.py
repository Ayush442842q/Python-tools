#!/usr/bin/env python3
"""
Git Commit Activity Punchcard Generator

Analyzes git history to extract commit dates and times, producing a beautiful
visual punchcard (matrix of weekday vs. hour) in the terminal using density symbols,
along with detailed work-pattern statistics.

Usage:
    python git_commit_punchcard.py [options]
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Days of the week
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Punchcard symbols (representing density from empty to maximum)
PUNCH_SYMBOLS = [" ", "·", "•", "o", "O", "0", "■", "█"]

def get_git_commit_dates(author=None, since=None, until=None, branch=None, max_count=None):
    """Fetch commit ISO dates from git log."""
    cmd = ["git", "log", "--pretty=format:%ad", "--date=iso"]
    
    if branch:
        cmd.append(branch)
    if author:
        cmd.append(f"--author={author}")
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    if max_count:
        cmd.append(f"-n {max_count}")
        
    try:
        # Run command in a way that respects git environment and current working directory
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
        return result.stdout.strip().splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e}", file=sys.stderr)
        print("Ensure you are inside a Git repository and have git installed.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'git' command not found. Please install Git.", file=sys.stderr)
        sys.exit(1)

def parse_dates(date_strings):
    """Parse git log date strings and return list of (weekday, hour) tuples."""
    commit_times = []
    for date_str in date_strings:
        if not date_str.strip():
            continue
        try:
            # Git ISO date format: 2026-06-28 07:06:25 +0530
            # We can parse the first 19 characters: YYYY-MM-DD HH:MM:SS
            dt_part = date_str[:19]
            dt = datetime.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
            # dt.weekday() returns 0 for Mon, 6 for Sun
            commit_times.append((dt.weekday(), dt.hour))
        except ValueError:
            # Fallback if date parsing fails for some custom format
            continue
    return commit_times

def generate_punchcard(commit_times):
    """Build the 7x24 grid of commit frequencies."""
    # 7 days, 24 hours initialized to 0
    grid = [[0 for _ in range(24)] for _ in range(7)]
    for day, hour in commit_times:
        grid[day][hour] += 1
    return grid

def print_punchcard(grid, colorize=True):
    """Render the punchcard grid visually in the terminal."""
    max_val = max(max(row) for row in grid) if any(any(row) for row in grid) else 0
    
    # Hours header
    hours_header = "     " + " ".join(f"{h:02d}" for h in range(24))
    print(f"{BOLD}{hours_header}{RESET}")
    print("   " + "—" * 74)
    
    for day_idx in range(7):
        day_name = DAYS[day_idx]
        row_str = []
        for hour_idx in range(24):
            count = grid[day_idx][hour_idx]
            if count == 0:
                symbol = PUNCH_SYMBOLS[0]
            else:
                # Map value to range of symbols (1 to len(PUNCH_SYMBOLS)-1)
                factor = count / max_val
                symbol_idx = int(factor * (len(PUNCH_SYMBOLS) - 1))
                symbol_idx = max(1, symbol_idx)
                symbol = PUNCH_SYMBOLS[symbol_idx]
                
            # Formatting with colors
            if colorize and count > 0:
                if count > max_val * 0.75:
                    symbol = f"{GREEN}{symbol}{RESET}"
                elif count > max_val * 0.40:
                    symbol = f"{CYAN}{symbol}{RESET}"
                else:
                    symbol = f"{BLUE}{symbol}{RESET}"
                    
            row_str.append(symbol)
            
        print(f"{BOLD}{day_name} |{RESET}  " + "  ".join(row_str) + f"  {BOLD}|{RESET}")
        
    print("   " + "—" * 74)
    print(f"Legend (density):  [Empty] " + " ".join(PUNCH_SYMBOLS[1:]) + " [Max]")

def print_statistics(grid, total_commits):
    """Compute and print work pattern statistics."""
    if total_commits == 0:
        print("\nNo commits found for the specified filters.")
        return
        
    # Peak day
    day_totals = [sum(row) for row in grid]
    peak_day_idx = day_totals.index(max(day_totals))
    peak_day_name = DAYS[peak_day_idx]
    
    # Peak hour
    hour_totals = [sum(grid[d][h] for d in range(7)) for h in range(24)]
    peak_hour = hour_totals.index(max(hour_totals))
    
    # Peak slot (specific day & hour)
    flat_grid = [(grid[d][h], d, h) for d in range(7) for h in range(24)]
    peak_slot_val, peak_slot_day, peak_slot_hour = max(flat_grid)
    
    # Workday vs Weekend
    weekday_commits = sum(day_totals[0:5])
    weekend_commits = sum(day_totals[5:7])
    weekday_pct = (weekday_commits / total_commits) * 100
    weekend_pct = (weekend_commits / total_commits) * 100
    
    # Time of day grouping
    morning = sum(hour_totals[6:12])   # 6am - 12pm
    afternoon = sum(hour_totals[12:18]) # 12pm - 6pm
    evening = sum(hour_totals[18:24])   # 6pm - 12am
    night = sum(hour_totals[0:6])       # 12am - 6am
    
    print(f"\n{BOLD}{CYAN}=== COMMIT PATTERN STATISTICS ===={RESET}\n")
    print(f"Total Commits Analyzed: {BOLD}{total_commits}{RESET}")
    print(f"Peak Activity Day:      {BOLD}{peak_day_name}{RESET} ({day_totals[peak_day_idx]} commits, {day_totals[peak_day_idx]/total_commits*100:.1f}%)")
    print(f"Peak Activity Hour:     {BOLD}{peak_hour:02d}:00 - {peak_hour:02d}:59{RESET} ({hour_totals[peak_hour]} commits, {hour_totals[peak_hour]/total_commits*100:.1f}%)")
    print(f"Peak Work Slot:         {BOLD}{DAYS[peak_slot_day]} at {peak_slot_hour:02d}:00{RESET} ({peak_slot_val} commits)")
    print(f"Weekday Commits (M-F):  {BOLD}{weekday_commits}{RESET} ({weekday_pct:.1f}%)")
    print(f"Weekend Commits (S-S):  {BOLD}{weekend_commits}{RESET} ({weekend_pct:.1f}%)")
    
    print(f"\n{BOLD}Time of Day Breakdown:{RESET}")
    print(f"  Morning (06:00-12:00):   {morning:<5} ({morning/total_commits*100:4.1f}%) " + "#" * int(morning/total_commits*20))
    print(f"  Afternoon (12:00-18:00): {afternoon:<5} ({afternoon/total_commits*100:4.1f}%) " + "#" * int(afternoon/total_commits*20))
    print(f"  Evening (18:00-00:00):   {evening:<5} ({evening/total_commits*100:4.1f}%) " + "#" * int(evening/total_commits*20))
    print(f"  Night (00:00-06:00):     {night:<5} ({night/total_commits*100:4.1f}%) " + "#" * int(night/total_commits*20))
    print()

def main():
    parser = argparse.ArgumentParser(description="Generate an ASCII punchcard of Git commit activity.")
    parser.add_argument("--author", help="Filter commits by author name or email pattern")
    parser.add_argument("--since", help="Filter commits since date (e.g. '3 months ago', '2023-01-01')")
    parser.add_argument("--until", help="Filter commits until date (e.g. '1 month ago', '2023-12-31')")
    parser.add_argument("--branch", help="Specific branch/ref to analyze (default: current HEAD)")
    parser.add_argument("--max-count", "-n", type=int, help="Limit number of commits to analyze")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")
    
    args = parser.parse_args()
    
    # Ensure we are running inside or target a directory of a Git repo
    if not os.path.exists(".git"):
        # Look around or check parent directories
        is_in_repo = False
        curr_dir = os.getcwd()
        while True:
            if os.path.exists(os.path.join(curr_dir, ".git")):
                is_in_repo = True
                break
            parent = os.path.dirname(curr_dir)
            if parent == curr_dir:
                break
            curr_dir = parent
            
        if not is_in_repo:
            print("Error: The current directory is not a Git repository (no '.git' folder found).", file=sys.stderr)
            sys.exit(1)
            
    print(f"Fetching Git log...")
    date_strings = get_git_commit_dates(
        author=args.author,
        since=args.since,
        until=args.until,
        branch=args.branch,
        max_count=args.max_count
    )
    
    commit_times = parse_dates(date_strings)
    grid = generate_punchcard(commit_times)
    
    print(f"\n{BOLD}{CYAN}=== GIT COMMIT PUNCHCARD ===={RESET}")
    if args.branch:
        print(f"Branch: {args.branch}")
    if args.author:
        print(f"Author Filter: {args.author}")
    if args.since or args.until:
        print(f"Date Filter: since={args.since or 'any'}, until={args.until or 'any'}")
    print(f"Commits Analyzed: {len(commit_times)}\n")
    
    print_punchcard(grid, colorize=not args.no_color)
    print_statistics(grid, len(commit_times))

if __name__ == "__main__":
    main()
