#!/usr/bin/env python3
"""
venv_relocator - Relocate a virtual environment to a new path

A utility to scan a Python virtual environment directory and update all absolute
path references in configuration files, shebang lines, and activation scripts
to point to the new location.

Usage:
    python tools/venv_relocator.py /path/to/venv [options]

Example:
    python tools/venv_relocator.py my_env --verbose
"""

import argparse
import os
import sys
import re

# File extensions or names to search and replace paths in
TARGET_FILES = [
    # Configuration
    "pyvenv.cfg",
    # Activation scripts (Linux/macOS)
    "activate",
    "activate.csh",
    "activate.fish",
    # Activation scripts (Windows)
    "activate.bat",
    "Activate.ps1",
    # Python script entry points
    "pip",
    "pip3",
    "pip-script.py",
    "easy_install-script.py",
]

# Patterns of files in bin/ or Scripts/ to scan for shebangs
SHEBANG_EXTENSIONS = (".py", "", ".bat", ".ps1")


def detect_old_path(venv_dir):
    """Attempt to detect the old path from pyvenv.cfg or activation scripts."""
    # Check pyvenv.cfg first
    cfg_path = os.path.join(venv_dir, "pyvenv.cfg")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Try to find base-prefix or home
                for line in content.splitlines():
                    if line.startswith("home =") or line.startswith("base-prefix ="):
                        # Just to see if we can get the parent path, but home points to Python executable
                        pass
        except Exception:
            pass

    # Check activation scripts for VIRTUAL_ENV="path"
    activate_paths = [
        os.path.join(venv_dir, "bin", "activate"),
        os.path.join(venv_dir, "Scripts", "activate"),
        os.path.join(venv_dir, "Scripts", "activate.bat"),
    ]
    for act_path in activate_paths:
        if os.path.exists(act_path):
            try:
                with open(act_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # Linux shell: VIRTUAL_ENV="/old/path"
                    m = re.search(r'VIRTUAL_ENV=["\']([^"\']+)["\']', content)
                    if m:
                        return os.path.normpath(m.group(1))
                    # Windows bat: set "VIRTUAL_ENV=path"
                    m = re.search(r'set\s+"VIRTUAL_ENV=([^"]+)"', content)
                    if m:
                        return os.path.normpath(m.group(1))
                    # Windows ps1: $env:VIRTUAL_ENV = "path"
                    m = re.search(r'\$env:VIRTUAL_ENV\s*=\s*["\']([^"\']+)["\']', content)
                    if m:
                        return os.path.normpath(m.group(1))
            except Exception:
                pass
    return None


def scan_and_relocate(venv_dir, old_path, new_path, dry_run=False, verbose=False):
    """Scan the virtual environment and replace paths."""
    print(f"Relocating Virtual Environment: {venv_dir}")
    print(f"  Old Path: {old_path}")
    print(f"  New Path: {new_path}")
    if dry_run:
        print("  *** DRY RUN MODE - No files will be modified ***")

    # Normalize paths for matching both slashes (Windows/Unix compatibility)
    old_path_f = old_path.replace("\\", "/")
    old_path_b = old_path.replace("/", "\\")
    new_path_f = new_path.replace("\\", "/")
    new_path_b = new_path.replace("/", "\\")

    modified_count = 0
    errors_count = 0

    # Locate files in the venv
    files_to_process = []

    # 1. Root configuration files
    cfg_path = os.path.join(venv_dir, "pyvenv.cfg")
    if os.path.exists(cfg_path):
        files_to_process.append(cfg_path)

    # 2. Scripts directories (bin or Scripts)
    scripts_dirs = [os.path.join(venv_dir, "bin"), os.path.join(venv_dir, "Scripts")]
    for s_dir in scripts_dirs:
        if not os.path.exists(s_dir):
            continue
        for root, _, files in os.walk(s_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Filter by name or extension
                name_lower = file.lower()
                ext = os.path.splitext(name_lower)[1]
                if name_lower in TARGET_FILES or ext in SHEBANG_EXTENSIONS:
                    files_to_process.append(file_path)

    # Process files
    for file_path in files_to_process:
        try:
            # Read file content
            with open(file_path, "rb") as f:
                raw_content = f.read()

            try:
                content = raw_content.decode("utf-8")
                is_binary = False
            except UnicodeDecodeError:
                # Skip binary files that are not script templates
                if verbose:
                    print(f"Skipping binary file: {file_path}")
                continue

            # Check if old path exists in file
            has_match = (old_path_f in content) or (old_path_b in content) or (old_path in content)
            
            if has_match:
                if verbose or dry_run:
                    print(f"Match found in: {file_path}")
                
                # Perform replacement for both slash types
                new_content = content
                # Replace double-backslashes first (for JSON/escaped paths)
                new_content = new_content.replace(old_path_b.replace("\\", "\\\\"), new_path_b.replace("\\", "\\\\"))
                # Replace normal slashes
                new_content = new_content.replace(old_path_f, new_path_f)
                new_content = new_content.replace(old_path_b, new_path_b)
                
                if not dry_run:
                    with open(file_path, "w", encoding="utf-8", newline="") as f:
                        f.write(new_content)
                    if verbose:
                        print(f"  Updated successfully.")
                modified_count += 1
            else:
                if verbose:
                    print(f"No match in: {file_path}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            errors_count += 1

    print("\nRelocation Summary:")
    print(f"  Files modified: {modified_count}")
    print(f"  Errors encountered: {errors_count}")
    if dry_run:
        print("  (Dry run complete. No files were actually changed.)")
    else:
        print("  Relocation complete!")
    return modified_count


def main():
    parser = argparse.ArgumentParser(
        description="Relocate a Python virtual environment to a new absolute path"
    )
    parser.add_argument(
        "venv_dir",
        help="Path to the virtual environment folder to relocate"
    )
    parser.add_argument(
        "--old-path",
        help="The old absolute path of the venv. If omitted, the tool attempts to auto-detect it."
    )
    parser.add_argument(
        "--new-path",
        help="The new absolute path of the venv. Defaults to the current absolute path of venv_dir."
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Preview changes without making modifications"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose execution details"
    )

    args = parser.parse_args()

    # Validate venv directory
    venv_dir = os.path.abspath(args.venv_dir)
    if not os.path.isdir(venv_dir):
        print(f"Error: {venv_dir} is not a valid directory.")
        return 1

    # Detect new path (current absolute path of venv_dir)
    new_path = args.new_path
    if not new_path:
        new_path = venv_dir
    else:
        new_path = os.path.abspath(new_path)

    # Detect old path
    old_path = args.old_path
    if not old_path:
        old_path = detect_old_path(venv_dir)
        if not old_path:
            print("Error: Could not auto-detect old path. Please specify it using --old-path.")
            return 1
        print(f"Auto-detected old path: {old_path}")
    else:
        old_path = os.path.normpath(old_path)

    # Run relocation
    scan_and_relocate(venv_dir, old_path, new_path, dry_run=args.dry_run, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
