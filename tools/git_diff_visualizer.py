#!/usr/bin/env python3
"""
git_diff_visualizer.py - Colored Git Diff Visualizer with Inline Highlights
Parses unified diff inputs (from git diff command or stdin/files) and renders them in the terminal
with ANSI colors, custom themes, and inline word/character highlights for adjacent changes.
"""

import sys
import os
import re
import subprocess
import argparse
import difflib
import shutil

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

# Text Colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Background Colors for Inline Highlights
BG_RED_LIGHT = "\033[48;5;52m"
BG_GREEN_LIGHT = "\033[48;5;22m"
BG_RED_BRIGHT = "\033[48;5;196m\033[38;5;231m"
BG_GREEN_BRIGHT = "\033[48;5;82m\033[38;5;16m"

def get_terminal_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def get_terminal_height():
    try:
        return shutil.get_terminal_size().lines
    except Exception:
        return 24

def strip_ansi(text):
    return re.sub(r'\033\[[0-9;]*[mK]', '', text)

def format_inline_diff(del_line, add_line, use_color=True):
    """
    Computes character-level inline differences between deleted and added lines.
    """
    if not use_color:
        return del_line, add_line

    # Remove the leading '-' and '+'
    del_content = del_line[1:]
    add_content = add_line[1:]

    # Use SequenceMatcher to find matching blocks
    matcher = difflib.SequenceMatcher(None, del_content, add_content)
    
    del_parts = []
    add_parts = []
    
    last_del_idx = 0
    last_add_idx = 0
    
    for block in matcher.get_matching_blocks():
        del_idx, add_idx, size = block
        
        # Process mismatch before the matching block
        if del_idx > last_del_idx:
            mismatch = del_content[last_del_idx:del_idx]
            del_parts.append(f"{BG_RED_BRIGHT}{mismatch}{RESET}{RED}")
        if add_idx > last_add_idx:
            mismatch = add_content[last_add_idx:add_idx]
            add_parts.append(f"{BG_GREEN_BRIGHT}{mismatch}{RESET}{GREEN}")
            
        # Process the matching block itself
        if size > 0:
            matching = del_content[del_idx:del_idx+size]
            del_parts.append(matching)
            add_parts.append(matching)
            
        last_del_idx = del_idx + size
        last_add_idx = add_idx + size

    formatted_del = f"{RED}-{BG_RED_LIGHT}{''.join(del_parts)}{RESET}"
    formatted_add = f"{GREEN}+{BG_GREEN_LIGHT}{''.join(add_parts)}{RESET}"
    return formatted_del, formatted_add

def colorize_diff(diff_lines, use_color=True, inline_diff=True):
    """
    Parses unified diff lines and yields colored formatted lines.
    """
    # Keep track of line buffer for inline word/character diffs
    line_buffer = []
    
    for line in diff_lines:
        # Strip trailing newlines
        line = line.rstrip('\r\n')
        
        # Flush buffer if current line is not part of a modification block
        if line_buffer:
            if line.startswith('-') and not line.startswith('---'):
                line_buffer.append(line)
                continue
            elif line.startswith('+') and not line.startswith('+++'):
                line_buffer.append(line)
                continue
            else:
                yield from flush_buffer(line_buffer, use_color, inline_diff)
                line_buffer = []
                
        if line.startswith('-') and not line.startswith('---'):
            line_buffer.append(line)
        elif line.startswith('+') and not line.startswith('+++'):
            line_buffer.append(line)
        else:
            yield format_line(line, use_color)
            
    if line_buffer:
        yield from flush_buffer(line_buffer, use_color, inline_diff)

def flush_buffer(buffer, use_color, inline_diff):
    """
    Processes the buffered deletion and addition lines, doing inline diffing if appropriate.
    """
    deletions = [line for line in buffer if line.startswith('-')]
    additions = [line for line in buffer if line.startswith('+')]
    
    # If we have an equal number of deletions and additions, perform pairwise inline highlights
    if inline_diff and len(deletions) == len(additions) and len(deletions) > 0:
        for d_line, a_line in zip(deletions, additions):
            f_del, f_add = format_inline_diff(d_line, a_line, use_color)
            yield f_del
            yield f_add
    else:
        # Otherwise, just print them normally with standard red/green highlights
        for line in buffer:
            yield format_line(line, use_color)

