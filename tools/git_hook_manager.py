#!/usr/bin/env python3
"""
Git Hook Manager - Install, manage, and share Git hooks across repositories.

A CLI tool to easily install, configure, and share Git hooks between projects.

Features:
- Install hooks from a central hooks directory
- Create hooks from templates
- Enable/disable hooks per repository
- Share hooks across multiple repositories
- List installed hooks with status
- Uninstall hooks
- Validate hook scripts

Usage:
    python git_hook_manager.py install <hook_name> [--source FILE]
    python git_hook_manager.py list
    python git_hook_manager.py enable <hook_name>
    python git_hook_manager.py disable <hook_name>
    python git_hook_manager.py uninstall <hook_name>
    python git_hook_manager.py templates

Example:
    python git_hook_manager.py install pre-commit
    python git_hook_manager.py install pre-push --source hooks/pre-push.sh
    python git_hook_manager.py list
"""

import os
import sys
import stat
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# Common Git hooks
GIT_HOOKS = [
    'applypatch-msg', 'pre-applypatch', 'post-applypatch',
    'pre-commit', 'pre-merge-commit', 'prepare-commit-msg',
    'commit-msg', 'post-commit', 'pre-rebase', 'post-checkout',
    'post-merge', 'pre-push', 'pre-receive', 'update',
    'proc-receive', 'post-receive', 'post-update',
    'reference-transaction', 'push-to-checkout', 'fsmonitor-watchman'
]

# Hook templates
HOOK_TEMPLATES = {
    'pre-commit': '''#!/bin/bash
# Pre-commit hook: run before each commit

# Exit on first error
set -e

# Lint staged files (example)
echo "Running pre-commit checks..."

# Add your checks here:
# - Run linters
# - Run formatters
# - Run tests
# - Check for secrets

echo "Pre-commit checks passed!"
exit 0
''',
    'pre-push': '''#!/bin/bash
# Pre-push hook: run before each push

set -e

echo "Running pre-push checks..."

# Add your checks here:
# - Run full test suite
# - Check branch naming conventions
# - Verify commit messages

echo "Pre-push checks passed!"
exit 0
''',
    'commit-msg': '''#!/bin/bash
# Commit message hook: validate commit messages

set -e

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

echo "Validating commit message..."

# Check message length
MSG_LENGTH=$(echo "$COMMIT_MSG" | head -1 | wc -c)
if [ $MSG_LENGTH -gt 72 ]; then
    echo "Warning: First line exceeds 72 characters"
fi

# Add your validation here:
# - Check for conventional commit format
# - Check for issue references

echo "Commit message validation passed!"
exit 0
''',
    'post-merge': '''#!/bin/bash
# Post-merge hook: run after a merge

echo "Running post-merge actions..."

# Check if package.json changed and install dependencies
if git diff-tree -r --name-only HEAD^..HEAD | grep -q package.json; then
    echo "package.json changed, running npm install..."
    npm install
fi

# Check if requirements.txt changed
if git diff-tree -r --name-only HEAD^..HEAD | grep -q requirements.txt; then
    echo "requirements.txt changed, running pip install..."
    pip install -r requirements.txt
fi

echo "Post-merge actions complete!"
''',
    'post-checkout': '''#!/bin/bash
# Post-checkout hook: run after checkout

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
PREV_BRANCH=$3

echo "Switched to branch: $BRANCH_NAME"

# Run setup tasks when switching branches
# - Install dependencies
# - Generate config files
# etc.

echo "Post-checkout actions complete!"
'''
}


