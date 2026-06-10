#!/usr/bin/env python3
"""
Code Line Counter (CLOC)

A standalone utility to recursively scan a directory and count lines of code,
blank lines, and comments for various programming languages.

Usage:
    python tools/code_line_counter.py [options] [directory]

Examples:
    python tools/code_line_counter.py .
    python tools/code_line_counter.py --exclude venv,tests .
    python tools/code_line_counter.py --by-file --json .
"""

import argparse
import os
import json
import sys
from pathlib import Path

# Language definitions
LANGUAGES = {
    '.py': {'name': 'Python', 'single': '#', 'multi_start': '"""', 'multi_end': '"""'},
    '.js': {'name': 'JavaScript', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.mjs': {'name': 'JavaScript', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.ts': {'name': 'TypeScript', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.tsx': {'name': 'TypeScript React', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.jsx': {'name': 'JavaScript React', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.html': {'name': 'HTML', 'single': None, 'multi_start': '<!--', 'multi_end': '-->'},
    '.htm': {'name': 'HTML', 'single': None, 'multi_start': '<!--', 'multi_end': '-->'},
    '.css': {'name': 'CSS', 'single': None, 'multi_start': '/*', 'multi_end': '*/'},
    '.go': {'name': 'Go', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.java': {'name': 'Java', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.c': {'name': 'C', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.h': {'name': 'C Header', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.cpp': {'name': 'C++', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.cc': {'name': 'C++', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.rs': {'name': 'Rust', 'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.sh': {'name': 'Shell', 'single': '#', 'multi_start': None, 'multi_end': None},
    '.bash': {'name': 'Shell', 'single': '#', 'multi_start': None, 'multi_end': None},
    '.md': {'name': 'Markdown', 'single': None, 'multi_start': '<!--', 'multi_end': '-->'},
    '.json': {'name': 'JSON', 'single': None, 'multi_start': None, 'multi_end': None},
    '.yaml': {'name': 'YAML', 'single': '#', 'multi_start': None, 'multi_end': None},
    '.yml': {'name': 'YAML', 'single': '#', 'multi_start': None, 'multi_end': None},
    '.xml': {'name': 'XML', 'single': None, 'multi_start': '<!--', 'multi_end': '-->'},
    '.sql': {'name': 'SQL', 'single': '--', 'multi_start': '/*', 'multi_end': '*/'}
}

DEFAULT_EXCLUDES = {
    '.git', 'node_modules', 'venv', 'env', '.env', '__pycache__',
    '.idea', '.vscode', 'dist', 'build', '.mypy_cache', '.pytest_cache'
}

def analyze_file(file_path, lang_def):
    """Analyze a single file and count blank, comment, and code lines."""
    blanks = 0
    comments = 0
    code = 0
    
    single_marker = lang_def['single']
    multi_start = lang_def['multi_start']
    multi_end = lang_def['multi_end']
    
    in_multi_comment = False
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_stripped = line.strip()
                
                # Check blank
                if not line_stripped:
                    blanks += 1
                    continue
                
                # Check multi-line comment state
                if in_multi_comment:
                    comments += 1
                    if multi_end and multi_end in line_stripped:
                        in_multi_comment = False
                    continue
                
                # Check start of multi-line comment
                if multi_start and line_stripped.startswith(multi_start):
                    comments += 1
                    # Check if it also ends on the same line
                    if not (multi_end and multi_end in line_stripped[len(multi_start):]):
                        in_multi_comment = True
                    continue
                
                # Check single line comment
                if single_marker and line_stripped.startswith(single_marker):
                    comments += 1
                    continue
                
                # If none of the above, it's code
                code += 1
                
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None
        
    return {
        'blanks': blanks,
        'comments': comments,
        'code': code,
        'total': blanks + comments + code
    }

def print_table(headers, rows, alignments=None):
    """Helper to print a beautiful, aligned text table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))
            
    if not alignments:
        alignments = ['L'] + ['R'] * (len(headers) - 1)
        
    # Print separator
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    print(sep)
    
    # Print header
    header_str = "|"
    for idx, h in enumerate(headers):
        align = alignments[idx]
        w = col_widths[idx]
        if align == 'R':
            header_str += f" {h.rjust(w)} |"
        else:
            header_str += f" {h.ljust(w)} |"
    print(header_str)
    print(sep.replace('+', '|').replace('-', '='))
    
    # Print rows
    for row in rows:
        row_str = "|"
        for idx, val in enumerate(row):
            align = alignments[idx]
            w = col_widths[idx]
            val_str = str(val)
            if align == 'R':
                row_str += f" {val_str.rjust(w)} |"
            else:
                row_str += f" {val_str.ljust(w)} |"
        print(row_str)
        
    print(sep)

def scan_directory(root_dir, excludes):
    """Recursively scan a directory and analyze matching files."""
    results = {}
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter directories in-place to respect exclude lists
        dirnames[:] = [d for d in dirnames if d not in excludes and not d.startswith('.')]
        
        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()
            
            if ext in LANGUAGES:
                lang_def = LANGUAGES[ext]
                lang_name = lang_def['name']
                
                stats = analyze_file(fpath, lang_def)
                if stats is None:
                    continue
                    
                rel_path = str(fpath.relative_to(root_dir))
                
                if lang_name not in results:
                    results[lang_name] = {
                        'files_count': 0,
                        'blanks': 0,
                        'comments': 0,
                        'code': 0,
                        'total': 0,
                        'files': []
                    }
                    
                results[lang_name]['files_count'] += 1
                results[lang_name]['blanks'] += stats['blanks']
                results[lang_name]['comments'] += stats['comments']
                results[lang_name]['code'] += stats['code']
                results[lang_name]['total'] += stats['total']
                results[lang_name]['files'].append({
                    'path': rel_path,
                    **stats
                })
                
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Recursively scan directories and count lines of code, comments, and blank lines."
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to scan (default: current directory)'
    )
    parser.add_argument(
        '-e', '--exclude',
        help='Comma-separated directories to exclude (e.g. "tests,node_modules")'
    )
    parser.add_argument(
        '--by-file',
        action='store_true',
        help='Output details for each individual file instead of summary by language'
    )
    parser.add_argument(
        '-j', '--json',
        action='store_true',
        help='Output findings in JSON format'
    )
    
    args = parser.parse_args()
    
    scan_path = Path(args.directory).resolve()
    if not scan_path.exists():
        print(f"Error: Directory '{args.directory}' does not exist.", file=sys.stderr)
        return 1
        
    if not scan_path.is_dir():
        print(f"Error: Path '{args.directory}' is not a directory.", file=sys.stderr)
        return 1
        
    # Build list of excluded directories
    excludes = set(DEFAULT_EXCLUDES)
    if args.exclude:
        excludes.update(d.strip() for d in args.exclude.split(','))
        
    # Run scan
    results = scan_directory(scan_path, excludes)
    
    if not results:
        if args.json:
            print(json.dumps({}, indent=2))
        else:
            print("No supported programming languages detected in the specified directory.")
        return 0
        
    if args.json:
        # Format JSON output
        out_data = {}
        if args.by_file:
            for lang, data in results.items():
                for f in data['files']:
                    out_data[f['path']] = {
                        'language': lang,
                        'blanks': f['blanks'],
                        'comments': f['comments'],
                        'code': f['code'],
                        'total': f['total']
                    }
        else:
            for lang, data in results.items():
                out_data[lang] = {
                    'files': data['files_count'],
                    'blanks': data['blanks'],
                    'comments': data['comments'],
                    'code': data['code'],
                    'total': data['total']
                }
        print(json.dumps(out_data, indent=2))
        return 0
        
    if args.by_file:
        headers = ["File Path", "Language", "Blank", "Comment", "Code", "Total"]
        rows = []
        tot_blanks = tot_comments = tot_code = tot_lines = 0
        
        for lang, data in results.items():
            for f in sorted(data['files'], key=lambda x: x['path']):
                rows.append([
                    f['path'],
                    lang,
                    f['blanks'],
                    f['comments'],
                    f['code'],
                    f['total']
                ])
                tot_blanks += f['blanks']
                tot_comments += f['comments']
                tot_code += f['code']
                tot_lines += f['total']
                
        rows.append(["TOTAL", f"{len(rows)} files", tot_blanks, tot_comments, tot_code, tot_lines])
        print_table(headers, rows, alignments=['L', 'L', 'R', 'R', 'R', 'R'])
    else:
        headers = ["Language", "Files", "Blank", "Comment", "Code", "Total"]
        rows = []
        tot_files = tot_blanks = tot_comments = tot_code = tot_lines = 0
        
        # Sort languages by code lines desc
        sorted_langs = sorted(results.items(), key=lambda x: x[1]['code'], reverse=True)
        for lang, data in sorted_langs:
            rows.append([
                lang,
                data['files_count'],
                data['blanks'],
                data['comments'],
                data['code'],
                data['total']
            ])
            tot_files += data['files_count']
            tot_blanks += data['blanks']
            tot_comments += data['comments']
            tot_code += data['code']
            tot_lines += data['total']
            
        rows.append(["TOTAL", tot_files, tot_blanks, tot_comments, tot_code, tot_lines])
        print_table(headers, rows, alignments=['L', 'R', 'R', 'R', 'R', 'R'])
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
