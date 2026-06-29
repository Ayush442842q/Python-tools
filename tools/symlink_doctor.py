#!/usr/bin/env python3
"""
Symbolic Link Doctor - A tool to scan directories recursively, diagnose broken,
cyclic, or absolute symlinks, and provide interactive utility to fix or convert them.
"""

import argparse
import sys
import os

def check_cycle(link_path):
    """
    Check if a symlink forms a cycle (points back to itself or intermediate links in a loop).
    """
    visited = {os.path.abspath(link_path)}
    curr = link_path
    while os.path.islink(curr):
        try:
            target = os.readlink(curr)
        except Exception:
            break
        
        # Resolve target path relative to the directory of the current symlink
        parent = os.path.dirname(curr)
        resolved = os.path.abspath(os.path.join(parent, target))
        
        if resolved in visited:
            return True
        visited.add(resolved)
        curr = resolved
    return False

def diagnose_symlink(path):
    """
    Diagnose a single symlink.
    Returns a dict with properties:
      - exists: True if target exists
      - is_absolute: True if the target path is absolute
      - target: raw target string
      - resolved_target: absolute path of target
      - has_cycle: True if link forms a cycle
    """
    target = os.readlink(path)
    parent = os.path.dirname(path)
    resolved_target = os.path.abspath(os.path.join(parent, target))
    
    is_absolute = os.path.isabs(target)
    exists = os.path.exists(path)  # os.path.exists follows symlinks
    has_cycle = check_cycle(path)
    
    return {
        "exists": exists,
        "is_absolute": is_absolute,
        "target": target,
        "resolved_target": resolved_target,
        "has_cycle": has_cycle
    }

def scan_directory(directory):
    """
    Scan directory recursively for symlinks.
    Returns:
       dict mapping path to diagnostic info
    """
    issues = {}
    print(f"Scanning directory '{directory}' recursively...")
    
    count = 0
    for root, dirs, files in os.walk(directory):
        # Scan files and directories since both can be symlinks
        for item in files + dirs:
            full_path = os.path.join(root, item)
            # Use lstat to check for symlinks without following them
            try:
                if os.path.islink(full_path):
                    count += 1
                    issues[full_path] = diagnose_symlink(full_path)
            except Exception as e:
                # Handle permission errors or deleted files
                pass
                
    print(f"✓ Scan completed. Found {count} symbolic links.")
    return issues

def fix_absolute_to_relative(path, diag_info):
    """Convert an absolute symlink to a relative one."""
    target = diag_info["target"]
    if not os.path.isabs(target):
        return True
        
    parent = os.path.dirname(path)
    resolved_target = diag_info["resolved_target"]
    
    # Compute relative path
    rel_target = os.path.relpath(resolved_target, parent)
    
    try:
        os.remove(path)
        os.symlink(rel_target, path)
        print(f"✓ Converted to relative: {path} -> {rel_target}")
        return True
    except Exception as e:
        print(f"✗ Failed to convert {path}: {e}", file=sys.stderr)
        return False

def prune_broken_link(path):
    """Delete a broken symlink."""
    try:
        os.remove(path)
        print(f"✓ Deleted broken link: {path}")
        return True
    except Exception as e:
        print(f"✗ Failed to delete {path}: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Symbolic Link Doctor - Scan, diagnose, and fix symlinks."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan recursively (default: current directory)"
    )
    parser.add_argument(
        "--fix-absolute",
        action="store_true",
        help="Automatically convert all absolute symlinks to relative links"
    )
    parser.add_argument(
        "--prune-broken",
        action="store_true",
        help="Automatically delete all broken symlinks"
    )
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    symlinks = scan_directory(args.directory)
    
    # Separate types of issues
    broken = []
    absolute = []
    cyclic = []
    healthy = []
    
    for path, diag in symlinks.items():
        if diag["has_cycle"]:
            cyclic.append((path, diag))
        elif not diag["exists"]:
            broken.append((path, diag))
        elif diag["is_absolute"]:
            absolute.append((path, diag))
        else:
            healthy.append((path, diag))
            
    print("\nDiagnostic Summary:")
    print(f"  Healthy relative links: {len(healthy)}")
    print(f"  Broken links (dead targets): {len(broken)}")
    print(f"  Absolute links (non-portable): {len(absolute)}")
    print(f"  Cyclic links (infinite loop): {len(cyclic)}")
    
    # Print details if there are any issues
    if broken:
        print("\n[!] Broken Links:")
        for path, diag in broken:
            print(f"  - {path} -> {diag['target']} (Target doesn't exist)")
            
    if absolute:
        print("\n[!] Absolute Links (Non-portable):")
        for path, diag in absolute:
            print(f"  - {path} -> {diag['target']}")
            
    if cyclic:
        print("\n[!] Cyclic Links:")
        for path, diag in cyclic:
            print(f"  - {path} -> {diag['target']} (Forms infinite loop)")
            
    # Apply automatic fixes
    if args.prune_broken and broken:
        print("\nPruning broken links...")
        for path, _ in broken:
            prune_broken_link(path)
            
    if args.fix_absolute and absolute:
        print("\nConverting absolute links to relative...")
        for path, diag in absolute:
            fix_absolute_to_relative(path, diag)
            
    # Interactive Wizard if run without fix flags and issues exist
    has_issues = broken or absolute or cyclic
    if not args.prune_broken and not args.fix_absolute and has_issues:
        print("\nRun with --fix-absolute to convert non-portable paths.")
        print("Run with --prune-broken to clean up dead links.")

if __name__ == "__main__":
    main()
