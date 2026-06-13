#!/usr/bin/env python3
"""
Directory Diff & Sync Planner
Recursively compares two directories, identifying:
- Files unique to Directory A
- Files unique to Directory B
- Files in both that differ in size, modified time, or SHA-256 content hash.
Supports flat or tree listings, ignore lists, and sync plan generation.
"""

import argparse
import sys
import os
import hashlib
import fnmatch

# ANSI Color Codes
COLOR_ADDED = "\033[92m"    # Green
COLOR_REMOVED = "\033[91m"  # Red
COLOR_CHANGED = "\033[93m"  # Yellow
COLOR_MUTED = "\033[90m"    # Grey
COLOR_RESET = "\033[0m"


def get_file_hash(filepath):
    """Calculates SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return None


def scan_directory(dir_path, ignore_patterns):
    """Scans directory and returns mapping of rel_path -> {size, mtime, abs_path}."""
    file_map = {}
    for root, dirs, files in os.walk(dir_path):
        # Filter directories in-place for recursion
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in ignore_patterns)]
        
        for file in files:
            if any(fnmatch.fnmatch(file, pat) for pat in ignore_patterns):
                continue
                
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, dir_path)
            
            try:
                stat = os.stat(abs_path)
                file_map[rel_path] = {
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'abs_path': abs_path
                }
            except Exception:
                pass
                
    return file_map


def print_tree(tree_dict, current_dir="", prefix="", color=False):
    """Recursively prints the unified directory tree."""
    keys = sorted(tree_dict.keys())
    for idx, key in enumerate(keys):
        is_last = (idx == len(keys) - 1)
        connector = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "
        
        val = tree_dict[key]
        if isinstance(val, dict) and '_status' not in val:
            # It's a directory
            print(f"{prefix}{connector}{key}/")
            print_tree(val, current_dir, prefix + child_prefix, color)
        else:
            # It's a file
            status = val.get('_status')
            status_char = ""
            clr = ""
            
            if status == 'added':
                status_char = "[+]"
                clr = COLOR_ADDED
            elif status == 'removed':
                status_char = "[-]"
                clr = COLOR_REMOVED
            elif status == 'changed':
                status_char = "[*]"
                clr = COLOR_CHANGED
            else:
                status_char = "[=]"
                clr = COLOR_MUTED
                
            if color:
                print(f"{prefix}{connector}{clr}{status_char} {key}{COLOR_RESET}")
            else:
                print(f"{prefix}{connector}{status_char} {key}")


def build_tree_dict(flat_results):
    """Builds a nested dictionary representation of flat results for tree output."""
    tree = {}
    for rel_path, status in flat_results.items():
        parts = rel_path.split(os.sep)
        curr = tree
        for part in parts[:-1]:
            if part not in curr:
                curr[part] = {}
            curr = curr[part]
        curr[parts[-1]] = {'_status': status}
    return tree


def main():
    parser = argparse.ArgumentParser(
        description="Directory Diff & Sync Planner - Recursively compare and synchronize two directories."
    )
    parser.add_argument('dir_a', help="Directory A (Source/Reference)")
    parser.add_argument('dir_b', help="Directory B (Target to compare/modify)")
    
    parser.add_argument(
        '--hash', '-H', action='store_true',
        help="Compare files by content hash (SHA-256) instead of just size and modification time."
    )
    parser.add_argument(
        '--flat', '-f', action='store_true',
        help="Output results as a flat list instead of a nested tree structure."
    )
    parser.add_argument(
        '--ignore', '-i', action='append', default=[],
        help="Glob pattern to ignore (can be specified multiple times, e.g. -i '*.git' -i '__pycache__')."
    )
    parser.add_argument(
        '--sync-script', '-s',
        help="Generate a sync script (.bat on Windows, .sh on Linux/Mac) to update Directory B to match Directory A."
    )
    parser.add_argument(
        '--color', action='store_true',
        help="Enable colored terminal outputs indicating differences."
    )
    
    args = parser.parse_args()

    if not os.path.isdir(args.dir_a):
        print(f"Error: Path '{args.dir_a}' is not a valid directory.", file=sys.stderr)
        return 1
    if not os.path.isdir(args.dir_b):
        print(f"Error: Path '{args.dir_b}' is not a valid directory.", file=sys.stderr)
        return 1

    # Default ignores
    ignore_patterns = ['.git', '.gitignore', '__pycache__', '*.pyc', '.DS_Store', 'Thumbs.db']
    if args.ignore:
        ignore_patterns.extend(args.ignore)

    print(f"Scanning Directory A: {args.dir_a} ...")
    files_a = scan_directory(args.dir_a, ignore_patterns)
    print(f"Scanning Directory B: {args.dir_b} ...")
    files_b = scan_directory(args.dir_b, ignore_patterns)

    all_paths = set(files_a.keys()) | set(files_b.keys())
    
    results = {}
    stats = {'added': 0, 'removed': 0, 'changed': 0, 'identical': 0}
    sync_actions = []

    for path in all_paths:
        if path in files_a and path not in files_b:
            results[path] = 'added' # Unique to A (needs copying to B)
            stats['added'] += 1
            sync_actions.append(('copy', path))
        elif path not in files_a and path in files_b:
            results[path] = 'removed' # Unique to B (needs deletion from B)
            stats['removed'] += 1
            sync_actions.append(('delete', path))
        else:
            # In both - check if different
            file_info_a = files_a[path]
            file_info_b = files_b[path]
            
            is_different = False
            if args.hash:
                hash_a = get_file_hash(file_info_a['abs_path'])
                hash_b = get_file_hash(file_info_b['abs_path'])
                is_different = (hash_a != hash_b)
            else:
                # Compare sizes and mtimes
                # Check size first, then mtime (within a small threshold, e.g. 1 second)
                size_diff = (file_info_a['size'] != file_info_b['size'])
                mtime_diff = abs(file_info_a['mtime'] - file_info_b['mtime']) > 1.0
                is_different = size_diff or mtime_diff
                
            if is_different:
                results[path] = 'changed'
                stats['changed'] += 1
                sync_actions.append(('copy', path))
            else:
                results[path] = 'identical'
                stats['identical'] += 1

    # Print comparison results
    print("\n" + "=" * 45)
    print("         DIRECTORY COMPARISON RESULTS")
    print("=" * 45)
    print(f"Legend:  [+] Unique to A  [-] Unique to B  [*] Modified  [=] Identical")
    print("-" * 45)

    if args.flat:
        for path in sorted(results.keys()):
            status = results[path]
            if status == 'identical':
                if args.color:
                    print(f"{COLOR_MUTED}[=] {path}{COLOR_RESET}")
                else:
                    print(f"[=] {path}")
            elif status == 'added':
                if args.color:
                    print(f"{COLOR_ADDED}[+] {path}{COLOR_RESET}")
                else:
                    print(f"[+] {path}")
            elif status == 'removed':
                if args.color:
                    print(f"{COLOR_REMOVED}[-] {path}{COLOR_RESET}")
                else:
                    print(f"[-] {path}")
            elif status == 'changed':
                if args.color:
                    print(f"{COLOR_CHANGED}[*] {path}{COLOR_RESET}")
                else:
                    print(f"[*] {path}")
    else:
        tree = build_tree_dict(results)
        print_tree(tree, color=args.color)

    # Print Summary Statistics
    print("-" * 45)
    print(f"Summary Statistics:")
    print(f"  Identical Files:   {stats['identical']}")
    print(f"  Modified Files:    {stats['changed']}")
    print(f"  Unique to Dir A:   {stats['added']}")
    print(f"  Unique to Dir B:   {stats['removed']}")
    print(f"  Total Scanned:     {len(all_paths)}")
    print("=" * 45 + "\n")

    # Generate Sync Script
    if args.sync_script and sync_actions:
        is_windows = sys.platform.startswith('win')
        script_lines = []
        
        if is_windows:
            script_lines.append("@echo off")
            script_lines.append(f"echo Synchronizing Directory B ({args.dir_b}) to match Directory A ({args.dir_a})...")
            
            for action, path in sync_actions:
                abs_a = os.path.join(args.dir_a, path)
                abs_b = os.path.join(args.dir_b, path)
                
                if action == 'copy':
                    # Create directory path if it doesn't exist
                    dir_b = os.path.dirname(abs_b)
                    script_lines.append(f'if not exist "{dir_b}" mkdir "{dir_b}"')
                    script_lines.append(f'copy /Y "{abs_a}" "{abs_b}" >nul')
                elif action == 'delete':
                    script_lines.append(f'del /F /Q "{abs_b}" >nul')
                    
            script_lines.append("echo Sync completed successfully!")
        else:
            script_lines.append("#!/bin/bash")
            script_lines.append(f'echo "Synchronizing Directory B ({args.dir_b}) to match Directory A ({args.dir_a})..."')
            
            for action, path in sync_actions:
                abs_a = os.path.join(args.dir_a, path)
                abs_b = os.path.join(args.dir_b, path)
                
                if action == 'copy':
                    dir_b = os.path.dirname(abs_b)
                    script_lines.append(f'mkdir -p "{dir_b}"')
                    script_lines.append(f'cp -f "{abs_a}" "{abs_b}"')
                elif action == 'delete':
                    script_lines.append(f'rm -f "{abs_b}"')
                    
            script_lines.append('echo "Sync completed successfully!"')

        try:
            with open(args.sync_script, 'w', encoding='utf-8') as f:
                f.write("\n".join(script_lines) + "\n")
            print(f"Synchronization script saved to '{args.sync_script}'")
            if not is_windows:
                # Try making the script executable on Unix systems
                try:
                    os.chmod(args.sync_script, 0o755)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error writing synchronization script: {e}", file=sys.stderr)
            return 1
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
