#!/usr/bin/env python3
"""
Git Preflight Checker - Pre-commit and Staging Health Hook

This tool audits the active Git staging area and repository context before
committing or pushing code. It checks:
    1. Active branch name conventions
    2. Staged file size budgets (preventing commits of > 1MB files)
    3. Accidental debug statements left in code (print, debugger, pdb, console.log)
    4. Secrets or credentials accidentally staged (keys, tokens, entropy scan)
    5. Conventional commits syntax audit on the last commit message

It returns exit code 0 on success, and 1 if any critical checks fail,
making it a perfect pre-commit hook.

Requirements:
    - Pure Python 3 (uses standard 'git' command line tool)
"""

import sys
import os
import subprocess
import re
import math
import argparse

# ANSI Terminal Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'blue': '\033[34m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def run_git_command(args):
    """Safely executes a git command and returns output, or None on error"""
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

# High-entropy calculations to catch secrets/keys
def calculate_entropy(s):
    """Calculates Shannon Entropy of a string to identify high-entropy secrets"""
    if not s:
        return 0
    entropy = 0
    # Create frequency map
    char_counts = {}
    for char in s:
        char_counts[char] = char_counts.get(char, 0) + 1
    # Compute probabilities
    for count in char_counts.values():
        p = count / len(s)
        entropy -= p * math.log2(p)
    return entropy

