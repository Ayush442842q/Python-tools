#!/usr/bin/env python3
"""
Git Commit Message Linter & Hook Installer

Lints commit messages for compliance with the Conventional Commits specification.
Can scan past commit history range or integrate directly with Git hooks to block non-compliant commits.

Conventional Commits format:
    <type>(<scope>): <description>

    [optional body]

    [optional footer(s)]

Supported types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.

Usage:
    python tools/git_commit_linter.py -m "feat(ui): add navbar search"
    python tools/git_commit_linter.py --range "origin/main..HEAD"
    python tools/git_commit_linter.py --install-hook
"""

import argparse
import os
import re
import subprocess
import sys

CONVENTIONAL_TYPES = {
    'feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'build', 'ci', 'chore', 'revert'
}

HEADER_REGEX = re.compile(
    r'^([a-zA-Z0-9_-]+)(?:\(([a-zA-Z0-9_ \/-]+)\))?(!)?:\s+(.+)$'
)

def lint_message(message_text):
    """
    Validates a commit message text.
    Returns a list of error/warning strings. Empty list means validation passed.
    """
    errors = []
    lines = [line.rstrip() for line in message_text.strip().split('\n')]
    
    if not lines or not lines[0]:
        return ["Commit message is empty."]

    header = lines[0]
    
    # 1. Header length check
    if len(header) > 72:
        errors.append(f"Header line exceeds 72 characters (current: {len(header)}).")
    elif len(header) < 10:
        errors.append(f"Header line is too short (current: {len(header)}). Should be descriptive.")

    # 2. Check structure using regex
    match = HEADER_REGEX.match(header)
    if not match:
        errors.append(
            "Header does not match Conventional Commits format: '<type>(<scope>): <description>'.\n"
            "   Example: feat(auth): add login functionality"
        )
    else:
        ctype, scope, breaking, desc = match.groups()
        
        # Check if type is allowed
        if ctype.lower() not in CONVENTIONAL_TYPES:
            errors.append(
                f"Type '{ctype}' is not a valid conventional commit type.\n"
                f"   Allowed types: {', '.join(sorted(CONVENTIONAL_TYPES))}"
            )
            
        # Check description casing/punctuation
        if desc:
            if desc[0].isupper():
                errors.append("Description should start with a lowercase letter.")
            if desc.endswith('.'):
                errors.append("Description should not end with a period.")

    # 3. Check spacing after header line
    if len(lines) > 1:
        if lines[1] != "":
            errors.append("Header must be followed by a blank line before body/footer.")

    return errors

def get_git_root():
    """Returns absolute path to the root of the local git repository."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return root
    except subprocess.CalledProcessError:
        return None

def scan_history(rev_range):
    """Lints historical git commit messages in a revision range."""
    print(f"📊 Scanning commit history for range: {rev_range}")
    try:
        # Get hashes and full commit messages
        # Separated by a special delimiter to make parsing multiple commits robust
        delimiter = "---COMMIT-MESSAGE-END---"
        raw_logs = subprocess.check_output(
            ["git", "log", rev_range, f"--format=%h%n%B%n{delimiter}"],
            stderr=subprocess.STDOUT
        ).decode('utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running git log: {e.output.decode('utf-8')}", file=sys.stderr)
        return 1

    commits = raw_logs.split(delimiter)
    failed_commits = 0
    total_commits = 0

    for commit in commits:
        commit = commit.strip()
        if not commit:
            continue
        
        total_commits += 1
        lines = commit.split('\n')
        commit_hash = lines[0]
        commit_msg = "\n".join(lines[1:])
        
        errors = lint_message(commit_msg)
        if errors:
            failed_commits += 1
            print(f"\n❌ Commit [{commit_hash}] is invalid:")
            # Print first line of commit message for context
            first_line = commit_msg.split('\n')[0] if commit_msg else ""
            print(f"   Original message: \"{first_line}\"")
            for err in errors:
                print(f"   - {err}")

    print("\n" + "=" * 40)
    print(f"📋 Scan complete. Checked {total_commits} commits.")
    if failed_commits > 0:
        print(f"⚠️ Found {failed_commits} invalid commits.")
        return 1
    print("✅ All commits in range conform to standards!")
    return 0

def install_hook():
    """Installs this script as a git commit-msg hook."""
    git_root = get_git_root()
    if not git_root:
        print("❌ Error: Not in a git repository.", file=sys.stderr)
        return 1

    hooks_dir = os.path.join(git_root, ".git", "hooks")
    if not os.path.exists(hooks_dir):
        os.makedirs(hooks_dir)

    hook_path = os.path.join(hooks_dir, "commit-msg")
    script_path = os.path.abspath(__file__)

    # Write git bash hook script
    # Points to this exact script path
    hook_content = f"""#!/bin/sh
# Conventional Commit message hook installed by git_commit_linter.py

# Run the python linter on the commit message file
python "{script_path}" --file "$1"
"""
    try:
        with open(hook_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(hook_content)
        
        # Make the hook executable (Unix-like systems)
        if os.name != 'nt':
            os.chmod(hook_path, 0o755)
            
        print("✅ Git commit-msg hook installed successfully!")
        print(f"   Hook Path: {hook_path}")
        return 0
    except Exception as e:
        print(f"❌ Failed to write hook: {e}", file=sys.stderr)
        return 1

def uninstall_hook():
    """Removes the git commit-msg hook."""
    git_root = get_git_root()
    if not git_root:
        print("❌ Error: Not in a git repository.", file=sys.stderr)
        return 1

    hook_path = os.path.join(git_root, ".git", "hooks", "commit-msg")
    if os.path.exists(hook_path):
        try:
            os.remove(hook_path)
            print("🗑️ Git commit-msg hook uninstalled.")
            return 0
        except Exception as e:
            print(f"❌ Failed to delete hook: {e}", file=sys.stderr)
            return 1
    else:
        print("ℹ️ Hook is not installed.")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Git Commit Message Linter & Hook Installer - Verify conventional commit standards.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-m', '--message', help='Commit message text to lint directly')
    group.add_argument('-f', '--file', help='Path to a commit message file (e.g. .git/COMMIT_EDITMSG)')
    group.add_argument('-r', '--range', help='Revision range (e.g. HEAD~5..HEAD) to lint past history')
    group.add_argument('--install-hook', action='store_true', help='Install conventional commit hook in current git repository')
    group.add_argument('--uninstall-hook', action='store_true', help='Uninstall conventional commit hook')

    args = parser.parse_args()

    if args.install_hook:
        return install_hook()
    elif args.uninstall_hook:
        return uninstall_hook()
    elif args.range:
        return scan_history(args.range)
        
    # Read message from argument or file
    message_text = ""
    if args.message:
        message_text = args.message
    elif args.file:
        if not os.path.exists(args.file):
            print(f"❌ Error: File '{args.file}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                message_text = f.read()
        except Exception as e:
            print(f"❌ Error reading file: {e}", file=sys.stderr)
            return 1

    errors = lint_message(message_text)
    if errors:
        print("❌ Conventional Commit Validation Failed:")
        for err in errors:
            print(f"   - {err}")
        return 1
        
    print("✅ Commit message is valid!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
