#!/usr/bin/env python3
"""
SemVer Range Checker & Calculator
---------------------------------
Parses Semantic Versioning (SemVer 2.0.0) strings, bumps major/minor/patch/prerelease versions,
evaluates range expressions (^, ~, >=, <=, etc.), and sorts lists of versions.

Author: Antigravity
License: MIT
"""

import sys
import re
import json
import argparse
from typing import Optional, List, Tuple

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class SemVer:
    def __init__(self, version_str: str):
        self.raw = version_str.strip()
        match = SEMVER_REGEX.match(self.raw)
        if not match:
            raise ValueError(f"Invalid SemVer string: '{version_str}'")
        
        groups = match.groupdict()
        self.major = int(groups["major"])
        self.minor = int(groups["minor"])
        self.patch = int(groups["patch"])
        self.prerelease = groups["prerelease"]
        self.build = groups["buildmetadata"]

    def _prerelease_key(self):
        if not self.prerelease:
            return (1,)  # Non-prerelease is greater than prerelease
        parts = []
        for p in self.prerelease.split("."):
            if p.isdigit():
                parts.append((0, int(p)))
            else:
                parts.append((1, p))
        return (0, parts)

    def tuple_key(self):
        return (self.major, self.minor, self.patch, self._prerelease_key())

    def __eq__(self, other):
        if not isinstance(other, SemVer):
            return False
        return (self.major, self.minor, self.patch, self._prerelease_key()) == (other.major, other.minor, other.patch, other._prerelease_key())

    def __lt__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.tuple_key() < other.tuple_key()

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)

    def __str__(self):
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res += f"-{self.prerelease}"
        if self.build:
            res += f"+{self.build}"
        return res

    def bump(self, part: str, pre_label: str = "alpha") -> "SemVer":
        if part == "major":
            return SemVer(f"{self.major + 1}.0.0")
        elif part == "minor":
            return SemVer(f"{self.major}.{self.minor + 1}.0")
        elif part == "patch":
            return SemVer(f"{self.major}.{self.minor}.{self.patch + 1}")
        elif part == "prerelease":
            if not self.prerelease:
                return SemVer(f"{self.major}.{self.minor}.{self.patch + 1}-{pre_label}.1")
            match = re.search(r"(\d+)$", self.prerelease)
            if match:
                num = int(match.group(1)) + 1
                base = self.prerelease[:match.start(1)]
                return SemVer(f"{self.major}.{self.minor}.{self.patch}-{base}{num}")
            else:
                return SemVer(f"{self.major}.{self.minor}.{self.patch}-{self.prerelease}.1")
        else:
            raise ValueError(f"Unknown bump target: '{part}'. Choose major, minor, patch, or prerelease.")


def parse_range_clause(clause: str, version: SemVer) -> bool:
    clause = clause.strip()
    if not clause or clause == "*":
        return True

    # Caret range: ^1.2.3 -> >=1.2.3 <2.0.0 (or <1.3.0 if major is 0)
    if clause.startswith("^"):
        base_v = SemVer(clause[1:])
        if base_v.major > 0:
            upper = SemVer(f"{base_v.major + 1}.0.0")
        elif base_v.minor > 0:
            upper = SemVer(f"0.{base_v.minor + 1}.0")
        else:
            upper = SemVer(f"0.0.{base_v.patch + 1}")
        return version >= base_v and version < upper

    # Tilde range: ~1.2.3 -> >=1.2.3 <1.3.0
    if clause.startswith("~"):
        base_v = SemVer(clause[1:])
        upper = SemVer(f"{base_v.major}.{base_v.minor + 1}.0")
        return version >= base_v and version < upper

    # Standard comparison operators
    op_match = re.match(r"^(>=|<=|>|<|==|=|!=)?\s*(.+)$", clause)
    if not op_match:
        return False
    op, target_str = op_match.groups()
    op = op or "=="
    target_v = SemVer(target_str)

    if op in ("==", "="):
        return version == target_v
    elif op == "!=":
        return version != target_v
    elif op == ">":
        return version > target_v
    elif op == ">=":
        return version >= target_v
    elif op == "<":
        return version < target_v
    elif op == "<=":
        return version <= target_v
    return False


