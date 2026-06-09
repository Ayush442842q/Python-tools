#!/usr/bin/env python3
"""
Code Search and Regex Replacer - A powerful codebase search and replace tool.

Features:
- Search files recursively using literal text or regular expressions.
- Exclude specific directories (e.g., node_modules, .git, venv) and filter by glob patterns.
- Preview changes with a git-like colorized unified diff.
- Zero external dependencies.
"""

import argparse
import difflib
import fnmatch
import os
import re
import sys

# Terminal coloring helper
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

    @classmethod
    def disable(cls):
        cls.HEADER = ''
        cls.BLUE = ''
        cls.GREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''
        cls.CYAN = ''

def should_skip_dir(dir_name, exclude_patterns):
    """Check if a directory matches any exclude pattern."""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(dir_name, pattern) or dir_name == pattern:
            return True
    return False

def should_include_file(file_name, include_patterns):
    """Check if a file matches any include pattern (globs)."""
    if not include_patterns:
        return True
    for pattern in include_patterns:
        if fnmatch.fnmatch(file_name, pattern):
            return True
    return False

def search_files(directory, query_pat, is_regex, ignore_case, include_patterns, exclude_dirs):
    """Search for matches in files recursively."""
    matches = {}
    
    # Compile regex pattern
    flags = re.IGNORECASE if ignore_case else 0
    if not is_regex:
        escaped_query = re.escape(query_pat)
        regex = re.compile(escaped_query, flags)
    else:
        try:
            regex = re.compile(query_pat, flags)
        except re.error as e:
            print(f"{Colors.FAIL}Error compiling regex query: {e}{Colors.ENDC}")
            sys.exit(1)

    for root, dirs, files in os.walk(directory):
        # In-place modify dirs to skip excluded directories in os.walk
        dirs[:] = [d for d in dirs if not should_skip_dir(d, exclude_dirs)]
        
        for file in files:
            if not should_include_file(file, include_patterns):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except Exception:
                continue # Skip unreadable files
                
            file_matches = []
            for line_idx, line in enumerate(lines, 1):
                match_objs = list(regex.finditer(line))
                if match_objs:
                    file_matches.append({
                        'line_no': line_idx,
                        'content': line,
                        'matches': match_objs
                    })
            
            if file_matches:
                matches[file_path] = file_matches
                
    return matches, regex

def main():
    parser = argparse.ArgumentParser(description="Code Search and Regex Replacer - A powerful codebase find and replace utility")
    parser.add_argument("query", help="Text pattern to search for")
    parser.add_argument("replacement", nargs="?", help="Text replacement string")
    parser.add_argument("-d", "--dir", default=".", help="Root directory to search in (default: '.')")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive search")
    parser.add_argument("-r", "--regex", action="store_true", help="Treat query as a regular expression")
    parser.add_argument("-f", "--filter", help="Comma-separated glob file filters (e.g. '*.py,*.js')")
    parser.add_argument("-e", "--exclude", default=".git,node_modules,venv,.venv,__pycache__,build,dist", 
                        help="Comma-separated folder names to exclude (default: standard development folders)")
    parser.add_argument("--write", action="store_true", help="Apply replacements and write changes to files")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    if args.no_color or sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            if args.no_color or not sys.stdout.isatty():
                Colors.disable()

    # Parse filters and exclusions
    include_patterns = [p.strip() for p in args.filter.split(',')] if args.filter else []
    exclude_dirs = [d.strip() for d in args.exclude.split(',')] if args.exclude else []

    print(f"{Colors.BOLD}Searching for:{Colors.ENDC} {args.query!r}")
    print(f"{Colors.BOLD}Target Directory:{Colors.ENDC} {os.path.abspath(args.dir)}")
    if include_patterns:
        print(f"{Colors.BOLD}File Filters:{Colors.ENDC} {', '.join(include_patterns)}")
    print("-" * 60)

    matches, compiled_regex = search_files(
        args.dir, 
        args.query, 
        args.regex, 
        args.ignore_case, 
        include_patterns, 
        exclude_dirs
    )

    if not matches:
        print("No matches found.")
        return 0

    total_matches = sum(len(m) for m in matches.values())
    print(f"Found {total_matches} match(es) across {len(matches)} file(s):\n")

    # If only searching, display matches
    if args.replacement is None:
        for file_path, file_matches in matches.items():
            rel_path = os.path.relpath(file_path, args.dir)
            print(f"{Colors.CYAN}{rel_path}{Colors.ENDC}:")
            for m in file_matches:
                line_content = m['content'].rstrip('\n')
                # Colorize the matching spans in the line
                highlighted_line = ""
                last_idx = 0
                for match_obj in m['matches']:
                    start, end = match_obj.span()
                    highlighted_line += line_content[last_idx:start]
                    highlighted_line += f"{Colors.FAIL}{Colors.BOLD}{line_content[start:end]}{Colors.ENDC}"
                    last_idx = end
                highlighted_line += line_content[last_idx:]
                
                print(f"  {Colors.GREEN}line {m['line_no']}:{Colors.ENDC} {highlighted_line}")
            print()
        return 0

    # If replacement is provided, perform search & replace
    print(f"{Colors.BOLD}Replacement Text:{Colors.ENDC} {args.replacement!r}")
    print("-" * 60)

    files_modified = 0
    replacements_made = 0

    for file_path, file_matches in matches.items():
        rel_path = os.path.relpath(file_path, args.dir)
        
        # Read file lines
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_lines = f.readlines()
        except Exception as e:
            print(f"{Colors.FAIL}Could not read file {rel_path}: {e}{Colors.ENDC}")
            continue

        new_lines = []
        file_repl_count = 0
        for line in original_lines:
            # Count matches on this line
            m_count = len(compiled_regex.findall(line))
            if m_count > 0:
                file_repl_count += m_count
                new_line = compiled_regex.sub(args.replacement, line)
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        replacements_made += file_repl_count

        # Show diff
        print(f"\n{Colors.BOLD}{Colors.CYAN}Diff for {rel_path} ({file_repl_count} replacements):{Colors.ENDC}")
        diff = list(difflib.unified_diff(
            original_lines, 
            new_lines, 
            fromfile=f"a/{rel_path}", 
            tofile=f"b/{rel_path}", 
            n=2
        ))
        
        for diff_line in diff:
            if diff_line.startswith('+') and not diff_line.startswith('+++'):
                print(f"{Colors.GREEN}{diff_line.rstrip()}{Colors.ENDC}")
            elif diff_line.startswith('-') and not diff_line.startswith('---'):
                print(f"{Colors.FAIL}{diff_line.rstrip()}{Colors.ENDC}")
            elif diff_line.startswith('@@'):
                print(f"{Colors.BLUE}{diff_line.rstrip()}{Colors.ENDC}")
            else:
                print(diff_line.rstrip())

        if args.write:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                files_modified += 1
                print(f"{Colors.GREEN}✓ Applied changes to {rel_path}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.FAIL}✗ Failed to write changes to {rel_path}: {e}{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}Dry-run mode: Changes were not saved to {rel_path}. Run with --write to apply.{Colors.ENDC}")

    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}Search & Replace Summary{Colors.ENDC}")
    print("=" * 50)
    print(f"Total Matches Replaced: {replacements_made}")
    if args.write:
        print(f"Files Modified:         {files_modified} out of {len(matches)}")
    else:
        print(f"Files Proposed to Mod:  {len(matches)}")
        print(f"{Colors.WARNING}Note: No changes written. Run with --write to persist changes.{Colors.ENDC}")
    print("=" * 50 + "\n")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nSearch cancelled by user.")
        sys.exit(1)
