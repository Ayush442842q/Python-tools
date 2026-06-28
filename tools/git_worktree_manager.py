#!/usr/bin/env python3
"""
Git Worktree Manager

A utility tool to list, add, remove, and prune Git worktrees, making it easier
to manage concurrent branch checkouts in separate directories.

Usage:
    python tools/git_worktree_manager.py list
    python tools/git_worktree_manager.py add path/to/dir branch_name [-b]
    python tools/git_worktree_manager.py remove path/to/dir [--force]
    python tools/git_worktree_manager.py prune
"""

import argparse
import sys
import os
import subprocess

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

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def run_cmd(args, cwd=None):
    """Helper to run shell command and return stdout. Raises on failure."""
    res = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        encoding='utf-8',
        errors='ignore'
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"Command failed with exit code {res.returncode}")
    return res.stdout.strip()

def check_git_repo():
    try:
        run_cmd(["git", "rev-parse", "--is-inside-work-tree"])
    except Exception:
        print(f"{COLORS['red']}Error: Current directory or parent is not a Git repository.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)

def list_worktrees():
    """Lists all active worktrees with details."""
    try:
        # 'git worktree list --porcelain' gives details line-by-line
        # format:
        # worktree /path/to/dir
        # commit <hash>
        # branch refs/heads/<name>
        output = run_cmd(["git", "worktree", "list", "--porcelain"])
    except Exception as e:
        print(f"{COLORS['red']}Failed to list worktrees: {e}{COLORS['reset']}", file=sys.stderr)
        return

    worktrees = []
    current = {}
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        
        parts = line.split(' ', 1)
        if len(parts) == 2:
            key, val = parts
            current[key] = val
    if current:
        worktrees.append(current)

    if not worktrees:
        print("No worktrees found.")
        return

    print(f"{COLORS['bold']}{'PATH':<50} {'BRANCH':<20} {'COMMIT':<10} {'STATUS':<10}{COLORS['reset']}")
    print("-" * 95)
    
    for wt in worktrees:
        path = wt.get("worktree", "")
        branch_ref = wt.get("branch", "")
        commit = wt.get("commit", "")[:8] if "commit" in wt else "N/A"
        
        # Format branch name
        if branch_ref.startswith("refs/heads/"):
            branch = branch_ref[len("refs/heads/"):]
        else:
            branch = branch_ref or "detached HEAD"
            
        # Determine status (main repo or additional worktree)
        is_main = " (main)" if worktrees.index(wt) == 0 else ""
        status = "Main" if is_main else "Worktree"
        
        path_display = path
        # Shorten path display if it fits inside terminal nicely or highlight main
        if is_main:
            path_display = f"{COLORS['blue']}{path}{COLORS['reset']}"
            branch_display = f"{COLORS['cyan']}{branch}{COLORS['reset']}"
        else:
            path_display = f"{COLORS['green']}{path}{COLORS['reset']}"
            branch_display = f"{COLORS['yellow']}{branch}{COLORS['reset']}"

        print(f"{path_display:<59} {branch_display:<29} {commit:<10} {status:<10}")

def add_worktree(path, branch, create_new=False):
    """Adds a new worktree check out at path on branch."""
    cmd = ["git", "worktree", "add"]
    if create_new:
        cmd.append("-b")
    cmd.extend([path, branch])
    
    print(f"Creating worktree at '{COLORS['cyan']}{path}{COLORS['reset']}' checking out branch '{COLORS['green']}{branch}{COLORS['reset']}'...")
    try:
        out = run_cmd(cmd)
        print(out)
        print(f"{COLORS['green']}Successfully created worktree!{COLORS['reset']}")
    except Exception as e:
        print(f"{COLORS['red']}Failed to add worktree: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)

def remove_worktree(path, force=False):
    """Removes a worktree and deletes its administrative dir and files."""
    cmd = ["git", "worktree", "remove", path]
    if force:
        cmd.append("--force")
        
    print(f"Removing worktree at '{COLORS['cyan']}{path}{COLORS['reset']}'...")
    try:
        out = run_cmd(cmd)
        if out:
            print(out)
        print(f"{COLORS['green']}Successfully removed worktree!{COLORS['reset']}")
    except Exception as e:
        print(f"{COLORS['red']}Failed to remove worktree: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)

def prune_worktrees():
    """Prunes stale worktree administrative directories."""
    print("Pruning stale worktree administrative directories...")
    try:
        out = run_cmd(["git", "worktree", "prune", "-v"])
        if out:
            print(out)
        else:
            print("No stale worktrees to prune.")
        print(f"{COLORS['green']}Pruning complete.{COLORS['reset']}")
    except Exception as e:
        print(f"{COLORS['red']}Failed to prune: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Git Worktree Management Utility")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-commands")
    
    # List sub-command
    subparsers.add_parser("list", help="List all worktrees")
    
    # Add sub-command
    add_parser = subparsers.add_parser("add", help="Add a new worktree")
    add_parser.add_argument("path", help="Path to create the worktree directory")
    add_parser.add_argument("branch", help="Branch to checkout in the worktree")
    add_parser.add_argument("-b", "--create-branch", action="store_true", help="Create a new branch instead of checking out existing")
    
    # Remove sub-command
    remove_parser = subparsers.add_parser("remove", help="Remove an existing worktree")
    remove_parser.add_argument("path", help="Path of the worktree directory to remove")
    remove_parser.add_argument("-f", "--force", action="store_true", help="Force removal of dirty or modified worktree")
    
    # Prune sub-command
    subparsers.add_parser("prune", help="Prune stale worktree details")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    check_git_repo()
    
    if args.command == "list":
        list_worktrees()
    elif args.command == "add":
        add_worktree(args.path, args.branch, args.create_branch)
    elif args.command == "remove":
        remove_worktree(args.path, args.force)
    elif args.command == "prune":
        prune_worktrees()

if __name__ == "__main__":
    main()
