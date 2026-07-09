#!/usr/bin/env python3
"""
Changelog Linter - Validates CHANGELOG.md files against the "Keep a Changelog" standard.
"""

import argparse
import os
import re
import sys
from typing import List, Tuple, Set

# Keep a Changelog standard sections
ALLOWED_SECTIONS = {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}

# Regex patterns
H1_PATTERN = re.compile(r"^#\s+(.+)$")
# Matches: ## [1.0.0] - 2023-10-27 or ## [Unreleased]
VERSION_PATTERN = re.compile(r"^##\s+\[([^\]]+)\](?:\s+-\s+(\d{4}-\d{2}-\d{2}))?\s*$")
SECTION_PATTERN = re.compile(r"^###\s+(.+)$")
LINK_DEF_PATTERN = re.compile(r"^\[([^\]]+)\]:\s+(https?://.+)$")

class ChangelogLinter:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.errors: List[Tuple[int, str]] = []
        self.warnings: List[Tuple[int, str]] = []

    def log_error(self, line_num: int, message: str):
        self.errors.append((line_num, message))

    def log_warning(self, line_num: int, message: str):
        self.warnings.append((line_num, message))

    def lint(self) -> bool:
        if not os.path.exists(self.filepath):
            self.log_error(0, f"File '{self.filepath}' does not exist.")
            return False

        with open(self.filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        has_h1 = False
        in_version = False
        current_version = ""
        current_section = ""
        version_headers: List[str] = []
        defined_links: Set[str] = set()

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()

            # 1. Check H1 header (Changelog Title)
            if line.startswith("# "):
                if has_h1:
                    self.log_error(idx, "Multiple H1 headers found. Only one '# Changelog' is allowed.")
                else:
                    has_h1 = True
                    h1_match = H1_PATTERN.match(stripped)
                    if h1_match and "changelog" not in h1_match.group(1).lower():
                        self.log_warning(idx, f"H1 header content is '{h1_match.group(1)}'. Recommended to contain 'Changelog'.")

            # 2. Check Version headers
            elif line.startswith("## "):
                in_version = True
                current_section = ""
                version_match = VERSION_PATTERN.match(stripped)
                if not version_match:
                    self.log_error(idx, "Invalid version header format. Expected '## [Version]' or '## [Version] - YYYY-MM-DD'.")
                    current_version = "INVALID"
                else:
                    version_str, date_str = version_match.groups()
                    current_version = version_str
                    version_headers.append(version_str)

                    # Validate version format (Unreleased or SemVer-like)
                    if version_str.lower() != "unreleased":
                        semver_pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?$"
                        if not re.match(semver_pattern, version_str):
                            self.log_warning(idx, f"Version '{version_str}' does not strictly follow Semantic Versioning (SemVer).")

                    # Validate date
                    if version_str.lower() == "unreleased" and date_str:
                        self.log_error(idx, "Unreleased version header should not contain a release date.")
                    elif version_str.lower() != "unreleased" and not date_str:
                        self.log_error(idx, f"Release version '{version_str}' is missing a date. Expected 'YYYY-MM-DD'.")

            # 3. Check Section headers
            elif line.startswith("### "):
                if not in_version:
                    self.log_error(idx, "Section header found before any version header.")
                    continue

                section_match = SECTION_PATTERN.match(stripped)
                if not section_match:
                    self.log_error(idx, "Invalid section header format.")
                else:
                    section_name = section_match.group(1)
                    current_section = section_name
                    if section_name not in ALLOWED_SECTIONS:
                        self.log_error(idx, f"Invalid section name '{section_name}'. Allowed: {', '.join(ALLOWED_SECTIONS)}.")

            # 4. Check link definitions at the bottom
            elif line.startswith("[") and "]:" in stripped:
                link_match = LINK_DEF_PATTERN.match(stripped)
                if link_match:
                    ref_name, ref_url = link_match.groups()
                    defined_links.add(ref_name)

        # 5. Check if Unreleased or versions have matching link definitions
        for v in version_headers:
            if v not in defined_links:
                self.log_warning(0, f"Missing reference link definition at bottom of file for version [{v}].")

        return len(self.errors) == 0

def main():
    parser = argparse.ArgumentParser(description="Lint a CHANGELOG.md file against 'Keep a Changelog' standard.")
    parser.add_argument("file", nargs="?", default="CHANGELOG.md", help="Path to the changelog file (default: CHANGELOG.md)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    args = parser.parse_args()

    linter = ChangelogLinter(args.file)
    success = linter.lint()

    print(f"\nLinting '{args.file}'...")
    print("-" * 50)

    # Print errors
    if linter.errors:
        print(f"\nErrors found ({len(linter.errors)}):")
        for line, msg in sorted(linter.errors):
            loc = f"Line {line}: " if line > 0 else ""
            print(f"  [ERROR] {loc}{msg}")

    # Print warnings
    if linter.warnings:
        print(f"\nWarnings found ({len(linter.warnings)}):")
        for line, msg in sorted(linter.warnings):
            loc = f"Line {line}: " if line > 0 else ""
            print(f"  [WARN]  {loc}{msg}")

    print("\nSummary:")
    print(f"  Errors: {len(linter.errors)}")
    print(f"  Warnings: {len(linter.warnings)}")

    if linter.errors or (args.strict and linter.warnings):
        print("\nResult: FAILED")
        sys.exit(1)
    else:
        print("\nResult: PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
