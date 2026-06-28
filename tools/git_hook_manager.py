#!/usr/bin/env python3
"""
Git Hook Manager
A command-line utility to inspect, create, activate, deactivate, and test Git hooks locally.
"""

import argparse
import os
import sys
import shutil
import stat

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"

# Standard git hooks list
GIT_HOOKS = [
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
    "post-update",
    "reference-transaction",
    "push-to-checkout",
    "pre-auto-gc",
    "post-rewrite",
    "sendemail-validate",
    "fsmonitor-watchman",
    "p4-changelog",
    "p4-prepare-changelog",
    "p4-post-changelog",
    "p4-pre-submit",
]

# Pre-defined useful hook templates
HOOK_TEMPLATES = {
    "pre-commit-python-lint": r"""#!/usr/bin/env python3
# Pre-commit hook: Auto-run python syntax check and linter on staged files
import sys
import subprocess

def main():
    print("[Pre-Commit Hook] Checking Python files...")
    # Get names of staged files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=True
    )
    staged_files = [f for f in result.stdout.splitlines() if f.endswith(".py")]
    
    if not staged_files:
        print("[Pre-Commit Hook] No Python files staged. Skipping.")
        return 0

    failed = False
    for filepath in staged_files:
        # Check syntax
        syntax_res = subprocess.run([sys.executable, "-m", "py_compile", filepath], capture_output=True)
        if syntax_res.returncode != 0:
            print(f"[Pre-Commit Hook] Syntax error in {filepath}:")
            print(syntax_res.stderr.decode().strip())
            failed = True
            continue

        # Optional: check for print statements, breakpoints, pdb or debug tags
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if "import pdb; pdb.set_trace()" in content or "breakpoint()" in content:
                    print(f"[Pre-Commit Hook] ERROR: Active breakpoint found in {filepath}!")
                    failed = True
        except Exception as e:
            print(f"[Pre-Commit Hook] Error reading {filepath}: {e}")

    if failed:
        print("[Pre-Commit Hook] Rejected commit due to issues in staged files.")
        return 1
    
    print("[Pre-Commit Hook] All checks passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    "commit-msg-lint": r"""#!/usr/bin/env python3
# Commit-msg hook: Validate conventional commit format
import sys
import re

def main():
    commit_msg_filepath = sys.argv[1]
    with open(commit_msg_filepath, "r", encoding="utf-8") as f:
        commit_msg = f.read().strip()

    # Skip validation for merge commits or empty commits
    if commit_msg.startswith("Merge branch") or not commit_msg:
        return 0

    # Conventional commit regex
    pattern = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9_-]+\))?!?: .+$"
    if not re.match(pattern, commit_msg.splitlines()[0]):
        print("[Commit-Msg Hook] ERROR: Invalid commit message format!")
        print("First line must match: <type>(<scope>)?: <description>")
        print("Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert")
        print(f"Your message: {commit_msg.splitlines()[0]}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    "pre-push-tests": r"""#!/bin/sh
# Pre-push hook: Run unit tests before pushing code to remote repo
echo "[Pre-Push Hook] Running unit test suite..."
python -m unittest discover -s tests -p "*_test.py"
if [ $? -ne 0 ]; then
    echo "[Pre-Push Hook] ERROR: Unit tests failed. Push aborted."
    exit 1
fi
echo "[Pre-Push Hook] All tests passed. Proceeding with push."
exit 0
"""
}

def print_color(text, color):
    """Print text with ANSI color if supported."""
    print(f"{color}{text}{COLOR_RESET}")

def find_git_dir():
    """Locate the .git directory by searching current and parent directories."""
    curr = os.path.abspath(os.getcwd())
    while True:
        git_dir = os.path.join(curr, ".git")
        if os.path.isdir(git_dir):
            # Check if it's a file (in worktrees) or a folder
            return git_dir
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return None

def is_executable(filepath):
    """Check if file has executable permissions."""
    if os.name == 'nt':
        # On Windows, we can't reliably check POSIX executable bits,
        # but we can look for specific header/extension and check if file is readable
        return os.path.exists(filepath)
    st = os.stat(filepath)
    return bool(st.st_mode & stat.S_IXUSR)

def set_executable(filepath, executable=True):
    """Set file executable bit (on POSIX systems)."""
    if os.name == 'nt':
        return
    st = os.stat(filepath)
    if executable:
        os.chmod(filepath, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        # Turn off execution flags
        os.chmod(filepath, st.st_mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)

def list_hooks(hooks_dir):
    """List status of all git hooks in directory."""
    print_color(f"{COLOR_BOLD}{'HOOK NAME':<25} | {'STATUS':<12} | {'TYPE/DESCRIPTION'}{COLOR_RESET}")
    print("-" * 75)
    
    for hook in GIT_HOOKS:
        hook_path = os.path.join(hooks_dir, hook)
        sample_path = hook_path + ".sample"
        disabled_path = hook_path + ".disabled"
        
        status = "Missing"
        color = COLOR_RESET
        
        if os.path.exists(hook_path):
            if is_executable(hook_path):
                status = "ACTIVE"
                color = COLOR_GREEN
            else:
                status = "INACTIVE"
                color = COLOR_YELLOW
        elif os.path.exists(disabled_path):
            status = "DISABLED"
            color = COLOR_BLUE
        elif os.path.exists(sample_path):
            status = "Sample only"
            color = COLOR_RESET
            
        print(f"{color}{hook:<25}{COLOR_RESET} | {color}{status:<12}{COLOR_RESET} | ", end="")
        # Brief explanation
        if hook == "pre-commit":
            print("Runs before commit index is updated. Used to lint or run local checks.")
        elif hook == "commit-msg":
            print("Validates commit message content. Used to enforce format rules.")
        elif hook == "prepare-commit-msg":
            print("Pre-populates the commit message editor.")
        elif hook == "pre-push":
            print("Runs before git push is executed. Used to run full test suites.")
        else:
            print("Standard Git Hook event trigger.")

def show_hook(hooks_dir, hook):
    """Show details of a specific hook."""
    hook_path = os.path.join(hooks_dir, hook)
    if not os.path.exists(hook_path):
        # Check disabled
        disabled_path = hook_path + ".disabled"
        if os.path.exists(disabled_path):
            hook_path = disabled_path
        else:
            print_color(f"[-] Hook '{hook}' is not created yet.", COLOR_RED)
            return

    print_color(f"[*] Showing hook: {hook} ({'ACTIVE' if is_executable(hook_path) else 'INACTIVE/DISABLED'})", COLOR_BOLD + COLOR_BLUE)
    print(f"Path: {hook_path}\n" + "-" * 50)
    try:
        with open(hook_path, "r", encoding="utf-8") as f:
            print(f.read())
    except Exception as e:
        print_color(f"Error reading file: {e}", COLOR_RED)

def enable_hook(hooks_dir, hook):
    """Activate a hook."""
    hook_path = os.path.join(hooks_dir, hook)
    disabled_path = hook_path + ".disabled"

    if os.path.exists(disabled_path):
        os.rename(disabled_path, hook_path)
        print(f"[+] Re-enabled hook '{hook}' from disabled storage.")
    
    if os.path.exists(hook_path):
        set_executable(hook_path, True)
        print_color(f"[+] Hook '{hook}' is now ACTIVE.", COLOR_GREEN)
    else:
        print_color(f"[-] Hook '{hook}' does not exist. Use --create to create one.", COLOR_RED)

def disable_hook(hooks_dir, hook, archive=True):
    """Deactivate a hook."""
    hook_path = os.path.join(hooks_dir, hook)
    disabled_path = hook_path + ".disabled"

    if not os.path.exists(hook_path):
        print_color(f"[-] Active hook '{hook}' does not exist.", COLOR_RED)
        return

    if archive:
        if os.path.exists(disabled_path):
            os.remove(disabled_path)
        os.rename(hook_path, disabled_path)
        print_color(f"[+] Hook '{hook}' deactivated (renamed to {hook}.disabled).", COLOR_GREEN)
    else:
        set_executable(hook_path, False)
        print_color(f"[+] Hook '{hook}' deactivated (executable bit removed).", COLOR_GREEN)

def create_hook(hooks_dir, hook, template_name):
    """Create a new hook from template."""
    if template_name not in HOOK_TEMPLATES:
        print_color(f"[-] Unknown template '{template_name}'. Available: {', '.join(HOOK_TEMPLATES.keys())}", COLOR_RED)
        return
        
    hook_path = os.path.join(hooks_dir, hook)
    if os.path.exists(hook_path):
        backup_path = hook_path + ".bak"
        shutil.copy2(hook_path, backup_path)
        print(f"[*] Existing hook backed up to {hook}.bak")

    try:
        with open(hook_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(HOOK_TEMPLATES[template_name])
        set_executable(hook_path, True)
        print_color(f"[+] Created hook '{hook}' using template '{template_name}'.", COLOR_GREEN)
    except Exception as e:
        print_color(f"[-] Failed to write hook: {e}", COLOR_RED)

def test_hook(hooks_dir, hook, args_list):
    """Execute a hook script locally to test it."""
    hook_path = os.path.join(hooks_dir, hook)
    if not os.path.exists(hook_path):
        print_color(f"[-] Hook file '{hook}' does not exist.", COLOR_RED)
        return

    import subprocess
    cmd = [hook_path] + args_list
    print_color(f"[*] Executing test: {' '.join(cmd)}", COLOR_BOLD + COLOR_BLUE)
    
    # Check if executable
    if not is_executable(hook_path) and os.name != 'nt':
        print_color("[!] Warning: Hook file is not executable. Automatically granting permissions to test it...", COLOR_YELLOW)
        set_executable(hook_path, True)
        
    try:
        # On Windows, shell=True may be required depending on script headers
        shell = os.name == 'nt'
        res = subprocess.run(cmd, shell=shell)
        print("-" * 50)
        if res.returncode == 0:
            print_color(f"[+] Hook passed with exit code 0.", COLOR_GREEN)
        else:
            print_color(f"[-] Hook rejected/failed with exit code {res.returncode}.", COLOR_RED)
    except Exception as e:
        print_color(f"[-] Failed to execute hook: {e}", COLOR_RED)

def main():
    parser = argparse.ArgumentParser(
        description="Git Hook Manager - Inspect, create, and toggle Git hooks locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--list", action="store_true", help="List all hooks status")
    group.add_argument("-s", "--show", help="Show contents of a specific hook")
    group.add_argument("-e", "--enable", help="Activate/enable a specific hook")
    group.add_argument("-d", "--disable", help="Deactivate/disable a specific hook")
    group.add_argument("-t", "--test", help="Test run a specific hook")
    
    parser.add_argument("-c", "--create", help="Create or overwrite a hook (specify hook name, e.g. 'pre-commit')")
    parser.add_argument("--template", choices=list(HOOK_TEMPLATES.keys()), help="Template name to use when creating a hook")
    parser.add_argument("--args", nargs=argparse.REMAINDER, default=[], help="Arguments to pass to test runner")

    args = parser.parse_args()

    git_dir = find_git_dir()
    if not git_dir:
        print_color("Error: Not a Git repository (or no .git directory found in parent folders).", COLOR_RED)
        return 1

    hooks_dir = os.path.join(git_dir, "hooks")
    if not os.path.isdir(hooks_dir):
        try:
            os.makedirs(hooks_dir)
            print(f"[+] Created hooks folder: {hooks_dir}")
        except Exception as e:
            print_color(f"Error creating hooks directory: {e}", COLOR_RED)
            return 1

    if args.list:
        list_hooks(hooks_dir)
    elif args.show:
        show_hook(hooks_dir, args.show)
    elif args.enable:
        enable_hook(hooks_dir, args.enable)
    elif args.disable:
        disable_hook(hooks_dir, args.disable)
    elif args.test:
        test_hook(hooks_dir, args.test, args.args)
    elif args.create:
        if not args.template:
            print_color("Error: You must specify a --template option when using --create.", COLOR_RED)
            return 1
        create_hook(hooks_dir, args.create, args.template)
    else:
        # Default action: list hooks
        list_hooks(hooks_dir)

    return 0

if __name__ == "__main__":
    sys.exit(main())
