#!/usr/bin/env python3
"""
Git PR Template Generator
Parses local branch commits against a base branch (like main or master) to generate
a structured, markdown-formatted Pull Request description template.
"""

import subprocess
import re
import argparse
import sys
import os
from typing import Dict, List, Set, Tuple


def run_git_command(args: List[str], cwd: str = ".") -> str:
    """Run a git command and return its stdout as a string."""
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=cwd
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: git {' '.join(args)}", file=sys.stderr)
        print(f"Error: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Git executable not found on system PATH.", file=sys.stderr)
        sys.exit(1)


def get_current_branch(cwd: str) -> str:
    """Get the name of the active git branch."""
    return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def get_commits(base_branch: str, current_branch: str, cwd: str) -> List[Tuple[str, str, str]]:
    """Get list of commits (hash, author, message) between base_branch and current_branch."""
    # Format: hash|author|subject
    log_format = "%H|%an|%s"
    output = run_git_command(["log", f"{base_branch}..{current_branch}", f"--format={log_format}"], cwd)
    if not output:
        return []
        
    commits = []
    for line in output.split("\n"):
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append((parts[0], parts[1], parts[2]))
    return commits


def get_changed_files(base_branch: str, current_branch: str, cwd: str) -> List[str]:
    """Get list of files changed between base_branch and current_branch."""
    output = run_git_command(["diff", f"{base_branch}..{current_branch}", "--name-only"], cwd)
    if not output:
        return []
    return output.split("\n")


def parse_commits(commits: List[Tuple[str, str, str]]) -> Tuple[Dict[str, List[str]], Set[str], List[str]]:
    """
    Parse commit subjects to extract conventional commit groupings, issue references,
    and fallback uncategorized commit subjects.
    """
    categories = {
        "feat": [],
        "fix": [],
        "docs": [],
        "style": [],
        "refactor": [],
        "perf": [],
        "test": [],
        "chore": [],
        "ci": [],
        "build": []
    }
    issues = set()
    other_commits = []
    
    # Regexes for parsing
    conv_commit_re = re.compile(r"^([a-z]+)(?:\([a-zA-Z0-9_-]+\))?!?\s*:\s*(.*)$", re.IGNORECASE)
    issue_re = re.compile(r"(?:close|closes|fix|fixes|resolve|resolves|refs)?\s*#(\d+)\b", re.IGNORECASE)
    
    for _, _, subject in commits:
        # Check conventional commit format
        match = conv_commit_re.match(subject)
        if match:
            c_type = match.group(1).lower()
            desc = match.group(2).strip()
            if c_type in categories:
                categories[c_type].append(desc)
            else:
                other_commits.append(subject)
        else:
            other_commits.append(subject)
            
        # Check for issue references
        for issue_match in issue_re.finditer(subject):
            issues.add(issue_match.group(1))
            
    # Clean empty categories
    active_categories = {k: v for k, v in categories.items() if v}
    return active_categories, issues, other_commits


def generate_pr_markdown(
    base: str,
    head: str,
    categories: Dict[str, List[str]],
    issues: Set[str],
    other_commits: List[str],
    changed_files: List[str]
) -> str:
    """Constructs the Pull Request Description markdown string."""
    title_suggest = ""
    # Suggest a title based on the first feature or fix
    if "feat" in categories:
        title_suggest = f"feat: {categories['feat'][0]}"
    elif "fix" in categories:
        title_suggest = f"fix: {categories['fix'][0]}"
    elif other_commits:
        title_suggest = other_commits[0]
    else:
        title_suggest = f"PR from {head}"

    md = []
    md.append(f"# Pull Request Description")
    md.append(f"\n> **Suggested PR Title:** `{title_suggest}`")
    md.append(f"\n## 🚀 Summary of Changes")
    
    if not categories and not other_commits:
        md.append("- *No changes detected or commits match the base branch.*")
    
    if "feat" in categories:
        md.append("\n### 🆕 New Features")
        for feat in categories["feat"]:
            md.append(f"- {feat}")
            
    if "fix" in categories:
        md.append("\n### 🐛 Bug Fixes")
        for fix in categories["fix"]:
            md.append(f"- {fix}")
            
    # Group remaining technical commits
    tech_improvements = []
    for k in ["refactor", "perf", "test", "build", "ci", "style", "docs", "chore"]:
        if k in categories:
            for item in categories[k]:
                tech_improvements.append(f"- **{k.capitalize()}**: {item}")
                
    if tech_improvements:
        md.append("\n### 🛠️ Technical Improvements")
        md.extend(tech_improvements)
        
    if other_commits:
        md.append("\n### 📝 Other Commits")
        for commit in other_commits:
            md.append(f"- {commit}")
            
    md.append("\n## ⛓️ Related Issues")
    if issues:
        for issue in sorted(issues):
            md.append(f"- Closes #{issue}")
    else:
        md.append("- None (or link issues manually here)")
        
    md.append("\n## 📁 Modified Files")
    if changed_files:
        md.append("<details>")
        md.append(f"<summary>View all {len(changed_files)} changed files</summary>\n")
        for file in changed_files:
            md.append(f"- `{file}`")
        md.append("\n</details>")
    else:
        md.append("- No files modified.")
        
    md.append("\n## 🧪 Checklist")
    md.append("- [ ] My code follows the code style of this project.")
    md.append("- [ ] I have performed a self-review of my own code.")
    md.append("- [ ] I have commented my code, particularly in hard-to-understand areas.")
    md.append("- [ ] I have made corresponding changes to the documentation.")
    md.append("- [ ] My changes generate no new warnings.")
    md.append("- [ ] I have added tests that prove my fix is effective or that my feature works.")
    md.append("- [ ] New and existing unit tests pass locally with my changes.")
    
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate a markdown template for Pull Requests from Git commits.")
    parser.add_argument("--base", default="main", help="Base branch to compare against (default: main)")
    parser.add_argument("--cwd", default=".", help="Working directory of git repository")
    parser.add_argument("--output", help="Save the PR template to a markdown file")
    
    args = parser.parse_args()
    
    if not os.path.exists(os.path.join(args.cwd, ".git")):
        print(f"Error: '{args.cwd}' is not a valid git repository (no .git folder found).", file=sys.stderr)
        sys.exit(1)
        
    head_branch = get_current_branch(args.cwd)
    
    if head_branch == args.base:
        print(f"Warning: Current branch is same as base branch ({args.base}). No commits can be compared.", file=sys.stderr)
        
    commits = get_commits(args.base, head_branch, args.cwd)
    changed_files = get_changed_files(args.base, head_branch, args.cwd)
    
    categories, issues, other_commits = parse_commits(commits)
    
    pr_template = generate_pr_markdown(
        args.base, head_branch, categories, issues, other_commits, changed_files
    )
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(pr_template)
        print(f"PR Template successfully generated and saved to: {args.output}")
    else:
        print(pr_template)


if __name__ == "__main__":
    main()
