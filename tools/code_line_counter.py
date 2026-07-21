#!/usr/bin/env python3
"""
Code Line Counter
Counts lines of code, comments, and blank lines for various programming languages in a directory.

Usage:
    python tools/code_line_counter.py [directory] [options]

Arguments:
    directory              Directory to scan (default: current directory)

Options:
    -e, --exclude DIRS     Comma-separated list of directories to exclude (default: .git,node_modules,__pycache__,venv,.venv)
    -i, --include EXTS     Comma-separated list of file extensions to include (e.g. py,js,cpp)
    -f, --format FORMAT    Output format: table, json, csv (default: table)
    -h, --help             Show this help message and exit

Example:
    python tools/code_line_counter.py .
    python tools/code_line_counter.py ./src -i py,js -f json
"""

import argparse
import json
import os
import sys

# Language mappings with their extensions and comment markers
# format: extension -> (language_name, line_comment_prefix, block_comment_start, block_comment_end)
LANGUAGES = {
    'py': ('Python', '#', '"""', '"""'),
    'js': ('JavaScript', '//', '/*', '*/'),
    'ts': ('TypeScript', '//', '/*', '*/'),
    'jsx': ('React JSX', '//', '/*', '*/'),
    'tsx': ('React TSX', '//', '/*', '*/'),
    'c': ('C', '//', '/*', '*/'),
    'cpp': ('C++', '//', '/*', '*/'),
    'h': ('C/C++ Header', '//', '/*', '*/'),
    'hpp': ('C++ Header', '//', '/*', '*/'),
    'cs': ('C#', '//', '/*', '*/'),
    'java': ('Java', '//', '/*', '*/'),
    'go': ('Go', '//', '/*', '*/'),
    'rs': ('Rust', '//', '/*', '*/'),
    'swift': ('Swift', '//', '/*', '*/'),
    'kt': ('Kotlin', '//', '/*', '*/'),
    'rb': ('Ruby', '#', '=begin', '=end'),
    'pl': ('Perl', '#', None, None),
    'sh': ('Shell', '#', None, None),
    'bat': ('Batch', 'REM', None, None),
    'ps1': ('PowerShell', '#', '<#', '#>'),
    'sql': ('SQL', '--', '/*', '*/'),
    'html': ('HTML', None, '<!--', '-->'),
    'xml': ('XML', None, '<!--', '-->'),
    'css': ('CSS', None, '/*', '*/'),
    'scss': ('SCSS', '//', '/*', '*/'),
    'md': ('Markdown', None, '<!--', '-->'),
    'yaml': ('YAML', '#', None, None),
    'yml': ('YAML', '#', None, None),
    'json': ('JSON', None, None, None),
    'toml': ('TOML', '#', None, None),
    'ini': ('INI', ';', None, None),
}

DEFAULT_EXCLUDES = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist', '.idea', '.vscode'}


def analyze_file(file_path, comment_rules):
    """Analyze a file and return (code_lines, comment_lines, blank_lines, total_lines)."""
    lang_name, line_marker, block_start, block_end = comment_rules
    
    code = 0
    comments = 0
    blanks = 0
    total = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return 0, 0, 0, 0

    total = len(lines)
    in_block_comment = False
    
    for line in lines:
        stripped = line.strip()
        
        # 1. Blank line
        if not stripped:
            blanks += 1
            continue
            
        # 2. Block comments handling
        if block_start and block_end:
            if in_block_comment:
                comments += 1
                if block_end in stripped:
                    # check if the block comment ends at the end of the line
                    idx = stripped.find(block_end)
                    remainder = stripped[idx + len(block_end):].strip()
                    if remainder:
                        # block comment ended, but there is code remaining on the line
                        pass
                    in_block_comment = False
                continue
            elif stripped.startswith(block_start):
                comments += 1
                if block_end not in stripped[len(block_start):] or block_start == block_end:
                    in_block_comment = True
                continue

        # 3. Line comments
        if line_marker and stripped.startswith(line_marker):
            comments += 1
            continue
            
        # 4. Code lines
        code += 1

    return code, comments, blanks, total


