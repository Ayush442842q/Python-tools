#!/usr/bin/env python3
"""
Git History Commit Author Rewriter
Safely rewrites author names and emails in local Git repositories.
"""

import sys
import os
import subprocess
import argparse

def is_git_repo():
    """Checks if the current directory is a git repository."""
    return os.path.exists(".git")

def is_working_tree_clean():
    """Checks if the git working tree is clean."""
    try:
        output = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL)
        return len(output.strip()) == 0
    except subprocess.SubprocessError:
        return False

def get_current_branch():
    """Gets the name of the current active branch."""
    try:
        output = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL)
        return output.strip().decode('utf-8')
    except subprocess.SubprocessError:
        return None

def amend_last_commit(new_name, new_email):
    """Amends the author details of the very last commit."""
    author_str = f"{new_name} <{new_email}>"
    cmd = ["git", "commit", "--amend", f"--author={author_str}", "--no-edit"]
    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("✅ Successfully amended the last commit's author details.")
    except subprocess.SubprocessError as e:
        print(f"❌ Failed to amend last commit: {e}")

def generate_filter_branch_cmd(old_email, new_name, new_email):
    """Generates the git filter-branch command block."""
    # Escape quotes and formatting for shells
    filter_script = f"""
if [ "$GIT_COMMITTER_EMAIL" = "{old_email}" ]
then
    export GIT_COMMITTER_NAME="{new_name}"
    export GIT_COMMITTER_EMAIL="{new_email}"
fi
if [ "$GIT_AUTHOR_EMAIL" = "{old_email}" ]
then
    export GIT_AUTHOR_NAME="{new_name}"
    export GIT_AUTHOR_EMAIL="{new_email}"
fi
"""
    # Clean up layout
    filter_script_one_line = filter_script.replace('\n', ' ').strip()
    cmd = f'git filter-branch --env-filter \'{filter_script_one_line}\' --tag-name-filter cat -- --branches --tags'
    return cmd

def main():
    parser = argparse.ArgumentParser(description="Git Commit Author History Rewriter")
    parser.add_argument("--last", action="store_true", help="Amend ONLY the last commit's author details")
    parser.add_argument("--old-email", help="The old email address to scan for and replace")
    parser.add_argument("--new-name", help="The new author/committer name")
    parser.add_argument("--new-email", help="The new author/committer email")
    parser.add_argument("--force", action="store_true", help="Skip clean working tree safety checks")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show what would run without executing history rewrites")
    args = parser.parse_args()

    if not is_git_repo():
        print("❌ Error: Not in a Git repository directory.")
        sys.exit(1)

    print("==============================================")
    print("  Git Commit Author History Rewriter")
    print("==============================================")

    # Interactive mode if arguments are missing
    last_mode = args.last
    old_email = args.old_email
    new_name = args.new_name
    new_email = args.new_email

    if not last_mode and not old_email:
        mode_choice = input("Do you want to amend [1] ONLY the last commit, or [2] rewrite the entire history? (1/2): ").strip()
        if mode_choice == "1":
            last_mode = True
        elif mode_choice == "2":
            last_mode = False
        else:
            print("Invalid selection.")
            sys.exit(1)

    if not new_name:
        new_name = input("Enter NEW author name: ").strip()
    if not new_email:
        new_email = input("Enter NEW author email: ").strip()

    if not new_name or not new_email:
        print("❌ Error: New author name and email are required.")
        sys.exit(1)

    if last_mode:
        if args.dry_run:
            print(f"[DRY-RUN] Would run: git commit --amend --author=\"{new_name} <{new_email}>\" --no-edit")
        else:
            amend_last_commit(new_name, new_email)
        sys.exit(0)

    # Full history rewrite mode
    if not old_email:
        old_email = input("Enter the OLD email address to replace in history: ").strip()
        if not old_email:
            print("❌ Error: Old email is required for full history rewrite.")
            sys.exit(1)

    # Safety checks
    if not args.force and not is_working_tree_clean():
        print("❌ Error: Your Git working directory is not clean. Commit or stash your changes first.")
        print("To bypass this check, use the --force flag.")
        sys.exit(1)

    branch = get_current_branch()
    print(f"Active Branch: {branch}")
    print(f"Action: Replace commits matching <{old_email}> with '{new_name} <{new_email}>'.")
    print("-" * 50)

    filter_cmd = generate_filter_branch_cmd(old_email, new_name, new_email)

    print("⚠️ WARNING: Rewriting git history is destructive and changes all commit hashes!")
    print("Ensure you have a backup of this repository or a remote backup before proceeding.")
    print("\nCommand to execute:")
    print(filter_cmd)
    print("-" * 50)

    if args.dry_run:
        print("[DRY-RUN] Skipping execution. Run without --dry-run or approve interactive prompt to execute.")
        sys.exit(0)

    confirm = input("Are you absolutely sure you want to proceed? (yes/no): ").strip().lower()
    if confirm == "yes":
        print("\nExecuting rewrite...")
        # Since git filter-branch can be slow or might require -f if a backup ref already exists, we run it
        # We append -f for convenience in rewriting repeatedly
        exec_cmd = filter_cmd.replace("git filter-branch", "git filter-branch -f")
        try:
            # We run it using shell=True since it contains shell scripting constructs
            subprocess.run(exec_cmd, shell=True, check=True)
            print("\n✅ Successfully rewrote repository history.")
            print("\nTo push changes to your remote repository, run:")
            print(f"  git push origin {branch} --force")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error executing rewrite: {e}")
            sys.exit(1)
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()
