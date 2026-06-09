#!/usr/bin/env python3
"""
Markdown Linter - A style and formatting checker for Markdown files.

Checks files for:
- Heading hierarchy (MD001 - no skipping heading levels)
- Trailing whitespace (MD002)
- Consecutive blank lines (MD003 - max 2 consecutive blank lines)
- Empty links/images (MD004 - e.g., []() or ![]())
- Missing image alt text (MD005 - e.g., ![](image.png))
- Missing code block languages (MD006 - e.g., triple backticks without a language)
"""

import argparse
import os
import re
import sys

# Terminal colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @classmethod
    def disable(cls):
        cls.HEADER = ''
        cls.BLUE = ''
        cls.GREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''

# Rules definition
RULES = {
    'MD001': 'Heading levels must only increment by 1 (e.g., no ### directly after #)',
    'MD002': 'Line contains trailing whitespace',
    'MD003': 'Too many consecutive blank lines (maximum of 2 allowed)',
    'MD004': 'Empty link target or description',
    'MD005': 'Image missing alternative description text',
    'MD006': 'Code block missing syntax highlighting language'
}

def lint_file(file_path):
    """Lints a single markdown file and returns list of errors."""
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [{'line': 0, 'rule': 'ERROR', 'msg': f"Could not read file: {e}", 'snippet': ''}]

    prev_heading_level = 0
    blank_lines_count = 0
    in_code_block = False

    for idx, line in enumerate(lines, 1):
        stripped_line = line.rstrip('\r\n')
        
        # Rule MD002: Trailing whitespace
        if len(stripped_line) < len(line) - 2 and line.endswith((' \n', ' \r\n', '\t\n')):
            # Note: Markdown allows double spaces at the end for line break, so check if it is more than 2 spaces, or if it is a single space/tab.
            # However, typically strict linters warn about any trailing whitespace unless it's explicitly double-space for breaks.
            # Let's warn if it is a single space or tab.
            trimmed = line.rstrip('\r\n')
            if trimmed.endswith(' ') and not trimmed.endswith('  '):
                errors.append({
                    'line': idx,
                    'rule': 'MD002',
                    'msg': RULES['MD002'],
                    'snippet': trimmed
                })

        # Track code blocks
        if stripped_line.startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                # Rule MD006: Missing language
                lang = stripped_line[3:].strip()
                if not lang:
                    errors.append({
                        'line': idx,
                        'rule': 'MD006',
                        'msg': RULES['MD006'],
                        'snippet': stripped_line
                    })
            continue

        if in_code_block:
            continue

        # Rule MD003: Consecutive blank lines
        if not stripped_line.strip():
            blank_lines_count += 1
            if blank_lines_count > 2:
                errors.append({
                    'line': idx,
                    'rule': 'MD003',
                    'msg': RULES['MD003'],
                    'snippet': '<blank line>'
                })
        else:
            blank_lines_count = 0

        # Rule MD001: Heading levels
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped_line)
        if heading_match:
            current_level = len(heading_match.group(1))
            if prev_heading_level > 0 and current_level > prev_heading_level + 1:
                errors.append({
                    'line': idx,
                    'rule': 'MD001',
                    'msg': f"{RULES['MD001']} (went from H{prev_heading_level} to H{current_level})",
                    'snippet': stripped_line
                })
            prev_heading_level = current_level

        # Rule MD004: Empty links/images
        # Find all patterns of []() or ![]()
        link_matches = re.finditer(r'(!?)\[(.*?)\]\((.*?)\)', stripped_line)
        for m in link_matches:
            is_image = bool(m.group(1))
            label = m.group(2).strip()
            url = m.group(3).strip()

            if not url or (not label and not is_image):
                errors.append({
                    'line': idx,
                    'rule': 'MD004',
                    'msg': RULES['MD004'],
                    'snippet': m.group(0)
                })

            # Rule MD005: Image alt text
            if is_image and not label:
                errors.append({
                    'line': idx,
                    'rule': 'MD005',
                    'msg': RULES['MD005'],
                    'snippet': m.group(0)
                })

    return errors

