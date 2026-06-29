#!/usr/bin/env python3
"""
Python Magic Number Detector
Static analyzer to scan Python files and find hardcoded magic numbers using AST.
"""

import argparse
import ast
import os
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_IGNORE = {0, 1, 2, -1, 10, 100, 0.0, 1.0, 0.5, 0.1, -1.0}

class MagicNumberVisitor(ast.NodeVisitor):
    def __init__(self, filename, lines, ignore_list):
        self.filename = filename
        self.lines = lines
        self.ignore_list = ignore_list
        self.findings = []
        self.current_assignment_target = None
        self.in_uppercase_assignment = False

    def visit_Assign(self, node):
        # Check if the target of assignment is an uppercase constant
        is_uppercase = False
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                is_uppercase = True
                break
        
        old_state = self.in_uppercase_assignment
        self.in_uppercase_assignment = is_uppercase
        
        self.generic_visit(node)
        
        self.in_uppercase_assignment = old_state

    def visit_AnnAssign(self, node):
        is_uppercase = isinstance(node.target, ast.Name) and node.target.id.isupper()
        old_state = self.in_uppercase_assignment
        self.in_uppercase_assignment = is_uppercase
        
        self.generic_visit(node)
        
        self.in_uppercase_assignment = old_state

    def visit_Constant(self, node):
        # Handles Python 3.8+ constants
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            self.check_number(node.value, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_Num(self, node):
        # Handles Python < 3.8 numbers
        self.check_number(node.n, node.lineno, node.col_offset)
        self.generic_visit(node)

    def check_number(self, value, lineno, col_offset):
        # Skip if in ignore list or inside an uppercase constant assignment
        if value in self.ignore_list or self.in_uppercase_assignment:
            return

        # Double check if it looks like we're in a standard slice (e.g. index 0, 1, 2, etc. - though those are ignored)
        # Add to findings
        source_line = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
        self.findings.append({
            "value": value,
            "line": lineno,
            "col": col_offset,
            "source": source_line
        })

def analyze_file(filepath, ignore_list):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()
        
        try:
            tree = ast.parse(content, filename=filepath)
        except SyntaxError as e:
            return None, f"Syntax error: {e}"

        visitor = MagicNumberVisitor(filepath, lines, ignore_list)
        visitor.visit(tree)
        return visitor.findings, None
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(
        description="Scan Python files for hardcoded magic numbers (numerical literals used in code operations)."
    )
    parser.add_argument("path", help="File or directory path to scan")
    parser.add_argument(
        "--ignore",
        default="0,1,2,-1,10,100,0.0,1.0,0.5,0.1",
        help="Comma-separated list of numbers to ignore"
    )
    parser.add_argument(
        "--exclude-dirs",
        default="venv,.git,__pycache__,.pytest_cache,.agents",
        help="Comma-separated list of directories to exclude from recursive scans"
    )

    args = parser.parse_args()

    # Parse ignore list
    ignore_set = set()
    for val in args.ignore.split(","):
        try:
            if "." in val:
                ignore_set.add(float(val))
            else:
                ignore_set.add(int(val))
        except ValueError:
            pass

    exclude_dirs = [d.strip() for d in args.exclude_dirs.split(",")]

    target_path = args.path
    if not os.path.exists(target_path):
        print(f"{RED}Error: Path '{target_path}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    python_files = []
    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            python_files.append(target_path)
    else:
        for root, dirs, files in os.walk(target_path):
            # Prune excluded directories in place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))

    if not python_files:
        print(f"{YELLOW}No Python (.py) files found to scan.{RESET}")
        sys.exit(0)

    print(f"{BOLD}{BLUE}Scanning {len(python_files)} Python file(s) for magic numbers...{RESET}")
    print(f"Ignoring numbers: {sorted(list(ignore_set))}\n")

    total_findings = 0
    files_with_findings = 0

    for filepath in sorted(python_files):
        findings, err = analyze_file(filepath, ignore_set)
        if err:
            print(f"{YELLOW}Skipped {filepath}: {err}{RESET}")
            continue
        
        if findings:
            files_with_findings += 1
            total_findings += len(findings)
            rel_path = os.path.relpath(filepath)
            print(f"{BOLD}{UNDERLINE_IF_POSSIBLE(rel_path)}{RESET}")
            for f in findings:
                print(f"  {RED}Line {f['line']}:{f['col']}{RESET} - Magic number: {BOLD}{f['value']}{RESET}")
                print(f"    Code: {BLUE}{f['source']}{RESET}")
            print()

    print("=" * 60)
    if total_findings > 0:
        print(f"{RED}{BOLD}Scan complete. Found {total_findings} magic number(s) across {files_with_findings} file(s).{RESET}")
        print(f"{YELLOW}Recommendation: Replace these with named UPPERCASE constants at the module/class level.{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}Scan complete. No magic numbers found! All clean!{RESET}")
        sys.exit(0)

def UNDERLINE_IF_POSSIBLE(text):
    return f"\033[4m{text}\033[24m"

if __name__ == "__main__":
    main()
