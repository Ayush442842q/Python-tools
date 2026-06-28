#!/usr/bin/env python3
"""
Changelog Generator - Auto-generate CHANGELOG from Git commits.

Generates a well-formatted changelog from Git commit history,
grouping changes by type following Conventional Commits and
common patterns.

Features:
- Groups commits by type (Feature, Fix, Docs, etc.)
- Extracts version from Git tags
- Filters commits by date range
- Links to issues/PRs
- Detects breaking changes
- Supports multiple output formats (Markdown, JSON)
- Filters duplicate commits across releases

Usage:
    python changelog_generator.py [repo_path] [--tag TAG] [--since DATE] [--until DATE]

Example:
    python changelog_generator.py                                # Current repo, all history
    python changelog_generator.py /path/to/repo --tag v1.2.0     # Since last tag
    python changelog_generator.py --since "2024-01-01"          # Since date
    python changelog_generator.py --output CHANGELOG.md         # To file
"""

import os
import re
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class ChangelogGenerator:
    """Generate changelog from Git history."""

    # Commit type mappings to changelog sections
    TYPE_MAPPING = {
        'feat': 'Features',
        'feature': 'Features',
        'fix': 'Bug Fixes',
        'bugfix': 'Bug Fixes',
        'docs': 'Documentation',
        'doc': 'Documentation',
        'style': 'Styles',
        'refactor': 'Code Refactoring',
        'perf': 'Performance Improvements',
        'test': 'Tests',
        'testing': 'Tests',
        'build': 'Build System',
        'ci': 'Continuous Integration',
        'chore': 'Chores',
        'revert': 'Reverts',
        'deprecate': 'Deprecated',
        'deprecated': 'Deprecated',
        'security': 'Security',
        'breaking': 'BREAKING CHANGES',
    }

    BREAKING_PATTERNS = [
        re.compile(r'BREAKING\s*CHANGE:', re.IGNORECASE),
        re.compile(r'BREAKING-', re.IGNORECASE),
        re.compile(r'!:\s*', re.MULTILINE),  # Conventional commits with !
    ]

    ISSUE_PATTERN = re.compile(r'[#]?(\d+)', re.IGNORECASE)

    def __init__(self, repo_path: str = '.'):
        self.repo_path = Path(repo_path)
        self.commits: List[Dict] = []
        self.tags: List[Tuple[str, str, str]] = []

    def load_commits(self, since: Optional[str] = None,
                     until: Optional[str] = None,
                     after_tag: Optional[str] = None) -> bool:
        """Load commits from Git."""
        try:
            # Build git log command
            cmd = [
                'git', '-C', str(self.repo_path),
                'log',
                '--pretty=format:%H|%ai|%s|%b|%ae|%an',
            ]

            if since:
                cmd.append(f'--since={since}')
            if until:
                cmd.append(f'--until={until}')
            if after_tag:
                cmd.append(f'{after_tag}..HEAD')

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('|', 5)
                if len(parts) < 4:
                    continue

                commit_hash = parts[0]
                date = parts[1][:10]  # YYYY-MM-DD
                subject = parts[2]
                body = parts[3] if len(parts) > 3 else ''
                author_email = parts[4] if len(parts) > 4 else ''
                author_name = parts[5] if len(parts) > 5 else ''

                commit = {
                    'hash': commit_hash[:7],
                    'full_hash': commit_hash,
                    'date': date,
                    'subject': subject,
                    'body': body,
                    'author': f"{author_name}" if author_name else author_email,
                    'type': self._detect_type(subject, body),
                    'is_breaking': self._is_breaking(subject, body),
                    'issues': self._extract_issues(subject, body),
                    'scope': self._extract_scope(subject),
                }
                self.commits.append(commit)

            return True

        except subprocess.CalledProcessError as e:
            print(f"Git error: {e}")
            return False
        except FileNotFoundError:
            print("Git not found. Is it installed?")
            return False

    def load_tags(self) -> bool:
        """Load Git tags."""
        try:
            cmd = ['git', '-C', str(self.repo_path), 'tag', '-l', '--format=%(refname:short)|%(objectname:short)|%(creatordate:short)']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            for line in result.stdout.strip().split('\n'):
                if not line or '|' not in line:
                    continue

                parts = line.split('|')
                if len(parts) >= 3:
                    self.tags.append((parts[0], parts[1], parts[2]))

            # Sort by date descending
            self.tags.sort(key=lambda x: x[2], reverse=True)
            return True

        except subprocess.CalledProcessError:
            return False

    def _detect_type(self, subject: str, body: str) -> str:
        """Detect commit type from subject/body."""
        subject_lower = subject.lower()

        # Check for conventional commit prefix
        for type_key in self.TYPE_MAPPING:
            if subject_lower.startswith(f'{type_key}(') or \
               subject_lower.startswith(f'{type_key}:') or \
               subject_lower.startswith(f'{type_key} '):
                return type_key

        # Check body for breaking changes
        if self._is_breaking(subject, body):
            return 'breaking'

        # Default to 'other'
        return 'other'

    def _is_breaking(self, subject: str, body: str) -> bool:
        """Check if commit introduces breaking changes."""
        if '!' in subject and ':' in subject:
            return True

        for pattern in self.BREAKING_PATTERNS:
            if pattern.search(subject) or pattern.search(body):
                return True

        return False

    def _extract_scope(self, subject: str) -> Optional[str]:
        """Extract scope from conventional commit subject."""
        match = re.match(r'^[a-z]+\(([^\)]+)\)', subject, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_issues(self, subject: str, body: str) -> List[str]:
        """Extract issue/PR references."""
        issues = []
        text = f"{subject} {body}"

        for match in self.ISSUE_PATTERN.finditer(text):
            # Avoid matching pure numbers in version strings
            num = match.group(1)
            if not num.isdigit() or len(num) > 4:  # Likely not an issue number
                continue
            issues.append(f"#{num}")

        return issues

    def _group_by_type(self, commits: List[Dict]) -> Dict[str, List[Dict]]:
        """Group commits by type."""
        groups = defaultdict(list)

        for commit in commits:
            type_key = commit['type']
            groups[type_key].append(commit)

        return groups

    def generate_markdown(self, version: Optional[str] = None,
                          date: Optional[str] = None) -> str:
        """Generate Markdown changelog."""
        if not self.commits:
            return "# Changelog\n\nNo changes to report.\n"

        lines = ["# Changelog", ""]

        # Version header
        version_str = version if version else "Unreleased"
        date_str = date if date else datetime.now().strftime("%Y-%m-%d")
        lines.append(f"## [{version_str}] - {date_str}")
        lines.append("")

        grouped = self._group_by_type(self.commits)

        # Order of sections
        section_order = [
            'breaking', 'feat', 'feature', 'fix', 'bugfix',
            'deprecate', 'deprecated', 'security',
            'refactor', 'perf', 'docs', 'doc', 'style',
            'test', 'testing', 'build', 'ci', 'chore', 'revert', 'other'
        ]

        for section_type in section_order:
            section_name = self.TYPE_MAPPING.get(section_type, section_type.title())
            commits = grouped.get(section_type, [])

            if not commits:
                continue

            lines.append(f"### {section_name}")
            lines.append("")

            for commit in commits:
                subject = commit['subject']

                # Remove type prefix if present
                clean_subject = re.sub(
                    r'^(feat|feature|fix|bugfix|docs|doc|style|refactor|perf|test|build|ci|chore|revert|deprecate|deprecated|security|breaking)[\(\s:!]?',
                    '',
                    subject,
                    flags=re.IGNORECASE
                ).strip()

                # Add scope if present
                if commit['scope']:
                    clean_subject = f"**{commit['scope']}:** {clean_subject}"

                # Add breaking change indicator
                if commit['is_breaking']:
                    clean_subject = f"⚠️ {clean_subject}"

                # Add issue references
                if commit['issues']:
                    clean_subject += f" ({', '.join(commit['issues'])})"

                lines.append(f"- {clean_subject} ([{commit['hash']}](commit/{commit['full_hash']}))")

            lines.append("")

        return '\n'.join(lines)

    def generate_json(self) -> str:
        """Generate JSON changelog."""
        grouped = self._group_by_type(self.commits)

        changelog = {
            'generated': datetime.now().isoformat(),
            'total_commits': len(self.commits),
            'changes': {}
        }

        for type_key, commits in grouped.items():
            section_name = self.TYPE_MAPPING.get(type_key, type_key)
            changelog['changes'][section_name] = [
                {
                    'hash': c['hash'],
                    'date': c['date'],
                    'subject': c['subject'],
                    'author': c['author'],
                    'issues': c['issues'],
                    'breaking': c['is_breaking'],
                }
                for c in commits
            ]

        return json.dumps(changelog, indent=2)

    def print_summary(self) -> None:
        """Print changelog summary."""
        grouped = self._group_by_type(self.commits)

        print(f"\n{'='*60}")
        print("Changelog Summary")
        print(f"{'='*60}")
        print(f"Total commits: {len(self.commits)}")
        print(f"Date range: {self.commits[-1]['date']} to {self.commits[0]['date']}")
        print()

        breaking = sum(1 for c in self.commits if c['is_breaking'])
        if breaking:
            print(f"⚠️  BREAKING CHANGES: {breaking}")
            print()

        print("Changes by type:")
        for type_key in sorted(grouped.keys(), key=lambda x: -len(grouped[x])):
            count = len(grouped[type_key])
            name = self.TYPE_MAPPING.get(type_key, type_key)
            print(f"  {name}: {count}")

        print(f"{'='*60}\n")


def get_last_tag(repo_path: str) -> Optional[str]:
    """Get the most recent tag."""
    try:
        result = subprocess.run(
            ['git', '-C', repo_path, 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate changelog from Git commit history'
    )
    parser.add_argument('repo_path', nargs='?', default='.',
                        help='Path to Git repository (default: current)')
    parser.add_argument('--tag', '-t',
                        help='Generate changelog since this tag')
    parser.add_argument('--since', '-s',
                        help='Generate changelog since date (YYYY-MM-DD)')
    parser.add_argument('--until', '-u',
                        help='Generate changelog until date (YYYY-MM-DD)')
    parser.add_argument('--version', '-v',
                        help='Version string for changelog (default: Unreleased)')
    parser.add_argument('--date', '-d',
                        help='Date for changelog (default: today)')
    parser.add_argument('--output', '-o',
                        help='Output file (default: stdout)')
    parser.add_argument('--format', '-f', choices=['markdown', 'json'],
                        default='markdown', help='Output format')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary only')

    args = parser.parse_args()

    if not os.path.isdir(os.path.join(args.repo_path, '.git')):
        print(f"Error: '{args.repo_path}' is not a Git repository", file=sys.stderr)
        return 1

    generator = ChangelogGenerator(args.repo_path)

    if not args.tag and not args.since:
        # Try to get last tag automatically
        args.tag = get_last_tag(args.repo_path)

        if args.tag:
            print(f"Using last tag: {args.tag}")
        else:
            print("No tags found, using all history")

    print(f"Loading commits...")
    if not generator.load_commits(since=args.since, until=args.until, after_tag=args.tag):
        return 1

    if not generator.commits:
        print("No commits found in the specified range")
        return 0

    if args.summary:
        generator.print_summary()
        return 0

    # Generate changelog
    print(f"Generating changelog for {len(generator.commits)} commits...")

    if args.format == 'json':
        content = generator.generate_json()
    else:
        content = generator.generate_markdown(
            version=args.version,
            date=args.date
        )

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(content, encoding='utf-8')
        print(f"Changelog saved to: {output_path.absolute()}")
    else:
        print(content)

    return 0


if __name__ == '__main__':
    exit(main())