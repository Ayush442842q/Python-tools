#!/usr/bin/env python3
"""
Interactive Git Squash Helper
A CLI utility to safely squash local commits on the current branch.
Uses git soft-reset to squash commits without encountering rebase conflicts.
"""

import sys
import os
import subprocess
import argparse
from typing import List, Tuple, Optional

# Color utilities for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

def run_git(args: List[str]) -> Tuple[int, str, str]:
    """Run a git command and return its exit code, stdout, and stderr."""
    try:
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except FileNotFoundError:
        print_colored("Error: Git command not found in system PATH.", RED)
        sys.exit(1)

def get_current_branch() -> str:
    code, stdout, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        print_colored("Error: Not a git repository or HEAD is detached.", RED)
        sys.exit(1)
    return stdout

def get_merge_base(base_branch: str) -> str:
    """Find the common ancestor commit between HEAD and the base branch."""
    code, stdout, stderr = run_git(["merge-base", base_branch, "HEAD"])
    if code != 0:
        print_colored(f"Error finding merge base with '{base_branch}': {stderr}", RED)
        sys.exit(1)
    return stdout

def get_commits_since(commit_hash: str) -> List[Tuple[str, str, str]]:
    """Get list of commits (hash, short_hash, subject) since the specified commit."""
    # format: hash|subject
    code, stdout, _ = run_git(["log", f"{commit_hash}..HEAD", "--reverse", "--format=%H|%s"])
    if code != 0 or not stdout:
        return []
    
    commits = []
    for line in stdout.splitlines():
        if "|" in line:
            h, subj = line.split("|", 1)
            commits.append((h, h[:7], subj))
    return commits

def has_unstaged_changes() -> bool:
    """Check if there are any unstaged or staged changes in the workspace."""
    code, stdout, _ = run_git(["status", "--porcelain"])
    return code == 0 and bool(stdout)

def main():
    parser = argparse.ArgumentParser(
        description="Interactive Git Squash Helper - Safe squashing using soft-resets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python git_squash_helper.py                   # Auto-detects base branch (main/master) and prompts interactively
  python git_squash_helper.py --base develop    # Squash commits since diverging from develop branch
  python git_squash_helper.py -n 3              # Squash the last 3 commits
  python git_squash_helper.py -n 4 -m "Feature: core components"
        """
    )
    parser.add_argument("-b", "--base", type=str, help="Base branch to calculate commits since (e.g. main, master, develop)")
    parser.add_argument("-n", "--count", type=int, help="Squash exactly the last N commits")
    parser.add_argument("-m", "--message", type=str, help="Commit message for the squashed commit")
    parser.add_argument("--dry-run", action="store_true", help="Preview the squash action without executing")
    
    args = parser.parse_args()

    # 1. Verify clean repository
    if has_unstaged_changes():
        print_colored("Warning: You have uncommitted or untracked files in your working directory.", YELLOW)
        print_colored("It is highly recommended to stash or commit your changes before squashing.", YELLOW)
        ans = input("Proceed anyway? (y/N): ").strip().lower()
        if ans != 'y':
            print("Aborted.")
            sys.exit(0)

    # 2. Get current branch
    current_branch = get_current_branch()
    print_colored(f"Current branch: {BOLD}{current_branch}{RESET}", CYAN)

    # 3. Determine base branch if not provided
    base_branch = args.base
    if not base_branch:
        # Check standard branches
        for b in ["main", "master", "develop", "origin/main", "origin/master"]:
            code, _, _ = run_git(["rev-parse", "--verify", b])
            if code == 0:
                base_branch = b
                break
        if not base_branch:
            print_colored("Error: Could not auto-detect a base branch (main, master, develop). Please specify with --base.", RED)
            sys.exit(1)

    print_colored(f"Base branch: {BOLD}{base_branch}{RESET}", CYAN)

    # 4. Get commits to squash
    commits = []
    if args.count:
        if args.count < 2:
            print_colored("Error: You must squash at least 2 commits.", RED)
            sys.exit(1)
        # Get list of last N commits
        code, stdout, _ = run_git(["log", f"-{args.count}", "--reverse", "--format=%H|%s"])
        if code == 0 and stdout:
            for line in stdout.splitlines():
                if "|" in line:
                    h, subj = line.split("|", 1)
                    commits.append((h, h[:7], subj))
        if len(commits) < args.count:
            print_colored(f"Error: Current branch only has {len(commits)} commits total.", RED)
            sys.exit(1)
    else:
        # Find divergence point
        ancestor = get_merge_base(base_branch)
        commits = get_commits_since(ancestor)
        
        if not commits:
            print_colored(f"No commits found on branch '{current_branch}' since diverging from '{base_branch}'.", GREEN)
            return

    # 5. Display commits
    print_colored(f"\nFound {len(commits)} commit(s) to squash:", BOLD)
    for idx, (_, short_h, subj) in enumerate(commits, 1):
        print(f"  {idx:2d}. {short_h} - {subj}")

    if len(commits) < 2:
        print_colored("\nNeed at least 2 commits to perform a squash.", YELLOW)
        return

    # 6. Prepare squashed commit message
    default_msg = ""
    # Aggregate subject lines
    default_msg += "Squashed commits:\n"
    for _, _, subj in commits:
        default_msg += f"- {subj}\n"

    commit_msg = args.message if args.message else default_msg

    print_colored("\nProposed Commit Message:", BOLD)
    print_colored(commit_msg, YELLOW)

    # 7. Ask for confirmation
    if args.dry_run:
        print_colored("\n[Dry Run] Squash preview complete. No changes made.", GREEN)
        return

    confirm = input(f"\nAre you sure you want to squash these {len(commits)} commits? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Squash cancelled.")
        return

    # 8. Perform soft reset to the parent of the oldest commit in the list
    # The oldest commit in our list is commits[0][0]
    target_parent = f"{commits[0][0]}^"
    
    print(f"\nPerforming soft reset to {target_parent}...")
    code, stdout, stderr = run_git(["reset", "--soft", target_parent])
    if code != 0:
        print_colored(f"Error resetting branch: {stderr}", RED)
        print_colored("If reset failed, your branch remains unchanged.", YELLOW)
        sys.exit(1)

    # 9. Create the new combined commit
    # Write message to temp file to handle multiline safely
    temp_msg_file = ".git_squash_msg.tmp"
    try:
        with open(temp_msg_file, "w", encoding="utf-8") as f:
            f.write(commit_msg)
        
        print("Creating squashed commit...")
        code, stdout, stderr = run_git(["commit", "-F", temp_msg_file])
        if code != 0:
            print_colored(f"Error creating squashed commit: {stderr}", RED)
            print_colored("Your changes are still staged. You can commit them manually using:", YELLOW)
            print_colored("  git commit -m \"<your message>\"", BOLD)
        else:
            print_colored("\nSuccess! Commits successfully squashed.", GREEN)
            _, show_out, _ = run_git(["log", "-1", "--stat"])
            print(show_out)
    finally:
        if os.path.exists(temp_msg_file):
            os.remove(temp_msg_file)

if __name__ == "__main__":
    main()
