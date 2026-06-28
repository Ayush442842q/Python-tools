#!/usr/bin/env python3
"""
Git Repository Health & Bloat Analyzer
Analyzes a local Git repository and provides a comprehensive health report:
- Measures .git database size and loose object count (indicates if garbage collection is needed)
- Scans history to identify the largest files (blobs) bloating the pack file database
- Lists top contributors and total commit count
- Identifies stale local branches (no commits in X days)
- Checks working tree status (uncommitted/untracked files)
- Validates presence of essential files (README, LICENSE, .gitignore)

License: MIT
"""

import os
import sys
import subprocess
import argparse
from collections import Counter
from datetime import datetime

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}[i] {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}[✗] Error: {msg}{Colors.ENDC}", file=sys.stderr)

def format_size(size_bytes):
    """Formats bytes into human-readable size formats."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def run_git_command(args, cwd=None):
    """Helper to run git subprocess commands."""
    try:
        result = subprocess.run(
            ['git'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("Git is not installed or not in system PATH.")

def is_git_repo(path):
    """Checks if a directory is a Git repository."""
    if not os.path.exists(path):
        return False
    try:
        out = run_git_command(['rev-parse', '--is-inside-work-tree'], cwd=path)
        return out == 'true'
    except Exception:
        return False

def get_git_dir_size(repo_path):
    """Calculates size of the .git directory."""
    git_dir = os.path.join(repo_path, '.git')
    total_size = 0
    if not os.path.exists(git_dir):
        return 0
    for dirpath, _, filenames in os.walk(git_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip symbolic links
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def analyze_git_bloat(repo_path, limit=10):
    """Finds the largest blobs in Git history using rev-list and cat-file."""
    print_info("Scanning Git history database for large blobs (this may take a few seconds)...")
    
    # We pipe rev-list into cat-file using Git's batch-check mode
    # Command: git rev-list --objects --all
    try:
        # Get list of all objects
        rev_list_proc = subprocess.Popen(
            ['git', 'rev-list', '--objects', '--all'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_path
        )
        
        # Batch check their type, size, and paths
        cat_file_proc = subprocess.Popen(
            ['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)'],
            stdin=rev_list_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_path,
            text=True
        )
        
        rev_list_proc.stdout.close()
        stdout, _ = cat_file_proc.communicate()
        
        blobs = []
        for line in stdout.splitlines():
            parts = line.strip().split(' ', 3)
            if len(parts) >= 3 and parts[1] == 'blob':
                sha = parts[0]
                size = int(parts[2])
                path = parts[3] if len(parts) > 3 else ""
                blobs.append((size, sha, path))
                
        # Remove duplicate SHAs to avoid listing different branches' reference to the same file
        unique_blobs = {}
        for size, sha, path in blobs:
            if sha not in unique_blobs or len(path) > len(unique_blobs[sha][1]):
                unique_blobs[sha] = (size, path)
                
        sorted_blobs = sorted(
            [(size, sha, path) for sha, (size, path) in unique_blobs.items()],
            key=lambda x: x[0],
            reverse=True
        )
        
        return sorted_blobs[:limit]
    except Exception as e:
        print_warning(f"Could not complete Git bloat analysis: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description="Git Repository Health & Bloat Analyzer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze git repository in the current directory
  python git_repo_health_analyzer.py
  
  # Analyze a specific repository path
  python git_repo_health_analyzer.py -p /path/to/repo
        """
    )
    
    parser.add_argument("-p", "--path", default=".", help="Path to the Git repository (default: current directory)")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Number of large files to list in bloat report (default: 10)")
    parser.add_argument("-s", "--stale-days", type=int, default=30, help="Threshold in days to define stale local branches (default: 30)")
    
    args = parser.parse_args()

    repo_path = os.path.abspath(args.path)

    if not os.path.exists(repo_path):
        print_error(f"Specified path does not exist: {repo_path}")
        sys.exit(1)

    if not is_git_repo(repo_path):
        print_error(f"The path '{repo_path}' is not inside a Git repository working tree.")
        sys.exit(1)

    print_success(f"Target repository: {repo_path}")

    # 1. Gather Repository Info
    print_header("Repository Metadata & Health")
    
    git_dir_size = get_git_dir_size(repo_path)
    print(f"  {Colors.BOLD}Git Database Size:{Colors.ENDC} {format_size(git_dir_size)}")

    try:
        count_obj = run_git_command(['count-objects', '-v'], cwd=repo_path)
        loose_count = 0
        loose_size = 0
        in_pack_count = 0
        
        for line in count_obj.splitlines():
            if line.startswith('count: '):
                loose_count = int(line.split(': ')[1])
            elif line.startswith('size: '):
                loose_size = int(line.split(': ')[1]) * 1024  # reported in KB
            elif line.startswith('in-pack: '):
                in_pack_count = int(line.split(': ')[1])
                
        print(f"  {Colors.BOLD}Loose Objects:{Colors.ENDC} {loose_count} ({format_size(loose_size)})")
        print(f"  {Colors.BOLD}Packed Objects:{Colors.ENDC} {in_pack_count}")
        
        if loose_count > 100:
            print_warning("  Large number of loose objects. Running 'git gc' is recommended to optimize the repository.")
        else:
            print_success("  Git database is well-packed.")
    except Exception as e:
        print_warning(f"  Could not get object counts: {e}")

    # 2. Check Standard Repository Files
    print_header("Standard Quality Checklist")
    checklist = {
        'README.md': ['readme.md', 'readme.txt', 'readme'],
        'LICENSE': ['license', 'license.md', 'license.txt', 'copying'],
        '.gitignore': ['.gitignore'],
        'CONTRIBUTING.md': ['contributing.md', 'contributing'],
        'CODE_OF_CONDUCT.md': ['code_of_conduct.md', 'code_of_conduct']
    }
    
    for file_desc, alternatives in checklist.items():
        found = False
        for alt in alternatives:
            if os.path.exists(os.path.join(repo_path, alt)):
                found = True
                break
        if found:
            print(f"  {Colors.GREEN}✔ {file_desc:20} Present{Colors.ENDC}")
        else:
            print(f"  {Colors.RED}✘ {file_desc:20} Missing{Colors.ENDC}")

    # 3. Analyze Working Tree
    print_header("Working Tree Status")
    try:
        status_out = run_git_command(['status', '--porcelain'], cwd=repo_path)
        if not status_out:
            print_success("  Working tree is clean. No uncommitted changes.")
        else:
            lines = status_out.splitlines()
            uncommitted = len([l for l in lines if not l.startswith('??')])
            untracked = len([l for l in lines if l.startswith('??')])
            print_warning(f"  Uncommitted modifications: {uncommitted}")
            print_warning(f"  Untracked files: {untracked}")
            print(f"  Run 'git status' for details.")
    except Exception as e:
        print_warning(f"  Could not read git status: {e}")

    # 4. Commit Metrics & Contributors
    print_header("Commit History & Contributor Stats")
    try:
        # Get total commit count
        total_commits = run_git_command(['rev-list', '--count', 'HEAD'], cwd=repo_path)
        print(f"  {Colors.BOLD}Total Commits (HEAD):{Colors.ENDC} {total_commits}")
        
        # Get authors
        authors_raw = run_git_command(['log', '--format=%an', '--all'], cwd=repo_path)
        authors = authors_raw.splitlines()
        author_counts = Counter(authors)
        
        print(f"  {Colors.BOLD}Unique Authors:{Colors.ENDC} {len(author_counts)}")
        print(f"  {Colors.BOLD}Top Contributors:{Colors.ENDC}")
        for author, count in author_counts.most_common(5):
            pct = (count / len(authors)) * 100
            print(f"    - {author:30} {count:5} commits ({pct:.1f}%)")
            
    except Exception as e:
        print_warning(f"  Could not read commit stats: {e}")

    # 5. Stale Branches
    print_header("Stale Branches")
    try:
        # Format: refname | committerdate:raw | authorname
        branches_raw = run_git_command(
            ['for-each-ref', '--format=%(refname:short) | %(committerdate:raw) | %(authorname)', 'refs/heads/'],
            cwd=repo_path
        )
        
        now = datetime.now()
        stale_count = 0
        active_count = 0
        
        for line in branches_raw.splitlines():
            if not line:
                continue
            parts = line.split(' | ')
            branch_name = parts[0]
            timestamp = int(parts[1].split(' ')[0])
            author = parts[2]
            
            commit_date = datetime.fromtimestamp(timestamp)
            days_ago = (now - commit_date).days
            
            if days_ago > args.stale_days:
                stale_count += 1
                if stale_count <= 5:  # Limit display
                    print(f"  {Colors.YELLOW}! Stale branch:{Colors.ENDC} {Colors.CYAN}{branch_name}{Colors.ENDC} ({days_ago} days ago by {author})")
            else:
                active_count += 1
                
        print(f"  Summary: {active_count} active branch(es), {stale_count} stale branch(es) (> {args.stale_days} days of inactivity)")
    except Exception as e:
        print_warning(f"  Could not inspect branches: {e}")

    # 6. Database Bloat - Largest Files in History
    print_header(f"Top {args.limit} Largest Files in Git History (Bloat Report)")
    large_blobs = analyze_git_bloat(repo_path, limit=args.limit)
    if large_blobs:
        print(f"  {'Size':12} | {'SHA1':8} | {'File Path':40}")
        print("  " + "-" * 70)
        for size, sha, path in large_blobs:
            path_display = path if path else "<deleted or unnamed blob>"
            print(f"  {format_size(size):12} | {sha[:8]} | {path_display}")
        print(f"\n  {Colors.BLUE}Tip:{Colors.ENDC} If you need to purge a large file completely from git history, use 'git-filter-repo' or 'bfg-repo-cleaner'.")
    else:
        print("  No large files or history database is empty.")

if __name__ == "__main__":
    main()
