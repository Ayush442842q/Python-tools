#!/usr/bin/env python3
"""Environment File Security Linter

Lint .env and configuration files for security vulnerabilities, hardcoded secrets,
weak defaults, duplicate keys, unquoted spaces, and improper naming conventions.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

# Common secret patterns
SECRET_PATTERNS = [
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID"),
    (re.compile(r'EAACEdEose0cBA[0-9A-Za-z]+'), "Facebook Access Token"),
    (re.compile(r'ghp_[0-9a-zA-Z]{36}'), "GitHub Personal Access Token"),
    (re.compile(r'xox[baprs]-[0-9a-zA-Z]{10,48}'), "Slack Token"),
    (re.compile(r'sk_live_[0-9a-zA-Z]{24}'), "Stripe Live API Key"),
    (re.compile(r'-----BEGIN (RSA|EC|PGP|PRIVATE) KEY-----'), "Private Key Block"),
    (re.compile(r'postgres://[^:]+:[^@]+@'), "PostgreSQL Connection String with Password"),
    (re.compile(r'mysql://[^:]+:[^@]+@'), "MySQL Connection String with Password"),
    (re.compile(r'mongodb(\+srv)?://[^:]+:[^@]+@'), "MongoDB Connection String with Password"),
]

WEAK_DEFAULTS = {
    "SECRET_KEY": {"secret", "changeme", "123456", "password", "key", "default"},
    "JWT_SECRET": {"secret", "changeme", "jwt_secret", "123456"},
    "DATABASE_URL": {"postgres://user:pass@localhost/db", "mysql://root:root@localhost/db"},
    "PASSWORD": {"admin", "password", "root", "123456", "secret"},
    "DB_PASSWORD": {"admin", "password", "root", "123456", "secret"},
}


class EnvLinter:
    def __init__(self):
        self.seen_keys: Dict[str, int] = {}

    def lint_file(self, filepath: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        self.seen_keys.clear()

        try:
            lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            return [{
                "file": str(filepath),
                "line": 1,
                "severity": "HIGH",
                "issue": "Read Error",
                "key": "N/A",
                "message": f"Cannot read file: {e}"
            }]

        is_example_file = ".example" in filepath.name or ".template" in filepath.name

        for idx, line in enumerate(lines, start=1):
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue

            if "=" not in raw_line:
                findings.append({
                    "file": str(filepath),
                    "line": idx,
                    "severity": "LOW",
                    "issue": "Malformed Line",
                    "key": raw_line,
                    "message": "Line does not contain an '=' assignment operator."
                })
                continue

            parts = raw_line.split("=", 1)
            key = parts[0].strip()
            value = parts[1].strip()

            # 1. Duplicate key check
            if key in self.seen_keys:
                findings.append({
                    "file": str(filepath),
                    "line": idx,
                    "severity": "MEDIUM",
                    "issue": "Duplicate Key",
                    "key": key,
                    "message": f"Key '{key}' was previously defined on line {self.seen_keys[key]}."
                })
            else:
                self.seen_keys[key] = idx

            # 2. Casing check
            if not key.isupper() and not key.startswith("#"):
                findings.append({
                    "file": str(filepath),
                    "line": idx,
                    "severity": "LOW",
                    "issue": "Non-Uppercase Key",
                    "key": key,
                    "message": f"Environment key '{key}' should be uppercase."
                })

            # 3. Unquoted value with spaces
            if " " in value and not (value.startswith('"') and value.endswith('"')) and not (value.startswith("'") and value.endswith("'")):
                findings.append({
                    "file": str(filepath),
                    "line": idx,
                    "severity": "LOW",
                    "issue": "Unquoted Value With Spaces",
                    "key": key,
                    "message": f"Value for '{key}' contains spaces but is not quoted."
                })

            # 4. Check secret patterns (if not an example template file)
            if not is_example_file:
                for pattern, secret_type in SECRET_PATTERNS:
                    if pattern.search(value):
                        findings.append({
                            "file": str(filepath),
                            "line": idx,
                            "severity": "HIGH",
                            "issue": "Hardcoded Secret",
                            "key": key,
                            "message": f"Detected hardcoded {secret_type} in value."
                        })
                        break

            # 5. Check weak defaults
            val_unquoted = value.strip("'\"").lower()
            if key.upper() in WEAK_DEFAULTS:
                weak_set = WEAK_DEFAULTS[key.upper()]
                if val_unquoted in weak_set:
                    findings.append({
                        "file": str(filepath),
                        "line": idx,
                        "severity": "HIGH" if not is_example_file else "MEDIUM",
                        "issue": "Weak Default Secret",
                        "key": key,
                        "message": f"Insecure or default value '{value}' used for sensitive key '{key}'."
                    })

            # 6. Check production debug mode
            if key.upper() == "DEBUG" and val_unquoted in ("true", "1", "yes") and not is_example_file:
                findings.append({
                    "file": str(filepath),
                    "line": idx,
                    "severity": "MEDIUM",
                    "issue": "Debug Mode Enabled",
                    "key": key,
                    "message": "DEBUG mode is set to True, which may expose verbose stack traces."
                })

        return findings


def run_tests():
    """Self-test routine for env_file_security_linter."""
    sample_env = """
