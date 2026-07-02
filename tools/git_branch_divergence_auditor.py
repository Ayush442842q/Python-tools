#!/usr/bin/env python3
"""
Git Branch Divergence Auditor & Merge Conflict Predictor
Compares two Git branches to map divergent commits, identify overlapping file changes,
estimate collision risks in shared edits, and suggest resolution strategies.

Features:
1. Validates Git repository status and branch existences.
2. Identifies the nearest common ancestor commit (merge base).
3. Lists unique commits, authorship, and timeline on each branch since divergence.
4. Identifies files modified in BOTH branches since the ancestor (representing immediate conflict paths).
5. Performs simple line-interval collision checks on overlaps to calculate conflict probability.
6. Renders a structured text dashboard in the terminal with colored indicators.
"""

import argparse
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_DIM = "\033[2m"

def supports_color() -> bool:
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_CYAN = ""
    COLOR_DIM = ""


def run_command(cmd: List[str]) -> Tuple[int, str]:
    """Runs a system command and returns exit code and stdout string."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return 0, res.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stderr.strip()
    except FileNotFoundError:
        return -1, "Git executable not found."


def get_commit_info(commit: str) -> str:
    """Retrieves standard summary line for a commit."""
    code, out = run_command(["git", "show", "-s", "--format=%h - %an: %s (%cr)", commit])
    return out if code == 0 else commit


def get_diff_lines(branch: str, base: str, filepath: str) -> Set[int]:
    """Retrieves line numbers that were added or modified in filepath in branch relative to base."""
    code, out = run_command(["git", "diff", f"{base}...{branch}", "--", filepath])
    if code != 0:
        return set()
        
    modified_lines = set()
    current_line = 0
    
    # Simple parse of unified diff hunk headers, e.g. @@ -4,8 +4,7 @@
    for line in out.splitlines():
        if line.startswith("@@"):
            match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                current_line = int(match.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            modified_lines.add(current_line)
            current_line += 1
        elif line.startswith("-") or line.startswith("\\"):
            # Deletions do not shift the current line pointer in target file
            pass
        else:
            current_line += 1
            
    return modified_lines


# Workaround for import re inside functions to keep global scope cleaner
import re

def audit_divergence(branch1: str, branch2: str):
    # Verify we are inside a git repo
    code, out = run_command(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0 or out != "true":
        print(f"{COLOR_RED}Error: Not inside a Git repository.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Verify branches exist
    for b in (branch1, branch2):
        c, _ = run_command(["git", "rev-parse", "--verify", b])
        if c != 0:
            print(f"{COLOR_RED}Error: Branch '{b}' does not exist.{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)

    # 1. Find merge base (ancestor)
    code, merge_base = run_command(["git", "merge-base", branch1, branch2])
    if code != 0 or not merge_base:
        print(f"{COLOR_RED}Error: Could not find common ancestor commit.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_CYAN}=== GIT BRANCH DIVERGENCE AUDITOR ==={COLOR_RESET}\n")
    print(f"Comparing branches:")
    print(f"  Branch 1 (Source) : {COLOR_BOLD}{branch1}{COLOR_RESET}")
    print(f"  Branch 2 (Target) : {COLOR_BOLD}{branch2}{COLOR_RESET}")
    print(f"  Common Ancestor   : {COLOR_YELLOW}{get_commit_info(merge_base)}{COLOR_RESET}\n")

    # 2. Get unique commits on Branch 1 since ancestor
    _, b1_commits_raw = run_command(["git", "log", f"{merge_base}..{branch1}", "--oneline"])
    b1_commits = b1_commits_raw.splitlines() if b1_commits_raw else []

    # 3. Get unique commits on Branch 2 since ancestor
    _, b2_commits_raw = run_command(["git", "log", f"{merge_base}..{branch2}", "--oneline"])
    b2_commits = b2_commits_raw.splitlines() if b2_commits_raw else []

    print(f"{COLOR_BOLD}Commit Divergence Summary:{COLOR_RESET}")
    print(f"  Commits unique to {COLOR_BOLD}{branch1}{COLOR_RESET}: {COLOR_YELLOW}{len(b1_commits)}{COLOR_RESET}")
    print(f"  Commits unique to {COLOR_BOLD}{branch2}{COLOR_RESET}: {COLOR_YELLOW}{len(b2_commits)}{COLOR_RESET}\n")

    # 4. Get modified files on each branch
    _, b1_files_raw = run_command(["git", "diff", "--name-only", f"{merge_base}..{branch1}"])
    b1_files = set(b1_files_raw.splitlines()) if b1_files_raw else set()

    _, b2_files_raw = run_command(["git", "diff", "--name-only", f"{merge_base}..{branch2}"])
    b2_files = set(b2_files_raw.splitlines()) if b2_files_raw else set()

    overlap_files = b1_files.intersection(b2_files)

    print(f"{COLOR_BOLD}File Modifications:{COLOR_RESET}")
    print(f"  Files modified on {COLOR_BOLD}{branch1}{COLOR_RESET}: {len(b1_files)}")
    print(f"  Files modified on {COLOR_BOLD}{branch2}{COLOR_RESET}: {len(b2_files)}")
    print(f"  Overlapping modifications (both branches): {COLOR_RED if overlap_files else COLOR_GREEN}{len(overlap_files)}{COLOR_RESET}\n")

    if overlap_files:
        print(f"{COLOR_BOLD}{COLOR_RED}⚠️ WARNING: Overlapping files detected (Potential Merge Conflicts):{COLOR_RESET}")
        for file in sorted(overlap_files):
            # Check line ranges to estimate conflict risk
            b1_lines = get_diff_lines(branch1, merge_base, file)
            b2_lines = get_diff_lines(branch2, merge_base, file)
            
            collision_lines = b1_lines.intersection(b2_lines)
            
            if collision_lines:
                risk = f"{COLOR_RED}HIGH COLLISION RISK (Overlap on lines {list(collision_lines)[:5]}...){COLOR_RESET}"
            elif b1_lines and b2_lines:
                # Calculate minimum distance between edits
                min_dist = min(abs(x - y) for x in b1_lines for y in b2_lines)
                if min_dist < 5:
                    risk = f"{COLOR_YELLOW}MEDIUM RISK (Edits within {min_dist} lines of each other){COLOR_RESET}"
                else:
                    risk = f"{COLOR_GREEN}LOW RISK (Edits are separated by {min_dist} lines){COLOR_RESET}"
            else:
                risk = f"{COLOR_CYAN}UNKNOWN RISK (Diff reading failed or metadata file){COLOR_RESET}"

            print(f"  - {COLOR_BOLD}{file}{COLOR_RESET}")
            print(f"    Status: {risk}")
        print()
    else:
        print(f"{COLOR_BOLD}{COLOR_GREEN}✓ Clear Path! No overlapping files found. Merging should be clean.{COLOR_RESET}\n")

    # 5. Suggest commands
    print(f"{COLOR_BOLD}Suggested Resolution Commands:{COLOR_RESET}")
    print(f"  To preview changes of {COLOR_BOLD}{branch1}{COLOR_RESET} against {COLOR_BOLD}{branch2}{COLOR_RESET}:")
    print(f"    {COLOR_CYAN}git diff {branch2}...{branch1}{COLOR_RESET}")
    print(f"  To test-merge without committing:")
    print(f"    {COLOR_CYAN}git checkout {branch2} && git merge --no-commit --no-ff {branch1}{COLOR_RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Audits Git branch divergence to find overlapping file changes and predict merge conflicts.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("branch1", help="First branch (e.g. feature branch)")
    parser.add_argument("branch2", help="Second branch (e.g. main/development branch)")
    
    args = parser.parse_args()
    audit_divergence(args.branch1, args.branch2)


if __name__ == "__main__":
    main()
