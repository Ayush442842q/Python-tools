#!/usr/bin/env python3
"""
Git Reflog & Orphaned Commit Recoverer

Scans the Git reflog to locate dangling or orphaned commits (commits that are no longer
reachable by any active branch or tag due to resets, deleted branches, or interactive rebases).
Provides an interactive command-line interface to inspect commit diffs and recover them.

Usage:
    python tools/git_reflog_recoverer.py [options]
"""

import argparse
import datetime
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"

def run_git_command(args: List[str]) -> Tuple[bool, str]:
    """Execute a git command and return (success, output_string)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="ignore"
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
    except FileNotFoundError:
        return False, "Git command-line utility not found in PATH."

def get_reachable_commits() -> Set[str]:
    """Get all commits reachable from any branch, tag, remote, or stash reference."""
    success, output = run_git_command(["rev-list", "--all", "--reflog", "--indexed-objects"])
    if not success:
        # Fallback to simple --all check if above flags are not fully supported
        success, output = run_git_command(["rev-list", "--all"])
    
    if not success:
        return set()
    
    return set(output.splitlines())

def get_reflog_commits() -> List[Dict[str, str]]:
    """Parse the reflog from git or read .git/logs/HEAD directly."""
    # Try running git reflog
    success, output = run_git_command(["reflog", "show", "--date=raw", "--format=%H|%gd|%cr|%gs"])
    commits = []
    
    if success and output:
        for line in output.splitlines():
            parts = line.split("|")
            if len(parts) >= 4:
                commits.append({
                    "sha": parts[0],
                    "reflog_id": parts[1],
                    "relative_date": parts[2],
                    "message": parts[3]
                })
        return commits

    # Fallback: Parse .git/logs/HEAD manually if git command doesn't return reflog
    git_log_path = os.path.join(".git", "logs", "HEAD")
    if not os.path.exists(git_log_path):
        return []

    try:
        with open(git_log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 6:
                    # Format: old_sha new_sha author_name <email> timestamp tz message
                    new_sha = parts[1]
                    timestamp = float(parts[4])
                    # Reconstruct message
                    msg_index = line.find(" +")
                    if msg_index != -1:
                        # find end of timezone (+0530)
                        msg = line[msg_index + 7:].strip()
                    else:
                        msg = " ".join(parts[5:])
                    
                    dt = datetime.datetime.fromtimestamp(timestamp)
                    commits.append({
                        "sha": new_sha,
                        "reflog_id": f"HEAD@{{{len(commits)}}}",
                        "relative_date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "message": msg
                    })
        # Return reversed to show latest first
        return list(reversed(commits))
    except Exception:
        return []

def get_commit_details(sha: str) -> Dict[str, str]:
    """Get metadata for a specific commit."""
    success, output = run_git_command(["show", "-s", "--format=%an|%ae|%ad|%s", sha])
    if success and output:
        parts = output.split("|")
        if len(parts) == 4:
            return {
                "author": parts[0],
                "email": parts[1],
                "date": parts[2],
                "subject": parts[3]
            }
    return {
        "author": "Unknown",
        "email": "",
        "date": "Unknown",
        "subject": "Unknown Commit Details"
    }

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Git Reflog & Orphaned Commit Recoverer"
    )
    parser.add_argument(
        "-a", "--all", action="store_true",
        help="Show all reflog commits (default: only show orphaned/unreachable commits)"
    )
    args = parser.parse_args()

    # Detect color capabilities on Windows
    if sys.platform == "win32":
        os.system("color")

    print("=" * 65)
    print(" GIT REFLOG & ORPHANED COMMIT RECOVERER")
    print("=" * 65)

    # Check if in a git repository
    if not os.path.exists(".git"):
        print(f"{COLOR_RED}Error: Not a git repository (no .git folder found).{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print("Analyzing repository history...")
    reachable = get_reachable_commits()
    reflog_list = get_reflog_commits()

    if not reflog_list:
        print(f"{COLOR_YELLOW}No commits found in the reflog history.{COLOR_RESET}")
        sys.exit(0)

    # Filter to find orphaned/dangling commits
    orphaned_commits: List[Dict[str, str]] = []
    seen_shas: Set[str] = set()

    for item in reflog_list:
        sha = item["sha"]
        if sha in seen_shas:
            continue
        seen_shas.add(sha)

        is_reachable = sha in reachable
        if not is_reachable or args.all:
            # Fetch details
            details = get_commit_details(sha)
            orphaned_commits.append({
                "sha": sha,
                "reflog_id": item["reflog_id"],
                "relative_date": item["relative_date"],
                "message": item["message"],
                "subject": details["subject"],
                "author": details["author"],
                "date": details["date"],
                "reachable": is_reachable
            })

    if not orphaned_commits:
        print(f"{COLOR_GREEN}✔ All commits in the reflog are reachable. No orphaned commits detected!{COLOR_RESET}")
        sys.exit(0)

    print(f"\nLocated {COLOR_BOLD}{len(orphaned_commits)}{COLOR_RESET} orphaned/dangling commits:")
    
    # Interactive loop
    while True:
        print("\n" + "-" * 65)
        for idx, item in enumerate(orphaned_commits[:15], 1):
            reachability_tag = "" if not item["reachable"] else f" {COLOR_GREEN}[Active]{COLOR_RESET}"
            sha_short = item["sha"][:8]
            print(f"[{COLOR_CYAN}{idx:2d}{COLOR_RESET}] {COLOR_BOLD}{sha_short}{COLOR_RESET} - {item['subject'][:45]:45} ({item['relative_date']}){reachability_tag}")
        
        if len(orphaned_commits) > 15:
            print(f"... and {len(orphaned_commits) - 15} more commits.")

        print("-" * 65)
        print("Actions:")
        print("  Select a number (e.g. '1') to inspect a commit.")
        print("  Type 'q' to quit.")
        
        try:
            choice = input("\nChoose an option: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "q":
            break

        try:
            val = int(choice)
            if 1 <= val <= len(orphaned_commits):
                selected = orphaned_commits[val - 1]
                
                # Show commit detail sub-menu
                while True:
                    print("\n" + "=" * 55)
                    print(f"{COLOR_BOLD}COMMIT DETAILS:{COLOR_RESET}")
                    print(f"  Hash:     {COLOR_YELLOW}{selected['sha']}{COLOR_RESET}")
                    print(f"  Author:   {selected['author']}")
                    print(f"  Date:     {selected['date']}")
                    print(f"  Subject:  {COLOR_BOLD}{selected['subject']}{COLOR_RESET}")
                    print(f"  Reflog:   {selected['message']}")
                    print("=" * 55)
                    print("Options:")
                    print("  [d] Show Commit Diff")
                    print("  [r] Recover Commit (create new branch)")
                    print("  [b] Back to Main List")
                    
                    sub_choice = input("\nSelect detail option: ").strip().lower()
                    if sub_choice == "b":
                        break
                    elif sub_choice == "d":
                        print(f"\nGenerating diff for {selected['sha'][:8]}...")
                        # Run git diff
                        diff_success, diff_out = run_git_command(["diff-tree", "-p", "--cc", selected["sha"]])
                        if diff_success and diff_out:
                            print("\n" + diff_out[:2000])  # limit output to 2000 chars
                            if len(diff_out) > 2000:
                                print(f"\n{COLOR_YELLOW}... [Diff output truncated. Use standard git tools for full diff] ...{COLOR_RESET}")
                        else:
                            # Try show command
                            show_success, show_out = run_git_command(["show", selected["sha"]])
                            if show_success:
                                print("\n" + show_out[:2000])
                            else:
                                print(f"{COLOR_RED}Could not display diff: {diff_out}{COLOR_RESET}")
                    elif sub_choice == "r":
                        new_branch = input("Enter name for new branch (e.g. 'recovered-fix'): ").strip()
                        if not new_branch:
                            print("Branch name cannot be empty.")
                            continue
                        
                        rec_success, rec_out = run_git_command(["branch", new_branch, selected["sha"]])
                        if rec_success:
                            print(f"\n{COLOR_GREEN}✔ SUCCESS! Created branch '{new_branch}' pointing to {selected['sha'][:8]}.{COLOR_RESET}")
                            print(f"Run 'git checkout {new_branch}' to switch to it.")
                            # Refresh lists
                            reachable = get_reachable_commits()
                            selected["reachable"] = True
                        else:
                            print(f"{COLOR_RED}Failed to create branch: {rec_out}{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Invalid option index.{COLOR_RESET}")
        except ValueError:
            print(f"{COLOR_RED}Please enter a valid numeric choice or 'q'.{COLOR_RESET}")

if __name__ == "__main__":
    main()
