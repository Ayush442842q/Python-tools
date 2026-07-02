#!/usr/bin/env python3
"""
Python Regex Auditor
A static analysis tool that parses Python source files using AST, extracts all
regular expression literal patterns passed to the 're' module, validates their syntax,
and audits them for potential security risks like ReDoS (Regular Expression Denial of Service).

Usage:
    python tools/python_regex_auditor.py <path_to_file_or_dir> [--verbose]
"""

import argparse
import ast
import os
import re
import sys

# ANSI colors for styling
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Common patterns matching ReDoS (e.g., nested quantifiers, overlapping repetitions)
# 1. Nested quantifiers: e.g. (a+)+, (\w*)*, (.*)+
NESTED_QUANTIFIER_RE = re.compile(r"\([^)]*[\*\+][^)]*\)[\*\+]")
# 2. Overlapping alternates: e.g. (a|a+)+
OVERLAPPING_ALTERNATE_RE = re.compile(r"\([^|)]+\|[^|)]*[\*\+][^)]*\)[\*\+]")


def audit_pattern(pattern):
    """
    Audits a regular expression string for syntax errors and potential ReDoS issues.
    Returns a list of dictionaries detailing the warnings found: (severity, message)
    """
    warnings = []
    
    # 1. Syntax check
    try:
        re.compile(pattern)
    except re.error as e:
        warnings.append({
            "severity": "HIGH",
            "type": "Syntax Error",
            "message": f"Regex compilation failed: {e}"
        })
        return warnings

    # 2. ReDoS - Nested quantifiers check, e.g. (a+)+
    if NESTED_QUANTIFIER_RE.search(pattern):
        warnings.append({
            "severity": "HIGH",
            "type": "ReDoS Risk",
            "message": "Potential nested quantifiers detected (e.g., '(a+)+' or '(\\w*)*'). Can cause exponential backtracking."
        })

    # 3. ReDoS - Overlapping alternations with quantifiers, e.g. (a|a+)+
    if OVERLAPPING_ALTERNATE_RE.search(pattern):
        warnings.append({
            "severity": "HIGH",
            "type": "ReDoS Risk",
            "message": "Potential overlapping alternations inside quantifier detected (e.g., '(a|a+)+'). Can cause exponential backtracking."
        })

    # 4. Common mistake: Unescaped dots in domain or IP-like regex
    # e.g., "192.168.1.1" instead of "192\.168\.1\.1"
    # Look for patterns like \d+\.\d+\.\d+\.\d+ where some dots might be unescaped
    if re.search(r"\w\.\w", pattern) and not re.search(r"\\\.", pattern) and not ("[" in pattern or "(" in pattern):
        # Basic heuristic for unescaped dot
        warnings.append({
            "severity": "LOW",
            "type": "Heuristic",
            "message": "Unescaped literal dot '.' detected. It will match any character. If you meant a literal dot, escape it as '\\.'."
        })

    # 5. Optimization: Capturing groups vs Non-capturing groups
    # Suggest (?:...) instead of (...) if no backreferences or matching captures seem needed
    # Only a basic warning if there are many capturing groups and no apparent group reference
    capture_groups_count = len(re.findall(r"(?<!\\)\((?!\?[P:=!])", pattern))
    if capture_groups_count > 3:
        warnings.append({
            "severity": "INFO",
            "type": "Optimization",
            "message": f"Contains multiple ({capture_groups_count}) capturing groups. Consider non-capturing groups '(?:...)' for better performance if captures are unused."
        })

    return warnings


