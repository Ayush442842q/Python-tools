#!/usr/bin/env python3
"""
Dockerfile Linter & Best Practices Checker
Parses Dockerfiles and checks them against common best practices,
such as unpinned base image versions, missing package manager cleanups,
running as root, and inefficient RUN statement layering.
"""

import sys
import os
import re
import argparse

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"

def supports_color():
    """Returns True if the terminal supports colored output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

# Disable colors if not supported
if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_YELLOW = ""
    COLOR_GREEN = ""
    COLOR_CYAN = ""

class Finding:
    def __init__(self, severity, line_no, instruction, rule_id, message, recommendation):
        self.severity = severity  # 'ERROR', 'WARNING', 'INFO'
        self.line_no = line_no
        self.instruction = instruction
        self.rule_id = rule_id
        self.message = message
        self.recommendation = recommendation

    def __str__(self):
        sev_color = COLOR_RED if self.severity == "ERROR" else (COLOR_YELLOW if self.severity == "WARNING" else COLOR_CYAN)
        line_str = f"Line {self.line_no}: " if self.line_no else ""
        inst_str = f"[{self.instruction}] " if self.instruction else ""
        return (
            f"{sev_color}{COLOR_BOLD}[{self.severity}]{COLOR_RESET} "
            f"{COLOR_BOLD}{line_str}{inst_str}{self.rule_id}{COLOR_RESET}\n"
            f"  Description: {self.message}\n"
            f"  Fix:         {COLOR_GREEN}{self.recommendation}{COLOR_RESET}\n"
        )

def lint_dockerfile(content):
    findings = []
    
    # Parse multi-line instructions consolidated by backslashes
    raw_lines = content.splitlines()
    logical_lines = []
    
    current_line = ""
    start_line_no = 1
    
    for idx, line in enumerate(raw_lines):
        line_no = idx + 1
        stripped = line.strip()
        
        if not stripped:
            continue
            
        if stripped.startswith("#"):
            continue
            
        if not current_line:
            start_line_no = line_no
            
        if stripped.endswith("\\"):
            current_line += stripped[:-1] + " "
        else:
            current_line += stripped
            logical_lines.append((start_line_no, current_line))
            current_line = ""
            
    if current_line:
        logical_lines.append((start_line_no, current_line))

    # Context variables for checking
    has_user = False
    has_workdir = False
    from_count = 0
    run_instructions = []
    
    for line_no, cmd_str in logical_lines:
        # Split command and arguments
        parts = cmd_str.split(None, 1)
        if not parts:
            continue
            
        instruction = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""
        
        if instruction == "FROM":
            from_count += 1
            # Check for unpinned versions or 'latest'
            if "AS" in args.upper():
                image_part = args.split(None, 1)[0]
            else:
                image_part = args
                
            if ":" not in image_part:
                findings.append(Finding(
                    "WARNING", line_no, "FROM", "DL3006",
                    "Base image version is not pinned. Implying 'latest' tag.",
                    "Specify a specific tag (e.g., 'python:3.9-slim' or SHA digest)."
                ))
            elif image_part.endswith(":latest"):
                findings.append(Finding(
                    "WARNING", line_no, "FROM", "DL3007",
                    "Avoid using the 'latest' tag for base images.",
                    "Use a stable, specific tag (e.g., 'python:3.9-slim' instead of 'python:latest')."
                ))
                
        elif instruction == "RUN":
            run_instructions.append((line_no, args))
            
            # Check apt-get commands
            if "apt-get" in args:
                # Check that update is combined with install
                if "apt-get update" in args and "apt-get install" not in args:
                    findings.append(Finding(
                        "ERROR", line_no, "RUN", "DL3009",
                        "Using 'apt-get update' in a separate RUN block caches intermediate layers without installation.",
                        "Combine 'apt-get update && apt-get install -y <packages>' in a single RUN block."
                    ))
                
                # Check for cleanup
                if "apt-get install" in args and "rm -rf /var/lib/apt/lists/*" not in args:
                    findings.append(Finding(
                        "WARNING", line_no, "RUN", "DL3015",
                        "Missing cleaning of apt caches to reduce Docker image size.",
                        "Add '&& rm -rf /var/lib/apt/lists/*' at the end of the RUN block."
                    ))
                
                # Check if -y flag is missing
                if "apt-get install" in args and not re.search(r"-y\b|--yes\b", args):
                    findings.append(Finding(
                        "ERROR", line_no, "RUN", "DL3014",
                        "Missing '-y' or '--yes' flag in interactive apt-get installation.",
                        "Add '-y' flag to the apt-get command to run non-interactively."
                    ))

            # Check sudo usage
            if "sudo " in args:
                findings.append(Finding(
                    "ERROR", line_no, "RUN", "DL3004",
                    "Avoid using 'sudo' inside container RUN statements.",
                    "Remove 'sudo'. Docker commands are run as root by default, or use USER instructions."
                ))

            # Check pip install no-cache-dir
            if "pip install" in args and "--no-cache-dir" not in args:
                findings.append(Finding(
                    "WARNING", line_no, "RUN", "DL3013",
                    "Missing '--no-cache-dir' in pip installation command.",
                    "Add '--no-cache-dir' to the pip install command (e.g., 'pip install --no-cache-dir <package>')."
                ))

            # Check npm install cache clean
            if "npm install" in args and not ("npm cache clean" in args or "--production" in args or "npm ci" in args):
                findings.append(Finding(
                    "INFO", line_no, "RUN", "DL3016",
                    "No npm cache cleaning or production flag found.",
                    "Consider cleaning npm cache with 'npm cache clean --force' or using '--production' flag."
                ))

        elif instruction == "USER":
            has_user = True
            
        elif instruction == "WORKDIR":
            has_workdir = True
            
        elif instruction == "ADD":
            # Check ADD vs COPY
            # ADD should only be used for remote URLs or tar files, otherwise COPY
            is_tar_or_url = re.search(r"\.(tar|tar\.gz|tgz|tar\.xz|tar\.bz2|zip)\b", args) or args.startswith("http://") or args.startswith("https://")
            if not is_tar_or_url:
                findings.append(Finding(
                    "WARNING", line_no, "ADD", "DL3020",
                    "Using ADD for local files/directories instead of COPY.",
                    "Use COPY instruction instead of ADD (unless adding a remote URL or auto-extracting a local tarball)."
                ))

        elif instruction == "EXPOSE":
            # Check port formats
            ports = args.split()
            for port in ports:
                # Remove optional protocol /tcp or /udp
                port_num = port.split("/")[0]
                if not port_num.isdigit():
                    findings.append(Finding(
                        "ERROR", line_no, "EXPOSE", "DL3011",
                        f"Invalid port format '{port}' in EXPOSE instruction.",
                        "Provide valid integer ports (e.g., 'EXPOSE 8080' or 'EXPOSE 80/tcp')."
                    ))

    # Multi-instruction validations
    if len(run_instructions) > 10:
        findings.append(Finding(
            "INFO", None, "RUN", "DL3000",
            f"High number of RUN instructions ({len(run_instructions)}) creates unnecessary layers.",
            "Combine sequential RUN statements using '&&' where logical."
        ))

    if not has_user:
        findings.append(Finding(
            "WARNING", None, "USER", "DL3002",
            "No USER instruction found. Container runs as root by default.",
            "Create a non-root system user and switch to it using 'USER <username>'."
        ))

    if not has_workdir:
        findings.append(Finding(
            "INFO", None, "WORKDIR", "DL3003",
            "No WORKDIR instruction found. Standard defaults to root directory '/'.",
            "Establish a clear application root with 'WORKDIR /app' or similar."
        ))

    return findings

def main():
    parser = argparse.ArgumentParser(
        description="Dockerfile Linter & Best Practices Checker - Analyze Dockerfiles for size, security, and readability issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("dockerfile", nargs="?", default="Dockerfile", help="Path to Dockerfile (default: 'Dockerfile')")
    parser.add_argument("--ignore", "-i", metavar="RULES", help="Comma-separated list of rule IDs to ignore (e.g., 'DL3002,DL3015')")
    parser.add_argument("--strict", "-s", action="store_true", help="Fail and return non-zero exit code on WARNING/INFO findings (normally only errors cause non-zero exit)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dockerfile):
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} File '{args.dockerfile}' not found.", file=sys.stderr)
        return 1
        
    if os.path.isdir(args.dockerfile):
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} '{args.dockerfile}' is a directory.", file=sys.stderr)
        return 1

    try:
        with open(args.dockerfile, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}{COLOR_BOLD}Error:{COLOR_RESET} Could not read file: {e}", file=sys.stderr)
        return 1

    print(f"Linting {COLOR_BOLD}{args.dockerfile}{COLOR_RESET}...\n")
    
    findings = lint_dockerfile(content)
    
    # Filter ignored rules
    if args.ignore:
        ignored_rules = {r.strip().upper() for r in args.ignore.split(",")}
        findings = [f for f in findings if f.rule_id not in ignored_rules]

    if not findings:
        print(f"{COLOR_GREEN}{COLOR_BOLD}Success!{COLOR_RESET} No issues found. Your Dockerfile adheres to best practices.")
        return 0

    # Sort findings by line number, then severity
    findings.sort(key=lambda x: (x.line_no or 999999, ["ERROR", "WARNING", "INFO"].index(x.severity)))

    errors = 0
    warnings = 0
    infos = 0

    for finding in findings:
        print(finding)
        if finding.severity == "ERROR":
            errors += 1
        elif finding.severity == "WARNING":
            warnings += 1
        elif finding.severity == "INFO":
            infos += 1

    summary_str = f"Summary: {COLOR_BOLD}{len(findings)} findings{COLOR_RESET} ("
    summary_parts = []
    if errors:
        summary_parts.append(f"{COLOR_RED}{errors} Errors{COLOR_RESET}")
    else:
        summary_parts.append("0 Errors")
        
    if warnings:
        summary_parts.append(f"{COLOR_YELLOW}{warnings} Warnings{COLOR_RESET}")
    else:
        summary_parts.append("0 Warnings")
        
    if infos:
        summary_parts.append(f"{COLOR_CYAN}{infos} Info{COLOR_RESET}")
    else:
        summary_parts.append("0 Info")
        
    summary_str += ", ".join(summary_parts) + ")"
    print(summary_str)

    if errors > 0:
        return 2
    if args.strict and (warnings > 0 or infos > 0):
        return 3
    return 0

if __name__ == "__main__":
    sys.exit(main())
