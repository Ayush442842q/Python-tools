#!/usr/bin/env python3
"""
Gitignore Rule Tester
---------------------
Tests file paths against .gitignore rules recursively, explaining which exact .gitignore file
and line pattern caused a file to be ignored or included (handling pattern negation '!').

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import fnmatch
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


class GitIgnorePattern:
    def __init__(self, pattern: str, source_file: str, line_number: int, base_dir: Path):
        self.raw_pattern = pattern
        self.source_file = source_file
        self.line_number = line_number
        self.base_dir = base_dir

        pattern_str = pattern.strip()
        self.is_negated = pattern_str.startswith("!")
        if self.is_negated:
            pattern_str = pattern_str[1:]

        self.directory_only = pattern_str.endswith("/")
        if self.directory_only:
            pattern_str = pattern_str[:-1]

        self.anchored = "/" in pattern_str[:-1] if pattern_str.startswith("/") else "/" in pattern_str
        if pattern_str.startswith("/"):
            pattern_str = pattern_str[1:]

        self.clean_pattern = pattern_str
        self.regex = self._pattern_to_regex(pattern_str)

    def _pattern_to_regex(self, pattern: str) -> re.Pattern:
        # Convert gitignore glob pattern to regex
        i, n = 0, len(pattern)
        res = []
        while i < n:
            c = pattern[i]
            i += 1
            if c == "*":
                if i < n and pattern[i] == "*":
                    i += 1
                    if i < n and pattern[i] == "/":
                        i += 1
                        res.append("(?:.*/)?")
                    else:
                        res.append(".*")
                else:
                    res.append("[^/]*")
            elif c == "?":
                res.append("[^/]")
            elif c in ".^$()+{}[]|\\":
                res.append("\\" + c)
            else:
                res.append(c)
        
        regex_str = "".join(res)
        if self.anchored:
            regex_str = "^" + regex_str + "(?:/.*)?$"
        else:
            regex_str = "(?:^|/)" + regex_str + "(?:/.*)?$"
        
        return re.compile(regex_str)

    def match(self, rel_path: str, is_dir: bool = False) -> bool:
        rel_path = rel_path.replace("\\", "/")
        if self.directory_only and not is_dir:
            return False
        return bool(self.regex.search(rel_path))


def load_gitignore_files(root_dir: Path) -> List[GitIgnorePattern]:
    patterns = []
    # Always include standard .git folder pattern
    patterns.append(GitIgnorePattern(".git", ".git/internal", 0, root_dir))

    for gitignore_path in root_dir.rglob(".gitignore"):
        try:
            rel_dir = gitignore_path.parent
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        patterns.append(GitIgnorePattern(line_str, str(gitignore_path), line_num, rel_dir))
        except Exception:
            pass

    return patterns


def check_path_against_rules(target_path: str, root_dir: Path, patterns: List[GitIgnorePattern]) -> Dict:
    abs_target = Path(target_path).resolve()
    try:
        rel_path = abs_target.relative_to(root_dir.resolve()).as_posix()
    except ValueError:
        rel_path = abs_target.as_posix()

    is_dir = abs_target.is_dir()

    matching_rule = None
    is_ignored = False

    for pat in patterns:
        if pat.match(rel_path, is_dir=is_dir):
            matching_rule = pat
            is_ignored = not pat.is_negated

    result = {
        "target_path": rel_path,
        "is_ignored": is_ignored,
        "matching_pattern": matching_rule.raw_pattern if matching_rule else None,
        "source_file": matching_rule.source_file if matching_rule else None,
        "line_number": matching_rule.line_number if matching_rule else None,
    }
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Check if paths match .gitignore rules and explain why."
    )
    parser.add_argument("paths", nargs="*", help="File or directory paths to test against .gitignore")
    parser.add_argument("-d", "--root-dir", default=".", help="Root project directory containing .gitignore (default: .)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    root_dir = Path(args.root_dir).resolve()
    patterns = load_gitignore_files(root_dir)

    if not args.paths:
        print(f"{BLUE}{BOLD}Gitignore Rule Tester - Demo Mode{RESET}\n")
        print(f"Loaded {len(patterns)} pattern rules from project root: {root_dir}")
        test_files = [".git/config", "build/output.log", "temp.tmp", "src/main.py", "node_modules/package.json"]
        for tf in test_files:
            res = check_path_against_rules(tf, root_dir, patterns)
            if res["is_ignored"]:
                print(f"  {RED}IGNORED{RESET}: {BOLD}{tf:<25}{RESET} -> Rule: '{res['matching_pattern']}' ({res['source_file']}:{res['line_number']})")
            else:
                print(f"  {GREEN}TRACKED{RESET}: {BOLD}{tf:<25}{RESET} -> No matching ignore pattern")
        return

    results = []
    for path_str in args.paths:
        res = check_path_against_rules(path_str, root_dir, patterns)
        results.append(res)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for res in results:
            if res["is_ignored"]:
                print(f"{RED}{BOLD}[IGNORED]{RESET} {res['target_path']}")
                print(f"  Matched Rule : '{res['matching_pattern']}'")
                print(f"  File Location: {res['source_file']}:{res['line_number']}\n")
            else:
                print(f"{GREEN}{BOLD}[NOT IGNORED]{RESET} {res['target_path']}")
                print(f"  Status: File is tracked by Git (no active ignore rule matched)\n")


if __name__ == "__main__":
    main()
