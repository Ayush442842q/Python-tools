#!/usr/bin/env python3
"""
Git Semantic Version Releaser - Analyze commit history using Conventional Commits to suggest the next version.
"""

import sys
import os
import re
import argparse
import subprocess

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def run_git(args, cwd=None):
    """Run a git command and return its output."""
    try:
        res = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git execution failed: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Git executable not found. Make sure git is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)

def parse_version(version_str):
    """Parse version string like v1.2.3 into a list of integers [1, 2, 3]."""
    # Remove leading 'v' if present
    match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        return [int(x) for x in match.groups()]
    return None

def format_version(version_list):
    """Format [1, 2, 3] list into v1.2.3 version string."""
    return f"v{version_list[0]}.{version_list[1]}.{version_list[2]}"

def main():
    parser = argparse.ArgumentParser(
        description="Analyze git history via Conventional Commits, suggest next Semantic Version, and draft changelog."
    )
    parser.add_argument('--path', default='.', help="Path to the git repository.")
    parser.add_argument('--since', help="Compare starting from this tag or commit hash instead of finding the latest tag automatically.")
    parser.add_argument('--tag', action='store_true', help="Create a git tag with the suggested version if changes are found.")
    parser.add_argument('--prefix', default='v', help="Prefix for the generated git tags (e.g. 'v').")
    
    args = parser.parse_args()
    
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    # Verify it is a git repo
    if not os.path.exists(os.path.join(args.path, '.git')):
        # Check if we are inside a git repo hierarchy
        is_git = run_git(['rev-parse', '--is-inside-work-tree'], cwd=args.path)
        if not is_git:
            print(f"{c_red}Error: Path '{args.path}' is not a git repository.{c_reset}", file=sys.stderr)
            sys.exit(1)
            
    # Find latest tag
    latest_tag = None
    if args.since:
        latest_tag = args.since
    else:
        # Get latest tag sorted by version-sort or creation date
        tags = run_git(['tag', '--sort=-v:refname'], cwd=args.path)
        if tags:
            latest_tag = tags.split('\n')[0]
        else:
            # Fallback: get any tag if none match version-sort
            tags_by_date = run_git(['tag', '--sort=-creatordate'], cwd=args.path)
            if tags_by_date:
                latest_tag = tags_by_date.split('\n')[0]

    # Get commits since the latest tag or initial commit
    git_log_args = ['log', '--oneline', '--no-merges']
    if latest_tag:
        git_log_args.append(f"{latest_tag}..HEAD")
        print(f"Analyzing commits since tag: {c_bold}{latest_tag}{c_reset}")
    else:
        print("No previous tags found. Analyzing all commits in the repository.")
        
    log_output = run_git(git_log_args, cwd=args.path)
    if not log_output:
        print(f"{c_green}No new commits found since the reference point. Version remains unchanged.{c_reset}")
        return
        
    commits = log_output.split('\n')
    print(f"Found {len(commits)} commits to analyze.\n")
    
    # Conventional commit regex patterns
    # e.g., feat(api): add new endpoints
    # e.g., fix!: solve security bug
    pattern = re.compile(r'^([a-f0-9]+)\s+([a-zA-Z0-9_-]+)(?:\(([^)]+)\))?(!)?:\s+(.*)$')
    
    features = []
    fixes = []
    breaking_changes = []
    others = []
    
    bump_type = 'none' # none -> patch -> minor -> major
    
    for commit_line in commits:
        match = pattern.match(commit_line)
        if not match:
            # Try to search for breaking change in body if we were parsing full logs,
            # but for oneline, check if commit subject contains BREAKING CHANGE
            others.append(commit_line)
            if 'BREAKING CHANGE' in commit_line or 'breaking change' in commit_line:
                bump_type = 'major'
                breaking_changes.append(commit_line)
            continue
            
        sha, commit_type, scope, is_breaking, description = match.groups()
        commit_type = commit_type.lower()
        
        # Determine bump requirements
        if is_breaking or 'BREAKING CHANGE' in commit_line:
            bump_type = 'major'
            breaking_changes.append((sha, commit_type, scope, description))
        elif commit_type == 'feat':
            if bump_type != 'major':
                bump_type = 'minor'
            features.append((sha, scope, description))
        elif commit_type == 'fix':
            if bump_type not in ['major', 'minor']:
                bump_type = 'patch'
            fixes.append((sha, scope, description))
        else:
            if bump_type == 'none':
                bump_type = 'patch'  # Chore/refactor/docs still warrant a patch bump if released
            others.append((sha, commit_type, scope, description))

    # Calculate current version
    current_version = [0, 0, 0]
    if latest_tag:
        parsed = parse_version(latest_tag)
        if parsed:
            current_version = parsed
            
    # Calculate next version
    next_version = list(current_version)
    if bump_type == 'major':
        next_version[0] += 1
        next_version[1] = 0
        next_version[2] = 0
    elif bump_type == 'minor':
        next_version[1] += 1
        next_version[2] = 0
    elif bump_type == 'patch':
        next_version[2] += 1
        
    current_str = format_version(current_version)
    next_str = format_version(next_version)
    
    print("=" * 60)
    print(f"Current Version:  {c_blue}{current_str}{c_reset}")
    print(f"Recommended Bump: {c_yellow}{bump_type.upper()}{c_reset}")
    print(f"Suggested Next:   {c_green}{next_str}{c_reset}")
    print("=" * 60 + "\n")
    
    # Print Changelog Draft
    print(f"{c_bold}--- DRAFT CHANGELOG ({next_str}) ---{c_reset}")
    
    if breaking_changes:
        print(f"\n{c_red}### ⚠ BREAKING CHANGES{c_reset}")
        for item in breaking_changes:
            if isinstance(item, tuple):
                sha, c_type, scope, desc = item
                scope_str = f"**{scope}**: " if scope else ""
                print(f"- {scope_str}{desc} ({sha})")
            else:
                print(f"- {item}")
                
    if features:
        print(f"\n{c_green}### Features{c_reset}")
        for sha, scope, desc in features:
            scope_str = f"**{scope}**: " if scope else ""
            print(f"- {scope_str}{desc} ({sha})")
            
    if fixes:
        print(f"\n{c_yellow}### Bug Fixes{c_reset}")
        for sha, scope, desc in fixes:
            scope_str = f"**{scope}**: " if scope else ""
            print(f"- {scope_str}{desc} ({sha})")
            
    if others:
        print(f"\n{c_blue}### Documentation & Maintenance{c_reset}")
        for item in others:
            if isinstance(item, tuple):
                sha, c_type, scope, desc = item
                scope_str = f"**{scope}**: " if scope else ""
                print(f"- {c_type}: {scope_str}{desc} ({sha})")
            else:
                print(f"- {item}")
                
    print("\n" + "-" * 60)
    
    # Handle Tagging
    if args.tag:
        if bump_type == 'none':
            print("No version bump needed. Skipping tag creation.")
            return
            
        print(f"Creating git tag: {next_str}...")
        tag_result = run_git(['tag', '-a', next_str, '-m', f"Release {next_str} (suggested by semver releaser)"], cwd=args.path)
        if tag_result is not None:
            print(f"{c_green}Successfully created tag {next_str}!{c_reset}")
            print(f"Run {c_bold}git push origin {next_str}{c_reset} to publish the tag.")

if __name__ == '__main__':
    main()
