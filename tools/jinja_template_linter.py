#!/usr/bin/env python3
"""
Jinja Template Linter - Static analysis and structural validation for Jinja2/Django templates.
"""

import argparse
import sys
import re
import os

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

# Regular expressions for Jinja blocks
RE_JINJA_EXPR = re.compile(r'\{\{.*?\}\}', re.DOTALL)
RE_JINJA_BLOCK = re.compile(r'\{%.*?%\}', re.DOTALL)
RE_JINJA_COMMENT = re.compile(r'\{#.*?#\}', re.DOTALL)

# Block matching control keywords
JINJA_START_BLOCKS = {"if", "for", "block", "macro", "filter", "with", "call", "set"}
JINJA_END_BLOCKS = {
    "endif": "if",
    "endfor": "for",
    "endblock": "block",
    "endmacro": "macro",
    "endfilter": "filter",
    "endwith": "with",
    "endcall": "call",
}

# Regex to find starting tag in block (e.g. {% if x > 1 %})
RE_BLOCK_COMMAND = re.compile(r'\{%\s*([-+]?)\s*(\w+)')

# HTML tag matcher (simplified for structural checks)
RE_HTML_TAG = re.compile(r'<(/?)(\w+)([^>]*?)>')

def check_template(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"], 0

    errors = []
    lines = content.splitlines()

    # Step 1: Check for unclosed template delimiters {{, {%, {#
    for idx, line in enumerate(lines, 1):
        # Count curly-braces and percentage/hash combinations
        open_expr = line.count("{{")
        close_expr = line.count("}}")
        if open_expr != close_expr:
            errors.append(f"Line {idx}: Unbalanced expression braces ('{{{{' vs '}}}}')")
            
        open_block = line.count("{%")
        close_block = line.count("%}")
        if open_block != close_block:
            errors.append(f"Line {idx}: Unbalanced block delimiters ('{{%' vs '%}}')")

        open_comment = line.count("{#")
        close_comment = line.count("#}")
        if open_comment != close_comment:
            errors.append(f"Line {idx}: Unbalanced comment delimiters ('{{#' vs '#}}')")

    # Step 2: Validate Jinja control block nesting (e.g., {% if %} ... {% endif %})
    block_stack = [] # Stack stores tuples: (block_type, line_number, full_token)
    
    # We tokenise all block tags and trace line numbers
    # To keep line numbers accurate, we scan line by line
    for idx, line in enumerate(lines, 1):
        for match in RE_BLOCK_COMMAND.finditer(line):
            cmd = match.group(2)
            if cmd in JINJA_START_BLOCKS:
                # Some 'set' blocks are inline {% set x = 1 %}, check if they contain a closing endset or assignment
                if cmd == "set" and "=" in line:
                    # Inline set, skip nesting validation
                    continue
                block_stack.append((cmd, idx, match.group(0)))
            elif cmd in JINJA_END_BLOCKS:
                expected_start = JINJA_END_BLOCKS[cmd]
                if not block_stack:
                    errors.append(f"Line {idx}: Found closing block '{cmd}' but no open control blocks are active")
                else:
                    last_start, start_line, token = block_stack.pop()
                    if last_start != expected_start:
                        errors.append(f"Line {idx}: Mismatched closing block '{cmd}' (expected '{last_start}' from Line {start_line})")

    # Check for unclosed blocks remaining on the stack
    while block_stack:
        block_type, start_line, token = block_stack.pop()
        errors.append(f"Line {start_line}: Unclosed Jinja control block '{block_type}'")

    # Step 3: Basic HTML tag balance check (ignoring self-closing and dynamic variables in tags)
    html_stack = []
    self_closing_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    
    # Simple scanner for HTML tags
    for idx, line in enumerate(lines, 1):
        # Strip comments and Jinja expression blocks to avoid matching brackets/tokens inside HTML tags
        cleaned_line = RE_JINJA_EXPR.sub("", line)
        cleaned_line = RE_JINJA_BLOCK.sub("", cleaned_line)
        cleaned_line = RE_JINJA_COMMENT.sub("", cleaned_line)
        
        for match in RE_HTML_TAG.finditer(cleaned_line):
            is_closing = bool(match.group(1))
            tag_name = match.group(2).lower()
            attrs = match.group(3)
            
            # Check if tag is self-closing (ends with '/')
            if attrs.strip().endswith("/") or tag_name in self_closing_tags:
                continue
                
            if is_closing:
                if not html_stack:
                    # Closing tag without open tag
                    errors.append(f"Line {idx}: Stray closing HTML tag '</{tag_name}>'")
                else:
                    last_tag, last_line = html_stack.pop()
                    if last_tag != tag_name:
                        # Re-add to stack if it doesn't match, to help debug nesting
                        errors.append(f"Line {idx}: Mismatched closing HTML tag '</{tag_name}>' (expected '</{last_tag}>' from Line {last_line})")
            else:
                html_stack.append((tag_name, idx))

    return errors, len(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Jinja Template Linter - Validate Jinja2 and Django HTML templates for structural errors."
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Template files or folders to check")
    parser.add_argument(
        "--extensions", nargs="*", default=[".html", ".jinja", ".j2", ".html.j2"],
        help="Template file extensions to lint"
    )
    args = parser.parse_args()

    files_to_check = []
    for path in args.paths:
        if os.path.isfile(path):
            files_to_check.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if any(file.endswith(ext) for ext in args.extensions):
                        files_to_check.append(os.path.join(root, file))

    if not files_to_check:
        print(f"{COLOR_YELLOW}No template files found with the specified extensions.{COLOR_RESET}")
        return

    print("=" * 80)
    print(f"{COLOR_BOLD}{COLOR_HEADER}JINJA2 / DJANGO TEMPLATE LINTER{COLOR_RESET}")
    print("=" * 80)
    print(f"Auditing {len(files_to_check)} template files...")
    print("=" * 80)
    print()

    total_errors = 0
    failing_files = 0

    for file_path in files_to_check:
        errors, lines_count = check_template(file_path)
        rel_path = os.path.relpath(file_path)
        
        if errors:
            failing_files += 1
            total_errors += len(errors)
            print(f"[{COLOR_RED}FAIL{COLOR_RESET}] {rel_path} ({lines_count} lines)")
            for err in errors:
                print(f"  • {COLOR_YELLOW}{err}{COLOR_RESET}")
            print()
        else:
            print(f"[{COLOR_GREEN}PASS{COLOR_RESET}] {rel_path} ({lines_count} lines)")

    print("=" * 80)
    print(f"{COLOR_BOLD}Audit Complete:{COLOR_RESET}")
    if total_errors == 0:
        print(f"  {COLOR_GREEN}All templates are structurally sound!{COLOR_RESET}")
    else:
        print(f"  {COLOR_RED}{failing_files} files failed validation with {total_errors} errors.{COLOR_RESET}")
    print("=" * 80)

if __name__ == "__main__":
    main()
