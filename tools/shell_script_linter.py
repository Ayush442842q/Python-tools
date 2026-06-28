#!/usr/bin/env python3
"""
Shell Script Quality Linter - A lightweight static analyzer for Bash/Shell scripts.
Scans for shebang issues, unquoted variables, unchecked cd/commands, deprecated backticks,
and missing error handling settings (e.g., set -e, set -o pipefail).
"""

import os
import sys
import re
import argparse
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

# Regular expressions for shell lint rules
RE_UNQUOTED_VAR = re.compile(r'(?<!\\)\$\{[a-zA-Z_][a-zA-Z0-9_]*\}|(?<!\\)\$[a-zA-Z_][a-zA-Z0-9_]*')
RE_DEPRECATED_BACKTICKS = re.compile(r'`[^`]+`')
RE_UNCHECKED_CD = re.compile(r'\bcd\s+[^&|;\n]+')
RE_CD_CHECKED = re.compile(r'(\|\||&&|;|exit|return|die)')

class ShellLinter:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.total_violations = 0
        self.total_scanned = 0

    def lint_file(self, filepath):
        self.total_scanned += 1
        violations = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            if self.verbose:
                print(f"Error reading file '{filepath}': {e}")
            return []

        if not lines:
            return []

        # 1. Shebang Check
        first_line = lines[0].strip()
        if not first_line.startswith("#!"):
            violations.append({
                'line': 1,
                'code': first_line[:40],
                'rule': 'Missing Shebang',
                'severity': 'HIGH',
                'description': "Shell scripts should start with a valid shebang (e.g., '#!/bin/bash' or '#!/bin/sh')."
            })
        elif "bash" not in first_line and "sh" not in first_line and "zsh" not in first_line:
            violations.append({
                'line': 1,
                'code': first_line,
                'rule': 'Uncommon Shebang',
                'severity': 'LOW',
                'description': f"Shebang '{first_line}' does not target common shell environments like sh, bash, or zsh."
            })

        # 2. Check for Error Prevention Options (set -e, set -o pipefail)
        has_set_e = False
        has_pipefail = False
        for line in lines:
            # Strip comments
            code_line = line.split('#')[0].strip()
            if code_line:
                if 'set -e' in code_line or 'set -o errexit' in code_line or '-e' in code_line.split():
                    has_set_e = True
                if 'pipefail' in code_line:
                    has_pipefail = True

        if not has_set_e:
            violations.append({
                'line': 1,
                'code': 'N/A',
                'rule': 'Missing set -e',
                'severity': 'MEDIUM',
                'description': "Consider adding 'set -e' near the beginning of the script so it exits immediately if any command returns a non-zero exit status."
            })

        if not has_pipefail:
            violations.append({
                'line': 1,
                'code': 'N/A',
                'rule': 'Missing set -o pipefail',
                'severity': 'LOW',
                'description': "Consider adding 'set -o pipefail' to prevent errors in pipelines from being masked by subsequent commands."
            })

        # Line-by-line checks
        for idx, line_content in enumerate(lines, 1):
            stripped = line_content.strip()
            
            # Skip empty lines or pure comments
            if not stripped or stripped.startswith('#'):
                continue
                
            # Remove inline comment for pattern matching
            code_part = line_content.split('#')[0].strip()

            # 3. Check for Deprecated Backticks
            if RE_DEPRECATED_BACKTICKS.search(code_part):
                violations.append({
                    'line': idx,
                    'code': stripped,
                    'rule': 'Deprecated Backticks',
                    'severity': 'MEDIUM',
                    'description': "Use '$(command)' instead of legacy backticks '`command`'. It is nesting-friendly and improves readability."
                })

            # 4. Check for Unquoted Variables (Space Bug Risk)
            # Find occurrences of $var or ${var} that are NOT enclosed in double quotes
            # A simple way is to check if $ exists and double quotes do not wrap it.
            # We will search for variable patterns.
            for match in RE_UNQUOTED_VAR.finditer(code_part):
                var_match = match.group(0)
                
                # Simple check if the match is inside double quotes
                match_start = match.start()
                match_end = match.end()
                
                # Count double quotes before and after on the same line
                quotes_before = code_part[:match_start].count('"')
                quotes_after = code_part[match_end:].count('"')
                
                # If odd count before/after, it is likely inside quotes. If even, it is unquoted.
                # (Ignoring complex multiline/escaped cases for simplicity, which is standard for light linters)
                if quotes_before % 2 == 0:
                    # Exceptions: inside single quotes (literals), or in assignments/declarations
                    single_quotes_before = code_part[:match_start].count("'")
                    if single_quotes_before % 2 == 1:
                        # Inside single quotes, which is expected for literals
                        continue
                        
                    # Skip common safe unquoted places like double-parentheses arithmetic (( var ))
                    if '((' in code_part[:match_start] and '))' in code_part[match_end:]:
                        continue
                        
                    violations.append({
                        'line': idx,
                        'code': var_match,
                        'rule': 'Unquoted Variable Reference',
                        'severity': 'MEDIUM',
                        'description': f"Variable reference '{var_match}' is unquoted. Quote it as \"{var_match}\" to prevent word splitting or glob expansion if it contains spaces."
                    })

            # 5. Check for Unchecked cd Command (Critical Failure Risk)
            # A 'cd' command without an '|| exit' or similar check means the script
            # could fail to change directory and execute subsequent destructive commands (like rm) in the wrong directory!
            if RE_UNCHECKED_CD.search(code_part):
                # Verify if it is checked on the same line
                if not RE_CD_CHECKED.search(code_part):
                    violations.append({
                        'line': idx,
                        'code': stripped,
                        'rule': 'Unchecked cd Command',
                        'severity': 'HIGH',
                        'description': "The 'cd' command is unchecked. If it fails, script execution will continue in the wrong directory. Append '|| exit' or check success."
                    })

        self.total_violations += len(violations)
        return violations

    def scan_directory(self, dirpath):
        root = Path(dirpath)
        results = {}
        for file_path in root.rglob('*.sh'):
            # Skip virtual environments and git folders
            if any(part.startswith('.') for part in file_path.parts) or 'venv' in file_path.parts:
                continue
            violations = self.lint_file(str(file_path))
            if violations:
                results[str(file_path.relative_to(root))] = violations
        return results

