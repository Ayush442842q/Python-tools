#!/usr/bin/env python3
"""
File Diff Tool - Compare two files line by line, generating colored terminal output or interactive HTML diffs.
"""

import argparse
import difflib
import sys
import os

# ANSI escape codes for colored console output
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_colored_diff(file1_lines, file2_lines, file1_name, file2_name, ignore_whitespace=False):
    """Generate and print colored unified diff to the console."""
    if ignore_whitespace:
        file1_clean = [line.rstrip() for line in file1_lines]
        file2_clean = [line.rstrip() for line in file2_lines]
        diff = difflib.unified_diff(
            file1_clean, file2_clean,
            fromfile=file1_name, tofile=file2_name,
            lineterm=''
        )
    else:
        diff = difflib.unified_diff(
            file1_lines, file2_lines,
            fromfile=file1_name, tofile=file2_name,
            lineterm=''
        )

    has_changes = False
    added_count = 0
    deleted_count = 0
    
    for line in diff:
        has_changes = True
        if line.startswith('+') and not line.startswith('+++'):
            print(f"{GREEN}{line}{RESET}")
            added_count += 1
        elif line.startswith('-') and not line.startswith('---'):
            print(f"{RED}{line}{RESET}")
            deleted_count += 1
        elif line.startswith('@@'):
            print(f"{BLUE}{line}{RESET}")
        else:
            print(line)
            
    if not has_changes:
        print("Files are identical.")
    else:
        print("\nSummary:")
        print(f"  {GREEN}+ Added lines:{RESET} {added_count}")
        print(f"  {RED}- Deleted lines:{RESET} {deleted_count}")

def generate_html_diff(file1_lines, file2_lines, file1_name, file2_name, output_path):
    """Generate a side-by-side HTML diff using difflib.HtmlDiff."""
    differ = difflib.HtmlDiff()
    html_content = differ.make_file(
        file1_lines, file2_lines,
        fromdesc=file1_name, todesc=file2_name,
        context=False  # Full side-by-side comparison
    )
    
    # Custom styling override for better presentation
    custom_style = """
    <style type="text/css">
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f8f9fa; }
        h1 { color: #343a40; text-align: center; }
        table.diff { border-collapse: collapse; border: 1px solid #dee2e6; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.05); background-color: #fff; }
        table.diff td { padding: 4px 8px; font-family: 'Courier New', Courier, monospace; font-size: 14px; }
        .diff_header { background-color: #e9ecef; text-align: right; color: #6c757d; user-select: none; width: 40px; border-right: 1px solid #dee2e6; }
        .diff_next { background-color: #f1f3f5; width: 20px; text-align: center; }
        .diff_add { background-color: #d4edda !important; color: #155724; }
        .diff_chg { background-color: #fff3cd !important; color: #856404; }
        .diff_sub { background-color: #f8d7da !important; color: #721c24; }
        thead { background-color: #343a40; color: #fff; font-weight: bold; }
        thead th { padding: 10px; border: 1px solid #454d55; }
    </style>
    """
    html_content = html_content.replace('</head>', f'{custom_style}</head>')
    html_content = html_content.replace('<body>', f'<body><h1>File Difference Report</h1>')
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML comparison report successfully generated at {output_path}")
        return True
    except Exception as e:
        print(f"Error saving HTML diff: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="File Diff Tool - Analyze differences between two files.")
    parser.add_argument("file1", help="Path to the first (original) file")
    parser.add_argument("file2", help="Path to the second (modified) file")
    parser.add_argument("-o", "--output-html", help="Path to output side-by-side HTML report")
    parser.add_argument("-w", "--ignore-whitespace", action="store_true", help="Ignore trailing whitespaces and blank line differences")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file1):
        print(f"Error: File '{args.file1}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.file2):
        print(f"Error: File '{args.file2}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        # Read files
        with open(args.file1, 'r', encoding='utf-8', errors='replace') as f1:
            file1_lines = f1.readlines()
        with open(args.file2, 'r', encoding='utf-8', errors='replace') as f2:
            file2_lines = f2.readlines()
            
        file1_name = os.path.basename(args.file1)
        file2_name = os.path.basename(args.file2)
        
        if args.output_html:
            generate_html_diff(file1_lines, file2_lines, file1_name, file2_name, args.output_html)
        else:
            print_colored_diff(file1_lines, file2_lines, file1_name, file2_name, args.ignore_whitespace)
            
    except Exception as e:
        print(f"Error comparing files: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
