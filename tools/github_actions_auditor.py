#!/usr/bin/env python3
"""
GitHub Actions Workflow Security Auditor

Scans GitHub Actions workflow YAML files (.github/workflows/*.yml) for security misconfigurations,
such as unpinned action versions (missing SHA), dangerous event triggers, inline script injection risks,
and overly permissive token permissions.

Usage:
    python tools/github_actions_auditor.py
    python tools/github_actions_auditor.py --path .github/workflows/deploy.yml
"""

import argparse
import os
import re
import sys

# Color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

# Unsafe context inputs that could be abused for script injection
UNSAFE_INPUTS = [
    r"github\.event\.issue\.title",
    r"github\.event\.issue\.body",
    r"github\.event\.pull_request\.title",
    r"github\.event\.pull_request\.body",
    r"github\.event\.comment\.body",
    r"github\.event\.head_commit\.message",
    r"github\.event\.head_commit\.author\.name",
    r"github\.event\.commits\[.*\]\.message",
    r"github\.head_ref",
]

def print_colored(text, color):
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_RESET}")
    else:
        print(text)

class WorkflowAuditor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.warnings = []
        self.high_severity = 0
        self.medium_severity = 0
        self.low_severity = 0

    def add_warning(self, severity, line_num, message, suggestion):
        self.warnings.append({
            "severity": severity,
            "line": line_num,
            "message": message,
            "suggestion": suggestion
        })
        if severity == "HIGH":
            self.high_severity += 1
        elif severity == "MEDIUM":
            self.medium_severity += 1
        else:
            self.low_severity += 1

    def audit(self):
        if not os.path.exists(self.filepath):
            return False

        with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        in_run_step = False
        run_indent = 0
        run_lines = []
        run_start_line = 0

        # Compile regexes
        uses_re = re.compile(r"^\s*uses\s*:\s*(.+)$")
        permissions_re = re.compile(r"^\s*permissions\s*:\s*(.+)$")
        pull_request_target_re = re.compile(r"^\s*pull_request_target\s*:\s*")
        
        # Regex to match SHA pin (40 hex chars)
        sha_pin_re = re.compile(r"@[a-fA-F0-9]{40}$")

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            # Detect inline run block endings
            if in_run_step:
                if stripped and indent <= run_indent and not stripped.startswith("-") and ":" in stripped:
                    # Run step has ended, analyze it
                    self.analyze_run_step(run_start_line, "".join(run_lines))
                    in_run_step = False
                    run_lines = []
                else:
                    run_lines.append(line)
                    continue

            # Detect run steps starting
            if stripped.startswith("run:"):
                in_run_step = True
                run_indent = indent
                run_start_line = idx
                run_lines = [line.split("run:", 1)[1]]
                continue
            elif stripped.startswith("-") and "run:" in stripped:
                in_run_step = True
                run_indent = indent
                run_start_line = idx
                run_lines = [line.split("run:", 1)[1]]
                continue

            # 1. Check permissions block
            permissions_match = permissions_re.match(line)
            if permissions_match:
                val = permissions_match.group(1).strip()
                if val == "write-all":
                    self.add_warning(
                        "HIGH",
                        idx,
                        "Overly permissive API token settings (permissions: write-all).",
                        "Explicitly define required read-only or read/write scopes for specific features (e.g., contents: read, pull-requests: write)."
                    )

            # 2. Check pull_request_target trigger
            if pull_request_target_re.match(line):
                self.add_warning(
                    "MEDIUM",
                    idx,
                    "Dangerous event trigger (pull_request_target) detected.",
                    "Ensure you do not checkout the untrusted head ref (fork) and execute scripts or build tools from it, as it allows arbitrary code execution with repository write access."
                )

            # 3. Check for unpinned actions (missing SHA)
            uses_match = uses_re.match(line)
            if uses_match:
                action = uses_match.group(1).strip().strip("'\"")
                # Ignore local actions
                if not action.startswith("./") and not action.startswith("docker://"):
                    # Check if action contains version tag
                    if "@" in action:
                        if not sha_pin_re.search(action):
                            # Skip standard checkout actions or common trusted setups if they are tagged, but security best practice is SHA pin
                            self.add_warning(
                                "LOW",
                                idx,
                                f"Action '{action}' is pinned to a mutable tag/branch instead of a fixed commit SHA.",
                                f"Use the full 40-character commit SHA of the action version for security (e.g. {action.split('@')[0]}@ac59398561...). Add a comment above it to specify the version tag."
                            )
                    else:
                        self.add_warning(
                            "MEDIUM",
                            idx,
                            f"Action '{action}' does not specify a version pin (no @tag or @SHA).",
                            f"Pin the action to a fixed commit SHA (e.g., {action}@ac59398561...)."
                        )

        # Handle final run step if workflow ends inside one
        if in_run_step and run_lines:
            self.analyze_run_step(run_start_line, "".join(run_lines))

        return True

    def analyze_run_step(self, line_num, code):
        # Check for potential script injections
        for pattern in UNSAFE_INPUTS:
            matches = re.findall(r"\$\{\{\s*" + pattern + r"\s*\}\}", code)
            if matches:
                # Flag script injection vulnerability
                self.add_warning(
                    "HIGH",
                    line_num,
                    f"Possible command injection via expression '{matches[0]}'.",
                    "Avoid referencing github event properties directly in scripts. Set them as environment variables (env: ...) and reference them via shell variables (e.g. $TITLE)."
                )

        # Check for secret echoing
        secrets_echo = re.search(r"echo\s+.*(\$\{\{\s*secrets\..*\}\})", code, re.IGNORECASE)
        if secrets_echo:
            self.add_warning(
                "MEDIUM",
                line_num,
                f"Echoing secrets in logs: {secrets_echo.group(1)}",
                "Ensure secrets are not printed or exposed in command outputs. Echoing secrets can inadvertently write them to CI logs."
            )

    def print_report(self):
        print(f"\n{COLOR_BOLD}Auditing Workflow: {self.filename} ({self.filepath}){COLOR_RESET}")
        print("-" * 80)
        
        if not self.warnings:
            print_colored("  ✓ No security warnings found. Excellent configuration!", COLOR_GREEN)
            return

        # Sort warnings by severity (HIGH, MEDIUM, LOW)
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_warnings = sorted(self.warnings, key=lambda w: (severity_order[w["severity"]], w["line"]))

        for w in sorted_warnings:
            sev_color = COLOR_RED if w["severity"] == "HIGH" else (COLOR_YELLOW if w["severity"] == "MEDIUM" else COLOR_CYAN)
            print_colored(f"[{w['severity']}] Line {w['line']}: {w['message']}", sev_color)
            print(f"  {COLOR_BOLD}Fix:{COLOR_RESET} {w['suggestion']}\n")

        print(f"Summary: {COLOR_RED}{self.high_severity} High{COLOR_RESET}, {COLOR_YELLOW}{self.medium_severity} Medium{COLOR_RESET}, {COLOR_CYAN}{self.low_severity} Low{COLOR_RESET} issues found.")

