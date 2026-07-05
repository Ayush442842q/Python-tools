#!/usr/bin/env python3
"""
Git Commit Co-Author Manager
----------------------------
CLI utility to manage, store, search, and format Git co-author commit message trailers.
Allows easy addition of 'Co-authored-by: Name <email>' trailers to commit messages,
managing team member alias files, and integrating with Git hooks (prepare-commit-msg).

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_CONFIG_PATH = Path.home() / ".git_coauthors.json"


def validate_email(email: str) -> bool:
    """Validates basic email address structure."""
    pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    return bool(re.match(pattern, email.strip()))


def format_coauthor_trailer(name: str, email: str) -> str:
    """Formats a single Git co-author trailer string."""
    return f"Co-authored-by: {name.strip()} <{email.strip()}>"


class CoAuthorManager:
    """Manages team co-author aliases and configuration storage."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.authors: Dict[str, Dict[str, str]] = {}
        self.load_config()

    def load_config(self):
        """Loads co-author configuration from JSON file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.authors = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config file '{self.config_path}': {e}", file=sys.stderr)
                self.authors = {}

    def save_config(self):
        """Saves current co-author dictionary to JSON file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.authors, f, indent=2)
        except Exception as e:
            print(f"Error saving config file '{self.config_path}': {e}", file=sys.stderr)

    def add_author(self, alias: str, name: str, email: str) -> bool:
        """Adds or updates a co-author alias."""
        alias_key = alias.lower().strip()
        if not validate_email(email):
            print(f"Error: Invalid email format '{email}'.", file=sys.stderr)
            return False
        self.authors[alias_key] = {"name": name.strip(), "email": email.strip()}
        self.save_config()
        return True

    def remove_author(self, alias: str) -> bool:
        """Removes a co-author alias."""
        alias_key = alias.lower().strip()
        if alias_key in self.authors:
            del self.authors[alias_key]
            self.save_config()
            return True
        return False

    def get_trailers(self, aliases: List[str]) -> List[str]:
        """Returns list of Co-authored-by trailer lines for given aliases."""
        trailers = []
        for alias in aliases:
            key = alias.lower().strip()
            if key in self.authors:
                entry = self.authors[key]
                trailers.append(format_coauthor_trailer(entry["name"], entry["email"]))
            else:
                # Handle raw "Name <email>" if provided
                match = re.match(r'^(.*?)\s*<([^>]+)>$', alias)
                if match:
                    trailers.append(format_coauthor_trailer(match.group(1), match.group(2)))
                else:
                    print(f"Warning: Alias or author pattern '{alias}' not found in team config.", file=sys.stderr)
        return trailers


def append_trailers_to_commit_file(file_path: str, trailers: List[str]):
    """Appends co-author trailer lines to an existing commit message file."""
    if not trailers:
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        trailer_block = "\n" + "\n".join(trailers) + "\n"
        if not content.endswith("\n"):
            content += "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content + trailer_block)
        print(f"Appended {len(trailers)} co-author trailer(s) to '{file_path}'.")
    except Exception as e:
        print(f"Error updating commit message file '{file_path}': {e}", file=sys.stderr)


def run_demo():
    """Run interactive demonstration with sample co-authors."""
    demo_authors = {
        "alice": {"name": "Alice Smith", "email": "alice@company.com"},
        "bob": {"name": "Bob Jones", "email": "bob@company.com"},
        "carol": {"name": "Carol Danvers", "email": "carol@hero.org"},
    }

    print(f"{BOLD}{CYAN}=== Git Commit Co-Author Manager Demo ==={RESET}\n")
    print(f"{BOLD}Registered Team Co-Authors:{RESET}")
    for alias, info in demo_authors.items():
        print(f"  • {BOLD}{alias}{RESET}: {info['name']} <{info['email']}>")

    selected_aliases = ["alice", "bob"]
    manager = CoAuthorManager(config_path=Path("temp_demo_coauthors.json"))
    manager.authors = demo_authors

    trailers = manager.get_trailers(selected_aliases)

    print(f"\n{BOLD}{YELLOW}--- Generated Git Co-Author Trailers for [{', '.join(selected_aliases)}] ---{RESET}\n")
    for tr in trailers:
        print(f"{GREEN}{tr}{RESET}")

    sample_commit_msg = "feat(auth): implement OAuth2 PKCE authorization flow"
    print(f"\n{BOLD}{YELLOW}--- Final Commit Message Preview ---{RESET}\n")
    print(sample_commit_msg + "\n\n" + "\n".join(trailers))


def main():
    parser = argparse.ArgumentParser(
        description="Manage Git co-authors and append 'Co-authored-by' trailers to commit messages."
    )
    parser.add_argument(
        "aliases", nargs="*", help="Co-author aliases or raw 'Name <email>' strings to include"
    )
    parser.add_argument(
        "-a", "--add", nargs=3, metavar=("ALIAS", "NAME", "EMAIL"), help="Add a new team co-author alias"
    )
    parser.add_argument("-r", "--remove", metavar="ALIAS", help="Remove a team co-author alias")
    parser.add_argument("-l", "--list", action="store_true", help="List all registered team co-author aliases")
    parser.add_argument(
        "-c", "--commit-file", help="Path to Git commit message file to append trailers to (for prepare-commit-msg hook)"
    )
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    args = parser.parse_args()

    if args.demo or (not args.aliases and not args.add and not args.remove and not args.list and not args.commit_file and sys.stdin.isatty()):
        run_demo()
        return

    manager = CoAuthorManager()

    if args.add:
        alias, name, email = args.add
        if manager.add_author(alias, name, email):
            print(f"Successfully registered alias '{alias}' -> {name} <{email}>.")
        return

    if args.remove:
        if manager.remove_author(args.remove):
            print(f"Successfully removed alias '{args.remove}'.")
        else:
            print(f"Alias '{args.remove}' not found.", file=sys.stderr)
        return

    if args.list:
        if not manager.authors:
            print("No co-author aliases registered yet. Use --add ALIAS NAME EMAIL to register team members.")
        else:
            print(f"{BOLD}Registered Co-Author Aliases ({len(manager.authors)}):{RESET}")
            for alias, info in manager.authors.items():
                print(f"  • {BOLD}{alias}{RESET}: {info['name']} <{info['email']}>")
        return

    if args.aliases:
        trailers = manager.get_trailers(args.aliases)
        if args.commit_file:
            append_trailers_to_commit_file(args.commit_file, trailers)
        else:
            for tr in trailers:
                print(tr)


if __name__ == "__main__":
    main()