def format_line(line, use_color):
    if not use_color:
        return line
        
    if line.startswith('diff --git'):
        # Style command line header
        filename = line.split(' ')[-1].replace('b/', '') if ' b/' in line else ''
        return f"{BOLD}{CYAN}{'=' * get_terminal_width()}{RESET}\n{BOLD}{WHITE}Diffing: {CYAN}{filename}{RESET}\n{DIM}{line}{RESET}"
    elif line.startswith('index '):
        return f"{DIM}{line}{RESET}"
    elif line.startswith('--- '):
        return f"{RED}{line}{RESET}"
    elif line.startswith('+++ '):
        return f"{GREEN}{line}{RESET}"
    elif line.startswith('@@ '):
        # Match hunk header: @@ -start,len +start,len @@ section
        match = re.match(r'^(@@\s+-\d+,\d+\s+\+\d+,\d+\s+@@)(.*)$', line)
        if match:
            hunk, context = match.groups()
            return f"{MAGENTA}{hunk}{RESET}{CYAN}{context}{RESET}"
        return f"{MAGENTA}{line}{RESET}"
    elif line.startswith('-'):
        return f"{RED}{line}{RESET}"
    elif line.startswith('+'):
        return f"{GREEN}{line}{RESET}"
    elif line.startswith('binary') or line.startswith('Binary'):
        return f"{YELLOW}{BOLD}{line}{RESET}"
    else:
        return line

def display_pages(lines):
    """
    Simple terminal pager that waits for space/enter if output exceeds terminal height.
    """
    term_height = get_terminal_height()
    page_size = term_height - 3
    
    line_count = 0
    for line in lines:
        print(line)
        line_count += len(line.split('\n'))
        
        if line_count >= page_size:
            try:
                # Prompt user for paging
                prompt = f"{BOLD}{BG_GREEN_BRIGHT} -- Press ENTER for next lines, 'q' to quit -- {RESET}"
                sys.stdout.write(prompt)
                sys.stdout.flush()
                
                # Read key (works in standard console)
                choice = sys.stdin.readline().strip().lower()
                # Clear prompt line
                sys.stdout.write('\r' + ' ' * len(strip_ansi(prompt)) + '\r')
                sys.stdout.flush()
                
                if choice == 'q':
                    break
                line_count = 0
            except KeyboardInterrupt:
                break

def main():
    parser = argparse.ArgumentParser(
        description="Visualizes git diff or general unified diff files with color and inline highlighting."
    )
    parser.add_argument(
        '-i', '--input', 
        help="Input diff file (or '-' for stdin). If omitted, runs 'git diff' in current directory."
    )
    parser.add_argument(
        '-n', '--no-color', 
        action='store_true', 
        help="Disable ANSI colored output."
    )
    parser.add_argument(
        '--no-inline', 
        action='store_true', 
        help="Disable inline word-level diffing."
    )
    parser.add_argument(
        '-p', '--page', 
        action='store_true', 
        help="Enable simple console pagination."
    )
    
    args = parser.parse_args()
    
    use_color = not args.no_color and sys.stdout.isatty()
    inline_diff = not args.no_inline
    
    diff_lines = []
    
    # 1. Read input from file/stdin or execute git diff
    if args.input == '-':
        diff_lines = sys.stdin.readlines()
    elif args.input:
        if not os.path.exists(args.input):
            print(f"Error: File '{args.input}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
            diff_lines = f.readlines()
    else:
        # Check if stdin has data piped to it (without blocking)
        if not sys.stdin.isatty():
            diff_lines = sys.stdin.readlines()
        else:
            # Run git diff in the current working directory
            try:
                # First check if it's a git repo
                subprocess.run(
                    ['git', 'rev-parse', '--is-inside-work-tree'], 
                    check=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                result = subprocess.run(
                    ['git', 'diff', '--no-color'], 
                    check=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                diff_lines = result.stdout.splitlines(keepends=True)
                
                # If git diff is empty, check staged diff
                if not diff_lines or all(not l.strip() for l in diff_lines):
                    result_staged = subprocess.run(
                        ['git', 'diff', '--cached', '--no-color'],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    diff_lines = result_staged.stdout.splitlines(keepends=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("Error: Not in a git repository or git command not available. Use -i to supply a diff file.", file=sys.stderr)
                sys.exit(1)
                
    if not diff_lines or all(not l.strip() for l in diff_lines):
        print("No differences found.")
        sys.exit(0)
        
    # Process and colorize lines
    colored_lines = colorize_diff(diff_lines, use_color, inline_diff)
    
    if args.page:
        display_pages(colored_lines)
    else:
        for line in colored_lines:
            print(line)

if __name__ == "__main__":
    main()
