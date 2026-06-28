#!/usr/bin/env python3
"""
Gitignore Cleaner - Find and untrack committed files matching .gitignore patterns

This tool helps keep Git repositories clean by:
1. Identifying files currently tracked by Git that match .gitignore rules.
2. Generating or running git commands to untrack them (git rm --cached).
3. Analyzing .gitignore for redundant or duplicate pattern rules.

Usage:
    python tools/gitignore_cleaner.py [--clean] [--path REPO_PATH]
"""

import argparse
import os
import subprocess
import sys
from typing import List, Tuple, Set

def run_git_command(args_list: List[str], cwd: str) -> Tuple[int, str, str]:
    """Runs a git command and returns exit code, stdout, and stderr."""
    try:
        res = subprocess.run(
            ['git'] + args_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        return res.returncode, res.stdout, res.stderr
    except FileNotFoundError:
        print("Error: 'git' executable not found. Is Git installed?", file=sys.stderr)
        sys.exit(1)

def get_tracked_ignored_files(repo_path: str) -> List[str]:
    """Finds tracked files that are ignored by git rules."""
    # -c (cached/tracked), -i (ignored), --exclude-standard (standard ignore files)
    code, stdout, stderr = run_git_command(
        ['ls-files', '-c', '-i', '--exclude-standard'],
        repo_path
    )
    if code != 0:
        print(f"Error checking ignored files: {stderr}", file=sys.stderr)
        return []
    return [line.strip() for line in stdout.splitlines() if line.strip()]

def parse_gitignore(gitignore_path: str) -> List[Tuple[int, str]]:
    """Parses a gitignore file and returns (line_number, pattern) pairs."""
    patterns = []
    if not os.path.exists(gitignore_path):
        return []
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            # Ignore empty lines and comments
            if line and not line.startswith('#'):
                patterns.append((idx, line))
    return patterns

def check_redundant_rules(patterns: List[Tuple[int, str]]) -> List[Tuple[int, str, str]]:
    """Identifies redundant rules in gitignore patterns (e.g. nested ignores)."""
    redundant = []
    # Sort patterns by length/complexity
    for i, (line1, pat1) in enumerate(patterns):
        for j, (line2, pat2) in enumerate(patterns):
            if i == j:
                continue
            
            # Simple redundancy check:
            # 1. Exact duplicate
            if pat1 == pat2 and line1 > line2:
                redundant.append((line1, pat1, f"Duplicate of line {line2}"))
                break
                
            # 2. Directory wildcard redundancy:
            # E.g., if line 2 is "build/" and line 1 is "build/*.log" or "build/debug.txt"
            if pat2.endswith('/') and pat1.startswith(pat2) and len(pat1) > len(pat2):
                redundant.append((line1, pat1, f"Redundant under directory ignore '{pat2}' at line {line2}"))
                break
                
            # E.g., if line 2 is "*.log" and line 1 is "logs/*.log"
            if pat2.startswith('*.') and pat1.endswith(pat2) and len(pat1) > len(pat2):
                redundant.append((line1, pat1, f"Redundant under global extension ignore '{pat2}' at line {line2}"))
                break
    return redundant

def main():
    parser = argparse.ArgumentParser(
        description="Scan Git repository for tracked files matching .gitignore patterns and audit .gitignore itself."
    )
    parser.add_argument(
        '--path',
        default='.',
        help='Path to the Git repository root (default: current directory)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Actually run git rm --cached on the identified files'
    )
    parser.add_argument(
        '--audit-only',
        action='store_true',
        help='Only audit .gitignore for redundant rules, skip scanning repository files'
    )
    
    args = parser.parse_args()
    repo_path = os.path.abspath(args.path)
    
    if not os.path.exists(repo_path):
        print(f"Error: Path '{repo_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Check if path is a git repo
    code, stdout, stderr = run_git_command(['rev-parse', '--is-inside-work-tree'], repo_path)
    if code != 0 or 'true' not in stdout:
        print(f"Error: Path '{repo_path}' is not inside a Git repository.", file=sys.stderr)
        sys.exit(1)

    print(f"\033[94mAnalyzing Git repository at: {repo_path}\033[0m")
    
    # 1. Audit .gitignore
    gitignore_file = os.path.join(repo_path, '.gitignore')
    if os.path.exists(gitignore_file):
        print("\n\033[93m--- Auditing .gitignore for redundant rules ---\033[0m")
        patterns = parse_gitignore(gitignore_file)
        redundancies = check_redundant_rules(patterns)
        if redundancies:
            print(f"Found {len(redundancies)} redundant rules:")
            for line, pat, reason in redundancies:
                print(f"  Line {line:3d}: \033[91m{pat:<25}\033[0m -> {reason}")
        else:
            print("No redundant rules found in .gitignore!")
    else:
        print("\nNo .gitignore file found at the repository root.")

    if args.audit_only:
        return 0

    # 2. Check for tracked but ignored files
    print("\n\033[93m--- Scanning repository for tracked but ignored files ---\033[0m")
    files = get_tracked_ignored_files(repo_path)
    
    if not files:
        print("\033[92mSuccess: No tracked files are matching current .gitignore rules.\033[0m")
        return 0
        
    print(f"Found {len(files)} tracked files that match ignore rules:")
    total_size = 0
    for file in files:
        full_filepath = os.path.join(repo_path, file)
        size_str = "Unknown"
        if os.path.exists(full_filepath):
            size = os.path.getsize(full_filepath)
            total_size += size
            # format size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
        print(f"  - {file} ({size_str})")
        
    if total_size > 0:
        if total_size < 1024:
            total_size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            total_size_str = f"{total_size / 1024:.1f} KB"
        else:
            total_size_str = f"{total_size / (1024 * 1024):.1f} MB"
        print(f"Total potential disk space saved: \033[92m{total_size_str}\033[0m")
        
    # 3. Clean or show instructions
    if args.clean:
        print("\n\033[93mUntracking files...\033[0m")
        # Run in chunks to prevent argument length limit issues on large repos
        chunk_size = 50
        for i in range(0, len(files), chunk_size):
            chunk = files[i:i+chunk_size]
            rm_code, rm_stdout, rm_stderr = run_git_command(['rm', '--cached'] + chunk, repo_path)
            if rm_code == 0:
                for f in chunk:
                    print(f"  Untracked: {f}")
            else:
                print(f"Error untracking files: {rm_stderr}", file=sys.stderr)
        print("\n\033[92mFinished untracking files! Note: You must commit these changes to save them.\033[0m")
    else:
        print("\n\033[93mAction required:\033[0m")
        print("These files are committed to history. To untrack them (keeping local copies), run:")
        print("  \033[96mpython tools/gitignore_cleaner.py --clean\033[0m")
        print("Or manually via Git:")
        print(f"  \033[96mgit rm --cached <filename>\033[0m")

if __name__ == '__main__':
    main()