def main():
    parser = argparse.ArgumentParser(description="Count lines of code in a directory.")
    parser.add_argument('directory', nargs='?', default='.', help='Directory to scan (default: current directory)')
    parser.add_argument('-e', '--exclude', default='',
                        help='Comma-separated list of directories to exclude')
    parser.add_argument('-i', '--include', default='',
                        help='Comma-separated list of extensions to include (e.g. py,js)')
    parser.add_argument('-f', '--format', choices=['table', 'json', 'csv'], default='table',
                        help='Output format (default: table)')
    
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist.", file=sys.stderr)
        return 1

    # Configure excludes
    exclude_dirs = DEFAULT_EXCLUDES.copy()
    if args.exclude:
        for d in args.exclude.split(','):
            exclude_dirs.add(d.strip())

    # Configure includes
    include_exts = None
    if args.include:
        include_exts = {ext.strip().lower().lstrip('.') for ext in args.include.split(',')}

    # Scan and aggregate results
    # stats: language_name -> {files, code, comments, blanks, total}
    stats = {}
    
    for root, dirs, files in os.walk(args.directory):
        # Filter directories in-place to prevent scanning excluded folders
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            ext = file.split('.')[-1].lower() if '.' in file else ''
            
            if include_exts and ext not in include_exts:
                continue
                
            if ext in LANGUAGES:
                lang_name, line_marker, block_start, block_end = LANGUAGES[ext]
                file_path = os.path.join(root, file)
                
                code, comments, blanks, total = analyze_file(file_path, LANGUAGES[ext])
                if total == 0:
                    continue
                    
                if lang_name not in stats:
                    stats[lang_name] = {
                        'files': 0,
                        'code': 0,
                        'comments': 0,
                        'blanks': 0,
                        'total': 0
                    }
                    
                stats[lang_name]['files'] += 1
                stats[lang_name]['code'] += code
                stats[lang_name]['comments'] += comments
                stats[lang_name]['blanks'] += blanks
                stats[lang_name]['total'] += total

    if not stats:
        print("No supported source files found.", file=sys.stderr)
        return 0

    # Sort results by code lines descending
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['code'], reverse=True)

    # Calculate Totals
    total_files = sum(s['files'] for _, s in stats.items())
    total_code = sum(s['code'] for _, s in stats.items())
    total_comments = sum(s['comments'] for _, s in stats.items())
    total_blanks = sum(s['blanks'] for _, s in stats.items())
    total_lines = sum(s['total'] for _, s in stats.items())

    if args.format == 'json':
        output = {
            'languages': {lang: s for lang, s in sorted_stats},
            'totals': {
                'files': total_files,
                'code': total_code,
                'comments': total_comments,
                'blanks': total_blanks,
                'total_lines': total_lines
            }
        }
        print(json.dumps(output, indent=2))
        
    elif args.format == 'csv':
        print("Language,Files,Code,Comments,Blanks,Total")
        for lang, s in sorted_stats:
            print(f"{lang},{s['files']},{s['code']},{s['comments']},{s['blanks']},{s['total']}")
        print(f"SUM,{total_files},{total_code},{total_comments},{total_blanks},{total_lines}")
        
    else:  # Table
        # Determine column widths
        header = ["Language", "Files", "Code", "Comments", "Blanks", "Total"]
        col_widths = [15, 8, 12, 12, 10, 12]
        
        # Format strings helper
        def format_row(lang, files, code, comments, blanks, total):
            return (
                f"| {lang.ljust(col_widths[0])} "
                f"| {str(files).rjust(col_widths[1])} "
                f"| {str(code).rjust(col_widths[2])} "
                f"| {str(comments).rjust(col_widths[3])} "
                f"| {str(blanks).rjust(col_widths[4])} "
                f"| {str(total).rjust(col_widths[5])} |"
            )

        separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        
        print(separator)
        print(f"| {'Language'.ljust(col_widths[0])} | {'Files'.rjust(col_widths[1])} | {'Code'.rjust(col_widths[2])} | {'Comments'.rjust(col_widths[3])} | {'Blanks'.rjust(col_widths[4])} | {'Total'.rjust(col_widths[5])} |")
        print(separator.replace('-', '='))
        
        for lang, s in sorted_stats:
            print(format_row(lang, s['files'], s['code'], s['comments'], s['blanks'], s['total']))
            
        print(separator.replace('-', '='))
        print(format_row("SUM", total_files, total_code, total_comments, total_blanks, total_lines))
        print(separator)

    return 0


if __name__ == '__main__':
    main()
