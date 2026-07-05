#!/usr/bin/env python3
"""
Conventional Commits Template Generator & Validator
-----------------------------------------------------
Interactive CLI tool for constructing standard Conventional Commit messages, validating commit message drafts
against standard rules (type, scope, 50-char subject limit, imperativeness, breaking change footers), and
installing global or local .gitmessage templates.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import argparse
import subprocess
from typing import Dict, Any, List, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

CONVENTIONAL_TYPES = {
    "feat": "A new feature for the user or codebase",
    "fix": "A bug fix",
    "docs": "Documentation changes only",
    "style": "Code style/formatting (white-space, formatting, missing semi-colons, etc)",
    "refactor": "Code restructuring without changing behavior or adding features",
    "perf": "Performance improvement code changes",
    "test": "Adding missing tests or correcting existing tests",
    "build": "Build system or external dependencies changes (example scopes: npm, maven)",
    "ci": "CI configuration files and scripts changes (example scopes: GitHub Actions, Travis)",
    "chore": "Other changes that don't modify src or test files",
    "revert": "Reverts a previous commit",
}

COMMIT_REGEX = re.compile(
    r'^(?P<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(?:\((?P<scope>[a-zA-Z0-9_\-\.\/]+)\))?(?P<breaking>!)?: (?P<subject>.+)$'
)


class CommitValidator:
    def __init__(self, commit_msg: str):
        self.raw_msg = commit_msg.strip()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.valid = True

    def validate(self) -> Dict[str, Any]:
        lines = self.raw_msg.splitlines()
        if not lines or not lines[0].strip():
            self.errors.append("Commit message is empty")
            self.valid = False
            return self._result()

        header = lines[0].strip()
        match = COMMIT_REGEX.match(header)

        if not match:
            self.errors.append("Header does not follow Conventional Commits format: '<type>(<scope>): <subject>'")
            self.valid = False
        else:
            commit_type = match.group('type')
            scope = match.group('scope')
            subject = match.group('subject')
            breaking = match.group('breaking')

            if len(header) > 72:
                self.errors.append(f"Header line length exceeds 72 characters ({len(header)} chars).")
                self.valid = False
            elif len(header) > 50:
                self.warnings.append(f"Header length is {len(header)} chars. Keeping headers under 50 chars is recommended.")

            if subject and subject[0].isupper():
                self.warnings.append("Subject line should start with a lowercase letter.")

            if subject and subject.endswith('.'):
                self.warnings.append("Subject line should not end with a period.")

            # Imperative mood check (common non-imperative words)
            first_word = subject.split()[0].lower() if subject else ""
            if first_word.endswith("ed") or first_word.endswith("ing") or first_word.endswith("s"):
                self.warnings.append(f"Use imperative mood for first word ('{first_word}' -> suggest command form like 'add', 'fix', 'update').")

            self.info.append(f"Type: {commit_type}" + (f", Scope: {scope}" if scope else "") + (" [BREAKING CHANGE]" if breaking else ""))

        # Check body and line lengths
        if len(lines) > 1 and lines[1].strip() != "":
            self.warnings.append("Second line of commit message must be empty to separate header from body.")

        for i, line in enumerate(lines[2:], start=3):
            if len(line) > 100:
                self.warnings.append(f"Line {i} in body exceeds recommended 100 character width ({len(line)} chars).")

        return self._result()

    def _result(self) -> Dict[str, Any]:
        return {
            "message": self.raw_msg,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def generate_commit_template_file(output_path: str) -> str:
    """Generate a standard .gitmessage template file content."""
    template = """# <type>(<scope>): <subject>
# |--- type: feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert
# |--- scope: module, file, or feature name (optional)
# |--- subject: concise, imperative-mood description (<= 50 chars, no trailing period)
#
# Explain the motivation behind this change and how it differs from previous behavior.
# 
# BREAKING CHANGE: <description of breaking changes if any>
# Fixes #<issue number>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template)
    return output_path


