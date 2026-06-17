#!/usr/bin/env python3
"""
git_large_file_finder - Git Large File Finder and History Analyzer

Scans the commit history of a local Git repository to identify large files
bloating the repository. It lists the largest blobs, summarizes cumulative sizes
by file path, finds the commits introducing them, and details how to remove them.

Usage:
    python tools/git_large_file_finder.py [--limit 10] [--min-size 1048576]
"""

import argparse
import subprocess
import sys
import os


def run_command(cmd, cwd=None):
    """Utility to run a system command and return stdout/stderr."""
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=True
        )
        return res.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr
    except FileNotFoundError:
        return None, "Command not found (is Git installed?)"


def format_size(bytes_sz):
    """Formats bytes into human-readable strings."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_sz < 1024.0:
            return f"{bytes_sz:.2f} {unit}"
        bytes_sz /= 1024.0
    return f"{bytes_sz:.2f} TB"


def get_git_objects(cwd):
    """
    Retrieves all blobs and their sizes in git history.
    Returns a dict: {sha: (size_bytes, path)}
    """
    # 1. Get list of all objects reachable in all refs
    stdout, err = run_command(['git', 'rev-list', '--objects', '--all'], cwd)
    if err:
        return None, f"Could not list git objects: {err}"

    lines = stdout.splitlines()
    sha_to_path = {}
    hashes_to_check = []

    for line in lines:
        parts = line.split(' ', 1)
        sha = parts[0]
        if len(parts) > 1:
            path = parts[1]
            sha_to_path[sha] = path
            hashes_to_check.append(sha)

    if not hashes_to_check:
        return {}, None

    # 2. Get sizes using git cat-file in batch mode
    # We pass hashes through stdin to cat-file
    try:
        proc = subprocess.Popen(
            ['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
            encoding='utf-8'
        )
        batch_input = "\n".join(hashes_to_check)
        stdout, stderr = proc.communicate(input=batch_input)
    except Exception as e:
        return None, f"Failed to run git cat-file: {e}"

    objects = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            sha, obj_type, size_str = parts
            if obj_type == 'blob':
                size = int(size_str)
                path = sha_to_path.get(sha, "Unknown")
                objects[sha] = (size, path)

    return objects, None


def get_introducing_commits(path, cwd):
    """Finds the commits where the large file path was modified."""
    stdout, err = run_command(['git', 'log', '--oneline', '--follow', '--all', '--', path], cwd)
    if err or not stdout:
        return ["Unknown Commit"]
    return stdout.splitlines()[:3]  # Return top 3 commits


def main():
    parser = argparse.ArgumentParser(
        description="Scans local Git repository commit history to find large files."
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of files to display (default: 10)")
    parser.add_argument("--min-size", type=int, default=1024*1024, help="Minimum file size in bytes to report (default: 1MB)")
    parser.add_argument("--cwd", default=".", help="Path to git repository (default: current directory)")

    args = parser.parse_args()

    # Verify directory is a git repo
    if not os.path.isdir(args.cwd):
        print(f"Error: Directory '{args.cwd}' does not exist.", file=sys.stderr)
        return 1

    is_repo, err = run_command(['git', 'rev-parse', '--is-inside-work-tree'], args.cwd)
    if err or "true" not in is_repo.lower():
        print(f"Error: Directory '{args.cwd}' is not inside a Git repository.", file=sys.stderr)
        return 1

    print("Scanning Git repository history for large blobs... (this may take a few seconds)")
    objects, err = get_git_objects(args.cwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if not objects:
        print("No file blobs found in Git history.")
        return 0

    # Sort objects by size
    sorted_objects = sorted(objects.items(), key=lambda x: x[1][0], reverse=True)

    # 1. Largest Single Blobs
    large_blobs = [item for item in sorted_objects if item[1][0] >= args.min_size]

    # 2. Cumulative Sizes by Path (multiple versions of a file)
    cumulative_sizes = {}
    for sha, (size, path) in sorted_objects:
        cumulative_sizes[path] = cumulative_sizes.get(path, 0) + size

    sorted_cumulative = sorted(cumulative_sizes.items(), key=lambda x: x[1], reverse=True)
    large_cumulative = [item for item in sorted_cumulative if item[1] >= args.min_size]

    print("\n" + "=" * 80)
    print(" GIT LARGE FILE HISTORY ANALYSIS")
    print("=" * 80)

    # Display Top Single Blobs
    print(f"\n[Top {args.limit} Largest Individual Blobs (>= {format_size(args.min_size)})]")
    print(f"{'SHA':<10} | {'Size':<12} | {'File Path'}")
    print("-" * 80)
    
    shown_blobs = large_blobs[:args.limit]
    for sha, (size, path) in shown_blobs:
        print(f"{sha[:8]:<10} | {format_size(size):<12} | {path}")

    # Display Top Cumulative paths
    print(f"\n[Top {args.limit} Largest Cumulative Paths in History (Total across all commits)]")
    print(f"{'Total Size':<12} | {'File Path'}")
    print("-" * 80)
    
    shown_cumulative = large_cumulative[:args.limit]
    for path, size in shown_cumulative:
        print(f"{format_size(size):<12} | {path}")

    # Display introduction commits for the top 3 largest single blobs
    if shown_blobs:
        print("\n[History Details for Largest Blobs]")
        for idx, (sha, (size, path)) in enumerate(shown_blobs[:3], 1):
            print(f"\n  {idx}. {path} ({format_size(size)})")
            commits = get_introducing_commits(path, args.cwd)
            print("     Recent commits modifying this path:")
            for c in commits:
                print(f"       - {c}")

    # Pruning tips
    if large_blobs:
        largest_path = large_blobs[0][1][1] if len(large_blobs[0][1]) > 1 else None
        example_path = largest_path or "path/to/large/file"
        print("\n" + "=" * 80)
        print(" ACTIONABLE HISTORY CLEANUP TIPS")
        print("=" * 80)
        print("To completely purge a file from your repository's history (including all tags/refs):")
        print("\nUsing git-filter-repo (recommended - requires pip install git-filter-repo):")
        print(f"  git filter-repo --path {example_path} --invert-paths")
        print("\nUsing legacy git filter-branch (slower):")
        print(f"  git filter-branch --force --index-filter \\")
        print(f"    \"git rm --cached --ignore-unmatch {example_path}\" \\")
        print("    --prune-empty --tag-name-filter cat -- --all")
        print("\nAfter pruning, force push to remote:")
        print("  git push origin --force --all --tags")
        print("=" * 80)
    else:
        print("\nNo files in history exceed the size threshold.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
