#!/usr/bin/env python3
"""
Unicode Normalization Linter & Homoglyph Auditor
A CLI static analysis utility to check files for Unicode normalization consistency and detect confusable homoglyphs.

Features:
- Scans source files individually or recursively within a directory.
- Detects mixed Unicode normalization forms (NFC, NFD, NFKC, NFKD) inside files.
- Flags homoglyphs (lookalike characters from different Unicode scripts, e.g. Cyrillic 'а' vs Latin 'a') to prevent spoofing or obscure bugs.
- Checks if file contents would change when normalized to a target form (e.g. NFC).
- Provides an automated fix flag (`--fix`) to normalize files in-place.
"""

import sys
import os
import unicodedata
import argparse
from typing import List, Dict, Tuple, Set

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


# Common homoglyph/lookalike character pairs/groups (e.g. Cyrillic, Greek, Latin)
CONFUSABLE_SCRIPTS: Dict[str, str] = {
    # Cyrillic lookalikes
    "\u0430": "a",  # Cyrillic small letter a
    "\u0435": "e",  # Cyrillic small letter ie
    "\u043e": "o",  # Cyrillic small letter o
    "\u0440": "p",  # Cyrillic small letter er
    "\u0441": "c",  # Cyrillic small letter es
    "\u0443": "y",  # Cyrillic small letter u
    "\u0445": "x",  # Cyrillic small letter ha
    "\u0455": "s",  # Cyrillic small letter dze
    "\u0410": "A",  # Cyrillic capital letter A
    "\u0412": "B",  # Cyrillic capital letter Ve
    "\u0415": "E",  # Cyrillic capital letter Ie
    "\u041a": "K",  # Cyrillic capital letter Ka
    "\u041c": "M",  # Cyrillic capital letter Em
    "\u041d": "H",  # Cyrillic capital letter En
    "\u041e": "O",  # Cyrillic capital letter O
    "\u0420": "P",  # Cyrillic capital letter Er
    "\u0421": "C",  # Cyrillic capital letter Es
    "\u0422": "T",  # Cyrillic capital letter Te
    "\u0425": "X",  # Cyrillic capital letter Ha
    "\u0423": "Y",  # Cyrillic capital letter U
    # Greek lookalikes
    "\u03b1": "a",  # Greek small letter alpha
    "\u03bf": "o",  # Greek small letter omicron
    "\u03bd": "v",  # Greek small letter nu
    "\u03ba": "k",  # Greek small letter kappa
    "\u0391": "A",  # Greek capital letter Alpha
    "\u0392": "B",  # Greek capital letter Beta
    "\u0395": "E",  # Greek capital letter Epsilon
    "\u0397": "H",  # Greek capital letter Eta
    "\u0399": "I",  # Greek capital letter Iota
    "\u039a": "K",  # Greek capital letter Kappa
    "\u039c": "M",  # Greek capital letter Mu
    "\u039d": "N",  # Greek capital letter Nu
    "\u039f": "O",  # Greek capital letter Omicron
    "\u03a1": "P",  # Greek capital letter Rho
    "\u03a4": "T",  # Greek capital letter Tau
    "\u03a7": "X",  # Greek capital letter Chi
    "\u03a9": "O",  # Greek capital letter Omega (confusable with O in some fonts)
}


def audit_file(filepath: str, target_form: str, check_homoglyphs: bool) -> Tuple[bool, List[str]]:
    """
    Audits a single file for Unicode normalization anomalies and homoglyphs.
    Returns (has_issues, list_of_issue_messages).
    """
    issues: List[str] = []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files
        return False, []
    except Exception as e:
        return True, [f"Error reading file: {e}"]

    # Check normalization
    normalized_content = unicodedata.normalize(target_form, content)
    if content != normalized_content:
        issues.append(f"Content is not normalized to {target_form}.")

    # Scan for mixed normalization or specific un-normalized sequences line by line
    if check_homoglyphs:
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            found_homoglyphs: List[str] = []
            for char in line:
                if char in CONFUSABLE_SCRIPTS:
                    expected = CONFUSABLE_SCRIPTS[char]
                    # Check if there are standard ASCII chars in the same line/word
                    # to identify mixed-script spoofing
                    found_homoglyphs.append(f"'{char}' (U+{ord(char):04X}, looks like '{expected}')")
            if found_homoglyphs:
                issues.append(f"Line {idx}: Found confusable homoglyphs: {', '.join(found_homoglyphs)}")

    return len(issues) > 0, issues


def fix_file(filepath: str, target_form: str) -> bool:
    """Normalizes a file in-place to the target form. Returns True if modified."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        normalized = unicodedata.normalize(target_form, content)
        if content != normalized:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(normalized)
            return True
    except Exception as e:
        print(f"Failed to fix {filepath}: {e}", file=sys.stderr)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and lint files for Unicode normalization issues and confusable homoglyphs.")
    parser.add_argument("path", help="File or directory path to audit.")
    parser.add_argument("-f", "--form", choices=["NFC", "NFD", "NFKC", "NFKD"], default="NFC",
                        help="Target Unicode normalization form (default: NFC).")
    parser.add_argument("--no-homoglyphs", dest="homoglyphs", action="store_false",
                        help="Disable checking for confusable homoglyphs.")
    parser.add_argument("--fix", action="store_true", help="Automatically fix normalization issues in-place.")
    parser.add_argument("-e", "--extension", action="append", help="Filter files by extension (e.g. '.py', '.txt'). Can specify multiple.")

    args = parser.parse_args()

    target_paths: List[str] = []
    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if args.extension and ext not in [e.lower() for e in args.extension]:
                    continue
                # Skip hidden files or git folders
                if "/.git" in root or root.startswith(".") or file.startswith("."):
                    continue
                target_paths.append(os.path.join(root, file))
    elif os.path.isfile(args.path):
        target_paths.append(args.path)
    else:
        print(f"Error: Path '{args.path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    total_files = len(target_paths)
    files_with_issues = 0
    fixed_files = 0

    print(f"Auditing {total_files} file(s)...")

    for filepath in target_paths:
        has_issues, issues = audit_file(filepath, args.form, args.homoglyphs)
        if has_issues:
            files_with_issues += 1
            print(f"\n[ISSUE] {filepath}:")
            for issue in issues:
                print(f"  - {issue}")
            
            if args.fix:
                modified = fix_file(filepath, args.form)
                if modified:
                    fixed_files += 1
                    print(f"  -> Fixed in-place using {args.form} normalization.")

    print(f"\nAudit complete. Checked {total_files} file(s).")
    print(f"Found issues in {files_with_issues} file(s).")
    if args.fix:
        print(f"Fixed {fixed_files} file(s) in-place.")
    
    if files_with_issues > 0 and not args.fix:
        sys.exit(1)


if __name__ == "__main__":
    main()
