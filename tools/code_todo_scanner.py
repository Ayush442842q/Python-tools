#!/usr/bin/env python3
"""
code_todo_scanner - Scan source code for developer checklist comments

Scans directories recursively for comments like TODO, FIXME, HACK, BUG, and REVIEW,
grouping and formatting them into reports (console, Markdown, or JSON).

Usage:
    python tools/code_todo_scanner.py [DIR] [--tags TAGS] [--format FORMAT]

Options:
    DIR                 Directory to scan (default: current directory)
    -t, --tags          Comma-separated list of tags to scan for (default: TODO,FIXME,HACK,BUG,REVIEW)
    -f, --format        Output format: text, markdown, json (default: text)
    -o, --output        Output file path (prints to stdout if omitted)
    --exclude-dirs      Comma-separated list of directories to ignore
    --extensions        Comma-separated list of file extensions to scan (e.g., py,js,ts)

Example:
    python tools/code_todo_scanner.py . -f markdown -o todo_report.md
"""

import os
import re
import sys
import json
import argparse

# Console colors
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_MAGENTA = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_END = "\033[0m"

# Default directories to ignore
DEFAULT_EXCLUDE_DIRS = {
    '.git', 'node_modules', '__pycache__', 'venv', '.venv', 'env', '.env',
    'dist', 'build', 'target', '.idea', '.vscode', '.pytest_cache', '.mypy_cache'
}

# Mapping of file extensions to human-readable languages
LANGUAGE_MAP = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.jsx': 'JavaScript (React)',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript (React)',
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.h': 'C/C++ Header',
    '.cs': 'C#',
    '.go': 'Go',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.sh': 'Shell Script',
    '.bash': 'Shell Script',
    '.sql': 'SQL',
    '.css': 'CSS',
    '.html': 'HTML',
    '.xml': 'XML',
    '.yml': 'YAML',
    '.yaml': 'YAML',
    '.toml': 'TOML',
    '.ini': 'Configuration'
}

def scan_file(file_path, tags_regex, tags_list):
    """Scan a single file line-by-line for TODO-like comments."""
    todos = []
    
    # Compile regex for comment tags
    # Group 1: The Tag (TODO/FIXME/etc.)
    # Group 2: The optional assignee e.g. (john) or [mary]
    # Group 3: The actual task text
    pattern_str = r'(?:#|//|--|/\*|<!--|\*)\s*(' + tags_regex + r')(?:\(([^)]+)\))?\s*[:\-]?\s*(.*)'
    pattern = re.compile(pattern_str, re.IGNORECASE)

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, start=1):
                # Check if line contains one of the tags first for performance
                if not any(tag.lower() in line.lower() for tag in tags_list):
                    continue
                    
                match = pattern.search(line)
                if match:
                    tag = match.group(1).upper()
                    assignee = match.group(2) or "Unassigned"
                    # Strip block comment suffix if present
                    message = match.group(3).strip()
                    if message.endswith('*/'):
                        message = message[:-2].strip()
                    if message.endswith('-->'):
                        message = message[:-3].strip()
                        
                    todos.append({
                        "line": line_num,
                        "tag": tag,
                        "assignee": assignee.strip(),
                        "message": message
                    })
    except Exception as e:
        # Silently skip files that fail to read (binary or permission issues)
        pass
        
    return todos

def generate_text_report(results):
    """Generate colorized text report for terminal output."""
    out = []
    total_count = 0
    
    # Sort files by path
    for file_path, todos in sorted(results.items()):
        if not todos:
            continue
        total_count += len(todos)
        out.append(f"\n{COLOR_BOLD}{COLOR_UNDERLINE}{file_path}{COLOR_END}")
        
        for item in todos:
            # Color tag according to severity
            tag = item['tag']
            if tag in ('FIXME', 'BUG'):
                tag_color = COLOR_RED
            elif tag == 'HACK':
                tag_color = COLOR_YELLOW
            elif tag in ('TODO', 'REVIEW'):
                tag_color = COLOR_CYAN
            else:
                tag_color = COLOR_BLUE
                
            assignee_str = f" [{item['assignee']}]" if item['assignee'] != "Unassigned" else ""
            out.append(f"  Line {item['line']:<4} | {tag_color}{COLOR_BOLD}{tag}{COLOR_END}{COLOR_MAGENTA}{assignee_str}{COLOR_END}: {item['message']}")
            
    out.append(f"\n{COLOR_GREEN}{COLOR_BOLD}Scan complete! Found {total_count} checklist item(s) across {len(results)} file(s).{COLOR_END}")
    return "\n".join(out)

