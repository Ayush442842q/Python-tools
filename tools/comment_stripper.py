#!/usr/bin/env python3
"""
Code Comment Stripper
A standalone CLI utility to strip comments, docstrings, and blank lines from source code files.
Supports Python, JavaScript/TypeScript, C, C++, and Java.
"""

import argparse
import os
import re
import sys


def strip_python_comments_and_docstrings(content, keep_docstrings=False, keep_blank_lines=True):
    """Strip comments and optionally docstrings from Python code."""
    # Pattern for docstrings (triple double/single quotes)
    # We need to handle this carefully without breaking string literals, but for a regex-based
    # standalone tool, we use standard regex patterns that match most common cases.
    if not keep_docstrings:
        # Match triple-quoted strings that are docstrings (standalone or right after def/class)
        # Note: A full AST parse is safer, but regex is portable and fast for standalone utilities.
        # This matches '''...''' and """..."""
        docstring_pattern = re.compile(r'(""\"|\'\'\')(.*?)\1', re.DOTALL)
        content = docstring_pattern.sub('', content)

    # Strip single line comments (#) not inside strings
    # A simple way to strip # comments while preserving them inside strings is to tokenise or use regex.
    # Below is a common regex to match strings or comments, and keep strings while removing comments.
    pattern = re.compile(
        r'(\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*"|#.*)'
    )
    
    def replace(match):
        group = match.group(0)
        if group.startswith('#'):
            return ''
        return group
        
    lines = []
    for line in content.splitlines():
        new_line = pattern.sub(replace, line)
        if not keep_blank_lines and not new_line.strip():
            continue
        lines.append(new_line)
        
    return '\n'.join(lines)


def strip_c_style_comments(content, keep_blank_lines=True):
    """Strip block (/* ... */) and line (// ...) comments from C/C++/Java/JS code."""
    # Pattern to match strings, block comments, and line comments
    pattern = re.compile(
        r'(\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*"|/\*.*?\*/|//.*)',
        re.DOTALL | re.MULTILINE
    )
    
    def replace(match):
        group = match.group(0)
        if group.startswith('/*') or group.startswith('//'):
            return ''
        return group
        
    content = pattern.sub(replace, content)
    
    if not keep_blank_lines:
        lines = [line for line in content.splitlines() if line.strip()]
        return '\n'.join(lines)
        
    return content


def process_file(input_file, output_file=None, lang=None, no_blank=False, no_docstrings=False):
    """Read file, strip comments, and write to output or stdout."""
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.", file=sys.stderr)
        return 1

    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{input_file}': {e}", file=sys.stderr)
        return 1

    # Auto-detect language
    if not lang:
        _, ext = os.path.splitext(input_file.lower())
        if ext == '.py':
            lang = 'python'
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            lang = 'javascript'
        elif ext in ['.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.cs']:
            lang = 'c-style'
        else:
            print(f"Warning: Unknown extension '{ext}'. Defaulting to C-style comments.", file=sys.stderr)
            lang = 'c-style'

    # Process based on language
    if lang == 'python':
        result = strip_python_comments_and_docstrings(
            content,
            keep_docstrings=not no_docstrings,
            keep_blank_lines=not no_blank
        )
    else:
        result = strip_c_style_comments(
            content,
            keep_blank_lines=not no_blank
        )

    # Output results
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"Successfully processed {input_file} -> {output_file}")
        except Exception as e:
            print(f"Error writing to '{output_file}': {e}", file=sys.stderr)
            return 1
    else:
        print(result)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Strip comments and blank lines from Python, JavaScript, C/C++, Java source files."
    )
    parser.add_argument("file", help="Path to the source file to process")
    parser.add_argument("-o", "--output", help="Path to write the stripped output (default: print to stdout)")
    parser.add_argument("--lang", choices=["python", "javascript", "c-style"],
                        help="Force language rules (default: auto-detected by file extension)")
    parser.add_argument("--no-blank", action="store_true", help="Strip empty/blank lines")
    parser.add_argument("--no-docstrings", action="store_true", help="For Python files, strip triple-quoted docstrings")

    args = parser.parse_args()
    return process_file(
        args.file,
        output_file=args.output,
        lang=args.lang,
        no_blank=args.no_blank,
        no_docstrings=args.no_docstrings
    )


if __name__ == "__main__":
    sys.exit(main())
