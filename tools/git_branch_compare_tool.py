#!/usr/bin/env python3
"""
Git Branch Compare Tool

Compares two Git branches locally and prints/saves a detailed report containing:
- Commits unique to branch A
- Commits unique to branch B
- Files changed between them (stating modifications/additions/deletions)
- Short line-level differences summary

Usage:
    python tools/git_branch_compare_tool.py main feature-branch
    python tools/git_branch_compare_tool.py main feature-branch -o comparison_report.md
"""

import sys
import subprocess
import os
import argparse
from typing import List, Tuple

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text: str, color: str):
    """Print to stderr or stdout with ANSI colors if enabled."""
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def run_git_cmd(args: List[str], cwd: str = ".") -> Tuple[int, str, str]:
    """Helper to run shell git command and capture output."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except FileNotFoundError:
        print_colored("[-] Error: 'git' executable not found on system path.", RED)
        sys.exit(1)
    except Exception as e:
        print_colored(f"[-] Execution Error: {e}", RED)
        sys.exit(1)

def verify_repo(cwd: str):
    """Verifies that we are within a valid Git repository."""
    code, out, err = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd)
    if code != 0 or out != "true":
        print_colored("[-] Error: Current directory is not a valid Git repository.", RED)
        sys.exit(1)

def verify_branch(branch: str, cwd: str):
    """Verifies that a branch exists locally or remotely."""
    code, out, err = run_git_cmd(["show-ref", "--verify", f"refs/heads/{branch}"], cwd)
    if code == 0:
        return
    # Check remotes
    code, out, err = run_git_cmd(["show-ref", f"refs/remotes/{branch}"], cwd)
    if code == 0:
        return
    # General checkout dry run or revision parse check
    code, out, err = run_git_cmd(["rev-parse", "--quiet", "--verify", branch], cwd)
    if code != 0:
        print_colored(f"[-] Error: Branch/Revision '{branch}' was not found in the repository.", RED)
        sys.exit(1)

def compare_branches(branch_a: str, branch_b: str, output_file: str, cwd: str):
    """Performs the branch analysis and prints/saves the summary."""
    verify_repo(cwd)
    verify_branch(branch_a, cwd)
    verify_branch(branch_b, cwd)

    report_lines = []
    
    # 1. Header
    title = f"Git Branch Comparison: {branch_a} vs {branch_b}"
    report_lines.append(f"# {title}")
    report_lines.append(f"Analyzed on: {run_git_cmd(['log', '-1', '--format=%ad'])[1]}")
    report_lines.append("")

    print_colored(f"[*] Comparing branch '{branch_a}' and branch '{branch_b}'...", BLUE)

    # 2. Commits unique to branch A (A..B means what B has but A doesn't; so B..A means A has but B doesn't)
    _, commits_a_only, _ = run_git_cmd(["log", f"{branch_b}..{branch_a}", "--oneline"], cwd)
    commits_a_list = [line.strip() for line in commits_a_only.splitlines() if line.strip()]
    
    # 3. Commits unique to branch B
    _, commits_b_only, _ = run_git_cmd(["log", f"{branch_a}..{branch_b}", "--oneline"], cwd)
    commits_b_list = [line.strip() for line in commits_b_only.splitlines() if line.strip()]

    # 4. File Diffs
    _, files_diff, _ = run_git_cmd(["diff", "--name-status", f"{branch_a}..{branch_b}"], cwd)
    files_list = [line.strip() for line in files_diff.splitlines() if line.strip()]

    # 5. Shortstat Summary
    _, shortstat, _ = run_git_cmd(["diff", "--shortstat", f"{branch_a}..{branch_b}"], cwd)

    # Compile report contents
    report_lines.append(f"## Line Diffs Summary")
    report_lines.append(f"`{shortstat if shortstat else 'No differences found'}`")
    report_lines.append("")

    # Commits summary
    report_lines.append(f"## Commit Discrepancies")
    report_lines.append(f"- **Commits unique to `{branch_a}` ({len(commits_a_list)}):**")
    if commits_a_list:
        for c in commits_a_list[:20]:
            report_lines.append(f"  - `{c}`")
        if len(commits_a_list) > 20:
            report_lines.append(f"  - ... and {len(commits_a_list) - 20} more commits.")
    else:
        report_lines.append("  - None")
    
    report_lines.append("")
    report_lines.append(f"- **Commits unique to `{branch_b}` ({len(commits_b_list)}):**")
    if commits_b_list:
        for c in commits_b_list[:20]:
            report_lines.append(f"  - `{c}`")
        if len(commits_b_list) > 20:
            report_lines.append(f"  - ... and {len(commits_b_list) - 20} more commits.")
    else:
        report_lines.append("  - None")
    report_lines.append("")

    # Files changed
    report_lines.append(f"## Files Changed ({len(files_list)})")
    if files_list:
        report_lines.append("| Status | File Path |")
        report_lines.append("|---|---|")
        for f in files_list:
            parts = f.split(None, 1)
            status = parts[0]
            filename = parts[1] if len(parts) > 1 else ""
            report_lines.append(f"| `{status}` | {filename} |")
    else:
        report_lines.append("- No files differed.")
    report_lines.append("")

    report_text = "\n".join(report_lines)

    # Print to console
    print_colored(f"\n=== {title} ===", BOLD + CYAN)
    print_colored(f"\nSummary of line changes: {shortstat if shortstat else 'None'}", YELLOW)
    print_colored(f"\nUnique commits on '{branch_a}': {len(commits_a_list)}", GREEN)
    print_colored(f"Unique commits on '{branch_b}': {len(commits_b_list)}", GREEN)
    print_colored(f"Files modified: {len(files_list)}", GREEN)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            print_colored(f"\n[+] Saved detailed Markdown report to '{output_file}'", GREEN)
        except Exception as e:
            print_colored(f"\n[-] Error saving output file: {e}", RED)
    else:
        print_colored("\n--- Detailed Output ---", CYAN)
        print(report_text)

def main():
    parser = argparse.ArgumentParser(description="Compares two local Git branches.")
    parser.add_argument("branch_a", help="The reference branch (e.g. main)")
    parser.add_argument("branch_b", help="The target branch to compare against (e.g. feature)")
    parser.add_argument("-o", "--output", help="Optional path to save Markdown report")
    parser.add_argument("-C", "--directory", default=".", help="Working directory of Git repo (default: .)")

    args = parser.parse_args()
    compare_branches(args.branch_a, args.branch_b, args.output, args.directory)

if __name__ == "__main__":
    main()
