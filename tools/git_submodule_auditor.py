#!/usr/bin/env python3
"""
Git Submodule Manager & Auditor

Recursively scans a Git repository for submodules, parses the `.gitmodules` config
natively, audits checkout commit statuses against the parent index, checks for
detached HEADs, and queries the remote status to detect out-of-sync submodules.

Usage:
    python git_submodule_auditor.py [path_to_repo_root]
"""

import sys
import os
import argparse
import configparser
import subprocess
import re

def run_git_cmd(args, cwd):
    """Utility to run a git command and return output, returning None on failure."""
    try:
        res = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return None

def parse_gitmodules(repo_root):
    """Parses .gitmodules file at the repository root using configparser."""
    gitmodules_path = os.path.join(repo_root, '.gitmodules')
    if not os.path.exists(gitmodules_path):
        return {}
        
    config = configparser.ConfigParser()
    try:
        config.read(gitmodules_path)
    except Exception as e:
        print(f"Warning: Failed to parse .gitmodules config: {e}", file=sys.stderr)
        return {}
        
    submodules = {}
    for section in config.sections():
        # Sections look like: submodule "path/to/submodule"
        match = re.match(r'^submodule\s+"(.+)"$', section)
        if not match:
            # Alternate format: [submodule] (no path name in section)
            continue
        sub_name = match.group(1)
        sub_path = config.get(section, 'path', fallback=sub_name)
        sub_url = config.get(section, 'url', fallback='')
        sub_branch = config.get(section, 'branch', fallback='HEAD')
        
        submodules[sub_path] = {
            'name': sub_name,
            'url': sub_url,
            'branch': sub_branch
        }
    return submodules

def get_submodule_commits(repo_root):
    """Gets the registered commit in the parent git index vs the actual checkout commit."""
    # Runs git submodule status to get current commits
    # Format of status: [+- ]<commit_hash> <path> (<branch_desc>)
    status_out = run_git_cmd(['submodule', 'status'], repo_root)
    commits_map = {}
    if status_out:
        for line in status_out.splitlines():
            line = line.strip()
            if not line:
                continue
            # Match state prefix, commit hash, path, and optional branch desc
            match = re.match(r'^([+\- ]?)([a-fA-F0-9]{40})\s+([^\s]+)(?:\s+\((.+)\))?$', line)
            if match:
                prefix = match.group(1)
                commit = match.group(2)
                sub_path = match.group(3)
                desc = match.group(4) or ''
                
                state = 'synced'
                if prefix == '+':
                    state = 'modified'  # checkout commit differs from index
                elif prefix == '-':
                    state = 'uninitialized'
                elif prefix == 'U':
                    state = 'conflict'
                    
                commits_map[sub_path] = {
                    'state': state,
                    'index_commit': commit,
                    'desc': desc
                }
    return commits_map

