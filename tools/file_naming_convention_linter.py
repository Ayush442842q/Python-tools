#!/usr/bin/env python3
"""File Naming Convention Linter

Audits file and directory names in a repository against customizable naming
conventions (e.g., kebab-case, snake_case, camelCase, PascalCase, lowercase, no spaces),
highlights violations, and offers automatic renaming capabilities.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

CONVENTIONS = {
    "kebab-case": r"^[a-z0-9]+(-[a-z0-9]+)*$",
    "snake_case": r"^[a-z0-9]+(_[a-z0-9]+)*$",
    "camelCase": r"^[a-z][a-zA-Z0-9]*$",
    "PascalCase": r"^[A-Z][a-zA-Z0-9]*$",
    "lowercase": r"^[a-z0-9_\-\.]+$",
    "no-spaces": r"^[^\s]+$",
}


def fix_name(stem: str, convention: str) -> str:
    """Attempt to transform a string stem into the target convention."""
    # Split by common boundaries
    tokens = re.split(r"[\s_\-\.]+", stem)
    tokens = [t for t in tokens if t]
    if not tokens:
        return stem

    if convention == "kebab-case":
        return "-".join(t.lower() for t in tokens)
    elif convention == "snake_case":
        return "_".join(t.lower() for t in tokens)
    elif convention == "camelCase":
        return tokens[0].lower() + "".join(t.capitalize() for t in tokens[1:])
    elif convention == "PascalCase":
        return "".join(t.capitalize() for t in tokens)
    elif convention == "lowercase":
        return stem.lower().replace(" ", "_")
    elif convention == "no-spaces":
        return stem.replace(" ", "_")
    return stem


class FileNamingLinter:
    def __init__(
        self,
        target_dir: Path,
        convention: str = "kebab-case",
        max_length: int = 255,
        ignore_dirs: Optional[List[str]] = None,
        file_exts: Optional[List[str]] = None,
    ):
        self.target_dir = target_dir
        self.convention = convention
        self.pattern = re.compile(CONVENTIONS.get(convention, CONVENTIONS["kebab-case"]))
        self.max_length = max_length
        self.ignore_dirs = set(ignore_dirs or [".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"])
        self.file_exts = set(ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in file_exts) if file_exts else None

    def check_stem(self, stem: str) -> List[str]:
        issues = []
        if len(stem) > self.max_length:
            issues.append(f"Exceeds max length ({len(stem)} > {self.max_length})")
        if " " in stem and self.convention != "no-spaces":
            issues.append("Contains whitespace")
        if not self.pattern.match(stem):
            issues.append(f"Does not match {self.convention} convention")
        return issues

    def scan(self) -> List[Dict]:
        results = []
        for root, dirs, files in os.walk(self.target_dir):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs and not d.startswith(".")]

            root_path = Path(root)

            # Check files
            for file_name in files:
                file_path = root_path / file_name
                stem = file_path.stem
                ext = file_path.suffix

                if self.file_exts and ext.lower() not in self.file_exts:
                    continue

                issues = self.check_stem(stem)
                if issues:
                    suggested_stem = fix_name(stem, self.convention)
                    suggested_name = f"{suggested_stem}{ext}"
                    results.append({
                        "path": file_path,
                        "type": "file",
                        "original": file_name,
                        "suggested": suggested_name,
                        "issues": issues,
                    })

            # Check directories
            for dir_name in dirs:
                dir_path = root_path / dir_name
                issues = self.check_stem(dir_name)
                if issues:
                    suggested_name = fix_name(dir_name, self.convention)
                    results.append({
                        "path": dir_path,
                        "type": "directory",
                        "original": dir_name,
                        "suggested": suggested_name,
                        "issues": issues,
                    })

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Audit file and directory names in a directory hierarchy against customizable naming rules."
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument(
        "--convention",
        choices=list(CONVENTIONS.keys()),
        default="kebab-case",
        help="Naming convention to enforce (default: kebab-case)",
    )
    parser.add_argument("--max-length", type=int, default=100, help="Maximum allowed stem length (default: 100)")
    parser.add_argument("--ext", nargs="+", help="Only scan files with these extensions (e.g. .py .js .md)")
    parser.add_argument("--fix", action="store_true", help="Automatically rename non-compliant files/directories")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be renamed without applying changes")

    args = parser.parse_args()
    target_dir = Path(args.path).resolve()

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"{COLOR_RED}Error: Directory '{target_dir}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_CYAN}File Naming Convention Linter{COLOR_RESET}")
    print(f"Target: {COLOR_BOLD}{target_dir}{COLOR_RESET}")
    print(f"Convention: {COLOR_YELLOW}{args.convention}{COLOR_RESET} | Max Length: {args.max_length}\n")

    linter = FileNamingLinter(
        target_dir=target_dir,
        convention=args.convention,
        max_length=args.max_length,
        file_exts=args.ext,
    )

    violations = linter.scan()

    if not violations:
        print(f"{COLOR_GREEN}✓ All scanned files and directories adhere to '{args.convention}'!{COLOR_RESET}")
        return

    print(f"{COLOR_YELLOW}Found {len(violations)} non-compliant item(s):{COLOR_RESET}\n")

    for v in violations:
        rel_path = v["path"].relative_to(target_dir)
        print(f"  [{v['type'].upper()}] {COLOR_BOLD}{rel_path}{COLOR_RESET}")
        for issue in v["issues"]:
            print(f"    - {COLOR_RED}{issue}{COLOR_RESET}")
        print(f"    Suggested Rename: {COLOR_GREEN}{v['suggested']}{COLOR_RESET}\n")

    if args.fix or args.dry_run:
        print(f"{COLOR_BOLD}Renaming Operations ({'DRY RUN' if args.dry_run else 'APPLYING CHANGES'}):{COLOR_RESET}")
        count = 0
        for v in violations:
            src = v["path"]
            dst = src.parent / v["suggested"]
            if src == dst:
                continue
            if args.dry_run:
                print(f"  [DRY-RUN] {src.name} -> {dst.name}")
            else:
                try:
                    src.rename(dst)
                    print(f"  {COLOR_GREEN}Renamed:{COLOR_RESET} {src.name} -> {dst.name}")
                    count += 1
                except Exception as e:
                    print(f"  {COLOR_RED}Failed to rename {src.name}: {e}{COLOR_RESET}")
        if not args.dry_run:
            print(f"\n{COLOR_GREEN}Successfully renamed {count} item(s).{COLOR_RESET}")


if __name__ == "__main__":
    main()