def main():
    parser = argparse.ArgumentParser(description="GitHub Actions Workflow Security Auditor")
    parser.add_argument(
        "--path",
        default=".github/workflows",
        help="Path to workflow file or directory containing workflow files (default: .github/workflows)"
    )
    args = parser.parse_args()

    paths_to_audit = []
    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".yml") or file.endswith(".yaml"):
                    paths_to_audit.append(os.path.join(root, file))
    elif os.path.isfile(args.path):
        paths_to_audit.append(args.path)
    else:
        print_colored(f"Error: Path '{args.path}' does not exist.", COLOR_RED)
        return 1

    if not paths_to_audit:
        print(f"No GitHub Actions workflow files (.yml/.yaml) found in '{args.path}'.")
        return 0

    total_high = 0
    total_medium = 0
    total_low = 0

    for filepath in paths_to_audit:
        auditor = WorkflowAuditor(filepath)
        if auditor.audit():
            auditor.print_report()
            total_high += auditor.high_severity
            total_medium += auditor.medium_severity
            total_low += auditor.low_severity

    print("\n" + "=" * 80)
    print(f"Total Workflow Audit Summary:")
    print(f"  High Severity:   {COLOR_RED}{total_high}{COLOR_RESET}")
    print(f"  Medium Severity: {COLOR_YELLOW}{total_medium}{COLOR_RESET}")
    print(f"  Low Severity:    {COLOR_CYAN}{total_low}{COLOR_RESET}")
    print("=" * 80)

    # Return 1 if there are High severity issues, else 0
    return 1 if total_high > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