def generate_markdown_report(results, dir_path):
    """Generate a clean GitHub-Flavored Markdown report with tables."""
    out = []
    out.append(f"# Code TODO/FIXME Scan Report")
    out.append(f"Generated on: {os.path.basename(os.path.abspath(dir_path))}")
    out.append(f"\n## Summary")
    
    total_todos = 0
    tag_counts = {}
    file_table_rows = []
    
    for file_path, todos in sorted(results.items()):
        if not todos:
            continue
        cnt = len(todos)
        total_todos += cnt
        file_table_rows.append(f"| [{file_path}]({file_path}) | {cnt} |")
        
        for item in todos:
            t = item['tag']
            tag_counts[t] = tag_counts.get(t, 0) + 1
            
    out.append(f"- **Total items found:** {total_todos}")
    out.append("- **Breakdown by Tag:**")
    for tag, val in sorted(tag_counts.items()):
        out.append(f"  - `{tag}`: {val}")
        
    out.append(f"\n## Files Table")
    out.append("| File Path | Items Count |")
    out.append("| --- | --- |")
    out.extend(file_table_rows)
    
    out.append(f"\n## Detailed List")
    for file_path, todos in sorted(results.items()):
        if not todos:
            continue
        out.append(f"\n### `{file_path}`")
        out.append("| Line | Tag | Assignee | Message |")
        out.append("| --- | --- | --- | --- |")
        for item in todos:
            out.append(f"| {item['line']} | `{item['tag']}` | {item['assignee']} | {item['message']} |")
            
    return "\n".join(out)

def main():
    parser = argparse.ArgumentParser(description="Scan project files recursively for developer checkmarks (TODO, FIXME, HACK, etc.)")
    parser.add_argument('dir', nargs='?', default='.', help='Directory to scan (default: current directory)')
    parser.add_argument('-t', '--tags', type=str, default='TODO,FIXME,HACK,BUG,REVIEW', help='Comma-separated list of tags to scan for')
    parser.add_argument('-f', '--format', choices=['text', 'markdown', 'json'], default='text', help='Output format')
    parser.add_argument('-o', '--output', type=str, help='Output file path')
    parser.add_argument('--exclude-dirs', type=str, help='Comma-separated directory names to ignore')
    parser.add_argument('--extensions', type=str, help='Comma-separated file extensions to scan (e.g. py,js,ts)')
    
    args = parser.parse_args()

    # Resolve scan directory
    scan_dir = os.path.abspath(args.dir)
    if not os.path.isdir(scan_dir):
        print(f"{COLOR_RED}Error: Directory '{scan_dir}' does not exist.{COLOR_END}", file=sys.stderr)
        return 1

    # Extract tags
    tags_list = [t.strip().upper() for t in args.tags.split(',') if t.strip()]
    if not tags_list:
        print(f"{COLOR_RED}Error: No tags specified for scanning.{COLOR_END}", file=sys.stderr)
        return 1
    tags_regex = '|'.join(re.escape(t) for t in tags_list)

    # Configure ignored directories
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    if args.exclude_dirs:
        exclude_dirs.update(d.strip() for d in args.exclude_dirs.split(',') if d.strip())

    # Configure extensions
    extensions = None
    if args.extensions:
        extensions = {'.' + ext.strip().lower().lstrip('.') for ext in args.extensions.split(',') if ext.strip()}

    results = {}

    # Recursive directory walk
    for root, dirs, files in os.walk(scan_dir):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            
            # Filter by extensions
            if extensions:
                if ext not in extensions:
                    continue
            else:
                # Default filter: only match files whose extension is in our LANGUAGE_MAP
                if ext not in LANGUAGE_MAP:
                    continue
                    
            full_path = os.path.join(root, file)
            # Make path relative to scan_dir for output cleanliness
            rel_path = os.path.relpath(full_path, scan_dir)
            
            file_todos = scan_file(full_path, tags_regex, tags_list)
            if file_todos:
                results[rel_path] = file_todos

    # Generate output string based on format
    if args.format == 'json':
        output_str = json.dumps(results, indent=2)
    elif args.format == 'markdown':
        output_str = generate_markdown_report(results, args.dir)
    else:
        output_str = generate_text_report(results)

    # Write output or print
    if args.output:
        try:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(output_str)
                f.write('\n')
            print(f"{COLOR_GREEN}Report successfully saved to: {COLOR_YELLOW}{args.output}{COLOR_END}")
        except Exception as e:
            print(f"{COLOR_RED}Error writing output file: {e}{COLOR_END}", file=sys.stderr)
            return 1
    else:
        print(output_str)

    return 0

if __name__ == "__main__":
    sys.exit(main())
