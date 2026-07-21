#!/usr/bin/env python3
"""
Git Branch Cleaner
Cleans up local Git branches that have been merged or whose upstream tracking branches have been deleted.

Usage:
    python tools/git_branch_cleaner.py [options]

Options:
    -d, --dry-run        Show which branches would be deleted without actually deleting them
    -m, --main BRANCH    Specify the main branch (default: auto-detect 'main' or 'master')
    -p, --prune          Run 'git fetch --prune' before scanning to update remote-tracking branches
    -f, --force          Force delete branches even if they are not fully merged
    -h, --help           Show this help message and exit

Example:
    python tools/git_branch_cleaner.py --dry-run
    python tools/git_branch_cleaner.py --prune
"""

import argparse
import subprocess
import sys
import os


def run_git_command(args, cwd=None):
    """Run a git command and return its stdout, or raise an exception on error."""
    try:
        result = subprocess.run(
            ['git'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please ensure Git is installed and in your PATH.")


def get_current_branch():
    """Get the name of the currently checked out branch."""
    return run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'])


def get_all_local_branches():
    """Get all local branch names."""
    output = run_git_command(['branch', '--format=%(refname:short)'])
    return [line.strip() for line in output.split('\n') if line.strip()]


def detect_main_branch():
    """Detect whether 'main' or 'master' is the primary branch."""
    branches = get_all_local_branches()
    if 'main' in branches:
        return 'main'
    if 'master' in branches:
        return 'master'
    # Fallback to current branch
    return get_current_branch()


def get_merged_branches(main_branch):
    """Get list of local branches that have been merged into main_branch."""
    output = run_git_command(['branch', '--merged', main_branch, '--format=%(refname:short)'])
    merged = [line.strip() for line in output.split('\n') if line.strip()]
    return merged


def get_gone_branches():
    """Get list of local branches whose remote tracking branch is 'gone'."""
    output = run_git_command(['branch', '-vv'])
    gone_branches = []
    for line in output.split('\n'):
        if not line.strip():
            continue
        # Format of branch -vv is:
        # * main                  a1b2c3d [origin/main] Commit message
        #   feature-branch        d4e5f6g [origin/feature-branch: gone] Commit message
        # We look for "[origin/xxxx: gone]"
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        
        # Determine branch name
        branch_name = parts[0]
        if branch_name == '*':
            branch_name = parts[1]
            
        rest = parts[2]
        if ': gone]' in rest:
            gone_branches.append(branch_name)
            
    return gone_branches


def main():
    parser = argparse.ArgumentParser(description="Clean up merged or stale local Git branches.")
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help='Preview branch deletions without performing them')
    parser.add_argument('-m', '--main', help='Specify the main integration branch (e.g. main, master)')
    parser.add_argument('-p', '--prune', action='store_true',
                        help="Run 'git fetch --prune' before scanning")
    parser.add_argument('-f', '--force', action='store_true',
                        help='Force delete branches even if they are not fully merged')
    
    args = parser.parse_args()

    # Check if we are in a git repository
    if not os.path.exists('.git'):
        # Check if parent directories contain .git (run git rev-parse to be sure)
        try:
            run_git_command(['rev-parse', '--is-inside-work-tree'])
        except RuntimeError:
            print("Error: Current directory is not a Git repository.", file=sys.stderr)
            return 1

    try:
        current_branch = get_current_branch()
        
        if args.prune:
            print("Fetching and pruning remote tracking branches...")
            try:
                run_git_command(['fetch', '--prune', '--all'])
            except Exception as e:
                print(f"Warning: Failed to fetch/prune: {e}", file=sys.stderr)

        main_branch = args.main if args.main else detect_main_branch()
        print(f"Primary branch identified as: {main_branch}")
        print(f"Current branch: {current_branch}")

        # Gather merged and gone branches
        merged_branches = get_merged_branches(main_branch)
        gone_branches = get_gone_branches()
        
        # Candidates for deletion
        candidates = set()
        
        # Branches merged into main branch
        for b in merged_branches:
            candidates.add(b)
            
        # Stale tracking branches (gone)
        for b in gone_branches:
            candidates.add(b)

        # Protection list: do not delete these branches
        protected_branches = {main_branch, current_branch, 'master', 'main', 'develop', 'dev'}
        to_delete = sorted([b for b in candidates if b not in protected_branches])

        if not to_delete:
            print("No stale local branches found to clean up.")
            return 0

        print(f"\nFound {len(to_delete)} branches eligible for deletion:")
        for b in to_delete:
            reason = []
            if b in merged_branches:
                reason.append("merged")
            if b in gone_branches:
                reason.append("remote-deleted/gone")
            print(f"  - {b} ({', '.join(reason)})")

        if args.dry_run:
            print("\n[Dry Run] No branches were deleted.")
            return 0

        # Perform deletion
        deleted_count = 0
        failed_count = 0
        
        print("\nDeleting branches:")
        for b in to_delete:
            # Determine delete command (-d for safe, -D for forced/unsafe)
            del_flag = '-D' if (args.force or b in gone_branches) else '-d'
            try:
                run_git_command(['branch', del_flag, b])
                print(f"  Successfully deleted: {b}")
                deleted_count += 1
            except Exception as e:
                print(f"  Failed to delete: {b} -> {e}")
                failed_count += 1

        print(f"\nCleanup complete: {deleted_count} branches deleted, {failed_count} failed.")

    except Exception as e:
        print(f"Error during execution: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