def main():
    parser = argparse.ArgumentParser(description="Shell Script Quality Linter - Lightweight static analyzer for Shell scripts")
    parser.add_argument("target", nargs="?", default=".", help="Shell script file or directory to scan")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details of files scanned")
    args = parser.parse_args()

    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_magenta = get_color('magenta')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
    print(f"{c_bold}{c_blue}                      Shell Script Quality Linter                     {c_reset}")
    print(f"{c_bold}{c_magenta}======================================================================{c_reset}")

    linter = ShellLinter(verbose=args.verbose)
    target_path = Path(args.target).resolve()

    if not target_path.exists():
        print(f"{c_red}Error: Path '{args.target}' does not exist.{c_reset}")
        sys.exit(1)

    if target_path.is_file():
        print(f"Scanning File: '{target_path.name}'")
        print("-" * 70)
        violations = linter.lint_file(str(target_path))
        if violations:
            print(f"\n{c_red}Found {len(violations)} quality issues:{c_reset}")
            for v in violations:
                sev_color = c_red if v['severity'] == 'HIGH' else (c_yellow if v['severity'] == 'MEDIUM' else c_blue)
                print(f"  Line {v['line']}: {sev_color}[{v['severity']}] {v['rule']}{c_reset}")
                print(f"    Code: {v['code']}")
                print(f"    Info: {v['description']}")
                print()
            sys.exit(1)
        else:
            print(f"\n{c_green}✓ Shell script passed all quality checks.{c_reset}")
            sys.exit(0)

    elif target_path.is_dir():
        print(f"Scanning Directory: '{target_path}'")
        print("-" * 70)
        results = linter.scan_directory(str(target_path))
        
        if results:
            print(f"\n{c_red}Issues found in {len(results)} shell scripts:{c_reset}")
            for rel_path, violations in results.items():
                print(f"\n{c_bold}{rel_path}{c_reset} ({len(violations)} issues):")
                for v in violations:
                    sev_color = c_red if v['severity'] == 'HIGH' else (c_yellow if v['severity'] == 'MEDIUM' else c_blue)
                    print(f"  Line {v['line']}: {sev_color}[{v['severity']}] {v['rule']}{c_reset}")
                    print(f"    Code: {v['code']}")
                    print(f"    Info: {v['description']}")
            print(f"\n{c_bold}{c_magenta}======================================================================{c_reset}")
            print(f"{c_red}STATUS: FAILED ({linter.total_violations} total violations across {linter.total_scanned} files){c_reset}")
            sys.exit(1)
        else:
            print(f"\n{c_green}✓ Directory clean. Scanned {linter.total_scanned} files, 0 issues found.{c_reset}")
            print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
            sys.exit(0)

if __name__ == "__main__":
    main()
