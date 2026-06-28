#!/usr/bin/env python3
"""
Git Ignore Visualizer
Visualizes files and directories ignored by Git in the current repository,
showing exactly which .gitignore rules matched them.
"""

import os
import sys
import argparse
import subprocess
from typing import Dict, List, Tuple, Set

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"

def is_git_repository(path: str) -> bool:
    """Check if the path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip() == "true"
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_git_ignored_files(path: str) -> Dict[str, Tuple[str, int, str]]:
    """
    Get a dictionary of ignored files mapped to their ignore source and pattern.
    Uses 'git status --ignored --porcelain=v1' and 'git check-ignore -v'.
    Returns:
        Dict: { relative_path: (gitignore_file, line_number, pattern) }
    """
    ignored_info = {}
    
    # 1. Get all files that git considers ignored
    try:
        # We run 'git status --ignored --porcelain' to get all ignored items
        status_res = subprocess.run(
            ["git", "status", "--ignored", "--porcelain=v1"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.SubprocessError as e:
        print(f"{RED}Error running git status: {e}{RESET}", file=sys.stderr)
        return {}

    ignored_paths = []
    for line in status_res.stdout.splitlines():
        if line.startswith("!! "):
            # !! means ignored
            ignored_path = line[3:].strip()
            # If the path ends with a slash, it's a directory
            ignored_paths.append(ignored_path)

    if not ignored_paths:
        return {}

    # 2. Query git check-ignore for detailed rules in batches (to avoid command length limits)
    # git check-ignore -v [--stdin]
    try:
        proc = subprocess.Popen(
            ["git", "check-ignore", "-v", "--stdin"],
            cwd=path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input="\n".join(ignored_paths))
    except Exception as e:
        print(f"{RED}Error running git check-ignore: {e}{RESET}", file=sys.stderr)
        return {}

    for line in stdout.splitlines():
        # Output format: <source>:<line>:<pattern> <path>
        # Example: .gitignore:5:*.log temp.log
        if not line.strip():
            continue
        
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        
        source = parts[0]
        line_num_str = parts[1]
        rest = parts[2]
        
        # Parse pattern and path
        # Note: the pattern might contain spaces or the path might contain spaces
        # The separator between pattern and path is a tab or a space, but git uses a tab or space.
        # Typically it's '<pattern>\t<path>'
        if "\t" in rest:
            pattern, file_path = rest.split("\t", 1)
        else:
            # Fallback if no tab is present
            pattern_parts = rest.split(" ", 1)
            if len(pattern_parts) == 2:
                pattern, file_path = pattern_parts
            else:
                pattern = rest
                file_path = rest # Fallback

        try:
            line_num = int(line_num_str)
        except ValueError:
            line_num = 0
            
        ignored_info[file_path.strip()] = (source, line_num, pattern)

    return ignored_info

def build_tree(paths: List[str]) -> dict:
    """Build a nested dictionary tree from a list of relative paths."""
    tree = {}
    for path in paths:
        parts = path.strip("/").split("/")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    return tree

def print_tree(
    tree: dict,
    ignored_info: Dict[str, Tuple[str, int, str]],
    current_dir: str = "",
    prefix: str = "",
    show_rules: bool = True
):
    """Recursively print the directory tree of ignored files."""
    keys = sorted(list(tree.keys()))
    for i, key in enumerate(keys):
        is_last = (i == len(keys) - 1)
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")
        
        # Calculate full relative path
        rel_path = os.path.join(current_dir, key).replace("\\", "/")
        
        # Check if the exact path or its parent directory is ignored
        # A directory might be ignored, in which case everything inside is ignored
        rule_desc = ""
        is_directly_ignored = rel_path in ignored_info
        
        # Check if any parent path is ignored
        parent_ignored = False
        parent_rule = None
        parts = rel_path.split("/")
        for j in range(1, len(parts)):
            parent_path = "/".join(parts[:j])
            if parent_path in ignored_info:
                parent_ignored = True
                parent_rule = ignored_info[parent_path]
                break
        
        if is_directly_ignored:
            source, line_num, pattern = ignored_info[rel_path]
            rule_desc = f" {GRAY}(matched {source}:{line_num} -> '{pattern}'){RESET}"
            name_str = f"{RED}{key}{RESET}"
        elif parent_ignored:
            source, line_num, pattern = parent_rule
            rule_desc = f" {GRAY}(inherited from {source}:{line_num} -> '{pattern}'){RESET}"
            name_str = f"{YELLOW}{key}/{RESET}" if tree[key] else f"{YELLOW}{key}{RESET}"
        else:
            name_str = f"{key}/{RESET}" if tree[key] else f"{key}"
            
        print(f"{prefix}{connector}{name_str}{rule_desc if show_rules else ''}")
        
        if tree[key]:
            print_tree(tree[key], ignored_info, rel_path, child_prefix, show_rules)

def main():
    parser = argparse.ArgumentParser(
        description="Visualize files and directories ignored by Git in the current repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python git_ignore_visualizer.py
  python git_ignore_visualizer.py --no-rules
  python git_ignore_visualizer.py -d /path/to/repo
        """
    )
    parser.add_argument(
        "-d", "--directory",
        default=".",
        help="Path to the Git repository (default: current directory)"
    )
    parser.add_argument(
        "--no-rules",
        action="store_true",
        help="Do not show the matching gitignore rules next to ignored files"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only display a summary of ignored files instead of the full tree"
    )
    
    args = parser.parse_args()
    
    repo_path = os.path.abspath(args.directory)
    
    if not is_git_repository(repo_path):
        print(f"{RED}Error: '{repo_path}' is not a Git repository.{RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{BOLD}{CYAN}Scanning Git repository at:{RESET} {repo_path}")
    
    ignored_info = get_git_ignored_files(repo_path)
    
    if not ignored_info:
        print(f"{GREEN}No files or directories are ignored by Git in this repository!{RESET}")
        return
        
    print(f"{BOLD}{YELLOW}Found {len(ignored_info)} ignored items:{RESET}\n")
    
    if args.summary_only:
        # Group by rule source
        by_source = {}
        for file_path, (source, line, pattern) in ignored_info.items():
            rule = f"{source}:{line} ({pattern})"
            if rule not in by_source:
                by_source[rule] = []
            by_source[rule].append(file_path)
            
        for rule, files in sorted(by_source.items()):
            print(f"{BOLD}{MAGENTA}Rule: {rule}{RESET}")
            for f in sorted(files):
                print(f"  - {f}")
    else:
        # Build and display tree
        tree = build_tree(list(ignored_info.keys()))
        print(f"{BOLD}{BLUE}. (Repository Root){RESET}")
        print_tree(tree, ignored_info, "", "", not args.no_rules)

if __name__ == "__main__":
    main()