def install_git_template(template_path: str, global_config: bool = False) -> bool:
    """Configure git commit.template setting using subprocess."""
    cmd = ["git", "config"]
    if global_config:
        cmd.append("--global")
    cmd.extend(["commit.template", os.path.abspath(template_path)])

    try:
        subprocess.run(cmd, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def build_commit_message(
    commit_type: str,
    scope: str = "",
    subject: str = "",
    body: str = "",
    breaking: str = "",
    issue: str = ""
) -> str:
    """Construct formatted Conventional Commit message string."""
    scope_str = f"({scope})" if scope else ""
    breaking_str = "!" if breaking else ""
    header = f"{commit_type}{scope_str}{breaking_str}: {subject}"

    lines = [header]
    if body:
        lines.append("")
        lines.append(body)

    footers = []
    if breaking:
        footers.append(f"BREAKING CHANGE: {breaking}")
    if issue:
        footers.append(f"Fixes #{issue}" if not issue.startswith("#") else f"Fixes {issue}")

    if footers:
        lines.append("")
        lines.extend(footers)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Conventional Commits Template Generator & Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python tools/git_commit_template_generator.py --validate "feat(api): add JWT token refresh endpoint"
  python tools/git_commit_template_generator.py --type feat --scope auth --subject "add oauth2 login"
  python tools/git_commit_template_generator.py --install-template
"""
    )

    parser.add_argument("--validate", help="Commit message string or file to validate")
    parser.add_argument("--type", choices=list(CONVENTIONAL_TYPES.keys()), help="Commit type")
    parser.add_argument("--scope", default="", help="Commit scope (e.g. auth, db, ui)")
    parser.add_argument("--subject", default="", help="Short imperative commit subject")
    parser.add_argument("--body", default="", help="Longer commit body explanation")
    parser.add_argument("--breaking", default="", help="Breaking change description")
    parser.add_argument("--issue", default="", help="Issue reference number (e.g. 123)")
    parser.add_argument("--install-template", action="store_true", help="Generate and set up .gitmessage template in git config")
    parser.add_argument("--global", dest="global_config", action="store_true", help="Use git config --global for template installation")

    args = parser.parse_args()

    if args.install_template:
        target_file = ".gitmessage"
        generate_commit_template_file(target_file)
        success = install_git_template(target_file, global_config=args.global_config)
        if success:
            scope_desc = "global" if args.global_config else "local repository"
            print(f"{GREEN}✓ Successfully generated '{target_file}' and installed into {scope_desc} git config.{RESET}")
        else:
            print(f"{YELLOW}⚠ Generated '{target_file}', but failed to run 'git config commit.template'.{RESET}")
        return

    if args.validate:
        msg = args.validate
        if os.path.exists(msg):
            with open(msg, 'r', encoding='utf-8') as f:
                msg = f.read()

        validator = CommitValidator(msg)
        res = validator.validate()

        print(f"\n{BOLD}{CYAN}=== Commit Message Audit ==={RESET}")
        print(f"Header: {BOLD}{res['message'].splitlines()[0]}{RESET}")

        if res['valid']:
            print(f"Status: {GREEN}✓ VALID Conventional Commit{RESET}")
        else:
            print(f"Status: {RED}✗ INVALID Conventional Commit{RESET}")

        for err in res['errors']:
            print(f"  {RED}✘ Error:{RESET} {err}")

        for warn in res['warnings']:
            print(f"  {YELLOW}⚠ Warning:{RESET} {warn}")

        for info in res['info']:
            print(f"  {BLUE}ℹ Info:{RESET} {info}")
        print()
        return

    if args.type and args.subject:
        msg = build_commit_message(
            commit_type=args.type,
            scope=args.scope,
            subject=args.subject,
            body=args.body,
            breaking=args.breaking,
            issue=args.issue
        )
        print(f"\n{BOLD}{CYAN}=== Formatted Commit Message ==={RESET}\n")
        print(f"{GREEN}{msg}{RESET}\n")

        # Self validate
        res = CommitValidator(msg).validate()
        if res['warnings']:
            print(f"{YELLOW}Notices:{RESET}")
            for w in res['warnings']:
                print(f"  - {w}")
        return

    # Demo output
    print(f"\n{BOLD}{CYAN}=== Conventional Commits Types & Usage ==={RESET}\n")
    for k, v in CONVENTIONAL_TYPES.items():
        print(f"  {BOLD}{k:<10}{RESET} : {v}")

    demo_msg = build_commit_message(
        commit_type="feat",
        scope="auth",
        subject="add multi-factor authentication support",
        body="Implement TOTP-based 2FA challenge during login flow for enhanced security.",
        issue="42"
    )
    print(f"\n{BOLD}Sample Commit Output:{RESET}\n{GREEN}{demo_msg}{RESET}\n")


if __name__ == "__main__":
    main()