class GitHookManager:
    """Manage Git hooks for a repository."""

    def __init__(self, repo_path: str = '.'):
        self.repo_path = Path(repo_path).absolute()
        self.git_dir = self.repo_path / '.git'
        self.hooks_dir = self.git_dir / 'hooks'
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that we're in a Git repository."""
        if not self.git_dir.exists():
            raise ValueError(f"Not a Git repository: {self.repo_path}")

        # Ensure hooks directory exists
        if not self.hooks_dir.exists():
            self.hooks_dir.mkdir(parents=True, exist_ok=True)

    def install_hook(self, hook_name: str, source: Optional[Path] = None,
                     template: bool = False) -> bool:
        """Install a Git hook."""
        hook_name = hook_name.lower()

        if hook_name not in GIT_HOOKS:
            print(f"Warning: '{hook_name}' is not a standard Git hook name")
            print(f"Valid hooks: {', '.join(GIT_HOOKS[:10])}...")

        hook_path = self.hooks_dir / hook_name

        # Determine source content
        if source:
            if not source.exists():
                print(f"Error: Source file not found: {source}")
                return False
            content = source.read_text()
        elif template:
            content = HOOK_TEMPLATES.get(hook_name, '#!/bin/bash\n# Custom hook\n')
        else:
            # Use template if available, else create minimal stub
            content = HOOK_TEMPLATES.get(hook_name, f'#!/bin/bash\n# {hook_name} hook\n\nexit 0\n')

        # Write hook
        hook_path.write_text(content, encoding='utf-8')

        # Make executable (Unix only)
        try:
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except (OSError, AttributeError):
            pass  # Windows doesn't support Unix permissions

        print(f"✓ Installed hook: {hook_name}")
        print(f"  Location: {hook_path}")
        if template:
            print(f"  Created from template")
        elif source:
            print(f"  Copied from: {source}")

        return True

    def enable_hook(self, hook_name: str) -> bool:
        """Enable a hook (make executable / rename from .disabled)."""
        hook_path = self.hooks_dir / hook_name
        disabled_path = self.hooks_dir / f"{hook_name}.disabled"

        if hook_path.exists():
            # Just make executable
            try:
                hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR)
                print(f"✓ Enabled hook: {hook_name}")
                return True
            except Exception as e:
                print(f"Error enabling hook: {e}")
                return False

        elif disabled_path.exists():
            # Rename from .disabled
            disabled_path.rename(hook_path)
            try:
                hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR)
                print(f"✓ Enabled hook: {hook_name}")
                return True
            except Exception as e:
                print(f"Error enabling hook: {e}")
                return False

        print(f"Error: Hook '{hook_name}' not found")
        return False

    def disable_hook(self, hook_name: str) -> bool:
        """Disable a hook (remove exec perms / rename to .disabled)."""
        hook_path = self.hooks_dir / hook_name

        if not hook_path.exists():
            # Check if already disabled
            disabled_path = self.hooks_dir / f"{hook_name}.disabled"
            if disabled_path.exists():
                print(f"Hook '{hook_name}' is already disabled")
                return True
            print(f"Error: Hook '{hook_name}' not found")
            return False

        # Try renaming to .disabled
        disabled_path = self.hooks_dir / f"{hook_name}.disabled"
        try:
            hook_path.rename(disabled_path)
            print(f"✓ Disabled hook: {hook_name}")
            return True
        except Exception:
            # Fallback: just remove execute permission
            try:
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)
                print(f"✓ Disabled hook (removed permissions): {hook_name}")
                return True
            except Exception as e:
                print(f"Error disabling hook: {e}")
                return False

    def uninstall_hook(self, hook_name: str) -> bool:
        """Uninstall (delete) a Git hook."""
        hook_path = self.hooks_dir / hook_name
        disabled_path = self.hooks_dir / f"{hook_name}.disabled"

        deleted = False

        if hook_path.exists():
            hook_path.unlink()
            deleted = True

        if disabled_path.exists():
            disabled_path.unlink()
            deleted = True

        if deleted:
            print(f"✓ Uninstalled hook: {hook_name}")
            return True
        else:
            print(f"Error: Hook '{hook_name}' not found")
            return False

    def list_hooks(self) -> List[Dict]:
        """List all hooks in the repository."""
        hooks = []

        if not self.hooks_dir.exists():
            return hooks

        # Check for standard hooks
        for hook_name in GIT_HOOKS:
            hook_path = self.hooks_dir / hook_name
            disabled_path = self.hooks_dir / f"{hook_name}.disabled"

            status = 'not_installed'
            if hook_path.exists():
                status = 'installed'
                # Check if executable
                if hook_path.stat().st_mode & stat.S_IXUSR:
                    status = 'active'
            elif disabled_path.exists():
                status = 'disabled'

            if status != 'not_installed':
                hooks.append({
                    'name': hook_name,
                    'status': status,
                    'path': str(hook_path if hook_path.exists() else disabled_path)
                })

        # Also list any non-standard hooks
        for item in self.hooks_dir.iterdir():
            name = item.name
            if name.endswith('.disabled'):
                name = name[:-9]

            if name not in [h['name'] for h in hooks] and name in GIT_HOOKS:
                hooks.append({
                    'name': name,
                    'status': 'installed' if item.suffix != '.disabled' else 'disabled',
                    'path': str(item)
                })

        return hooks

    def print_list(self) -> None:
        """Print list of hooks."""
        hooks = self.list_hooks()

        print(f"\n{'='*60}")
        print(f"Git Hooks in: {self.repo_path}")
        print(f"{'='*60}")

        if not hooks:
            print("No hooks installed")
        else:
            active = [h for h in hooks if h['status'] == 'active']
            disabled = [h for h in hooks if h['status'] in ['disabled', 'installed']]

            if active:
                print(f"\n✓ Active ({len(active)}):")
                for hook in active:
                    print(f"  {hook['name']}")

            if disabled:
                print(f"\n⊘ Disabled/Installed ({len(disabled)}):")
                for hook in disabled:
                    print(f"  {hook['name']} ({hook['status']})")

        print(f"\n{'='*60}")
        print(f"Total: {len(hooks)} hooks")
        print(f"{'='*60}\n")

    def list_templates(self) -> None:
        """List available hook templates."""
        print(f"\n{'='*60}")
        print("Available Hook Templates:")
        print(f"{'='*60}")

        for name, content in sorted(HOOK_TEMPLATES.items()):
            description = content.split('\n')[1].strip('#').strip() if '\n' in content else ''
            print(f"  {name:25} - {description}")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Manage Git hooks across repositories'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Install command
    install_parser = subparsers.add_parser('install', help='Install a Git hook')
    install_parser.add_argument('hook_name',
                                help='Name of the hook to install')
    install_parser.add_argument('--source', '-s', type=Path,
                                help='Source file to copy hook from')
    install_parser.add_argument('--template', '-t', action='store_true',
                                help='Create from template')
    install_parser.add_argument('--repo', '-r', default='.',
                                help='Git repository path (default: current)')

    # Enable command
    enable_parser = subparsers.add_parser('enable', help='Enable a Git hook')
    enable_parser.add_argument('hook_name', help='Name of the hook to enable')
    enable_parser.add_argument('--repo', '-r', default='.',
                               help='Git repository path (default: current)')

    # Disable command
    disable_parser = subparsers.add_parser('disable', help='Disable a Git hook')
    disable_parser.add_argument('hook_name', help='Name of the hook to disable')
    disable_parser.add_argument('--repo', '-r', default='.',
                                help='Git repository path (default: current)')

    # Uninstall command
    uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall a Git hook')
    uninstall_parser.add_argument('hook_name', help='Name of the hook to uninstall')
    uninstall_parser.add_argument('--repo', '-r', default='.',
                                  help='Git repository path (default: current)')

    # List command
    list_parser = subparsers.add_parser('list', help='List installed hooks')
    list_parser.add_argument('--repo', '-r', default='.',
                             help='Git repository path (default: current)')

    # Templates command
    subparsers.add_parser('templates', help='List available hook templates')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        manager = GitHookManager(args.repo if hasattr(args, 'repo') else '.')
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    if args.command == 'install':
        success = manager.install_hook(
            args.hook_name,
            source=args.source,
            template=args.template
        )
        return 0 if success else 1

    elif args.command == 'enable':
        success = manager.enable_hook(args.hook_name)
        return 0 if success else 1

    elif args.command == 'disable':
        success = manager.disable_hook(args.hook_name)
        return 0 if success else 1

    elif args.command == 'uninstall':
        success = manager.uninstall_hook(args.hook_name)
        return 0 if success else 1

    elif args.command == 'list':
        manager.print_list()
        return 0

    elif args.command == 'templates':
        manager.list_templates()
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main())