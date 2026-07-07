#!/usr/bin/env python3
"""
GitHub Actions Workflow Matrix & Cache Optimizer

Statically parses GitHub Actions workflow YAML files to identify optimizations for:
1. Matrix configuration (fail-fast settings, redundancy).
2. Step-level and job-level caching (setup-node, setup-python, setup-go, setup-java, etc.).
3. Missing timeouts (timeout-minutes) which prevent runaway jobs.
4. Top-level or job-level permissions to enforce the principle of least privilege.
5. Outdated action versions and recommended commit SHA pinning for security.

Usage:
    python tools/github_workflow_matrix_optimizer.py .github/workflows/
    python tools/github_workflow_matrix_optimizer.py .github/workflows/build.yml
"""

import os
import re
import sys
import argparse
from typing import Dict, List, Any, Tuple

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if the output terminal supports ANSI colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

# Toggle colors
USE_COLOR = supports_color()

def colorize(text: str, color_code: str) -> str:
    if USE_COLOR:
        return f"{color_code}{text}{COLOR_RESET}"
    return text

class YamlNode:
    """A simple helper representing a line and its indentation/content for parsing hierarchy."""
    def __init__(self, line_num: int, indent: int, key: str, value: str, raw: str):
        self.line_num = line_num
        self.indent = indent
        self.key = key.strip()
        self.value = value.strip()
        self.raw = raw
        self.children: List['YamlNode'] = []
        self.parent: 'YamlNode' = None

    def __repr__(self):
        return f"Node({self.key}: {self.value} at L{self.line_num})"

def parse_yaml_hierarchy(lines: List[str]) -> YamlNode:
    """Parses a YAML file outline structurally to build a parent-child hierarchy based on indentation."""
    root = YamlNode(0, -1, "root", "", "")
    current_stack = [root]

    for i, line in enumerate(lines, 1):
        # Skip empty lines or comments
        if not line.strip() or line.strip().startswith('#'):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # Check key-value pattern
        # Handles keys with spaces, dashes for lists, quotes
        match = re.match(r'^(?:-\s*)?([\w\-\.\/\"\']+)\s*:\s*(.*)$', stripped)
        if match:
            key, val = match.groups()
        else:
            # Maybe it is a list item without key-value, e.g. "- some-value"
            list_match = re.match(r'^-\s*(.*)$', stripped)
            if list_match:
                key = "-"
                val = list_match.group(1)
            else:
                key = stripped
                val = ""

        node = YamlNode(i, indent, key, val, line)

        # Pop stack until we find the parent (which has less indentation)
        while len(current_stack) > 1 and current_stack[-1].indent >= indent:
            current_stack.pop()

        parent = current_stack[-1]
        node.parent = parent
        parent.children.append(node)
        current_stack.append(node)

    return root

def find_nodes_by_key(root: YamlNode, target_key: str) -> List[YamlNode]:
    """Helper to find all nodes with a given key name in the tree."""
    results = []
    def traverse(node: YamlNode):
        if node.key == target_key:
            results.append(node)
        for child in node.children:
            traverse(child)
    traverse(root)
    return results

def get_node_by_path(root: YamlNode, path: List[str]) -> YamlNode:
    """Traverse down a strict path, e.g. ['jobs', 'build', 'steps']"""
    curr = root
    for step in path:
        found = False
        for child in curr.children:
            if child.key == step:
                curr = child
                found = True
                break
        if not found:
            return None
    return curr

class AuditFinding:
    def __init__(self, line: int, severity: str, message: str, fix_suggestion: str):
        self.line = line
        self.severity = severity  # 'INFO', 'WARN', 'CRITICAL'
        self.message = message
        self.fix_suggestion = fix_suggestion

    def __repr__(self):
        return f"[{self.severity}] L{self.line}: {self.message}"

