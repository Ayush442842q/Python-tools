#!/usr/bin/env python3
"""HTML Structural Validator & Linter

A standalone tool to validate HTML files for tag balance, structural nesting,
accessibility issues, and duplicate IDs. Requires no external dependencies.
"""

import argparse
from html.parser import HTMLParser
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Set

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"
COLOR_GREEN = "\033[32m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_BOLD = "\033[1m"

# Inline vs Block elements dictionary for basic nesting checks
# According to HTML5 specs, inline (phrasing) elements shouldn't contain block-level (flow) elements in most cases.
BLOCK_ELEMENTS = {
    'address', 'article', 'aside', 'blockquote', 'details', 'dialog', 'dd', 'div', 'dl', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'header', 'hgroup', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section', 'table', 'ul'
}

INLINE_ELEMENTS = {
    'a', 'abbr', 'b', 'bdi', 'bdo', 'br', 'button', 'cite', 'code', 'data', 'datalist', 'dfn',
    'em', 'i', 'iframe', 'img', 'input', 'kbd', 'label', 'mark', 'meter', 'noscript', 'object',
    'output', 'picture', 'progress', 'q', 'rp', 'rt', 'ruby', 's', 'samp', 'script', 'select',
    'small', 'span', 'strong', 'sub', 'sup', 'svg', 'textarea', 'time', 'u', 'var', 'wbr'
}

# Self-closing tags in HTML5
VOID_ELEMENTS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source',
    'track', 'wbr'
}


class HTMLStructureValidator(HTMLParser):
    def __init__(self, filepath: str = "Unknown"):
        super().__init__()
        self.filepath = filepath
        self.tag_stack: List[Tuple[str, int, int]] = []  # List of (tag_name, line, col)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.observed_ids: Dict[str, Tuple[int, int]] = {}
        self.labels: List[Tuple[str, int, int]] = []  # List of (for_attr, line, col)
        self.inputs: Set[str] = set()  # Set of input IDs
        self.h1_count = 0
        self.main_count = 0

    def error_msg(self, msg: str, line: int, col: int):
        self.errors.append(f"{COLOR_RED}[ERROR]{COLOR_RESET} Line {line}, Col {col}: {msg}")

    def warn_msg(self, msg: str, line: int, col: int):
        self.warnings.append(f"{COLOR_YELLOW}[WARN]{COLOR_RESET} Line {line}, Col {col}: {msg}")

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        line, col = self.getpos()
        attrs_dict = dict(attrs)

        # 1. Self-closing tags should not be pushed to stack
        if tag in VOID_ELEMENTS:
            self.check_void_attributes(tag, attrs_dict, line, col)
            return

        # 2. Check Nesting Rules
        if self.tag_stack:
            parent_tag, parent_line, _ = self.tag_stack[-1]
            
            # Phrasing (inline) content should not contain flow (block) content
            if parent_tag in INLINE_ELEMENTS and tag in BLOCK_ELEMENTS:
                # Exception: <a> can contain block elements in HTML5, but not buttons or interactive elements
                if parent_tag == 'a' and tag in {'a', 'button'}:
                    self.error_msg(f"Interactive element <{tag}> nested inside anchor <a>.", line, col)
                elif parent_tag != 'a':
                    self.warn_msg(f"Block-level element <{tag}> nested inside inline element <{parent_tag}> (opened on line {parent_line}).", line, col)

            # Specific nesting restrictions
            if parent_tag == 'p' and tag in BLOCK_ELEMENTS:
                self.warn_msg(f"Paragraph <p> implicitly closed by block-level element <{tag}>.", line, col)
            if parent_tag == 'button' and tag in {'button', 'a', 'input', 'select', 'textarea'}:
                self.error_msg(f"Interactive element <{tag}> nested inside <button>.", line, col)
            if parent_tag == 'a' and tag == 'a':
                self.error_msg("Anchor <a> nested inside another anchor <a>.", line, col)

        # 3. Track Special Structures
        if tag == 'h1':
            self.h1_count += 1
            if self.h1_count > 1:
                self.warn_msg("Multiple <h1> elements detected. It is recommended to have exactly one per page for SEO.", line, col)
        elif tag == 'main':
            self.main_count += 1
            if self.main_count > 1:
                self.error_msg("Multiple <main> elements detected. A document must only have one.", line, col)

        # 4. Attribute Checks
        self.check_attributes(tag, attrs_dict, line, col)

        # Push to stack
        self.tag_stack.append((tag, line, col))

    def handle_endtag(self, tag: str):
        line, col = self.getpos()
        if tag in VOID_ELEMENTS:
            return  # Void tags do not have end tags

        if not self.tag_stack:
            self.error_msg(f"Unexpected end tag </{tag}> with no matching start tag.", line, col)
            return

        # Find matching tag in stack
        stack_index = -1
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == tag:
                stack_index = i
                break

        if stack_index == -1:
            # No match found, check if it matches parent's close (misspelled close tag)
            expected_tag, start_line, _ = self.tag_stack[-1]
            self.error_msg(f"Mismatched end tag </{tag}>. Expected </{expected_tag}> (to match start tag on line {start_line}).", line, col)
        else:
            # Report unclosed tags that are being skipped
            for i in range(len(self.tag_stack) - 1, stack_index, -1):
                unclosed_tag, u_line, u_col = self.tag_stack[i]
                self.error_msg(f"Unclosed element <{unclosed_tag}> opened on line {u_line}.", line, col)
            
            # Pop stack up to matching tag
            self.tag_stack = self.tag_stack[:stack_index]

    def check_void_attributes(self, tag: str, attrs: Dict[str, str], line: int, col: int):
        if tag == 'img':
            if 'alt' not in attrs:
                self.warn_msg("<img> tag missing 'alt' attribute for accessibility.", line, col)
            elif not attrs['alt'].strip():
                self.warn_msg("<img> tag has empty 'alt' attribute.", line, col)
            if 'src' not in attrs:
                self.error_msg("<img> tag missing 'src' attribute.", line, col)

        if tag == 'input':
            if 'id' in attrs:
                self.inputs.add(attrs['id'])
            # Warn on input missing accessible name if it's not hidden/submit/button
            input_type = attrs.get('type', 'text').lower()
            if input_type not in {'hidden', 'submit', 'button', 'image', 'reset'}:
                if 'id' not in attrs and 'aria-label' not in attrs and 'aria-labelledby' not in attrs:
                    self.warn_msg(f"Input element of type '{input_type}' missing 'id' or 'aria-label' for accessibility.", line, col)

    def check_attributes(self, tag: str, attrs: Dict[str, str], line: int, col: int):
        # Check IDs
        if 'id' in attrs:
            val = attrs['id']
            if val in self.observed_ids:
                prev_line, prev_col = self.observed_ids[val]
                self.error_msg(f"Duplicate ID '{val}' detected. Previously defined on line {prev_line}, col {prev_col}.", line, col)
            else:
                self.observed_ids[val] = (line, col)

        # Check Labels
        if tag == 'label':
            if 'for' in attrs:
                self.labels.append((attrs['for'], line, col))
            else:
                self.warn_msg("<label> missing 'for' attribute (ensure it contains nested form controls).", line, col)

    def finalize(self):
        # 1. Report remaining open tags at EOF
        while self.tag_stack:
            tag, line, col = self.tag_stack.pop()
            self.error_msg(f"Unclosed element <{tag}> at end of file (opened on line {line}).", line, col)

        # 2. Check label/input association
        for label_for, line, col in self.labels:
            if label_for not in self.observed_ids:
                self.warn_msg(f"Label 'for' attribute refers to ID '{label_for}' which does not exist in the document.", line, col)


