#!/usr/bin/env python3
"""
Git Line Contribution Analyzer

A command-line tool that parses `git log --numstat` to calculate lines of code (LOC)
additions and deletions across the history of a repository. Generates contributor
rankings and file extension statistics with terminal ASCII bar charts.

Usage:
    python tools/git_line_contribution_analyzer.py [path/to/repo] [options]
"""

import argparse
import sys
import subprocess
import collections
import os
import shutil

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "magenta": "\033[95m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def run_git(args, cwd=None):
    """Helper to run git commands."""
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=cwd,
            check=True
        )
        return res.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return None

def draw_ascii_bar(value, max_value, max_width=30, color_code="cyan"):
    """Draws a horizontal progress bar based on value relative to max_value."""
    if max_value <= 0:
        return ""
    width = int((value / max_value) * max_width)
    bar = "█" * width
    color = COLORS.get(color_code, COLORS["cyan"])
    return f"{color}{bar}{COLORS['reset']}"

def analyze_git_history(repo_path, limit):
    # Verify git repo
    is_repo = run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    if not is_repo:
        print(f"{COLORS['red']}Error: '{repo_path}' is not a valid Git repository.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning Git repository at: {COLORS['bold']}{repo_path}{COLORS['reset']}")
    
    # We run: git log --numstat --format="COMMIT|%ae|%an"
    log_args = ["log", "--numstat", "--format=COMMIT|%ae|%an"]
    if limit:
        log_args.append(f"-n {limit}")
        
    log_output = run_git(log_args, cwd=repo_path)
    if not log_output:
        print(f"{COLORS['yellow']}No commit history or logs found.{COLORS['reset']}")
        return
        
    # Data structures
    # author -> {"added": X, "deleted": Y, "commits": Z}
    author_stats = collections.defaultdict(lambda: {"added": 0, "deleted": 0, "commits": 0})
    # ext -> {"added": X, "deleted": Y}
    ext_stats = collections.defaultdict(lambda: {"added": 0, "deleted": 0})
    
    current_author = None
    
    lines = log_output.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("COMMIT|"):
            parts = line.split('|', 2)
            if len(parts) >= 3:
                email = parts[1]
                name = parts[2]
                current_author = email if email else name
                author_stats[current_author]["commits"] += 1
            else:
                current_author = "Unknown"
        else:
            # Parse numstat format: <added> <deleted> <filename>
            parts = line.split(None, 2)
            if len(parts) == 3 and current_author:
                added_str, deleted_str, filename = parts
                
                # Check for binary files marked with "-"
                try:
                    added = int(added_str) if added_str != "-" else 0
                    deleted = int(deleted_str) if deleted_str != "-" else 0
                except ValueError:
                    continue
                    
                # Accumulate for author
                author_stats[current_author]["added"] += added
                author_stats[current_author]["deleted"] += deleted
                
                # Extract file extension
                _, ext = os.path.splitext(filename)
                ext = ext.lower().strip()
                if not ext:
                    ext = "(no extension)"
                    
                # Accumulate for extension
                ext_stats[ext]["added"] += added
                ext_stats[ext]["deleted"] += deleted

    return author_stats, ext_stats

def main():
    parser = argparse.ArgumentParser(description="Analyze Git lines of code contributions.")
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to the Git repository (default: current)")
    parser.add_argument("-n", "--limit", type=int, help="Limit number of commits to scan")
    parser.add_argument("--no-color", action="store_true", help="Disable console colors")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    repo_path = os.path.abspath(args.repo_path)
    
    analysis = analyze_git_history(repo_path, args.limit)
    if not analysis:
        return
        
    author_stats, ext_stats = analysis
    
    # 1. Contributor Rankings
    print(f"\n{COLORS['bold']}Lines of Code Contributions by Author:{COLORS['reset']}")
    print("=" * 90)
    
    # Sort authors by total lines added
    sorted_authors = sorted(author_stats.items(), key=lambda x: x[1]["added"], reverse=True)
    max_added = sorted_authors[0][1]["added"] if sorted_authors else 0
    
    for author, stats in sorted_authors[:15]:  # Show top 15
        net = stats["added"] - stats["deleted"]
        bar = draw_ascii_bar(stats["added"], max_added, color_code="green")
        print(f"  {author:<30} Additions: {COLORS['green']}{stats['added']:<7}{COLORS['reset']} Deletions: {COLORS['red']}{stats['deleted']:<7}{COLORS['reset']} Net: {COLORS['bold']}{net:<7}{COLORS['reset']} {bar}")
        
    # 2. Extension Statistics
    print(f"\n{COLORS['bold']}Lines of Code by File Extension:{COLORS['reset']}")
    print("=" * 90)
    
    # Sort extensions by total additions
    sorted_exts = sorted(ext_stats.items(), key=lambda x: x[1]["added"], reverse=True)
    max_ext_added = sorted_exts[0][1]["added"] if sorted_exts else 0
    
    for ext, stats in sorted_exts[:15]:  # Show top 15
        net = stats["added"] - stats["deleted"]
        bar = draw_ascii_bar(stats["added"], max_ext_added, color_code="yellow")
        print(f"  {ext:<15} Additions: {COLORS['green']}{stats['added']:<7}{COLORS['reset']} Deletions: {COLORS['red']}{stats['deleted']:<7}{COLORS['reset']} Net: {COLORS['bold']}{net:<7}{COLORS['reset']} {bar}")
        
    print()

if __name__ == "__main__":
    main()
