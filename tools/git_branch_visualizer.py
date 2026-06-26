#!/usr/bin/env python3
"""
Git Branch Commit Tree Visualizer
Runs git log --graph with customized unicode symbols, colors, and layouts.
Also displays metadata summaries about branches, tags, and commits.
"""

import sys
import os
import subprocess
import argparse

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_DIM = "\033[2m"

def supports_color():
    """Returns True if the terminal supports colored output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_MAGENTA = ""
    COLOR_CYAN = ""
    COLOR_DIM = ""

def run_command(cmd, cwd=None):
    """Executes a command and returns its stdout, or None on failure."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, check=True)
        return res.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

def is_git_repo(path):
    """Checks if path is inside a git repository."""
    ret = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    return ret == "true"

def get_repo_stats(path):
    """Gathers commit, branch, and tag count statistics."""
    stats = {}
    
    # Active branch name
    stats["branch"] = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path) or "Unknown"
    
    # Total local branches
    branches = run_command(["git", "branch", "--format=%(refname:short)"], cwd=path)
    stats["local_branches"] = branches.splitlines() if branches else []
    
    # Total tags
    tags = run_command(["git", "tag"], cwd=path)
    stats["tags"] = tags.splitlines() if tags else []
    
    # Total commits count
    commit_count = run_command(["git", "rev-list", "--count", "--all"], cwd=path)
    stats["total_commits"] = commit_count or "N/A"
    
    return stats

def main():
    parser = argparse.ArgumentParser(
        description="Git Branch Commit Tree Visualizer - Renders beautiful colored git graphs and reports repo status.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to git repository (default: current directory)")
    parser.add_argument("--max-count", "-n", type=int, default=30, help="Maximum number of commits to show (default: 30)")
    parser.add_argument("--all", "-a", action="store_true", help="Show all branches/references (by default shows active branch history)")
    parser.add_argument("--author", help="Filter commits by author pattern")
    parser.add_argument("--grep", help="Filter commits by message keyword pattern")
    parser.add_argument("--no-stats", action="store_true", help="Skip printing repository statistics summary")
    
    args = parser.parse_args()

    # Verify repository path
    abs_path = os.path.abspath(args.repo_path)
    if not os.path.exists(abs_path):
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} Path '{args.repo_path}' does not exist.", file=sys.stderr)
        return 1
        
    if not os.path.isdir(abs_path):
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} '{args.repo_path}' is not a directory.", file=sys.stderr)
        return 1

    # Check if Git is installed
    git_version = run_command(["git", "--version"])
    if not git_version:
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} Git is not installed or not in PATH.", file=sys.stderr)
        return 1

    # Check if path is a Git repository
    if not is_git_repo(abs_path):
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} '{args.repo_path}' is not a Git repository.", file=sys.stderr)
        return 1

    # Print repository stats
    if not args.no_stats:
        stats = get_repo_stats(abs_path)
        print(f"=== {COLOR_BOLD}Git Repository Summary{COLOR_RESET} ===")
        print(f"  Path:            {COLOR_BLUE}{abs_path}{COLOR_RESET}")
        print(f"  Active Branch:   {COLOR_GREEN}{COLOR_BOLD}{stats['branch']}{COLOR_RESET}")
        print(f"  Local Branches:  {len(stats['local_branches'])} ({', '.join(stats['local_branches'][:5])}" + (", ..." if len(stats["local_branches"]) > 5 else "") + ")")
        print(f"  Tags:            {len(stats['tags'])} tags")
        print(f"  Total Commits:   {stats['total_commits']} (all references)")
        print("=" * 50 + "\n")

    # Construct Git log command
    # Custom format: hash (bold blue) | author name (cyan) | relative date (yellow) | message (white) | decorations (auto-colored)
    log_format = "%C(bold blue)%h%C(reset) %C(bold cyan)<%an>%C(reset) %C(yellow)(%cr)%C(reset) %C(white)%s%C(reset)%C(auto)%d%C(reset)"
    
    cmd = [
        "git", "log", 
        "--graph", 
        f"--max-count={args.max_count}",
        f"--format={log_format}",
    ]
    
    if args.all:
        cmd.append("--all")
        
    if args.author:
        cmd.append(f"--author={args.author}")
        
    if args.grep:
        cmd.append(f"--grep={args.grep}")

    # Run the log and stream/print output
    print(f"{COLOR_BOLD}Commit Graph ({'All references' if args.all else stats['branch'] if not args.no_stats else 'Active branch'}):{COLOR_RESET}")
    print("-" * 50)
    
    # We must force color output from git log if terminal supports it
    if supports_color():
        cmd.append("--color=always")
        
    try:
        # Run subprocess and print output line by line
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=abs_path)
        
        for line in process.stdout:
            sys.stdout.write(line)
            
        stderr_output = process.stderr.read()
        if stderr_output:
            sys.stderr.write(f"{COLOR_RED}Git command error: {stderr_output}{COLOR_RESET}\n")
            
        process.wait()
        return process.returncode
    except Exception as e:
        print(f"{COLOR_RED}Error visualizing commit graph: {e}{COLOR_RESET}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
