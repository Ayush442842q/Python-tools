#!/usr/bin/env python3
"""
Git Stash Manager
An advanced CLI utility to inspect, search, and manage Git stashes.

Usage:
    python tools/git_stash_manager.py --list
    python tools/git_stash_manager.py --show 0
    python tools/git_stash_manager.py --search "work in progress"
    python tools/git_stash_manager.py --apply 1
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


def run_git_command(args: List[str]) -> Tuple[int, str, str]:
    """Execute a Git command and return its exit code, stdout, and stderr."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        print_colored("[!] Error: 'git' executable not found. Please ensure Git is installed.", COLOR_FAIL)
        sys.exit(1)


def is_git_repository() -> bool:
    """Check if the current directory is inside a Git repository."""
    code, _, _ = run_git_command(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def get_stash_list() -> List[Dict]:
    """Fetch and parse the list of stashes."""
    # Format options:
    # %gd: Ref name (e.g. stash@{0})
    # %h: Abbreviated commit hash
    # %gs: Stash subject
    # %cr: Committer date, relative (e.g. 2 hours ago)
    # %cd: Committer date (RFC2822 format)
    format_str = "%gd|%h|%gs|%cr|%cd"
    code, stdout, stderr = run_git_command(["stash", "list", f"--pretty=format:{format_str}"])
    
    if code != 0:
        print_colored(f"[!] Failed to retrieve stash list: {stderr}", COLOR_FAIL)
        sys.exit(1)
        
    stashes = []
    if not stdout:
        return stashes
        
    for line in stdout.split("\n"):
        parts = line.split("|")
        if len(parts) >= 5:
            ref, commit_hash, subject, relative_date, absolute_date = parts[:5]
            # Extract stash index, e.g., stash@{0} -> 0
            index_match = re.search(r"\{(\d+)\}", ref)
            index = int(index_match.group(1)) if index_match else -1
            
            # Parse branch name if present in subject, e.g. "WIP on main: ..."
            branch_match = re.search(r"WIP on ([^:]+):", subject)
            branch = branch_match.group(1) if branch_match else "unknown"
            
            stashes.append({
                "index": index,
                "ref": ref,
                "hash": commit_hash,
                "subject": subject,
                "relative_date": relative_date,
                "absolute_date": absolute_date,
                "branch": branch
            })
    return stashes


def display_stashes(stashes: List[Dict], search_query: Optional[str] = None):
    """Render the list of stashes in a visual table."""
    if not stashes:
        print_colored("[*] No stashes found.", COLOR_CYAN)
        return

    filtered_stashes = stashes
    if search_query:
        query = search_query.lower()
        filtered_stashes = [
            s for s in stashes 
            if query in s["subject"].lower() or query in s["branch"].lower()
        ]
        if not filtered_stashes:
            print_colored(f"[*] No stashes matching '{search_query}' found.", COLOR_WARNING)
            return

    # Calculate column widths
    idx_w = 5
    branch_w = max(len(s["branch"]) for s in filtered_stashes)
    branch_w = max(branch_w, 10)
    hash_w = 8
    date_w = max(len(s["relative_date"]) for s in filtered_stashes)
    date_w = max(date_w, 12)
    
    # Table Header
    header = f"{'Index':<{idx_w}} | {'Branch':<{branch_w}} | {'Hash':<{hash_w}} | {'Created':<{date_w}} | Description"
    print_colored("-" * len(header), COLOR_BLUE)
    print_colored(header, COLOR_BOLD + COLOR_HEADER)
    print_colored("-" * len(header), COLOR_BLUE)
    
    for s in filtered_stashes:
        row = f"{s['index']:<{idx_w}} | {s['branch']:<{branch_w}} | {s['hash']:<{hash_w}} | {s['relative_date']:<{date_w}} | {s['subject']}"
        print(row)
    print_colored("-" * len(header), COLOR_BLUE)
    print_colored(f"Total: {len(filtered_stashes)} stash(es) listed.", COLOR_CYAN)


def show_stash_details(index: int):
    """Show details of a specific stash (modified files and diff stat)."""
    stashes = get_stash_list()
    stash = next((s for s in stashes if s["index"] == index), None)
    
    if not stash:
        print_colored(f"[!] Error: Stash at index {index} not found.", COLOR_FAIL)
        return

    print_colored(f"\n{COLOR_BOLD}Stash Details for stash@{{{index}}}{COLOR_END}", COLOR_CYAN)
    print(f"Commit Hash:   {stash['hash']}")
    print(f"Active Branch: {stash['branch']}")
    print(f"Date Created:  {stash['absolute_date']} ({stash['relative_date']})")
    print(f"Description:   {stash['subject']}")
    print("-" * 60)

    # Fetch file change summary
    code, stdout, stderr = run_git_command(["stash", "show", f"stash@{{{index}}}"])
    if code == 0 and stdout:
        print_colored("Modified Files:", COLOR_BOLD + COLOR_BLUE)
        print(stdout)
    else:
        print_colored("[*] No structural file differences or empty stash.", COLOR_WARNING)
        
    print("-" * 60)
    # Ask if user wants to see the raw diff
    print_colored("Stash Diff Overview (first 20 lines):", COLOR_BOLD + COLOR_BLUE)
    diff_code, diff_out, _ = run_git_command(["stash", "show", "-p", f"stash@{{{index}}}"])
    if diff_code == 0 and diff_out:
        lines = diff_out.split("\n")
        for line in lines[:20]:
            if line.startswith("+") and not line.startswith("+++"):
                print_colored(line, COLOR_GREEN)
            elif line.startswith("-") and not line.startswith("---"):
                print_colored(line, COLOR_FAIL)
            elif line.startswith("@@"):
                print_colored(line, COLOR_CYAN)
            else:
                print(line)
        if len(lines) > 20:
            print_colored(f"... [Truncated {len(lines) - 20} lines. Run 'git stash show -p stash@{{{index}}}' for full diff]", COLOR_WARNING)
    else:
        print("No diff payload found.")


def manage_stash(action: str, index: int):
    """Apply, pop, or drop a stash."""
    ref = f"stash@{{{index}}}"
    stashes = get_stash_list()
    if not any(s["index"] == index for s in stashes):
        print_colored(f"[!] Error: Stash at index {index} does not exist.", COLOR_FAIL)
        sys.exit(1)
        
    if action == "apply":
        print_colored(f"[*] Applying {ref}...", COLOR_CYAN)
        code, stdout, stderr = run_git_command(["stash", "apply", ref])
    elif action == "pop":
        print_colored(f"[*] Popping (applying and dropping) {ref}...", COLOR_CYAN)
        code, stdout, stderr = run_git_command(["stash", "pop", ref])
    elif action == "drop":
        print_colored(f"[*] Dropping {ref}...", COLOR_WARNING)
        code, stdout, stderr = run_git_command(["stash", "drop", ref])
    else:
        return
        
    if code == 0:
        print_colored(f"[+] Success: {action.capitalize()} operation completed.", COLOR_GREEN)
        if stdout:
            print(stdout)
    else:
        print_colored(f"[!] Failed to {action} {ref}:", COLOR_FAIL)
        print(stderr or stdout)


def prune_old_stashes(days: int):
    """Drop stashes older than the specified number of days."""
    stashes = get_stash_list()
    if not stashes:
        print_colored("[*] No stashes to prune.", COLOR_CYAN)
        return

    now = datetime.now()
    pruned_count = 0

    print_colored(f"[*] Scanning for stashes older than {days} days...", COLOR_CYAN)
    
    # We must delete from highest index to lowest to avoid index shifting problems
    for stash in sorted(stashes, key=lambda x: x["index"], reverse=True):
        date_str = stash["absolute_date"]
        try:
            # Clean timezone offset if present (e.g. +0530)
            clean_date_str = re.sub(r"\s[+-]\d{4}$", "", date_str).strip()
            dt = datetime.strptime(clean_date_str, "%a, %d %b %Y %H:%M:%S")
            age_days = (now - dt).days
            
            if age_days > days:
                print_colored(f"[-] Pruning index {stash['index']} (Age: {age_days} days, Description: {stash['subject']})", COLOR_WARNING)
                code, _, stderr = run_git_command(["stash", "drop", f"stash@{{{stash['index']}}}"])
                if code == 0:
                    pruned_count += 1
                else:
                    print_colored(f"    [!] Failed to drop stash@{{{stash['index']}}}: {stderr}", COLOR_FAIL)
        except ValueError as ve:
            print_colored(f"[!] Could not parse date format '{date_str}' for index {stash['index']}: {ve}", COLOR_WARNING)

    print_colored(f"[+] Pruning finished. Removed {pruned_count} stash(es).", COLOR_GREEN)


def main():
    parser = argparse.ArgumentParser(
        description="Advanced Git Stash Manager CLI utility.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", "-l", action="store_true", help="List all stashes (default)")
    group.add_argument("--show", "-s", type=int, metavar="INDEX", help="Show detailed diff statistics for a stash index")
    group.add_argument("--apply", "-a", type=int, metavar="INDEX", help="Apply the stash at the specified index")
    group.add_argument("--pop", "-p", type=int, metavar="INDEX", help="Pop (apply and delete) the stash at the specified index")
    group.add_argument("--drop", "-d", type=int, metavar="INDEX", help="Drop (delete) the stash at the specified index")
    group.add_argument("--prune", type=int, metavar="DAYS", help="Prune stashes older than the specified number of days")
    
    parser.add_argument("--search", "-q", type=str, metavar="QUERY", help="Filter stashes by description/branch name")

    args = parser.parse_args()

    # Verify if directory is a git repo
    if not is_git_repository():
        print_colored("[!] Error: Current directory is not a Git repository.", COLOR_FAIL)
        sys.exit(1)

    if args.show is not None:
        show_stash_details(args.show)
    elif args.apply is not None:
        manage_stash("apply", args.apply)
    elif args.pop is not None:
        manage_stash("pop", args.pop)
    elif args.drop is not None:
        manage_stash("drop", args.drop)
    elif args.prune is not None:
        prune_old_stashes(args.prune)
    else:
        stashes = get_stash_list()
        display_stashes(stashes, args.search)


if __name__ == "__main__":
    main()
