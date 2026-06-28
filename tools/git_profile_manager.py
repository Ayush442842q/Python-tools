#!/usr/bin/env python3
"""Git Profile Manager

Manage multiple Git profiles (identities) and switch between them easily.
Supports setting names, emails, SSH keys, GPG signing keys, and directory-based
automatic switching using Git's conditional includes (`includeIf`).
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, Any, List

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

PROFILES_FILE = Path.home() / ".git_profiles.json"


def run_git(cmd: List[str], cwd: str = None) -> str:
    """Run a git command and return its stdout, stripping whitespace."""
    try:
        res = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def load_profiles() -> Dict[str, Dict[str, Any]]:
    if not PROFILES_FILE.exists():
        return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{COLOR_RED}Error loading profiles file: {e}{COLOR_RESET}", file=sys.stderr)
        return {}


def save_profiles(profiles: Dict[str, Dict[str, Any]]):
    try:
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        print(f"{COLOR_RED}Error saving profiles file: {e}{COLOR_RESET}", file=sys.stderr)


def get_current_git_identity() -> Dict[str, str]:
    """Get the active git configuration in the current folder."""
    return {
        "name": run_git(["config", "user.name"]),
        "email": run_git(["config", "user.email"]),
        "signingkey": run_git(["config", "user.signingkey"]),
        "ssh_cmd": run_git(["config", "core.sshCommand"])
    }


def add_profile(name: str, user_name: str, email: str, ssh_key: str = None, gpg_key: str = None):
    profiles = load_profiles()
    profiles[name] = {
        "user_name": user_name,
        "email": email,
        "ssh_key": ssh_key or "",
        "gpg_key": gpg_key or ""
    }
    save_profiles(profiles)
    print(f"{COLOR_GREEN}Success: Saved profile '{name}'!{COLOR_RESET}")


def list_profiles():
    profiles = load_profiles()
    current = get_current_git_identity()

    print(f"\n{COLOR_BOLD}Active Git Identity in current directory:{COLOR_RESET}")
    print(f"  Name:       {current['name'] or '(not set)'}")
    print(f"  Email:      {current['email'] or '(not set)'}")
    if current['signingkey']:
        print(f"  GPG Key:    {current['signingkey']}")
    if current['ssh_cmd']:
        print(f"  SSH Cmd:    {current['ssh_cmd']}")
    print()

    if not profiles:
        print(f"No profiles saved yet. Create one using: {sys.argv[0]} add <profile_name>")
        return

    print(f"{COLOR_BOLD}Saved Profiles:{COLOR_RESET}")
    for name, details in profiles.items():
        is_active = (details["user_name"] == current["name"] and details["email"] == current["email"])
        active_marker = f"{COLOR_GREEN}* (Active){COLOR_RESET}" if is_active else ""
        print(f"- {COLOR_CYAN}{name}{COLOR_RESET} {active_marker}")
        print(f"  Name:    {details['user_name']}")
        print(f"  Email:   {details['email']}")
        if details.get("ssh_key"):
            print(f"  SSH Key: {details['ssh_key']}")
        if details.get("gpg_key"):
            print(f"  GPG Key: {details['gpg_key']}")
        print()


def apply_profile(name: str, make_global: bool = False):
    profiles = load_profiles()
    if name not in profiles:
        print(f"{COLOR_RED}Error: Profile '{name}' not found.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    profile = profiles[name]
    scope = "--global" if make_global else "--local"

    # Verify if we are inside a repository when applying locally
    if not make_global and not run_git(["rev-parse", "--is-inside-work-tree"]):
        print(f"{COLOR_RED}Error: Not inside a Git repository. Use --global to apply globally.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Set basic info
    run_git(["config", scope, "user.name", profile["user_name"]])
    run_git(["config", scope, "user.email", profile["email"]])

    # GPG signing key
    if profile.get("gpg_key"):
        run_git(["config", scope, "user.signingkey", profile["gpg_key"]])
        run_git(["config", scope, "commit.gpgsign", "true"])
    else:
        # Unset signingkey if it was set
        try:
            subprocess.run(["git", "config", scope, "--unset", "user.signingkey"], stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", scope, "--unset", "commit.gpgsign"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # SSH command
    if profile.get("ssh_key"):
        ssh_key_path = Path(profile["ssh_key"]).expanduser().resolve()
        ssh_cmd = f"ssh -i {ssh_key_path} -o IdentitiesOnly=yes"
        run_git(["config", scope, "core.sshCommand", ssh_cmd])
    else:
        try:
            subprocess.run(["git", "config", scope, "--unset", "core.sshCommand"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    dest = "globally" if make_global else "locally to current repository"
    print(f"{COLOR_GREEN}Success: Applied profile '{name}' {dest}!{COLOR_RESET}")


def setup_auto_profile(name: str, path: str):
    """Set up conditional inclusion for directory-based switching."""
    profiles = load_profiles()
    if name not in profiles:
        print(f"{COLOR_RED}Error: Profile '{name}' not found.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    profile = profiles[name]
    folder_path = Path(path).expanduser().resolve()
    
    if not folder_path.exists():
        print(f"{COLOR_YELLOW}Warning: Directory '{folder_path}' does not exist yet.{COLOR_RESET}")

    # Ensure git config dir exists
    config_dir = Path.home() / ".git_profile_configs"
    config_dir.mkdir(exist_ok=True)
    
    # Create profile gitconfig file
    profile_config_path = config_dir / f"{name}.gitconfig"
    with open(profile_config_path, "w", encoding="utf-8") as f:
        f.write("[user]\n")
        f.write(f"\tname = {profile['user_name']}\n")
        f.write(f"\temail = {profile['email']}\n")
        if profile.get("gpg_key"):
            f.write(f"\tsigningkey = {profile['gpg_key']}\n")
            f.write("[commit]\n\tgpgsign = true\n")
        if profile.get("ssh_key"):
            ssh_key_path = Path(profile["ssh_key"]).expanduser().resolve()
            f.write("[core]\n")
            f.write(f"\tsshCommand = ssh -i {ssh_key_path} -o IdentitiesOnly=yes\n")

    # Add includeIf to global .gitconfig
    # Format of includeIf requires trailing slash for directories
    path_str = str(folder_path).replace("\\", "/")
    if not path_str.endswith("/"):
        path_str += "/"
        
    config_ref_path = str(profile_config_path).replace("\\", "/")

    # Check if includeIf is already configured
    # We can add it via git command: git config --global includeIf.gitdir:<path>.path <config_path>
    include_key = f"includeIf.gitdir:{path_str}.path"
    run_git(["config", "--global", include_key, config_ref_path])

    print(f"{COLOR_GREEN}Success: Automatically loading profile '{name}' for repositories under '{path_str}'{COLOR_RESET}")
    print(f"Verified via global git config include link: {include_key} -> {config_ref_path}")


def remove_profile(name: str):
    profiles = load_profiles()
    if name not in profiles:
        print(f"{COLOR_RED}Error: Profile '{name}' not found.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
    
    del profiles[name]
    save_profiles(profiles)
    print(f"{COLOR_GREEN}Success: Removed profile '{name}'.{COLOR_RESET}")


def main():
    parser = argparse.ArgumentParser(description="Git Profile Manager - Switch between multiple Git identities.")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Add Command
    add_parser = subparsers.add_parser("add", help="Add a new Git profile")
    add_parser.add_argument("name", help="Name of the profile (e.g. 'work', 'personal')")
    add_parser.add_argument("--user-name", required=True, help="Git user.name value")
    add_parser.add_argument("--email", required=True, help="Git user.email value")
    add_parser.add_argument("--ssh-key", help="Path to SSH private key for this profile")
    add_parser.add_argument("--gpg-key", help="GPG Signing Key ID (enables auto-commit-signing)")

    # Apply Command
    apply_parser = subparsers.add_parser("apply", help="Apply a Git profile")
    apply_parser.add_argument("name", help="Name of the profile to apply")
    apply_parser.add_argument("--global", action="store_true", dest="make_global", help="Apply profile globally (instead of locally)")

    # Auto Command
    auto_parser = subparsers.add_parser("auto", help="Set up automatic profile loading for a folder path")
    auto_parser.add_argument("name", help="Name of the profile")
    auto_parser.add_argument("path", help="Folder path (e.g. '~/work' or 'C:/Projects/Work')")

    # List Command
    subparsers.add_parser("list", help="List all saved profiles")

    # Remove Command
    remove_parser = subparsers.add_parser("remove", help="Remove a profile")
    remove_parser.add_argument("name", help="Name of the profile to delete")

    # Show Command
    subparsers.add_parser("show", help="Show active identity in current folder")

    args = parser.parse_args()

    if not args.command:
        list_profiles()
        sys.exit(0)

    if args.command == "add":
        add_profile(args.name, args.user_name, args.email, args.ssh_key, args.gpg_key)
    elif args.command == "apply":
        apply_profile(args.name, args.make_global)
    elif args.command == "auto":
        setup_auto_profile(args.name, args.path)
    elif args.command == "list":
        list_profiles()
    elif args.command == "remove":
        remove_profile(args.name)
    elif args.command == "show":
        current = get_current_git_identity()
        print(f"Current Name:  {current['name'] or '(not set)'}")
        print(f"Current Email: {current['email'] or '(not set)'}")


if __name__ == "__main__":
    main()