def audit_workflow(file_path: str) -> List[AuditFinding]:
    findings: List[AuditFinding] = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
    except Exception as e:
        return [AuditFinding(0, "CRITICAL", f"Failed to read file: {e}", "Ensure file exists and has correct permissions.")]

    root = parse_yaml_hierarchy(lines)

    # 1. Top-Level Permissions check
    permissions_nodes = find_nodes_by_key(root, "permissions")
    if not permissions_nodes:
        # Check if individual jobs define permissions
        jobs_node = get_node_by_path(root, ["jobs"])
        job_permissions_found = False
        if jobs_node:
            for job in jobs_node.children:
                if find_nodes_by_key(job, "permissions"):
                    job_permissions_found = True
                    break
        
        if not job_permissions_found:
            findings.append(AuditFinding(
                line=1,
                severity="WARN",
                message="No 'permissions' block defined at top-level or job-level.",
                fix_suggestion="Add a restrictive top-level permissions block: 'permissions: contents: read'"
            ))

    # 2. Audit Jobs block
    jobs_node = get_node_by_path(root, ["jobs"])
    if not jobs_node or not jobs_node.children:
        findings.append(AuditFinding(
            line=1,
            severity="INFO",
            message="No jobs defined in this workflow.",
            fix_suggestion="Define jobs to execute tasks."
        ))
        return findings

    for job in jobs_node.children:
        job_name = job.key
        
        # Check if job has timeout-minutes
        timeout_node = None
        for child in job.children:
            if child.key == "timeout-minutes":
                timeout_node = child
                break
        
        if not timeout_node:
            findings.append(AuditFinding(
                line=job.line_num,
                severity="WARN",
                message=f"Job '{job_name}' is missing an explicit 'timeout-minutes' setting.",
                fix_suggestion=f"Add 'timeout-minutes: 30' under job '{job_name}' to prevent hung runners from eating budget."
            ))
        else:
            try:
                mins = int(timeout_node.value)
                if mins > 120:
                    findings.append(AuditFinding(
                        line=timeout_node.line_num,
                        severity="INFO",
                        message=f"Job '{job_name}' has a very high timeout value ({mins} minutes).",
                        fix_suggestion="Consider lowering timeout to 30 or 60 minutes."
                    ))
            except ValueError:
                pass

        # Check Matrix strategy
        strategy_node = None
        for child in job.children:
            if child.key == "strategy":
                strategy_node = child
                break

        if strategy_node:
            matrix_node = None
            fail_fast_node = None
            for child in strategy_node.children:
                if child.key == "matrix":
                    matrix_node = child
                elif child.key == "fail-fast":
                    fail_fast_node = child

            if matrix_node:
                # Check for fail-fast setting
                if not fail_fast_node:
                    findings.append(AuditFinding(
                        line=strategy_node.line_num,
                        severity="WARN",
                        message=f"Job '{job_name}' defines a matrix but does not specify 'fail-fast'. It defaults to 'true'.",
                        fix_suggestion="Explicitly set 'fail-fast: false' if you want other matrix configurations to finish executing on failure, or 'fail-fast: true' to save compute."
                    ))

                # Analyze matrix complexity (nested dimensions)
                dimensions = len(matrix_node.children)
                if dimensions > 3:
                    findings.append(AuditFinding(
                        line=matrix_node.line_num,
                        severity="WARN",
                        message=f"Job '{job_name}' has a highly nested matrix ({dimensions} dimensions). This might trigger excessive concurrent jobs.",
                        fix_suggestion="Consider consolidating matrix parameters or limiting concurrency with 'max-parallel'."
                    ))

        # Check Steps inside job
        steps_node = None
        for child in job.children:
            if child.key == "steps":
                steps_node = child
                break

        if steps_node:
            # Track checkouts and setup actions
            checkout_count = 0
            node_setup_has_cache = False
            python_setup_has_cache = False
            go_setup_has_cache = False
            java_setup_has_cache = False
            
            node_setup_used = False
            python_setup_used = False
            go_setup_used = False
            java_setup_used = False

            for step in steps_node.children:
                # Steps are list items starting with '-'
                # Look for 'uses'
                uses_node = None
                with_node = None
                
                # Check step children
                for prop in step.children:
                    if prop.key == "uses":
                        uses_node = prop
                    elif prop.key == "with":
                        with_node = prop

                # If no 'uses' on the direct node, maybe step has properties like name, run, etc.
                # but 'uses' might be nested or direct
                if uses_node:
                    action = uses_node.value
                    
                    # 3. Check for checkout redundancy
                    if "actions/checkout" in action:
                        checkout_count += 1
                        # Check version pinning
                        if not re.search(r'@[a-f0-9]{40}', action):
                            findings.append(AuditFinding(
                                line=uses_node.line_num,
                                severity="INFO",
                                message=f"Action '{action}' is pinned using a mutable tag/version.",
                                fix_suggestion="For strict security, pin actions to a specific commit SHA (e.g. actions/checkout@v4 -> actions/checkout@1d930f8bc0d408f4c33fb3984e7248d28c31379e)."
                            ))

                    # 4. Check setup-node cache
                    if "actions/setup-node" in action:
                        node_setup_used = True
                        if with_node:
                            for param in with_node.children:
                                if param.key == "cache":
                                    node_setup_has_cache = True

                    # 5. Check setup-python cache
                    if "actions/setup-python" in action:
                        python_setup_used = True
                        if with_node:
                            for param in with_node.children:
                                if param.key == "cache":
                                    python_setup_has_cache = True

                    # 6. Check setup-go cache
                    if "actions/setup-go" in action:
                        go_setup_used = True
                        if with_node:
                            # actions/setup-go v4+ defaults to cache true, but let's check
                            for param in with_node.children:
                                if param.key == "cache" and param.value == "false":
                                    pass
                                elif param.key == "cache":
                                    go_setup_has_cache = True
                            if not with_node.children or not any(p.key == "cache" for p in with_node.children):
                                # If setup-go v4 is used, it caches by default. Check version
                                if "@v4" in action or "@v5" in action:
                                    go_setup_has_cache = True

                    # 7. Check setup-java cache
                    if "actions/setup-java" in action:
                        java_setup_used = True
                        if with_node:
                            for param in with_node.children:
                                if param.key == "cache":
                                    java_setup_has_cache = True

            # Flag missing caches
            if node_setup_used and not node_setup_has_cache:
                findings.append(AuditFinding(
                    line=steps_node.line_num,
                    severity="WARN",
                    message=f"Job '{job_name}' uses actions/setup-node but is missing dependency caching.",
                    fix_suggestion="Add 'cache: \"npm\"' (or yarn/pnpm) to the setup-node step 'with' parameters."
                ))
            if python_setup_used and not python_setup_has_cache:
                findings.append(AuditFinding(
                    line=steps_node.line_num,
                    severity="WARN",
                    message=f"Job '{job_name}' uses actions/setup-python but is missing dependency caching.",
                    fix_suggestion="Add 'cache: \"pip\"' (or pipenv/poetry) to the setup-python step 'with' parameters."
                ))
            if go_setup_used and not go_setup_has_cache:
                findings.append(AuditFinding(
                    line=steps_node.line_num,
                    severity="WARN",
                    message=f"Job '{job_name}' uses actions/setup-go but caching is disabled or outdated.",
                    fix_suggestion="Ensure you are using actions/setup-go@v5 and it has cache enabled."
                ))
            if java_setup_used and not java_setup_has_cache:
                findings.append(AuditFinding(
                    line=steps_node.line_num,
                    severity="WARN",
                    message=f"Job '{job_name}' uses actions/setup-java but is missing dependency caching.",
                    fix_suggestion="Add 'cache: \"maven\"' (or gradle) to the setup-java step 'with' parameters."
                ))

            if checkout_count > 1:
                findings.append(AuditFinding(
                    line=steps_node.line_num,
                    severity="INFO",
                    message=f"Job '{job_name}' contains duplicate checkouts ({checkout_count} found).",
                    fix_suggestion="Remove duplicate actions/checkout calls if they are redundant."
                ))

    return findings