def autofix_file(file_path):
    """Automatically fix simple warnings in file (MD002, MD003)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file for autofix: {e}")
        return False

    fixed_lines = []
    blank_lines_count = 0
    in_code_block = False
    fixes_applied = 0

    for line in lines:
        stripped_line = line.rstrip('\r\n')

        # Code block tracking
        if stripped_line.startswith('```'):
            in_code_block = not in_code_block
            fixed_lines.append(line)
            continue

        if in_code_block:
            fixed_lines.append(line)
            continue

        # MD002: Trailing whitespace
        if stripped_line.strip():
            # Check if there is trailing whitespace (and it is not double-space indicating hard break)
            # We strip trailing spaces except double-space at the end
            rstripped = line.rstrip('\r\n')
            ends_with_newline = line[len(rstripped):]
            
            if rstripped.endswith(' ') and not rstripped.endswith('  '):
                new_line = rstripped.rstrip() + ends_with_newline
                fixed_lines.append(new_line)
                fixes_applied += 1
                blank_lines_count = 0
                continue
            elif rstripped.endswith('\t'):
                new_line = rstripped.rstrip() + ends_with_newline
                fixed_lines.append(new_line)
                fixes_applied += 1
                blank_lines_count = 0
                continue
                
            blank_lines_count = 0
            fixed_lines.append(line)
        else:
            # MD003: Consecutive blank lines
            blank_lines_count += 1
            if blank_lines_count <= 2:
                fixed_lines.append(line)
            else:
                fixes_applied += 1 # Skipped this blank line

    if fixes_applied > 0:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)
            print(f"  {Colors.GREEN}✓ Applied {fixes_applied} auto-fix(es) to {os.path.basename(file_path)}{Colors.ENDC}")
            return True
        except Exception as e:
            print(f"  {Colors.FAIL}✗ Failed to write fixes: {e}{Colors.ENDC}")
            return False
    return False

def main():
    parser = argparse.ArgumentParser(description="Markdown Linter - Check and enforce consistent formatting in Markdown files")
    parser.add_argument("path", nargs="?", default=".", help="Markdown file or directory to lint (default: '.')")
    parser.add_argument("--fix", action="store_true", help="Auto-fix autofixable rules (MD002, MD003)")
    parser.add_argument("--no-color", action="store_true", help="Disable colorized terminal output")
    
    args = parser.parse_args()

    if args.no_color or sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            if args.no_color or not sys.stdout.isatty():
                Colors.disable()

    # Gather files
    files_to_lint = []
    if os.path.isfile(args.path):
        if args.path.endswith('.md'):
            files_to_lint.append(args.path)
    elif os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            # Exclude common directories
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv', '.venv', 'build', 'dist']]
            for file in files:
                if file.endswith('.md'):
                    files_to_lint.append(os.path.join(root, file))

    if not files_to_lint:
        print("No Markdown files (.md) found to lint.")
        return 0

    print(f"Linting {len(files_to_lint)} Markdown file(s)...")
    print("-" * 60)

    total_errors = 0
    files_with_errors = 0

    for file_path in files_to_lint:
        # Check autofix first if enabled
        if args.fix:
            autofix_file(file_path)

        errors = lint_file(file_path)
        if errors:
            files_with_errors += 1
            total_errors += len(errors)
            rel_path = os.path.relpath(file_path)
            print(f"\n{Colors.BOLD}{Colors.FAIL}Errors in {rel_path}:{Colors.ENDC}")
            for err in errors:
                print(f"  {Colors.WARNING}Line {err['line']}{Colors.ENDC} [{Colors.BLUE}{err['rule']}{Colors.ENDC}]: {err['msg']}")
                if err['snippet']:
                    print(f"    Snippet: `{err['snippet']}`")
        else:
            # All good
            pass

    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}Linter Summary{Colors.ENDC}")
    print("=" * 50)
    if total_errors == 0:
        print(f"{Colors.GREEN}✓ No issues found! All files conform to guidelines.{Colors.ENDC}")
    else:
        print(f"Files checked:      {len(files_to_lint)}")
        print(f"Files with issues:  {files_with_errors}")
        print(f"Total issues found: {Colors.FAIL}{total_errors}{Colors.ENDC}")
        if not args.fix:
            print(f"\n{Colors.WARNING}Tip: Run with --fix to automatically resolve whitespace and blank line issues.{Colors.ENDC}")
    print("=" * 50 + "\n")

    return 1 if total_errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