def audit_submodule(repo_root, sub_path, config_info, status_info):
    """Performs deep checks inside the submodule directory."""
    full_path = os.path.join(repo_root, sub_path)
    report = {
        'path': sub_path,
        'name': config_info.get('name', ''),
        'url': config_info.get('url', ''),
        'configured_branch': config_info.get('branch', 'HEAD'),
        'status': 'unknown',
        'checkout_commit': 'N/A',
        'index_commit': status_info.get('index_commit', 'N/A'),
        'current_branch': 'N/A',
        'is_detached': False,
        'untracked_files': False,
        'modified_files': False,
        'upstream_drift': 'unknown',
        'warnings': []
    }
    
    # 1. Check if directory exists
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        report['status'] = 'Missing folder'
        report['warnings'].append("Submodule directory does not exist on disk.")
        return report
        
    # 2. Check if initialized
    if status_info.get('state') == 'uninitialized':
        report['status'] = 'Uninitialized'
        report['warnings'].append("Submodule is configured but not initialized (run 'git submodule update --init').")
        return report

    # Check if .git exists inside the folder
    git_indicator = os.path.join(full_path, '.git')
    if not os.path.exists(git_indicator):
        report['status'] = 'Not a git repo'
        report['warnings'].append("Submodule folder is empty or not a valid Git repository checkout.")
        return report

    # 3. Retrieve current checked out commit and HEAD branch status
    # Run git commands inside the submodule directory
    checkout_hash = run_git_cmd(['rev-parse', 'HEAD'], full_path)
    if checkout_hash:
        report['checkout_commit'] = checkout_hash
    else:
        report['status'] = 'Corrupted git state'
        report['warnings'].append("Failed to read HEAD commit in submodule repository.")
        return report

    # Check branch name
    branch_name = run_git_cmd(['rev-parse', '--abbrev-ref', 'HEAD'], full_path)
    if branch_name:
        report['current_branch'] = branch_name
        if branch_name == 'HEAD':
            report['is_detached'] = True
            report['warnings'].append("Submodule is in a DETACHED HEAD state (not checked out to a branch).")

    # 4. Check index synchronization
    if report['checkout_commit'] != report['index_commit']:
        report['status'] = 'Out of sync with parent index'
        report['warnings'].append(f"Checked out commit ({report['checkout_commit'][:8]}) differs from index commit ({report['index_commit'][:8]}).")
    else:
        report['status'] = 'Synchronized with index'

    # 5. Check local worktree modifications
    sub_status = run_git_cmd(['status', '--porcelain'], full_path)
    if sub_status:
        for line in sub_status.splitlines():
            if line.startswith('??'):
                report['untracked_files'] = True
            else:
                report['modified_files'] = True
                
        if report['modified_files']:
            report['warnings'].append("Submodule contains uncommitted changes in tracked files.")
        if report['untracked_files']:
            report['warnings'].append("Submodule contains untracked files.")

    # 6. Check upstream branch synchronization status
    # If the submodule has remote configured
    remote_branch = config_info.get('branch', 'HEAD')
    if remote_branch != 'HEAD':
        # Fetch remote origin updates safely (no modifying action)
        # Check if remote branch matches local checkout
        remote_commit = run_git_cmd(['rev-parse', f'origin/{remote_branch}'], full_path)
        if remote_commit:
            if remote_commit == report['checkout_commit']:
                report['upstream_drift'] = 'Up-to-date with remote'
            else:
                # Checkout git diff statistics
                behind_ahead = run_git_cmd(['rev-list', '--left-right', '--count', f'HEAD...origin/{remote_branch}'], full_path)
                if behind_ahead:
                    ahead, behind = map(int, behind_ahead.split())
                    if behind > 0:
                        report['upstream_drift'] = f"Stale (behind origin by {behind} commits)"
                        report['warnings'].append(f"Submodule is out-of-date. Behind upstream '{remote_branch}' by {behind} commits.")
                    elif ahead > 0:
                        report['upstream_drift'] = f"Ahead of remote by {ahead} commits"
                    else:
                        report['upstream_drift'] = 'Differing histories'
        else:
            report['upstream_drift'] = 'Could not query origin'
            
    return report

def main():
    parser = argparse.ArgumentParser(
        description="Audit Git Submodules configuration, status, and synchronization.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository root directory (default: '.')"
    )
    
    args = parser.parse_args()
    
    repo_root = os.path.abspath(args.repo_path)
    
    # Check if directory is a git repo
    if not os.path.exists(os.path.join(repo_root, '.git')):
        print(f"Error: Directory '{repo_root}' is not a valid Git repository root.", file=sys.stderr)
        return 1

    print("Git Submodule Auditor")
    print(f"Scanning Repository: {repo_root}")
    print("=" * 70)
    
    # 1. Parse .gitmodules config
    submodule_configs = parse_gitmodules(repo_root)
    if not submodule_configs:
        print("No submodules defined in `.gitmodules` file. Repository is clean.")
        return 0

    # 2. Get submodule commits from git index status
    submodule_status = get_submodule_commits(repo_root)
    
    # 3. Perform audits
    reports = []
    issues_count = 0
    
    for sub_path, config_info in sorted(submodule_configs.items()):
        status_info = submodule_status.get(sub_path, {})
        rep = audit_submodule(repo_root, sub_path, config_info, status_info)
        reports.append(rep)
        issues_count += len(rep['warnings'])

    # 4. Display Results
    for rep in reports:
        print(f"\nSubmodule: \033[1m{rep['name']}\033[0m")
        print(f"  Path          : {rep['path']}")
        print(f"  Source URL    : {rep['url']}")
        print(f"  Tracking      : Branch '{rep['configured_branch']}' -> Checked out: '{rep['current_branch']}'")
        
        status_color = "\033[92m"  # Green
        if 'Missing' in rep['status'] or 'Uninitialized' in rep['status'] or 'Out of sync' in rep['status']:
            status_color = "\033[91m"  # Red
        elif 'modified' in rep['status'] or 'uncommitted' in rep['status']:
            status_color = "\033[93m"  # Yellow
            
        print(f"  Sync Status   : {status_color}{rep['status']}\033[0m")
        print(f"  Index Commit  : {rep['index_commit'][:8]}")
        print(f"  Active Commit : {rep['checkout_commit'][:8]}")
        
        if rep['configured_branch'] != 'HEAD':
            print(f"  Upstream Drift: {rep['upstream_drift']}")
            
        if rep['warnings']:
            print("  \033[91mIssues Identified:\033[0m")
            for w in rep['warnings']:
                print(f"    - [!] {w}")
        else:
            print("  \033[92m[✓] Submodule configuration is healthy.\033[0m")
            
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print(f"  Total submodules audited: {len(reports)}")
    print(f"  Total config/sync issues: {issues_count}")
    print("=" * 70)
    
    return 1 if issues_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
