#!/usr/bin/env python3
"""
Git Commit Message Linter
Lints git commit messages for compliance with the Conventional Commits specification.
Can be integrated as a git commit-msg hook.
"""

import argparse
import os
import re
import sys

# Allowed types according to Conventional Commits specification
CONVENTIONAL_TYPES = [
    "feat",      # A new feature
    "fix",       # A bug fix
    "docs",      # Documentation only changes
    "style",     # Changes that do not affect the meaning of the code (white-space, formatting, etc)
    "refactor",  # A code change that neither fixes a bug nor adds a feature
    "perf",      # A code change that improves performance
    "test",      # Adding missing tests or correcting existing tests
    "build",     # Changes that affect the build system or external dependencies
    "ci",        # Changes to our CI configuration files and scripts
    "chore",     # Other changes that don't modify src or test files
    "revert",    # Reverts a previous commit
]

# Regex pattern for conventional commit header
# Format: type(scope)!: description  (! is optional for breaking changes, scope is optional)
COMMIT_HEADER_PATTERN = re.compile(
    r'^(?P<type>[a-zA-Z0-9\-_]+)(?:\((?P<scope>[a-zA-Z0-9\-_]+)\))?(?P<breaking>!)?:\s+(?P<desc>.+)$'
)


def lint_commit_message(message_text, max_header_len=72):
    """
    Lint a commit message.
    Returns: (is_valid, list_of_errors)
    """
    lines = message_text.strip().splitlines()
    if not lines or not message_text.strip():
        return False, ["Commit message is empty."]

    errors = []
    header = lines[0].strip()

    # Rule 1: Header length limit
    if len(header) > max_header_len:
        errors.append(f"Header line exceeds maximum length of {max_header_len} chars (currently {len(header)} chars).")

    # Rule 2: Conventional Commits pattern matching
    match = COMMIT_HEADER_PATTERN.match(header)
    if not match:
        errors.append(
            "Header does not match Conventional Commits format: '<type>(scope): description' or '<type>: description'."
        )
    else:
        parts = match.groupdict()
        msg_type = parts["type"]
        msg_desc = parts["desc"]

        # Rule 3: Valid commit type
        if msg_type not in CONVENTIONAL_TYPES:
            errors.append(
                f"Type '{msg_type}' is not allowed. Must be one of: {', '.join(CONVENTIONAL_TYPES)}."
            )

        # Rule 4: Description capitalization (convention suggests lowercase start)
        if msg_desc and msg_desc[0].isupper():
            errors.append("Commit description should not start with a capital letter.")

        # Rule 5: No trailing period in header description
        if msg_desc and msg_desc.endswith('.'):
            errors.append("Commit description header should not end with a period.")

    # Rule 6: Body separation (must have empty line between header and body if body exists)
    if len(lines) > 1:
        if lines[1].strip() != "":
            errors.append("An empty line is required between the commit header and the body.")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(
        description="Lint git commit messages for Conventional Commits compliance."
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-m", "--message", help="Commit message string to lint")
    group.add_argument("-f", "--file", help="Path to a file containing the commit message (e.g. .git/COMMIT_EDITMSG)")
    group.add_argument("-i", "--interactive", action="store_true", help="Run in interactive mode to test a message")
    
    parser.add_argument("--max-length", type=int, default=72, help="Max length of header line (default: 72)")
    
    args = parser.parse_args()

    message_content = ""

    if args.message:
        message_content = args.message
    elif args.file:
        if not os.path.exists(args.file):
            print(f"Error: Commit message file '{args.file}' does not exist.", file=sys.stderr)
            return 2
        try:
            with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
                message_content = f.read()
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            return 2
    elif args.interactive:
        print("Enter your commit message below. Press Ctrl+D (Unix) or Ctrl+Z (Windows) then Enter to finish:")
        try:
            message_content = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nAborted.")
            return 1

    print("\n--- Linting Commit Message ---")
    print(message_content.strip())
    print("------------------------------")

    is_valid, errors = lint_commit_message(message_content, max_header_len=args.max_length)

    if is_valid:
        print("\n[SUCCESS] Commit message is conventional!")
        return 0
    else:
        print(f"\n[FAILED] Commit message is not conventional. Found {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
