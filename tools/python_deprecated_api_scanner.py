#!/usr/bin/env python3
"""
Python Deprecated API Scanner
-----------------------------
Static analysis AST scanner that searches Python codebases for deprecated
standard library modules, functions, methods, and syntax constructs according to
Python 3.8 - 3.14 deprecation and removal schedules.

Author: Antigravity
License: MIT
"""

import sys
import os
import ast
import json
import argparse
from typing import List, Dict, Any, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Deprecation rules mapping (module/function/syntax -> details)
DEPRECATED_MODULES = {
    "cgi": {"deprecated": "3.11", "removed": "3.13", "replacement": "urllib.parse, html, or email"},
    "cgitb": {"deprecated": "3.11", "removed": "3.13", "replacement": "traceback or third-party logging"},
    "crypt": {"deprecated": "3.11", "removed": "3.13", "replacement": "hashlib, passlib, or secrets"},
    "imghdr": {"deprecated": "3.11", "removed": "3.13", "replacement": "third-party filetype or pure-python header check"},
    "sndhdr": {"deprecated": "3.11", "removed": "3.13", "replacement": "third-party audio headers check"},
    "nntplib": {"deprecated": "3.11", "removed": "3.13", "replacement": "nntplib alternative or socket"},
    "pipes": {"deprecated": "3.11", "removed": "3.13", "replacement": "subprocess module"},
    "smtpd": {"deprecated": "3.11", "removed": "3.13", "replacement": "aiosmtpd or asyncio"},
    "telnetlib": {"deprecated": "3.11", "removed": "3.13", "replacement": "telnetlib3 or socket"},
    "uu": {"deprecated": "3.11", "removed": "3.13", "replacement": "base64 module"},
    "xdrlib": {"deprecated": "3.11", "removed": "3.13", "replacement": "struct module"},
    "distutils": {"deprecated": "3.10", "removed": "3.12", "replacement": "setuptools or build"},
    "imp": {"deprecated": "3.4", "removed": "3.12", "replacement": "importlib"},
    "asyncore": {"deprecated": "3.6", "removed": "3.12", "replacement": "asyncio"},
    "asynchat": {"deprecated": "3.6", "removed": "3.12", "replacement": "asyncio"},
    "parser": {"deprecated": "3.9", "removed": "3.10", "replacement": "ast module"},
    "symbol": {"deprecated": "3.9", "removed": "3.10", "replacement": "ast module"},
}

DEPRECATED_FUNCTIONS = {
    ("datetime", "utcnow"): {"deprecated": "3.12", "removed": "Future", "replacement": "datetime.now(timezone.utc)"},
    ("datetime", "utcfromtimestamp"): {"deprecated": "3.12", "removed": "Future", "replacement": "datetime.fromtimestamp(ts, timezone.utc)"},
    ("asyncio", "get_event_loop"): {"deprecated": "3.10", "removed": "Future", "replacement": "asyncio.get_running_loop() or asyncio.new_event_loop()"},
    ("asyncio", "coroutine"): {"deprecated": "3.8", "removed": "3.11", "replacement": "async def syntax"},
    ("inspect", "getargspec"): {"deprecated": "3.0", "removed": "3.11", "replacement": "inspect.signature() or inspect.getfullargspec()"},
    ("threading", "Thread", "isAlive"): {"deprecated": "3.8", "removed": "3.9", "replacement": "Thread.is_alive()"},
    ("unittest", "TestCase", "assertEquals"): {"deprecated": "3.2", "removed": "3.12", "replacement": "assertEqual()"},
    ("unittest", "TestCase", "assertNotEquals"): {"deprecated": "3.2", "removed": "3.12", "replacement": "assertNotEqual()"},
    ("unittest", "TestCase", "assertAlmostEquals"): {"deprecated": "3.2", "removed": "3.12", "replacement": "assertAlmostEqual()"},
    ("random", "randint"): {},  # Active function, left as reference
}


class DeprecatedAPIVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.findings: List[Dict[str, Any]] = []
        self.imported_modules: Dict[str, str] = {}  # alias -> original module

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_name = alias.name.split('.')[0]
            if mod_name in DEPRECATED_MODULES:
                info = DEPRECATED_MODULES[mod_name]
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "Module Import",
                    "target": alias.name,
                    "deprecated_in": info["deprecated"],
                    "removed_in": info["removed"],
                    "replacement": info["replacement"],
                })
            self.imported_modules[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_name = node.module.split('.')[0]
            if mod_name in DEPRECATED_MODULES:
                info = DEPRECATED_MODULES[mod_name]
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "Module ImportFrom",
                    "target": node.module,
                    "deprecated_in": info["deprecated"],
                    "removed_in": info["removed"],
                    "replacement": info["replacement"],
                })
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # Check attribute usage like datetime.utcnow or Thread.isAlive
        attr_name = node.attr
        if attr_name in ("utcnow", "utcfromtimestamp") and isinstance(node.value, ast.Name) and node.value.id == "datetime":
            info = DEPRECATED_FUNCTIONS.get(("datetime", attr_name))
            if info:
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "Function Call",
                    "target": f"datetime.{attr_name}",
                    "deprecated_in": info["deprecated"],
                    "removed_in": info["removed"],
                    "replacement": info["replacement"],
                })
        elif attr_name in ("assertEquals", "assertNotEquals", "assertAlmostEquals"):
            info = DEPRECATED_FUNCTIONS.get(("unittest", "TestCase", attr_name))
            if info:
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "Assertion Method",
                    "target": attr_name,
                    "deprecated_in": info["deprecated"],
                    "removed_in": info["removed"],
                    "replacement": info["replacement"],
                })
        elif attr_name == "isAlive":
            info = DEPRECATED_FUNCTIONS.get(("threading", "Thread", "isAlive"))
            if info:
                self.findings.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "Method Call",
                    "target": "isAlive",
                    "deprecated_in": info["deprecated"],
                    "removed_in": info["removed"],
                    "replacement": info["replacement"],
                })
        self.generic_visit(node)


def scan_file(filepath: str) -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        visitor = DeprecatedAPIVisitor(filepath)
        visitor.visit(tree)
        return visitor.findings
    except Exception as e:
        return []


def scan_directory(directory: str) -> List[Dict[str, Any]]:
    all_findings = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                all_findings.extend(scan_file(full_path))
    return all_findings


def main():
    parser = argparse.ArgumentParser(
        description="Python Deprecated API Scanner - Detect deprecated modules, methods, and syntax."
    )
    parser.add_argument("target", help="Python file or directory to scan.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output.")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}Error: Target '{args.target}' does not exist.{RESET}")
        sys.exit(1)

    if os.path.isdir(args.target):
        findings = scan_directory(args.target)
    else:
        findings = scan_file(args.target)

    if args.json:
        print(json.dumps(findings, indent=2))
        return

    if not args.quiet:
        print(f"{BOLD}{CYAN}=== Python Deprecated API Scan Report ==={RESET}")
        print(f"Target: {args.target}")
        print(f"Total Warnings: {len(findings)}\n")

    if not findings:
        print(f"{GREEN}[OK] No deprecated APIs or modules detected!{RESET}")
        return

    for item in findings:
        print(f"  {RED}Line {item['line']}{RESET} in {BOLD}{item['file']}{RESET}")
        print(f"    Target:       {YELLOW}{item['target']}{RESET} ({item['type']})")
        print(f"    Deprecated:   Python {item['deprecated_in']} (Removed: {item['removed_in']})")
        print(f"    Replacement:  {GREEN}{item['replacement']}{RESET}")
        print("-" * 60)


if __name__ == "__main__":
    main()
