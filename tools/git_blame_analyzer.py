#!/usr/bin/env python3
"""
Git Blame & Code Age Analyzer
Analyze the current codebase lines using 'git blame' to calculate line ownership
and the distribution of code age (how long ago lines were authored).
"""

import argparse
import datetime
import os
import subprocess
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

def is_git_repository() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip() == "true"
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_tracked_files(directory: str) -> List[str]:
    """Get all git-tracked files in the directory."""
    try:
        result = subprocess.run(
            ["git", "ls-files", directory],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        files = [f for f in result.stdout.splitlines() if os.path.isfile(f)]
        return files
    except subprocess.SubprocessError as e:
        print(f"{COLOR_RED}Error running git ls-files: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

def run_git_blame(file_path: str) -> List[Tuple[str, int]]:
    """Runs git blame on a file and returns list of (author_name, timestamp) per line."""
    try:
        # Use porcelain output format which is robust and easy to parse
        result = subprocess.run(
            ["git", "blame", "--porcelain", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.SubprocessError as e:
        # File might be untracked or new
        return []

    lines = result.stdout.splitlines()
    blame_data = []
    
    # Simple state machine to parse git blame --porcelain
    # The first line of each block starts with a hash, then details follow.
    current_author = None
    current_time = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split()
        if len(parts) >= 4 and len(parts[0]) == 40:
            # New commit block header
            # Format: <sha> <orig_line_num> <final_line_num> <num_lines_in_grp>
            # Let's read details for this commit
            author = "Unknown"
            timestamp = 0
            while i + 1 < len(lines) and not (len(lines[i+1].split()[0]) == 40 and len(lines[i+1].split()) >= 4):
                i += 1
                sub_line = lines[i]
                if sub_line.startswith("author "):
                    author = sub_line[7:].strip()
                elif sub_line.startswith("author-time "):
                    try:
                        timestamp = int(sub_line[12:].strip())
                    except ValueError:
                        pass
                elif sub_line.startswith("\t"):
                    # This is the actual code line, which marks the end of metadata
                    break
            blame_data.append((author, timestamp))
        i += 1
            
    return blame_data

def format_percentage(val: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(val / total) * 100:.1f}%"

def render_bar(val: int, total: int, width: int = 20) -> str:
    if total == 0:
        return "[" + " " * width + "]"
    filled = int((val / total) * width)
    return "[" + "=" * filled + " " * (width - filled) + "]"

def main():
    parser = argparse.ArgumentParser(description="Analyze Git codebase line ownership and code age distribution.")
    parser.add_argument("path", nargs="?", default=".", help="Directory or file path to analyze (default: current directory)")
    parser.add_argument("-e", "--extension", help="Filter analysis by file extension (e.g., .py, .js)")
    parser.add_argument("-w", "--width", type=int, default=20, help="Width of visual ASCII progress bars")
    
    args = parser.parse_args()
    
    if not is_git_repository():
        print(f"{COLOR_RED}Error: The directory '{os.path.abspath(args.path)}' is not part of a Git repository.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{COLOR_CYAN}Scanning Git tracked files...{COLOR_RESET}")
    all_files = get_tracked_files(args.path)
    
    if args.extension:
        ext = args.extension if args.extension.startswith('.') else f".{args.extension}"
        all_files = [f for f in all_files if f.endswith(ext)]
        
    if not all_files:
        print(f"{COLOR_YELLOW}No matching files found to analyze.{COLOR_RESET}")
        return
        
    print(f"Analyzing {len(all_files)} files using 'git blame'...")
    
    author_counts = defaultdict(int)
    age_counts = {
        "Recent (< 30 days)": 0,
        "Active (30-180 days)": 0,
        "Stale (180-365 days)": 0,
        "Legacy (> 1 year)": 0,
        "Unknown": 0
    }
    
    total_lines = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for idx, file_path in enumerate(all_files):
        # Progress indicator
        if sys.stdout.isatty():
            sys.stdout.write(f"\rProgress: {idx+1}/{len(all_files)} files parsed...")
            sys.stdout.flush()
            
        blame_info = run_git_blame(file_path)
        for author, timestamp in blame_info:
            total_lines += 1
            author_counts[author] += 1
            
            if timestamp == 0:
                age_counts["Unknown"] += 1
                continue
                
            line_date = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
            age_days = (now - line_date).days
            
            if age_days < 30:
                age_counts["Recent (< 30 days)"] += 1
            elif age_days < 180:
                age_counts["Active (30-180 days)"] += 1
            elif age_days < 365:
                age_counts["Stale (180-365 days)"] += 1
            else:
                age_counts["Legacy (> 1 year)"] += 1

    if sys.stdout.isatty():
        sys.stdout.write("\r" + " " * 60 + "\r") # Clear progress line
        
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== CODEBASE BLAME & AGE METRICS ==={COLOR_RESET}")
    print(f"Total analyzed files: {len(all_files)}")
    print(f"Total lines of code:  {total_lines}\n")
    
    if total_lines == 0:
        print(f"{COLOR_YELLOW}No lines found to aggregate.{COLOR_RESET}")
        return

    # Print Author Ownership
    print(f"{COLOR_BOLD}--- LINE OWNERSHIP BY AUTHOR ---{COLOR_RESET}")
    sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
    for author, count in sorted_authors:
        pct = format_percentage(count, total_lines)
        bar = render_bar(count, total_lines, args.width)
        print(f"  {author:<25} : {count:>8} lines ({pct:<6}) {COLOR_BLUE}{bar}{COLOR_RESET}")
        
    # Print Code Age Distribution
    print(f"\n{COLOR_BOLD}--- CODE AGE DISTRIBUTION ---{COLOR_RESET}")
    age_categories = [
        "Recent (< 30 days)",
        "Active (30-180 days)",
        "Stale (180-365 days)",
        "Legacy (> 1 year)"
    ]
    if age_counts["Unknown"] > 0:
        age_categories.append("Unknown")
        
    for category in age_categories:
        count = age_counts[category]
        pct = format_percentage(count, total_lines)
        bar = render_bar(count, total_lines, args.width)
        
        # Color-coding based on age category
        if "Recent" in category:
            color = COLOR_GREEN
        elif "Active" in category:
            color = COLOR_CYAN
        elif "Stale" in category:
            color = COLOR_YELLOW
        else:
            color = COLOR_RED
            
        print(f"  {category:<25} : {count:>8} lines ({pct:<6}) {color}{bar}{COLOR_RESET}")

if __name__ == "__main__":
    main()
