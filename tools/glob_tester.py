#!/usr/bin/env python3
"""
Glob Tester - Validate and inspect glob patterns against the local filesystem or custom path lists.
"""

import sys
import argparse
import fnmatch
from pathlib import Path

def test_on_filesystem(pattern, root_dir, files_only=False, dirs_only=False, case_sensitive=False):
    """Scan local directory structure and find paths matching the glob pattern."""
    root = Path(root_dir).resolve()
    if not root.is_dir():
        print(f"Error: Directory '{root_dir}' does not exist.")
        return []
        
    matches = []
    
    # If case sensitivity is required, we use standard pathlib matching which is platform-dependent by default.
    # Otherwise, we simulate matching.
    # Actually, pathlib.Path.glob is great for filesystem scanning.
    try:
        # Match all files recursively or normally based on pattern
        raw_matches = list(root.glob(pattern))
    except Exception as e:
        print(f"Invalid glob pattern or access error: {e}")
        return []
        
    for p in raw_matches:
        # Check filters
        if files_only and not p.is_file():
            continue
        if dirs_only and not p.is_dir():
            continue
            
        # Format relative to root for cleaner output
        try:
            rel_path = p.relative_to(root)
            matches.append(str(rel_path))
        except ValueError:
            matches.append(str(p))
            
    matches.sort()
    return matches

def test_on_custom_list(pattern, path_list, case_sensitive=False):
    """Test glob pattern against a static list of strings/paths using fnmatch."""
    matches = []
    # fnmatch is case-insensitive on Windows, case-sensitive on Unix.
    # We can force behavior by translating patterns or using case-insensitive comparison.
    for path_str in path_list:
        path_str = path_str.strip()
        if not path_str:
            continue
            
        is_match = False
        if case_sensitive:
            is_match = fnmatch.fnmatchcase(path_str, pattern)
        else:
            is_match = fnmatch.fnmatch(path_str.lower(), pattern.lower())
            
        if is_match:
            matches.append(path_str)
            
    matches.sort()
    return matches

def interactive_loop(root_dir, custom_paths=None, files_only=False, dirs_only=False, case_sensitive=False):
    print("=" * 60)
    print(" Glob Tester - Interactive Mode")
    if custom_paths:
        print(f" Testing patterns against {len(custom_paths)} simulated paths.")
    else:
        print(f" Testing patterns against directory: {Path(root_dir).resolve()}")
    print(" Type 'exit' or 'quit' or press Ctrl+C to stop.")
    print("=" * 60)
    
    while True:
        try:
            pattern = input("\nEnter glob pattern (e.g. **/*.py): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
        if pattern.lower() in ('exit', 'quit'):
            break
            
        if not pattern:
            continue
            
        if custom_paths:
            matches = test_on_custom_list(pattern, custom_paths, case_sensitive)
        else:
            matches = test_on_filesystem(pattern, root_dir, files_only, dirs_only, case_sensitive)
            
        print(f"Found {len(matches)} match(es):")
        for m in matches[:100]:
            print(f"  - {m}")
        if len(matches) > 100:
            print(f"  ... and {len(matches) - 100} more matches omitted.")

def main():
    parser = argparse.ArgumentParser(
        description="Glob Tester - Validate glob patterns against local directories or path list files."
    )
    parser.add_argument(
        "pattern", nargs="?", default=None,
        help="Glob pattern to test (if omitted, starts interactive mode)"
    )
    parser.add_argument(
        "-r", "--root", default=".",
        help="Root directory for filesystem search (default: '.')"
    )
    parser.add_argument(
        "-f", "--files-list", default=None,
        help="Path to a text file containing a list of mock paths (one per line) to run tests against"
    )
    parser.add_argument(
        "--files-only", action="store_true",
        help="Only match files (only applicable when searching local filesystem)"
    )
    parser.add_argument(
        "--dirs-only", action="store_true",
        help="Only match directories (only applicable when searching local filesystem)"
    )
    parser.add_argument(
        "-c", "--case-sensitive", action="store_true",
        help="Enforce case-sensitive matching"
    )
    
    args = parser.parse_args()
    
    custom_paths = None
    if args.files_list:
        try:
            with open(args.files_list, 'r') as f:
                custom_paths = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: Custom paths file '{args.files_list}' not found.")
            sys.exit(1)
            
    if args.pattern:
        # Batch Mode
        if custom_paths:
            matches = test_on_custom_list(args.pattern, custom_paths, args.case_sensitive)
        else:
            matches = test_on_filesystem(
                args.pattern, args.root, args.files_only, args.dirs_only, args.case_sensitive
            )
            
        print(f"Matches for '{args.pattern}': {len(matches)}")
        for m in matches:
            print(m)
    else:
        # Interactive Mode
        interactive_loop(
            args.root, custom_paths, args.files_only, args.dirs_only, args.case_sensitive
        )

if __name__ == "__main__":
    main()
