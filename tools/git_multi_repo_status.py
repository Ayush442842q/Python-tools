#!/usr/bin/env python3
"""
Multi-Git Repository Status Scanner
------------------------------------
Recursively scans a directory for Git repositories and displays a colorized dashboard
summarizing their status (active branch, dirty workdir, staged/unstaged changes,
unpushed/unpulled commits relative to their upstreams).

Dependencies:
    - python 3.6+
    - git (executable must be in PATH)

Usage:
    python tools/git_multi_repo_status.py [path] [--depth D] [--all]
"""

import os
import sys
import subprocess
import argparse
from typing import List, Dict, Any, Optional

# ANSI Escape Sequences for Color Output
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[36m"
COLOR_GRAY = "\033[90m"

def is_git_available() -> bool:
    """Check if the git command-line tool is available."""
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def run_git_cmd(repo_path: str, args: List[str]) -> Optional[str]:
    """Run a git command in the context of a specific repository path."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError:
        return None

def scan_for_git_repos(root_dir: str, max_depth: int) -> List[str]:
    """Recursively search for directories containing a .git folder up to a max depth."""
    repos = []
    root_depth = root_dir.rstrip(os.sep).count(os.sep)
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Calculate current depth relative to root_dir
        current_depth = dirpath.count(os.sep) - root_depth
        if current_depth > max_depth:
            # Prevent os.walk from recursing further
            dirnames.clear()
            continue
            
        if ".git" in dirnames or os.path.exists(os.path.join(dirpath, ".git")):
            repos.append(os.path.abspath(dirpath))
            # Don't recurse inside a Git repository
            dirnames.clear()
            
    return sorted(repos)

def analyze_repo(repo_path: str) -> Dict[str, Any]:
    """Analyze a single Git repository and return its status details."""
    info = {
        "path": repo_path,
        "name": os.path.basename(repo_path),
        "branch": "Unknown",
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "ahead": 0,
        "behind": 0,
        "has_upstream": False,
        "error": None
    }
    
    # 1. Get branch name
    branch = run_git_cmd(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch is None:
        info["error"] = "Failed to query repository (or empty repo)"
        return info
    info["branch"] = branch
    
    # 2. Get status (staged, unstaged, untracked)
    # Porous status format is easy to parse:
    # 'M ' or 'A ' etc. (staged)
    # ' M' or ' D' etc. (unstaged)
    # '??' (untracked)
    status_output = run_git_cmd(repo_path, ["status", "--porcelain"])
    if status_output is not None:
        for line in status_output.splitlines():
            if len(line) < 3:
                continue
            xy = line[:2]
            x, y = xy[0], xy[1]
            if x == "?":
                info["untracked"] += 1
            else:
                if x != " ":
                    info["staged"] += 1
                if y != " " and y != "?":
                    info["unstaged"] += 1
                    
    # 3. Check upstream status (ahead / behind count)
    # Get upstream branch name
    upstream = run_git_cmd(repo_path, ["rev-parse", "--abbrev-ref", "@{upstream}"])
    if upstream and not upstream.startswith("fatal:"):
        info["has_upstream"] = True
        ab_output = run_git_cmd(repo_path, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        if ab_output:
            try:
                parts = ab_output.split()
                if len(parts) == 2:
                    info["ahead"] = int(parts[0])
                    info["behind"] = int(parts[1])
            except ValueError:
                pass
                
    return info

def print_dashboard(repos_info: List[Dict[str, Any]], show_all: bool) -> None:
    """Print a styled dashboard summary of repositories."""
    if not repos_info:
        print(f"{COLOR_YELLOW}No Git repositories found.{COLOR_RESET}")
        return

    # Column widths
    col_name = max(len(info["name"]) for info in repos_info)
    col_name = max(col_name, 12)
    col_branch = max(len(info["branch"]) for info in repos_info)
    col_branch = max(col_branch, 10)
    
    header = (
        f"{COLOR_BOLD}{'Repository':<{col_name}}  {'Branch':<{col_branch}}  "
        f"{'Staged':>6}  {'Unstaged':>8}  {'Untracked':>9}  {'Ahead':>5}  {'Behind':>6}  {'Status':<15}{COLOR_RESET}"
    )
    
    print("\n" + header)
    print("-" * (col_name + col_branch + 56))
    
    dirty_count = 0
    clean_count = 0
    error_count = 0
    
    for info in repos_info:
        is_dirty = info["staged"] > 0 or info["unstaged"] > 0 or info["untracked"] > 0
        has_sync_issues = info["ahead"] > 0 or info["behind"] > 0
        
        # Decide if we skip clean repos
        if not show_all and not is_dirty and not has_sync_issues and info["error"] is None:
            clean_count += 1
            continue
            
        # Format metrics
        name_str = info["name"]
        branch_str = info["branch"]
        
        staged_str = str(info["staged"]) if info["staged"] > 0 else "-"
        unstaged_str = str(info["unstaged"]) if info["unstaged"] > 0 else "-"
        untracked_str = str(info["untracked"]) if info["untracked"] > 0 else "-"
        ahead_str = str(info["ahead"]) if info["ahead"] > 0 else "-"
        behind_str = str(info["behind"]) if info["behind"] > 0 else "-"
        
        # Determine overall status text & coloring
        if info["error"]:
            status_text = f"{COLOR_RED}Error: {info['error']}{COLOR_RESET}"
            error_count += 1
            name_color = COLOR_RED
        elif is_dirty:
            status_text = f"{COLOR_YELLOW}Uncommitted Changes{COLOR_RESET}"
            dirty_count += 1
            name_color = COLOR_YELLOW
        elif has_sync_issues:
            status_text = ""
            if info["ahead"] > 0 and info["behind"] > 0:
                status_text = f"{COLOR_CYAN}Diverged (+{info['ahead']}/-{info['behind']}){COLOR_RESET}"
            elif info["ahead"] > 0:
                status_text = f"{COLOR_GREEN}Ahead (+{info['ahead']}){COLOR_RESET}"
            else:
                status_text = f"{COLOR_CYAN}Behind (-{info['behind']}){COLOR_RESET}"
            clean_count += 1
            name_color = COLOR_CYAN
        else:
            status_text = f"{COLOR_GREEN}Clean{COLOR_RESET}"
            clean_count += 1
            name_color = COLOR_RESET
            
        print(
            f"{name_color}{name_str:<{col_name}}{COLOR_RESET}  "
            f"{COLOR_GRAY if info['branch'] == 'Unknown' else COLOR_BOLD}{branch_str:<{col_branch}}{COLOR_RESET}  "
            f"{COLOR_GREEN if info['staged'] > 0 else COLOR_RESET}{staged_str:>6}{COLOR_RESET}  "
            f"{COLOR_RED if info['unstaged'] > 0 else COLOR_RESET}{unstaged_str:>8}{COLOR_RESET}  "
            f"{COLOR_YELLOW if info['untracked'] > 0 else COLOR_RESET}{untracked_str:>9}{COLOR_RESET}  "
            f"{COLOR_GREEN if info['ahead'] > 0 else COLOR_RESET}{ahead_str:>5}{COLOR_RESET}  "
            f"{COLOR_CYAN if info['behind'] > 0 else COLOR_RESET}{behind_str:>6}{COLOR_RESET}  "
            f"{status_text:<15}"
        )
        
    print("-" * (col_name + col_branch + 56))
    
    total = len(repos_info)
    summary_str = f"Total Repositories: {total} | "
    if show_all:
        summary_str += f"{COLOR_GREEN}Clean: {clean_count}{COLOR_RESET} | "
    else:
        summary_str += f"{COLOR_GREEN}Clean (Hidden): {clean_count}{COLOR_RESET} | "
    summary_str += f"{COLOR_YELLOW}Dirty: {dirty_count}{COLOR_RESET} | "
    if error_count > 0:
        summary_str += f"{COLOR_RED}Errors: {error_count}{COLOR_RESET} | "
    print(summary_str.rstrip(" | "))
    
    if not show_all and clean_count > 0:
        print(f"{COLOR_GRAY}Note: {clean_count} clean repositories were hidden. Run with --all to view them.{COLOR_RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Multi-Git Repository Status Scanner: Analyze multiple repositories in a directory tree."
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory to start scanning (default: current directory)")
    parser.add_argument("-d", "--depth", type=int, default=3, help="Maximum subdirectory recursion depth (default: 3)")
    parser.add_argument("-a", "--all", action="store_true", help="Display all repositories, including those that are clean")
    
    args = parser.parse_args()
    
    if not is_git_available():
        print(f"{COLOR_RED}Error: Git is not installed or not found in system PATH.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    root_dir = os.path.abspath(args.path)
    if not os.path.isdir(root_dir):
        print(f"{COLOR_RED}Error: Path '{args.path}' is not a directory.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{COLOR_BOLD}Scanning for Git repositories in '{root_dir}' (max depth: {args.depth})...{COLOR_RESET}")
    repo_paths = scan_for_git_repos(root_dir, args.depth)
    
    if not repo_paths:
        print(f"{COLOR_YELLOW}No Git repositories found within depth {args.depth}.{COLOR_RESET}")
        sys.exit(0)
        
    print(f"Found {len(repo_paths)} repositories. Analyzing...")
    repos_info = []
    for path in repo_paths:
        repos_info.append(analyze_repo(path))
        
    print_dashboard(repos_info, args.all)

if __name__ == "__main__":
    main()