class RegexVisitor(ast.NodeVisitor):
    """AST visitor to find and analyze regular expression patterns in python source code."""
    
    def __init__(self, filename):
        self.filename = filename
        self.re_calls = []
        self.re_imported = False
        self.re_aliases = set()
        self.from_re_imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "re":
                self.re_imported = True
                self.re_aliases.add(alias.asname or "re")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == "re":
            self.re_imported = True
            for alias in node.names:
                self.from_re_imports.add(alias.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        is_re_call = False
        func_name = ""

        # Detect direct re.func(...) calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                if module_name == "re" or module_name in self.re_aliases:
                    is_re_call = True
                    func_name = node.func.attr
        # Detect from re import func; func(...) calls
        elif isinstance(node.func, ast.Name):
            if node.func.id in self.from_re_imports:
                is_re_call = True
                func_name = node.func.id

        if is_re_call and func_name in [
            "compile", "search", "match", "fullmatch", "split", "findall", "finditer", "sub", "subn"
        ]:
            # Regex pattern is typically the first argument
            pattern_arg = None
            if node.args:
                pattern_arg = node.args[0]
            elif node.keywords:
                for kw in node.keywords:
                    if kw.arg == "pattern":
                        pattern_arg = kw.value
                        break

            pattern_val = None
            is_literal = False

            if pattern_arg:
                # Handle string literals (ast.Constant in Python 3.8+, ast.Str in older versions)
                if isinstance(pattern_arg, ast.Constant) and isinstance(pattern_arg.value, str):
                    pattern_val = pattern_arg.value
                    is_literal = True
                elif isinstance(pattern_arg, ast.Str): # Fallback
                    pattern_val = pattern_arg.s
                    is_literal = True

            self.re_calls.append({
                "filename": self.filename,
                "line": node.lineno,
                "col": node.col_offset,
                "function": func_name,
                "pattern": pattern_val,
                "is_literal": is_literal
            })

        self.generic_visit(node)


def audit_file(filepath, verbose=False):
    """Parses and audits a single Python source file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"{RED}Error reading file '{filepath}': {e}{RESET}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        if verbose:
            print(f"{YELLOW}Warning: Skipping '{filepath}' due to Python syntax error: {e}{RESET}")
        return []

    visitor = RegexVisitor(filepath)
    visitor.visit(tree)
    
    findings = []
    for call in visitor.re_calls:
        if not call["is_literal"]:
            findings.append({
                "call": call,
                "warnings": [{
                    "severity": "INFO",
                    "type": "Dynamic Pattern",
                    "message": "Regex pattern is not a string literal. Static analysis skipped."
                }]
            })
            continue

        warnings = audit_pattern(call["pattern"])
        if warnings:
            findings.append({
                "call": call,
                "warnings": warnings
            })
        elif verbose:
            findings.append({
                "call": call,
                "warnings": [] # Safe literal pattern
            })

    return findings


def main():
    parser = argparse.ArgumentParser(
        description="Static Regex Auditor - Audits regular expressions in Python codebases for ReDoS and syntax issues."
    )
    parser.add_argument("path", help="Path to Python file or directory containing Python files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Include safe/dynamic patterns in the report")
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)
    if not os.path.exists(target_path):
        print(f"{RED}Error: Path '{args.path}' does not exist.{RESET}", file=sys.stderr)
        return 1

    py_files = []
    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            py_files.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))

    if not py_files:
        print(f"{YELLOW}No Python (.py) files found to scan.{RESET}")
        return 0

    print(f"{BOLD}Scanning {len(py_files)} Python source file(s) for regular expressions...{RESET}\n")

    total_findings_count = 0
    warnings_by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

    for filepath in py_files:
        findings = audit_file(filepath, verbose=args.verbose)
        if not findings:
            continue

        file_printed = False
        for f in findings:
            call = f["call"]
            warnings = f["warnings"]
            
            if not warnings and not args.verbose:
                continue

            if not file_printed:
                rel_path = os.path.relpath(filepath, os.path.dirname(target_path) if os.path.isfile(target_path) else target_path)
                print(f"{BOLD}{CYAN}File: {rel_path}{RESET}")
                file_printed = True

            loc_str = f"Line {call['line']}:{call['col']}"
            pattern_display = call['pattern']
            if pattern_display is not None:
                # Truncate pattern if too long
                if len(pattern_display) > 50:
                    pattern_display = pattern_display[:47] + "..."
                pattern_repr = f"r'{pattern_display}'"
            else:
                pattern_repr = "<Dynamic>"

            print(f"  {BOLD}{loc_str:<12} | Call: re.{call['function']}({pattern_repr}){RESET}")
            
            if not warnings:
                print(f"    {GREEN}✓ Safe (No structural warnings detected){RESET}")
                continue

            for w in warnings:
                severity = w["severity"]
                warnings_by_severity[severity] = warnings_by_severity.get(severity, 0) + 1
                total_findings_count += 1

                color = RED if severity == "HIGH" else (YELLOW if severity == "MEDIUM" else (BLUE if severity == "LOW" else CYAN))
                print(f"    [{color}{severity}{RESET}] {w['type']}: {w['message']}")
            print()

    # Print summary
    print(f"{BOLD}--- Audit Summary ---{RESET}")
    print(f"Total Python files scanned: {len(py_files)}")
    print(f"High Severity (ReDoS/Syntax error): {RED}{warnings_by_severity['HIGH']}{RESET}")
    print(f"Medium Severity: {YELLOW}{warnings_by_severity['MEDIUM']}{RESET}")
    print(f"Low Severity: {BLUE}{warnings_by_severity['LOW']}{RESET}")
    print(f"Info/Dynamic references: {CYAN}{warnings_by_severity['INFO']}{RESET}")

    if warnings_by_severity["HIGH"] > 0:
        return 2  # Return non-zero to indicate high risk findings
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Audit cancelled by user.{RESET}")
        sys.exit(1)
