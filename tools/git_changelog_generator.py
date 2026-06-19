#!/usr/bin/env python3
"""
Git Changelog & Release Notes Generator

This tool parses the git commit history of a local repository and generates
a structured, conventional-commit-compliant Markdown changelog.

Usage:
    python tools/git_changelog_generator.py [options]

Example:
    python tools/git_changelog_generator.py --repo . --range v1.0.0..HEAD --output CHANGELOG_NEW.md
"""

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Conventional commit type mappings to user-friendly headings
TYPE_HEADINGS = {
    'feat': '🚀 Features',
    'fix': '🐛 Bug Fixes',
    'perf': '⚡ Performance Improvements',
    'refactor': '♻️ Code Refactoring',
    'docs': '📝 Documentation',
    'style': '🎨 Code Style & Formatting',
    'test': '✅ Tests',
    'chore': '🔧 Maintenance & Chores',
    'build': '🏗️ Build System',
    'ci': '💚 Continuous Integration',
    'revert': '⏪ Reverts'
}

# Regex to parse conventional commit messages
# e.g., "feat(parser): add support for comments" -> type='feat', scope='parser', description='add support for comments'
CONVENTIONAL_COMMIT_RE = re.compile(
    r'^(?P<type>[a-zA-Z0-9_-]+)(?:\((?P<scope>[a-zA-Z0-9_ -]+)\))?(?P<breaking>!)?:\s+(?P<description>.+)$'
)

def run_git_command(args: List[str], repo_path: str) -> Tuple[int, str, str]:
    """Runs a git command in the specified directory and returns (exit_code, stdout, stderr)."""
    try:
        process = subprocess.Popen(
            ['git'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_path,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr
    except FileNotFoundError:
        return -1, "", "git executable not found in system PATH."
    except Exception as e:
        return -1, "", str(e)

def get_commits(repo_path: str, commit_range: Optional[str]) -> List[Tuple[str, str, str]]:
    """Fetches commit hash, author date, and full message for the specified range."""
    git_args = ['log', '--format=%H|%ad|%B%n---COMMIT_END---', '--date=short']
    if commit_range:
        git_args.append(commit_range)
    
    code, stdout, stderr = run_git_command(git_args, repo_path)
    if code != 0:
        print(f"Error running git log: {stderr}", file=sys.stderr)
        sys.exit(1)
        
    commits = []
    # Commits are separated by ---COMMIT_END--- followed by newline
    raw_commits = stdout.split('\n---COMMIT_END---\n')
    for raw in raw_commits:
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split('|', 2)
        if len(parts) >= 3:
            commit_hash = parts[0].strip()
            date = parts[1].strip()
            message = parts[2].strip()
            commits.append((commit_hash, date, message))
            
    return commits

def parse_commits(commits: List[Tuple[str, str, str]]) -> Tuple[Dict[str, List[str]], List[str], List[str]]:
    """Parses commits and groups them by conventional commit types, breaking changes, and uncategorized."""
    grouped = defaultdict(list)
    breaking_changes = []
    uncategorized = []
    
    for commit_hash, date, message in commits:
        lines = message.split('\n')
        header = lines[0].strip()
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
        
        # Check for breaking change signifiers in body or footers
        is_breaking = "BREAKING CHANGE:" in body or "BREAKING CHANGES:" in body
        
        match = CONVENTIONAL_COMMIT_RE.match(header)
        if match:
            c_type = match.group('type').lower()
            scope = match.group('scope')
            c_breaking = match.group('breaking')
            desc = match.group('description').strip()
            
            # Format the commit entry
            scope_prefix = f"**{scope}**: " if scope else ""
            hash_suffix = f" ({commit_hash[:7]})"
            entry = f"{scope_prefix}{desc}{hash_suffix}"
            
            if c_breaking or is_breaking:
                breaking_changes.append(f"**{scope_prefix}{desc}** ({commit_hash[:7]})")
                
            # If type is not in our known list, fall back to c_type
            group_key = c_type if c_type in TYPE_HEADINGS else 'chore'
            grouped[group_key].append(entry)
        else:
            # Check if this non-conventional commit has breaking change markers anyway
            if is_breaking:
                breaking_changes.append(f"**{header}** ({commit_hash[:7]})")
            
            hash_suffix = f" ({commit_hash[:7]})"
            uncategorized.append(f"{header}{hash_suffix}")
            
    return grouped, breaking_changes, uncategorized

def generate_markdown(
    grouped: Dict[str, List[str]], 
    breaking: List[str], 
    uncategorized: List[str],
    version_title: str,
    repo_path: str
) -> str:
    """Generates the final Markdown content."""
    md = []
    md.append(f"# {version_title}")
    md.append("")
    
    # Get current date
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")
    md.append(f"*Released on {today}*")
    md.append("")
    
    if breaking:
        md.append("### 🚨 BREAKING CHANGES")
        for change in breaking:
            md.append(f"- {change}")
        md.append("")
        
    # Order sections by priority of importance
    ordered_types = ['feat', 'fix', 'perf', 'refactor', 'revert', 'docs', 'style', 'test', 'build', 'ci', 'chore']
    
    has_sections = False
    for t in ordered_types:
        if t in grouped and grouped[t]:
            has_sections = True
            md.append(f"### {TYPE_HEADINGS.get(t, t.capitalize())}")
            for entry in grouped[t]:
                md.append(f"- {entry}")
            md.append("")
            
    # Include other types not in our list
    for t, entries in grouped.items():
        if t not in ordered_types and entries:
            has_sections = True
            md.append(f"### {t.capitalize()}")
            for entry in entries:
                md.append(f"- {entry}")
            md.append("")
            
    if uncategorized:
        md.append("### 📦 Other Changes")
        for entry in uncategorized:
            md.append(f"- {entry}")
        md.append("")
        
    if not has_sections and not breaking and not uncategorized:
        md.append("*No commits found matching the criteria.*")
        md.append("")
        
    return '\n'.join(md)

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a structured Markdown changelog from Git history.")
    parser.add_argument('--repo', default='.', help="Path to local Git repository (default: '.')")
    parser.add_argument('--range', help="Commit range (e.g. 'v1.0.0..HEAD' or 'v1.1.0..v1.2.0')")
    parser.add_argument('--title', default="Release Notes", help="Title for the release section (default: 'Release Notes')")
    parser.add_argument('--output', help="Path to write the markdown output (prints to stdout if omitted)")
    parser.add_argument('--verbose', action='store_true', help="Print verbose status info to stderr")
    
    args = parser.parse_args()
    
    repo_path = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo_path, '.git')):
        print(f"Error: Directory '{repo_path}' is not a Git repository.", file=sys.stderr)
        return 1
        
    if args.verbose:
        print(f"Scanning Git history in {repo_path}...", file=sys.stderr)
        if args.range:
            print(f"Range: {args.range}", file=sys.stderr)
            
    commits = get_commits(repo_path, args.range)
    if args.verbose:
        print(f"Found {len(commits)} commits.", file=sys.stderr)
        
    grouped, breaking, uncategorized = parse_commits(commits)
    markdown_content = generate_markdown(grouped, breaking, uncategorized, args.title, repo_path)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"Changelog written successfully to {args.output}")
        except Exception as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            return 1
    else:
        print(markdown_content)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
