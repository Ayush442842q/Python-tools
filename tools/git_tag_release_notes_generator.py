#!/usr/bin/env python3
"""
Git Tag & Release Notes Auto-Generator
--------------------------------------
Analyzes Git commit history between tags or commit ranges, categorizes commits by
Conventional Commit standards (feat, fix, docs, perf, refactor, test, chore, style),
detects breaking changes and issue references (#123), and formats Markdown release notes
and GitHub release JSON payloads.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import subprocess
import argparse
from typing import List, Dict, Any, Tuple, Optional

# Ensure stdout handles UTF-8 on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

CONVENTIONAL_MAP = {
    "feat": "Features",
    "feature": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance Improvements",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Testing",
    "tests": "Testing",
    "build": "Build & CI",
    "ci": "Build & CI",
    "style": "Code Style",
    "chore": "Maintenance & Chores"
}


def parse_git_log_output(log_text: str) -> List[Dict[str, Any]]:
    """Parse raw git log output into structured commit dictionaries."""
    commits = []
    lines = log_text.strip().splitlines()
    for line in lines:
        if not line.strip():
            continue
        parts = line.strip().split("|||")
        if len(parts) >= 4:
            commit_hash, author, date, subject = parts[0], parts[1], parts[2], parts[3]
            body = parts[4] if len(parts) > 4 else ""
            commits.append({
                "hash": commit_hash[:7],
                "full_hash": commit_hash,
                "author": author,
                "date": date,
                "subject": subject.strip(),
                "body": body.strip()
            })
    return commits


def fetch_git_commits(commit_range: Optional[str] = None) -> List[Dict[str, Any]]:
    """Execute git log CLI command to get commit history."""
    fmt = "%H|||%an|||%ad|||%s|||%b"
    cmd = ["git", "log", f"--format={fmt}", "--date=short"]
    if commit_range:
        cmd.append(commit_range)
        
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return parse_git_log_output(res.stdout)
    except Exception as e:
        return []


def categorize_commits(commits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Categorize commits by type, detect breaking changes and issue references."""
    categories: Dict[str, List[Dict[str, Any]]] = {}
    breaking_changes = []
    issues_closed = set()

    for c in commits:
        subj = c["subject"]
        body = c["body"]
        full_text = f"{subj}\n{body}"

        # Detect Issue References (#123, GH-123, Fixes #123)
        issue_matches = re.findall(r"(?:#|GH-)(\d+)", full_text, re.IGNORECASE)
        for issue_id in issue_matches:
            issues_closed.add(f"#{issue_id}")

        # Detect Breaking Changes
        is_breaking = False
        if "BREAKING CHANGE:" in full_text or "BREAKING-CHANGE:" in full_text:
            is_breaking = True
        elif re.match(r"^[a-zA-Z0-9_-]+\!: ", subj):
            is_breaking = True

        if is_breaking:
            breaking_changes.append(c)

        # Match Conventional Commits: type(scope): description
        match = re.match(r"^([a-zA-Z0-9_-]+)(?:\(([^)]+)\))?\!?: (.*)$", subj)
        if match:
            ctype = match.group(1).lower()
            scope = match.group(2)
            desc = match.group(3)

            cat_name = CONVENTIONAL_MAP.get(ctype, "Other Changes")
            if cat_name not in categories:
                categories[cat_name] = []
            
            categories[cat_name].append({
                "commit": c,
                "scope": scope,
                "description": desc
            })
        else:
            cat_name = "Other Changes"
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append({
                "commit": c,
                "scope": None,
                "description": subj
            })

    return {
        "categories": categories,
        "breaking_changes": breaking_changes,
        "issues_closed": sorted(list(issues_closed))
    }


def format_markdown_release(tag_title: str, categorized_data: Dict[str, Any]) -> str:
    """Format release notes in Markdown."""
    lines = [f"# Release Notes: {tag_title}\n"]

    breaking = categorized_data["breaking_changes"]
    if breaking:
        lines.append("## BREAKING CHANGES\n")
        for b in breaking:
            lines.append(f"- **{b['subject']}** (`{b['hash']}`) by @{b['author']}")
        lines.append("")

    categories = categorized_data["categories"]
    for cat_name, items in categories.items():
        lines.append(f"## {cat_name}\n")
        for item in items:
            scope_str = f"**{item['scope']}**: " if item["scope"] else ""
            c = item["commit"]
            lines.append(f"- {scope_str}{item['description']} (`{c['hash']}`)")
        lines.append("")

    issues = categorized_data["issues_closed"]
    if issues:
        lines.append("## Referenced Issues\n")
        lines.append(", ".join(issues))
        lines.append("")

    return "\n".join(lines)


DEMO_GIT_LOG = """a1b2c3d|||Alice Smith|||2026-07-01|||feat(auth): add OAuth2 login provider support|||Resolves #101
e5f6g7h|||Bob Jones|||2026-07-02|||fix(api): handle missing user headers gracefully|||Fixes #104
i9j0k1l|||Charlie Brown|||2026-07-03|||feat!: replace deprecated legacy query endpoint|||BREAKING CHANGE: The /v1/query endpoint has been removed. Use /v2/query instead.
m2n3o4p|||Diana Prince|||2026-07-04|||docs(readme): update setup and configuration guide|||Closes #88
q5r6s7t|||Evan Wright|||2026-07-05|||perf(db): optimize SQL indexing for user lookup|||
u8v9w0x|||Fiona Gallagher|||2026-07-06|||chore: bump dependency packages|||
"""


def main():
    parser = argparse.ArgumentParser(description="Git Tag & Release Notes Auto-Generator")
    parser.add_argument("--range", help="Git commit or tag range (e.g. v1.0.0..v1.1.0 or HEAD~5..HEAD)")
    parser.add_argument("--log-file", help="Parse git log text file instead of executing git command")
    parser.add_argument("--title", default="v1.1.0", help="Release version title (default: v1.1.0)")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Write release notes to file")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample commit history")

    args = parser.parse_args()

    if args.demo:
        print(f"{BOLD}{CYAN}=== Running Git Tag Release Notes Generator Demo ==={RESET}\n")
        commits = parse_git_log_output(DEMO_GIT_LOG)
    elif args.log_file:
        if not os.path.exists(args.log_file):
            print(f"{RED}Error: Log file '{args.log_file}' not found.{RESET}")
            sys.exit(1)
        with open(args.log_file, "r", encoding="utf-8") as f:
            commits = parse_git_log_output(f.read())
    else:
        commits = fetch_git_commits(args.range)
        if not commits:
            print(f"{YELLOW}No git commits found for range '{args.range or 'all'}'. Running demo fallback...{RESET}\n")
            commits = parse_git_log_output(DEMO_GIT_LOG)

    categorized = categorize_commits(commits)

    if args.format == "json":
        output_str = json.dumps({
            "tag_name": args.title,
            "name": f"Release {args.title}",
            "body": format_markdown_release(args.title, categorized),
            "draft": False,
            "prerelease": False,
            "issues_referenced": categorized["issues_closed"],
            "total_commits": len(commits)
        }, indent=2)
    elif args.format == "html":
        md_text = format_markdown_release(args.title, categorized)
        html_lines = ["<!DOCTYPE html><html><head><title>Release Notes</title></head><body>"]
        for line in md_text.splitlines():
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            else:
                html_lines.append(f"<p>{line}</p>")
        html_lines.append("</body></html>")
        output_str = "\n".join(html_lines)
    else:
        output_str = format_markdown_release(args.title, categorized)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"{GREEN}Release notes saved to {args.output}{RESET}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
