#!/usr/bin/env python3
"""
Git Branch Name Validator & Linter
Audits Git branch names in a repository against customizable naming rules and conventions.
Supports interactive renaming of violating branches, custom regex pattern config, and
exits with appropriate status codes for Git pre-commit/pre-push hooks or CI pipelines.
"""

import argparse
import subprocess
import sys
import re
from typing import List, Tuple, Dict, Optional

# Default prefixes and regex patterns
DEFAULT_PREFIXES = ["feature", "bugfix", "hotfix", "release", "support", "docs", "chore", "refactor", "test"]
DEFAULT_PATTERN = r'^(?:{prefixes})/[a-z0-9._-]+$'

# Color constants
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def run_git_command(args: List[str]) -> str:
    """Runs a git command and returns its standard output, raising an exception on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error running 'git {' '.join(args)}': {e.stderr.strip()}{RESET}", file=sys.stderr)
        raise RuntimeError("Git command failed")
    except FileNotFoundError:
        print(f"{RED}Error: 'git' executable not found. Make sure Git is installed and in your PATH.{RESET}", file=sys.stderr)
        sys.exit(1)

def get_branches(remote: bool = False) -> List[str]:
    """Retrieves list of branches in the current repository."""
    args = ["branch"]
    if remote:
        args.append("-r")
    else:
        args.append("--list")
    
    output = run_git_command(args)
    if not output:
        return []
    
    branches = []
    for line in output.split("\n"):
        # Strip indicator '*' and whitespace
        branch = line.replace("*", "").strip()
        # Strip remote path prefix if checking remotes
        if remote and branch.startswith("origin/"):
            # We want the bare name or relative name
            pass
        branches.append(branch)
    return branches

def get_current_branch() -> str:
    """Returns the name of the currently checked out branch."""
    return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])

def validate_branch(branch: str, pattern: str) -> Tuple[bool, str]:
    """Validates a branch name against a regex pattern."""
    # Strip remote prefix (e.g. origin/) if present
    name_to_check = branch
    if branch.startswith("origin/"):
        name_to_check = branch[len("origin/"):]
        
    # Ignore HEAD pointer references in remote output
    if "->" in name_to_check:
        return True, ""

    if re.match(pattern, name_to_check):
        return True, ""
    
    # Analyze common issues for helpful tips
    if name_to_check.upper() == name_to_check:
        return False, "Branch name is in ALL-CAPS; should be lowercase."
    if "_" in name_to_check and not "/" in name_to_check:
        return False, "Missing category prefix (e.g. feature/name or bugfix/name) and uses underscores instead of hyphens."
    if "/" not in name_to_check:
        return False, "Missing category prefix. Examples: feature/name, bugfix/name."
    
    parts = name_to_check.split("/", 1)
    prefix = parts[0]
    if len(parts) > 1 and prefix not in DEFAULT_PREFIXES:
        return False, f"Invalid prefix '{prefix}'. Allowed prefixes: {', '.join(DEFAULT_PREFIXES)}."
        
    return False, "Does not match conventions (lowercase, alphanumeric, hyphens/periods, category prefix)."

def rename_branch(old_name: str, new_name: str) -> bool:
    """Renames a local git branch."""
    try:
        run_git_command(["branch", "-m", old_name, new_name])
        return True
    except RuntimeError:
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Audit Git branch names against naming conventions and rules."
    )
    parser.add_argument(
        "-p", "--pattern",
        help="Custom regex pattern to validate branch names. If omitted, uses default prefixes format."
    )
    parser.add_argument(
        "--prefixes",
        help=f"Comma-separated list of allowed branch category prefixes (default: {','.join(DEFAULT_PREFIXES)})."
    )
    parser.add_argument(
        "-r", "--remote",
        action="store_true",
        help="Audit remote branches as well (read-only)."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Prompt to interactively rename violating local branches."
    )
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Only validate the current checked-out branch (ideal for pre-push hooks)."
    )

    args = parser.parse_args()

    # Determine allowed prefixes
    prefixes = DEFAULT_PREFIXES
    if args.prefixes:
        prefixes = [p.strip() for p in args.prefixes.split(",") if p.strip()]

    # Construct validation regex pattern
    validation_pattern = args.pattern
    if not validation_pattern:
        prefixes_pattern = "|".join(prefixes)
        validation_pattern = DEFAULT_PATTERN.format(prefixes=prefixes_pattern)

    try:
        # Check if we are inside a Git repository
        run_git_command(["rev-parse", "--is-inside-work-tree"])
    except RuntimeError:
        print(f"{RED}Error: Current directory is not a Git repository.{RESET}", file=sys.stderr)
        sys.exit(1)

    # Determine branches to check
    branches_to_check = []
    current_branch = get_current_branch()
    
    if args.check_current:
        branches_to_check = [current_branch]
    else:
        branches_to_check = get_branches(remote=False)
        if args.remote:
            remote_branches = get_branches(remote=True)
            branches_to_check.extend(remote_branches)

    # Remove duplicates while keeping order
    seen = set()
    branches_to_check = [x for x in branches_to_check if not (x in seen or seen.add(x))]

    violating_branches: List[Tuple[str, str]] = []
    passed_count = 0

    print(f"{BOLD}Auditing Git branch names against pattern:{RESET} `{validation_pattern}`\n")

    for branch in branches_to_check:
        is_valid, reason = validate_branch(branch, validation_pattern)
        if is_valid:
            passed_count += 1
        else:
            violating_branches.append((branch, reason))
            is_current = " (current)" if branch == current_branch else ""
            print(f"[{RED}FAIL{RESET}] {BOLD}{branch}{RESET}{is_current}")
            print(f"       Reason: {reason}")

    print("\n" + "=" * 50)
    print(f"Summary: Checked {len(branches_to_check)} branches. {GREEN}{passed_count} passed{RESET}, {RED}{len(violating_branches)} failed{RESET}.")
    print("=" * 50 + "\n")

    if not violating_branches:
        print(f"{GREEN}All checked branches comply with naming rules.{RESET}")
        sys.exit(0)

    # Interactive repair mode for local branches
    if args.interactive:
        renamed_count = 0
        for branch, reason in violating_branches:
            if branch.startswith("origin/"):
                print(f"{YELLOW}Skipping remote branch {branch} (cannot rename remotely via interactive prompt).{RESET}")
                continue
            
            print(f"Violating branch: {BOLD}{branch}{RESET}")
            try:
                response = input("Would you like to rename this branch? [y/N]: ").strip().lower()
                if response == 'y':
                    new_name = input("Enter new branch name: ").strip()
                    if not new_name:
                        print("Skipped (empty name).")
                        continue
                    
                    is_valid_new, new_reason = validate_branch(new_name, validation_pattern)
                    if not is_valid_new:
                        print(f"{YELLOW}Warning: New name '{new_name}' also violates guidelines. ({new_reason}){RESET}")
                        confirm = input("Rename anyway? [y/N]: ").strip().lower()
                        if confirm != 'y':
                            continue
                            
                    if rename_branch(branch, new_name):
                        print(f"{GREEN}Successfully renamed '{branch}' to '{new_name}'{RESET}")
                        renamed_count += 1
                    else:
                        print(f"{RED}Failed to rename branch.{RESET}")
            except (KeyboardInterrupt, EOFError):
                print("\nAborted interactive session.")
                break
        
        if renamed_count > 0:
            print(f"\n{GREEN}Successfully renamed {renamed_count} branches. Please run the tool again to re-audit.{RESET}")

    # Exit with failure status if there are remaining violating branches
    if not args.interactive:
        print(f"{YELLOW}Tip: Run with --interactive to repair local branch names.{RESET}")
    sys.exit(1)

if __name__ == "__main__":
    main()