def satisfies_range(version_str: str, range_str: str) -> bool:
    version = SemVer(version_str)
    # Range can be combined with space (AND) or || (OR)
    or_clauses = range_str.split("||")
    for or_clause in or_clauses:
        and_clauses = [c for c in or_clause.strip().split() if c]
        if all(parse_range_clause(ac, version) for ac in and_clauses):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="SemVer 2.0.0 Range Checker, Bumper, and Validator Utility."
    )
    parser.add_argument("version", nargs="?", help="Version string to evaluate or bump")
    parser.add_argument("-r", "--range", help="SemVer range string to evaluate against (e.g. '^1.2.0', '>=2.0.0 <3.0.0')")
    parser.add_argument("-b", "--bump", choices=["major", "minor", "patch", "prerelease"], help="Bump specified version component")
    parser.add_argument("-s", "--sort", nargs="+", help="Sort a list of version strings")
    parser.add_argument("-c", "--compare", help="Compare with another version string (prints -1, 0, or 1)")
    parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    args = parser.parse_args()

    if args.sort:
        try:
            parsed = [SemVer(v) for v in args.sort]
            sorted_versions = [str(v) for v in sorted(parsed)]
            if args.json:
                print(json.dumps({"sorted": sorted_versions}, indent=2))
            else:
                print(f"{GREEN}{BOLD}Sorted Versions:{RESET}")
                for v in sorted_versions:
                    print(f"  - {v}")
        except Exception as e:
            print(f"{RED}Error sorting versions: {e}{RESET}")
            sys.exit(1)
        return

    if not args.version:
        print(f"{BLUE}{BOLD}SemVer Range Checker - Demo Mode{RESET}\n")
        demo_ver = "1.4.2"
        demo_range = ">=1.0.0 <2.0.0"
        v = SemVer(demo_ver)
        sat = satisfies_range(demo_ver, demo_range)
        print(f"Version: {BOLD}{demo_ver}{RESET}")
        print(f"Parsed: major={v.major}, minor={v.minor}, patch={v.patch}, prerelease={v.prerelease}")
        print(f"Range: {BOLD}{demo_range}{RESET} -> {GREEN}SATISFIED{RESET}" if sat else f"Range: {BOLD}{demo_range}{RESET} -> {RED}NOT SATISFIED{RESET}")
        print(f"Bump major: {v.bump('major')}")
        print(f"Bump minor: {v.bump('minor')}")
        print(f"Bump patch: {v.bump('patch')}\n")
        return

    try:
        v = SemVer(args.version)
    except Exception as e:
        print(f"{RED}Invalid SemVer: {e}{RESET}")
        sys.exit(1)

    result_data = {"version": str(v), "valid": True}

    if args.bump:
        bumped = v.bump(args.bump)
        result_data["bumped"] = str(bumped)
        if not args.json:
            print(f"{GREEN}Bumped {args.bump}: {BOLD}{bumped}{RESET}")

    if args.range:
        satisfied = satisfies_range(args.version, args.range)
        result_data["range"] = args.range
        result_data["satisfied"] = satisfied
        if not args.json:
            status = f"{GREEN}SATISFIED{RESET}" if satisfied else f"{RED}NOT SATISFIED{RESET}"
            print(f"Range check ({args.range}): {status}")

    if args.compare:
        try:
            other_v = SemVer(args.compare)
            cmp_val = 0 if v == other_v else (1 if v > other_v else -1)
            result_data["compared_to"] = str(other_v)
            result_data["comparison_result"] = cmp_val
            if not args.json:
                symbol = "==" if cmp_val == 0 else (">" if cmp_val > 0 else "<")
                print(f"Comparison: {v} {symbol} {other_v}")
        except Exception as e:
            print(f"{RED}Invalid comparison target version: {e}{RESET}")
            sys.exit(1)

    if args.json:
        print(json.dumps(result_data, indent=2))


if __name__ == "__main__":
    main()
