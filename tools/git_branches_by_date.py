#!/usr/bin/env python3
"""
Git Branches by Date

A CLI utility to list local (and optionally remote) Git branches sorted by their
last commit date, showing the author, last commit subject, and merge status.
Helps developers locate stale branches for repository cleanup.

Usage:
    python tools/git_branches_by_date.py [options]
"""

import argparse
import sys
import subprocess
from datetime import datetime

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

def run_git(args):
    """Helper to run git commands and return output."""
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.strip() or f"Git command failed: {' '.join(args)}")
    except FileNotFoundError:
        raise RuntimeError("Git executable not found on this system.")

def parse_date(date_str):
    """Parse ISO git date string into a datetime object."""
    # format: 2026-06-28 15:19:15 +0530
    try:
        # Strip timezone offset for simple parsing
        clean_date = date_str.split(' ')[0] + ' ' + date_str.split(' ')[1]
        return datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.min

def get_merged_branches():
    """Returns a set of branches merged into HEAD."""
    merged_output = run_git(["branch", "--merged"])
    merged = set()
    for line in merged_output.split('\n'):
        line = line.strip().replace('*', '').strip()
        if line:
            merged.add(line)
    return merged

def main():
    parser = argparse.ArgumentParser(description="List Git branches sorted by last commit date.")
    parser.add_argument("-r", "--remote", action="store_true", help="Include remote tracking branches")
    parser.add_argument("-a", "--all", action="store_true", help="List both local and remote branches")
    parser.add_argument("--merged", action="store_true", help="Only show branches merged into HEAD")
    parser.add_argument("--no-merged", action="store_true", help="Only show branches NOT merged into HEAD")
    parser.add_argument("--reverse", action="store_true", help="Sort oldest first (default: newest first)")
    parser.add_argument("--no-color", action="store_true", help="Disable color outputs")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    try:
        # Verify if in git repo
        run_git(["rev-parse", "--is-inside-work-tree"])
    except RuntimeError as e:
        print(f"{COLORS['red']}Error: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    # Get branch format data
    # format fields: refname, commit date (ISO), author name, subject
    branch_args = ["branch"]
    if args.all:
        branch_args.append("-a")
    elif args.remote:
        branch_args.append("-r")
        
    branch_args.append('--format=%(refname:short)|%(authordate:iso)|%(authorname)|%(subject)')
    
    try:
        branch_data = run_git(branch_args)
        merged_set = get_merged_branches()
    except Exception as e:
        print(f"{COLORS['red']}Error: {e}{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    branches = []
    for line in branch_data.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('|', 3)
        if len(parts) < 4:
            continue
            
        refname, date_str, author, subject = parts
        
        # Skip HEAD pointer in remote branches list
        if "-> HEAD" in refname or "origin/HEAD" in refname:
            continue
            
        # Determine merge status
        is_merged = refname in merged_set or refname.replace("origin/", "") in merged_set
        
        # Apply filters
        if args.merged and not is_merged:
            continue
        if args.no_merged and is_merged:
            continue
            
        branches.append({
            "name": refname,
            "date_str": date_str,
            "date": parse_date(date_str),
            "author": author,
            "subject": subject,
            "merged": is_merged
        })
        
    # Sort
    branches.sort(key=lambda x: x["date"], reverse=not args.reverse)
    
    if not branches:
        print("No branches found matching the criteria.")
        return
        
    # Print table header
    print(f"{COLORS['bold']}{'BRANCH':<30} {'LAST COMMIT DATE':<20} {'AUTHOR':<15} {'MERGED':<8} {'LAST COMMIT SUBJECT':<40}{COLORS['reset']}")
    print("-" * 120)
    
    for b in branches:
        merged_disp = f"{COLORS['green']}Yes{COLORS['reset']}" if b["merged"] else f"{COLORS['red']}No{COLORS['reset']}"
        
        # Format date for display
        date_disp = b["date_str"].split(' ')[0] + ' ' + b["date_str"].split(' ')[1][:5] if b["date_str"] else "N/A"
        
        # Truncate subject if too long
        subj = b["subject"]
        if len(subj) > 40:
            subj = subj[:37] + "..."
            
        author_disp = b["author"]
        if len(author_disp) > 15:
            author_disp = author_disp[:12] + "..."
            
        # Highlight main/master branches
        name_disp = b["name"]
        if name_disp in ("main", "master", "origin/main", "origin/master"):
            name_disp = f"{COLORS['cyan']}{COLORS['bold']}{name_disp}{COLORS['reset']}"
        else:
            name_disp = f"{COLORS['yellow']}{name_disp}{COLORS['reset']}"
            
        print(f"{name_disp:<39} {date_disp:<20} {author_disp:<15} {merged_disp:<17} {subj:<40}")

if __name__ == "__main__":
    main()