class GitPreflightChecker:
    def __init__(self, size_budget_mb=1.0, block_main_commits=True):
        self.size_budget_bytes = size_budget_mb * 1024 * 1024
        self.block_main_commits = block_main_commits
        self.failures = []
        self.warnings = []

    def log_failure(self, check, msg):
        self.failures.append({"check": check, "message": msg})

    def log_warning(self, check, msg):
        self.warnings.append({"check": check, "message": msg})

    def check_branch_name(self):
        branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        if not branch:
            self.log_warning("Branch Name", "Not in a valid Git repository.")
            return

        # Block direct commits to main/master if enabled
        if self.block_main_commits and branch in ("main", "master"):
            self.log_failure("Branch Name", f"Direct commits to '{branch}' branch are blocked. Use a feature branch.")
            return

        # Check naming convention
        # Allowed prefixes: feature/, bugfix/, hotfix/, docs/, refactor/, chore/
        pattern = r'^(feature|bugfix|hotfix|docs|refactor|chore|release|test)/[a-zA-Z0-9\-_./]+$'
        if branch not in ("main", "master") and not re.match(pattern, branch):
            self.log_warning(
                "Branch Name",
                f"Branch '{branch}' does not match standard naming conventions (e.g. feature/add-login, bugfix/fix-auth)."
            )

    def check_staged_file_sizes(self):
        # List staged files with sizes
        staged_files_output = run_git_command(["diff", "--cached", "--name-status"])
        if not staged_files_output:
            return # No files staged

        for line in staged_files_output.splitlines():
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            status, filepath = parts[0], parts[1]
            if status == 'D':  # Skip deleted files
                continue

            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                if size > self.size_budget_bytes:
                    size_mb = size / (1024 * 1024)
                    self.log_failure(
                        "File Size",
                        f"Staged file '{filepath}' is too large ({size_mb:.2f} MB). Budget limit is {self.size_budget_bytes / (1024*1024):.1f} MB."
                    )

    def check_debug_and_secrets(self):
        # We want to scan the actual diff changes to find debug statements and secrets
        # Get diff of staged additions only
        diff_output = run_git_command(["diff", "--cached", "-U0"])
        if not diff_output:
            return

        # Simple parse of unified diff to track files and added lines
        current_file = None
        
        # Regexes for debug keywords
        debug_rules = [
            (r'console\.log\(', "JavaScript console.log"),
            (r'debugger;', "JavaScript debugger statement"),
            (r'print\(', "Python print statement"),
            (r'import pdb;.*pdb\.set_trace\(', "Python pdb debugger"),
            (r'breakpoint\(', "Python built-in breakpoint"),
            (r'System\.out\.print', "Java print statement"),
            (r'fmt\.Print', "Go print statement"),
        ]

        # Regexes for common API key and Token patterns
        secret_patterns = [
            (r'(?i)(aws_access_key_id|aws_secret_access_key|secret_key|api_key|token|password|auth_token|client_secret)\s*[:=]\s*["\'][a-zA-Z0-9_\-\+/]{16,}["\']', "Suspected Hardcoded Key/Secret"),
            (r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----', "Private Cryptographic Key"),
            (r'xox[pboar]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32}', "Slack Token"),
            (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
        ]

        for line in diff_output.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue
            
            # Staged line addition
            if line.startswith("+") and not line.startswith("+++"):
                added_code = line[1:].strip()
                if not added_code:
                    continue

                # 1. Audit Debug statements
                # Only check specific programming files
                file_ext = os.path.splitext(current_file or "")[1].lower()
                if file_ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".cpp", ".c", ".rs"):
                    # Exclude comments
                    if added_code.startswith(("#", "//", "/*", "*")):
                        continue
                        
                    for pattern, rule_name in debug_rules:
                        # For python print, make sure we only check python files
                        if rule_name.startswith("Python") and file_ext != ".py":
                            continue
                        # For JS console, only check JS/TS files
                        if rule_name.startswith("JavaScript") and file_ext not in (".js", ".ts", ".jsx", ".tsx"):
                            continue
                        
                        if re.search(pattern, added_code):
                            self.log_warning(
                                "Debug Statement",
                                f"Accidental debug statement '{rule_name}' found in '{current_file}': '{added_code}'"
                            )

                # 2. Audit Secrets
                for pattern, secret_type in secret_patterns:
                    if re.search(pattern, added_code):
                        self.log_failure(
                            "Secret Scanner",
                            f"Suspected {secret_type} exposed in '{current_file}': '{added_code[:40]}...'"
                        )
                        break
                
                # Check for high-entropy tokens (e.g. API keys or random hashes in strings)
                # Matches substrings inside quotes that look like high entropy hashes
                string_matches = re.findall(r'["\']([a-zA-Z0-9_\-\+/]{24,})["\']', added_code)
                for s in string_matches:
                    entropy = calculate_entropy(s)
                    # Base64 tokens or API keys usually have entropy > 4.5
                    if entropy > 4.6 and len(s) > 32:
                        # Exclude some obvious base64 mock arrays or paths
                        if "/" not in s and "\\" not in s:
                            self.log_warning(
                                "Secret Scanner",
                                f"High-entropy string detected in '{current_file}' (entropy={entropy:.2f}): '{s[:12]}...{s[-8:]}'"
                            )

    def check_conventional_commits(self):
        # Fetch last commit message
        last_commit_msg = run_git_command(["log", "-1", "--pretty=%B"])
        if not last_commit_msg:
            # Empty repository / no commits
            return

        first_line = last_commit_msg.splitlines()[0].strip()
        
        # Standard conventional commits: type(scope)!: description
        # Allowed types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
        pattern = r'^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9\-_\.]+\))?\!?: .+$'
        
        if not re.match(pattern, first_line):
            self.log_warning(
                "Commit Message",
                f"Last commit message '{first_line}' does not follow Conventional Commits formatting. Example: 'feat(auth): add login validation'."
            )

    def run_checks(self):
        # Ensure we are inside a Git repo
        git_check = run_git_command(["rev-parse", "--is-inside-work-tree"])
        if not git_check:
            print(colorize("Error: Not a git repository or git command not available.", 'red'))
            return False

        self.check_branch_name()
        self.check_staged_file_sizes()
        self.check_debug_and_secrets()
        self.check_conventional_commits()
        return len(self.failures) == 0

def main():
    parser = argparse.ArgumentParser(description="Git staging preflight check and validation hook.")
    parser.add_argument("-b", "--budget", type=float, default=1.0, help="File size budget in MB (default: 1.0 MB)")
    parser.add_argument("--allow-main", action="store_true", help="Allow committing directly to main/master branches")
    args = parser.parse_args()

    checker = GitPreflightChecker(
        size_budget_mb=args.budget,
        block_main_commits=not args.allow_main
    )

    print(colorize("=== Running Git Preflight Checks ===", 'bold'))
    success = checker.run_checks()

    # Output details
    # 1. Print failures (critical)
    if checker.failures:
        print(colorize("\n[CRITICAL FAILURES]", 'red'))
        for f in checker.failures:
            print(f"  {colorize('[x]', 'red')} {colorize(f['check'] + ':', 'bold')} {f['message']}")

    # 2. Print warnings (non-blocking)
    if checker.warnings:
        print(colorize("\n[WARNINGS]", 'yellow'))
        for w in checker.warnings:
            print(f"  {colorize('[!]', 'yellow')} {colorize(w['check'] + ':', 'bold')} {w['message']}")

    # 3. Print overall status
    print("\n" + "=" * 36)
    if success:
        print(colorize("STATUS: PASS (Preflight Successful)", 'green'))
        if checker.warnings:
            print(colorize("Check warnings above, but they are not blocking.", 'yellow'))
        sys.exit(0)
    else:
        print(colorize("STATUS: FAIL (Fix critical errors above)", 'red'))
        sys.exit(1)

if __name__ == "__main__":
    main()