def main():
    parser = argparse.ArgumentParser(description="Scan GitHub Actions workflows for matrix/cache/timeout/security optimizations.")
    parser.add_argument("path", help="Path to a workflow YAML file or a directory containing workflows.")
    parser.add_argument("--only-warnings", action="store_true", help="Only show WARN and CRITICAL issues.")
    
    args = parser.parse_args()

    target_files = []
    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    target_files.append(os.path.join(root, file))
    elif os.path.isfile(args.path):
        target_files.append(args.path)
    else:
        print(colorize(f"Error: Path '{args.path}' does not exist.", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    if not target_files:
        print("No GitHub Action workflow YAML files found to scan.")
        sys.exit(0)

    total_findings = 0
    warnings_or_criticals = 0

    print(colorize(f"=== Scanning {len(target_files)} GitHub Actions Workflow File(s) ===", COLOR_BOLD + COLOR_BLUE))
    
    for file in target_files:
        rel_path = os.path.relpath(file)
        findings = audit_workflow(file)
        
        # Filter if requested
        if args.only_warnings:
            findings = [f for f in findings if f.severity in ("WARN", "CRITICAL")]

        if not findings:
            print(f"\n{colorize('[PASS]', COLOR_GREEN)} {rel_path} - No optimization recommendations found.")
            continue

        print(f"\n{colorize('[AUDIT]', COLOR_YELLOW)} {colorize(rel_path, COLOR_BOLD)}")
        for finding in sorted(findings, key=lambda x: x.line):
            severity_str = f"[{finding.severity}]"
            if finding.severity == "CRITICAL":
                severity_str = colorize(severity_str, COLOR_RED)
                warnings_or_criticals += 1
            elif finding.severity == "WARN":
                severity_str = colorize(severity_str, COLOR_YELLOW)
                warnings_or_criticals += 1
            else:
                severity_str = colorize(severity_str, COLOR_BLUE)

            print(f"  Line {finding.line:<4} {severity_str} {finding.message}")
            if finding.fix_suggestion:
                print(f"            {colorize('Suggestion:', COLOR_GREEN)} {finding.fix_suggestion}")
            total_findings += 1

    print("\n" + "=" * 50)
    print(f"Scan complete. Total findings: {total_findings} ({warnings_or_criticals} warnings/criticals).")
    
    if warnings_or_criticals > 0:
        # Exit with a clean zero exit code since this is a reporting tool,
        # but could return non-zero in a strict CI lint mode.
        sys.exit(0)
    sys.exit(0)

if __name__ == "__main__":
    main()