# Sample Env
debug=true
SECRET_KEY=secret
DB_PASSWORD=123456
API_TOKEN=AKIAIOSFODNN7EXAMPLE
DUPLICATE_VAR=1
DUPLICATE_VAR=2
UNQUOTED_VAL=hello world
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write(sample_env)
        tmp_name = f.name

    try:
        linter = EnvLinter()
        results = linter.lint_file(Path(tmp_name))
        assert any(r["issue"] == "Hardcoded Secret" for r in results), "Failed to detect hardcoded AWS key"
        assert any(r["issue"] == "Weak Default Secret" for r in results), "Failed to detect weak default password"
        assert any(r["issue"] == "Duplicate Key" for r in results), "Failed to detect duplicate key"
        assert any(r["issue"] == "Non-Uppercase Key" for r in results), "Failed to detect lowercase key"
        print(f"{COLOR_GREEN}All tests passed successfully!{COLOR_RESET}")
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def main():
    parser = argparse.ArgumentParser(
        description="Lint .env files for security risks, weak defaults, and format anomalies."
    )
    parser.add_argument("target", nargs="?", default=".", help="File or directory path to analyze (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--severity", choices=["HIGH", "MEDIUM", "LOW"], help="Filter findings by minimum severity")
    parser.add_argument("--test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return 0

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{target_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        return 1

    env_files: List[Path] = []
    if target_path.is_file():
        env_files.append(target_path)
    elif target_path.is_dir():
        for p in target_path.rglob("*"):
            if p.is_file() and (".env" in p.name or p.name.endswith(".env")):
                if not any(part in ("venv", "node_modules", ".git") for part in p.parts):
                    env_files.append(p)

    linter = EnvLinter()
    all_findings: List[Dict[str, Any]] = []
    for fpath in env_files:
        all_findings.extend(linter.lint_file(fpath))

    # Severity ordering
    severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if args.severity:
        min_lvl = severity_order[args.severity]
        all_findings = [f for f in all_findings if severity_order.get(f["severity"], 0) >= min_lvl]

    if args.json:
        print(json.dumps(all_findings, indent=2))
        return 0

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Environment File Security Linter ==={COLOR_RESET}")
    print(f"Scanned {len(env_files)} file(s). Found {len(all_findings)} issue(s).\n")

    if not all_findings:
        print(f"{COLOR_GREEN}No security issues or bad practices detected!{COLOR_RESET}\n")
        return 0

    for item in all_findings:
        sev = item["severity"]
        sev_color = COLOR_RED if sev == "HIGH" else (COLOR_YELLOW if sev == "MEDIUM" else COLOR_GREY)

        print(f"{COLOR_BOLD}{item['file']}:{item['line']}{COLOR_RESET} [{sev_color}{sev}{COLOR_RESET}] Key: '{COLOR_BOLD}{item['key']}{COLOR_RESET}'")
        print(f"  ▸ {COLOR_CYAN}{item['issue']}{COLOR_RESET}: {item['message']}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
