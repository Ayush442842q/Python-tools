#!/usr/bin/env python3
"""
Markdown Changelog Generator - Auto-generate CHANGELOG.md from Git commits.

Parses Git history and generates a well-formatted CHANGELOG.md following
Keep a Changelog (https://keepachangelog.com/) conventions.

Usage:
    python changelog_generator.py                  # Generate from all commits
    python changelog_generator.py --tag v1.0.0     # Generate up to specific tag
    python changelog_generator.py --output CHANGES.md
    python changelog_generator.py --group-by-scope # Group by commit scope
"""

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime


def run_git_command(args):
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Git not found. Make sure git is installed and in PATH.")
        sys.exit(1)


def get_git_tags():
    """Get all git tags sorted by version."""
    output = run_git_command(['tag', '--sort=-v:refname'])
    if not output:
        return []
    return output.split('\n')


def get_commits_between_refs(start_ref, end_ref="HEAD"):
    """Get commits between two refs."""
    args = [
        'log',
        '--pretty=format:%H|%ad|%s|%b',
        '--date=iso',
        f'{start_ref}..{end_ref}'
    ]
    output = run_git_command(args)
    if not output:
        return []
    
    commits = []
    for line in output.split('\n'):
        if '|' in line:
            parts = line.split('|', 3)
            if len(parts) >= 3:
                commits.append({
                    'hash': parts[0][:7],
                    'date': parts[1],
                    'subject': parts[2],
                    'body': parts[3] if len(parts) > 3 else ''
                })
    return commits


def parse_commit_message(subject):
    """Parse conventional commit message."""
    # Pattern: type(scope): description
    pattern = r'^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<desc>.+)$'
    match = re.match(pattern, subject)
    
    if match:
        return {
            'type': match.group('type'),
            'scope': match.group('scope'),
            'breaking': match.group('breaking') is not None,
            'description': match.group('desc'),
            'conventional': True
        }
    
    # Non-conventional commit
    return {
        'type': 'other',
        'scope': None,
        'breaking': False,
        'description': subject,
        'conventional': False
    }


def categorize_commits(commits):
    """Categorize commits by type."""
    categories = {
        'feat': [],
        'fix': [],
        'docs': [],
        'style': [],
        'refactor': [],
        'perf': [],
        'test': [],
        'chore': [],
        'other': []
    }
    
    type_mapping = {
        'feature': 'feat',
        'bug': 'fix',
        'bugfix': 'fix',
        'documentation': 'docs',
        'refactoring': 'refactor',
        'performance': 'perf',
        'testing': 'test'
    }
    
    for commit in commits:
        parsed = parse_commit_message(commit['subject'])
        commit_type = parsed['type'].lower()
        
        # Map common variations
        commit_type = type_mapping.get(commit_type, commit_type)
        
        if commit_type in categories:
            categories[commit_type].append({
                **commit,
                **parsed
            })
        else:
            categories['other'].append({
                **commit,
                **parsed
            })
    
    return categories


def format_commit_entry(commit, include_hash=False):
    """Format a single commit entry for changelog."""
    entry = f"- {commit['description']}"
    
    if commit.get('scope'):
        entry = f"- **{commit['scope']}**: {commit['description']}"
    
    if commit.get('breaking'):
        entry += " ⚠️"
    
    if include_hash:
        entry += f" (`{commit['hash']}`)"
    
    return entry


def generate_changelog(commits, version="Unreleased", include_hash=False, group_by_scope=False):
    """Generate changelog markdown from commits."""
    categorized = categorize_commits(commits)
    
    sections = []
    section_order = [
        ('feat', '🚀 Features'),
        ('fix', '🐛 Bug Fixes'),
        ('docs', '📚 Documentation'),
        ('style', '💅 Styles'),
        ('refactor', '♻️ Refactoring'),
        ('perf', '⚡ Performance'),
        ('test', '✅ Tests'),
        ('chore', '🔧 Maintenance'),
        ('other', '📦 Other Changes')
    ]
    
    for commit_type, section_title in section_order:
        commit_list = categorized.get(commit_type, [])
        if not commit_list:
            continue
        
        if group_by_scope:
            # Group by scope
            by_scope = defaultdict(list)
            for commit in commit_list:
                scope = commit.get('scope') or 'General'
                by_scope[scope].append(commit)
            
            sections.append(f"\n### {section_title}\n")
            for scope, scoped_commits in sorted(by_scope.items()):
                sections.append(f"\n#### {scope}\n")
                for commit in scoped_commits:
                    sections.append(format_commit_entry(commit, include_hash))
        else:
            sections.append(f"\n### {section_title}\n")
            for commit in commit_list:
                sections.append(format_commit_entry(commit, include_hash))
    
    if not sections:
        return f"\n### {version}\n\n- No changes\n"
    
    return f"\n## [{version}] - {datetime.now().strftime('%Y-%m-%d')}\n" + '\n'.join(sections)


def get_version_from_tag(tag):
    """Extract version number from tag."""
    match = re.search(r'v?(\d+\.\d+\.\d+)', tag)
    return match.group(1) if match else tag


def main():
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG.md from Git commit history"
    )
    parser.add_argument('--tag', '-t', help='Generate changelog up to specific tag')
    parser.add_argument('--output', '-o', help='Output file (default: CHANGELOG.md)')
    parser.add_argument('--append', action='store_true',
                        help='Append to existing changelog instead of overwriting')
    parser.add_argument('--include-hash', action='store_true',
                        help='Include commit hashes in changelog')
    parser.add_argument('--group-by-scope', action='store_true',
                        help='Group commits by their conventional commit scope')
    parser.add_argument('--max-commits', type=int, default=500,
                        help='Maximum number of commits to process')
    parser.add_argument('--since', help='Generate changelog since specific date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        print("Error: Not in a git repository")
        sys.exit(1)
    
    # Get commits
    if args.tag:
        print(f"Generating changelog up to tag: {args.tag}")
        try:
            commits = get_commits_between_refs(args.tag)
            version = get_version_from_tag(args.tag)
        except SystemExit:
            # Tag might not exist, use HEAD
            commits = get_commits_between_refs(None, "HEAD")
            version = "Unreleased"
    else:
        commits = get_commits_between_refs(None, "HEAD")
        version = "Unreleased"
    
    # Filter by date if specified
    if args.since:
        since_date = datetime.strptime(args.since, '%Y-%m-%d')
        commits = [
            c for c in commits
            if datetime.strptime(c['date'].split()[0], '%Y-%m-%d') >= since_date
        ]
        version = f"{version} (since {args.since})"
    
    # Limit commits
    commits = commits[:args.max_commits]
    
    print(f"Processing {len(commits)} commits...")
    
    # Generate changelog
    changelog = generate_changelog(commits, version, args.include_hash, args.group_by_scope)
    
    # Output
    output_file = args.output or "CHANGELOG.md"
    
    if args.append and os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing = f.read()
        changelog = existing + changelog
    
    with open(output_file, 'w') as f:
        f.write(changelog)
    
    print(f"Changelog written to: {output_file}")
    
    # Print preview
    print("\n" + "=" * 60)
    print(changelog[:1000] + "..." if len(changelog) > 1000 else changelog)


if __name__ == '__main__':
    main()