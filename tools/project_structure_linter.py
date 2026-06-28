#!/usr/bin/env python3
"""
Project Structure Linter - Validate directory layouts, naming conventions,
and file rules against a custom schema or built-in standard templates.
"""

import os
import sys
import re
import json
import argparse
import fnmatch
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
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

# Default rules for standard Python projects
DEFAULT_RULES = {
    "project_name": "Standard Python Project Structure",
    "required_files": [
        "README.md",
        "LICENSE"
    ],
    "required_directories": [
        "tools"
    ],
    "forbidden_files": [
        "*.pyc",
        "__pycache__",
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
        "secret*.json",
        "*.tmp",
        "*backup*"
    ],
    "naming_conventions": {
        "python_files": "^[a-z0-9_]+\\.py$",
        "markdown_files": "^[A-Z0-9_]+\\.md$",
        "directories": "^[a-z0-9_.-]+$"
    },
    "max_file_size_kb": {
        "*.py": 500,
        "*.json": 1000
    },
    "ignored_directories": [
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "build",
        "dist",
        "*.egg-info"
    ]
}

class ProjectLinter:
    def __init__(self, root_dir, config_path=None):
        self.root_dir = Path(root_dir).resolve()
        self.config_path = config_path
        self.rules = DEFAULT_RULES.copy()
        self.errors = []
        self.warnings = []
        self.passed_checks = 0
        
        if config_path:
            self.load_config()

    def load_config(self):
        c_red = get_color('red')
        c_reset = get_color('reset')
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_rules = json.load(f)
                # Merge loaded rules into DEFAULT_RULES
                for key, val in loaded_rules.items():
                    if isinstance(val, dict) and key in self.rules:
                        self.rules[key].update(val)
                    else:
                        self.rules[key] = val
        except Exception as e:
            print(f"{c_red}Error loading configuration file: {e}. Using defaults.{c_reset}")

    def is_ignored(self, path):
        """Check if path matches any ignored directory pattern."""
        relative_path = path.relative_to(self.root_dir)
        parts = relative_path.parts
        for part in parts:
            for ignore_pat in self.rules.get("ignored_directories", []):
                if fnmatch.fnmatch(part, ignore_pat):
                    return True
        return False

    def check_required_files(self):
        """Verify that all required files exist in root."""
        for req_file in self.rules.get("required_files", []):
            file_path = self.root_dir / req_file
            if not file_path.exists() or not file_path.is_file():
                self.errors.append(f"Required file is missing: '{req_file}'")
            else:
                self.passed_checks += 1

    def check_required_directories(self):
        """Verify that all required directories exist in root."""
        for req_dir in self.rules.get("required_directories", []):
            dir_path = self.root_dir / req_dir
            if not dir_path.exists() or not dir_path.is_dir():
                self.errors.append(f"Required directory is missing: '{req_dir}'")
            else:
                self.passed_checks += 1

    def scan_files(self):
        """Recursively scan files and folders for rules."""
        naming_conventions = self.rules.get("naming_conventions", {})
        forbidden_patterns = self.rules.get("forbidden_files", [])
        size_limits = self.rules.get("max_file_size_kb", {})

        # Compile naming regexes
        compiled_regexes = {}
        for name_key, pattern in naming_conventions.items():
            try:
                compiled_regexes[name_key] = re.compile(pattern)
            except re.error as e:
                self.warnings.append(f"Invalid regex for naming convention '{name_key}': {e}")

        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)
            
            # Skip ignored directories
            if self.is_ignored(root_path):
                continue

            # Check directory naming
            for d in dirs:
                dir_full_path = root_path / d
                if self.is_ignored(dir_full_path):
                    continue

                self.passed_checks += 1
                dir_pattern = naming_conventions.get("directories")
                if dir_pattern:
                    if not re.match(dir_pattern, d):
                        self.errors.append(
                            f"Directory naming violation: '{dir_full_path.relative_to(self.root_dir)}' "
                            f"does not match directory rule '{dir_pattern}'"
                        )

            # Check files
            for f in files:
                file_full_path = root_path / f
                rel_file_path = file_full_path.relative_to(self.root_dir)

                # 1. Check forbidden files
                is_forbidden = False
                for forbidden_pat in forbidden_patterns:
                    if fnmatch.fnmatch(f, forbidden_pat) or fnmatch.fnmatch(str(rel_file_path).replace('\\', '/'), forbidden_pat):
                        self.errors.append(f"Forbidden file found: '{rel_file_path}' (matched rule '{forbidden_pat}')")
                        is_forbidden = True
                        break

                if is_forbidden:
                    continue

                self.passed_checks += 1

                # 2. Check file size limits
                try:
                    size_kb = file_full_path.stat().st_size / 1024.0
                    for size_pat, limit in size_limits.items():
                        if fnmatch.fnmatch(f, size_pat):
                            if size_kb > limit:
                                self.errors.append(
                                    f"File too large: '{rel_file_path}' is {size_kb:.1f}KB (max allowed is {limit}KB)"
                                )
                except Exception as e:
                    self.warnings.append(f"Could not read size of file '{rel_file_path}': {e}")

                # 3. Check naming conventions based on file extension
                if f.endswith('.py') and "python_files" in compiled_regexes:
                    if not compiled_regexes["python_files"].match(f):
                        self.errors.append(
                            f"Python file naming violation: '{rel_file_path}' "
                            f"does not match rule '{naming_conventions['python_files']}'"
                        )
                elif f.endswith('.md') and "markdown_files" in compiled_regexes:
                    if not compiled_regexes["markdown_files"].match(f):
                        self.errors.append(
                            f"Markdown file naming violation: '{rel_file_path}' "
                            f"does not match rule '{naming_conventions['markdown_files']}'"
                        )

    def run(self):
        self.check_required_files()
        self.check_required_directories()
        self.scan_files()

        c_red = get_color('red')
        c_green = get_color('green')
        c_yellow = get_color('yellow')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        print(f"\n{c_bold}Project Structure Linter: {self.rules['project_name']}{c_reset}")
        print("=" * 65)
        print(f"Target Directory:  {self.root_dir}")
        print(f"Total Rules Run:   {self.passed_checks + len(self.errors)}")
        print("-" * 65)

        if self.warnings:
            print(f"\n{c_yellow}Warnings:{c_reset}")
            for w in self.warnings:
                print(f"  [WARN] {w}")

        if self.errors:
            print(f"\n{c_red}Lint Violations ({len(self.errors)}):{c_reset}")
            for e in self.errors:
                print(f"  {c_red}✗{c_reset} {e}")
            print("\n" + "=" * 65)
            print(f"{c_red}STATUS: FAILED ({len(self.errors)} errors, {len(self.warnings)} warnings){c_reset}")
            return False
        else:
            print(f"\n{c_green}✓ Perfect! All structural checks passed successfully.{c_reset}")
            print("\n" + "=" * 65)
            print(f"{c_green}STATUS: SUCCESS{c_reset}")
            return True

def generate_sample_config(filepath):
    c_green = get_color('green')
    c_reset = get_color('reset')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_RULES, f, indent=4)
        print(f"{c_green}Sample structure config generated at '{filepath}'{c_reset}")
        return True
    except Exception as e:
        print(f"Error generating sample config: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Validate directory layout and structure naming conventions")
    parser.add_argument("directory", nargs="?", default=".", help="Root directory to check (default: current directory)")
    parser.add_argument("-c", "--config", help="Path to custom configuration JSON file")
    parser.add_argument("--generate-config", help="Generate a sample configuration JSON file at target path")
    args = parser.parse_args()

    if args.generate_config:
        success = generate_sample_config(args.generate_config)
        sys.exit(0 if success else 1)

    linter = ProjectLinter(args.directory, args.config)
    success = linter.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