def validate_file(filepath: Path) -> Tuple[List[str], List[str]]:
    validator = HTMLStructureValidator(filepath=str(filepath))
    try:
        content = filepath.read_text(encoding="utf-8")
        validator.feed(content)
        validator.finalize()
    except Exception as e:
        validator.errors.append(f"{COLOR_RED}[FATAL ERROR]{COLOR_RESET} Failed to read or parse file: {e}")
    return validator.errors, validator.warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate HTML structure, tag nesting, and accessibility guidelines."
    )
    parser.add_argument("path", help="Path to HTML file or directory containing HTML files.")
    parser.add_argument(
        "--errors-only", action="store_true", help="Only output errors, suppressing warnings."
    )
    args = parser.parse_args()

    target_path = Path(args.path)
    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    html_files = []
    if target_path.is_file():
        if target_path.suffix.lower() in {".html", ".htm"}:
            html_files.append(target_path)
    else:
        for ext in ["*.html", "*.htm"]:
            html_files.extend(target_path.rglob(ext))

    if not html_files:
        print(f"No HTML files found at '{args.path}'.")
        sys.exit(0)

    total_errors = 0
    total_warnings = 0

    print(f"{COLOR_BOLD}Scanning {len(html_files)} HTML file(s)...{COLOR_RESET}\n")

    for html_file in html_files:
        errors, warnings = validate_file(html_file)
        
        if errors or (warnings and not args.errors_only):
            # Print file header
            print(f"{COLOR_BOLD}{COLOR_BLUE}--- {html_file.relative_to(target_path.parent if target_path.is_file() else target_path)} ---{COLOR_RESET}")
            
            for err in errors:
                print(err)
            if not args.errors_only:
                for warn in warnings:
                    print(warn)
            print()
            
            total_errors += len(errors)
            total_warnings += len(warnings)

    print(f"{COLOR_BOLD}Validation Summary:{COLOR_RESET}")
    print(f"Files Scanned: {len(html_files)}")
    print(f"Errors Found:   {COLOR_RED if total_errors else COLOR_GREEN}{total_errors}{COLOR_RESET}")
    if not args.errors_only:
        print(f"Warnings Found: {COLOR_YELLOW if total_warnings else COLOR_GREEN}{total_warnings}{COLOR_RESET}")

    if total_errors > 0:
        sys.exit(1)
    else:
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}Success: HTML structure is valid!{COLOR_RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
