#!/usr/bin/env python3
"""
HTML Accessibility Checker - Analyze HTML files for WCAG compliance and accessibility issues.

Usage:
    python tools/html_accessibility_checker.py <FILE_OR_DIRECTORY>
"""

import os
import sys
import argparse
from html.parser import HTMLParser

# ANSI Color codes for clean output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

GENERIC_LINK_TEXTS = {
    "click here", "click", "here", "read more", "more", "learn more", 
    "go", "link", "page", "button", "continue", "start", "submit", "next", "prev"
}

class AccessibilityParser(HTMLParser):
    def __init__(self, filename=""):
        super().__init__()
        self.filename = filename
        self.issues = []
        
        # State tracking
        self.has_html = False
        self.has_lang = False
        self.has_title = False
        self.title_text = ""
        self.headings = [] # list of (tag, line_no)
        self.element_ids = {} # id -> list of line_no
        self.inputs = [] # list of dict: {id, type, line_no, has_label_wrap}
        self.label_fors = {} # for_id -> line_no
        self.current_tag_stack = [] # stack of tags currently open
        
        # Link and button tracking
        self.in_link = False
        self.link_start_line = 0
        self.link_attrs = []
        self.link_text_accumulator = []
        
        self.in_button = False
        self.button_start_line = 0
        self.button_attrs = []
        self.button_text_accumulator = []
        
        self.in_title = False

    def add_issue(self, severity, message, line_no):
        self.issues.append({
            "severity": severity, # 'ERROR' or 'WARNING'
            "message": message,
            "line": line_no
        })

    def handle_starttag(self, tag, attrs):
        self.current_tag_stack.append(tag)
        attrs_dict = dict(attrs)
        line_no, _ = self.getpos()

        # Track IDs
        if "id" in attrs_dict:
            elem_id = attrs_dict["id"].strip()
            if elem_id:
                if elem_id in self.element_ids:
                    self.element_ids[elem_id].append(line_no)
                else:
                    self.element_ids[elem_id] = [line_no]

        # 1. HTML tag checks
        if tag == "html":
            self.has_html = True
            if "lang" in attrs_dict and attrs_dict["lang"].strip():
                self.has_lang = True
            else:
                self.add_issue("ERROR", "<html> tag missing 'lang' attribute.", line_no)

        # 2. Image alt text check
        elif tag == "img":
            if "alt" not in attrs_dict:
                self.add_issue("ERROR", "<img> tag missing 'alt' attribute.", line_no)
            elif not attrs_dict["alt"].strip():
                # Decorative images should have role="presentation" or alt=""
                if attrs_dict.get("role") != "presentation" and "alt" in attrs_dict:
                    self.add_issue("WARNING", "<img> tag has empty 'alt' attribute without role='presentation' (if decorative).", line_no)

        # 3. Form input checking
        elif tag in ("input", "textarea", "select"):
            # Skip hidden inputs
            if tag == "input" and attrs_dict.get("type") == "hidden":
                pass
            else:
                # Check if wrapped in a label
                is_wrapped = "label" in self.current_tag_stack
                self.inputs.append({
                    "id": attrs_dict.get("id"),
                    "type": tag,
                    "line_no": line_no,
                    "has_label_wrap": is_wrapped,
                    "aria-label": attrs_dict.get("aria-label"),
                    "aria-labelledby": attrs_dict.get("aria-labelledby"),
                })

        # 4. Label for tracking
        elif tag == "label":
            if "for" in attrs_dict:
                self.label_fors[attrs_dict["for"].strip()] = line_no

        # 5. Heading hierarchy tracking
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append((tag, line_no))

        # 6. Title tag tracking
        elif tag == "title":
            self.in_title = True
            self.has_title = True

        # 7. Link (anchor) tracking
        elif tag == "a":
            self.in_link = True
            self.link_start_line = line_no
            self.link_attrs = attrs
            self.link_text_accumulator = []

        # 8. Button tracking
        elif tag == "button" or attrs_dict.get("role") == "button":
            self.in_button = True
            self.button_start_line = line_no
            self.button_attrs = attrs
            self.button_text_accumulator = []

    def handle_endtag(self, tag):
        line_no, _ = self.getpos()
        if self.current_tag_stack and self.current_tag_stack[-1] == tag:
            self.current_tag_stack.pop()
        else:
            # tag mismatch, let's just pop if found or ignore
            if tag in self.current_tag_stack:
                while self.current_tag_stack:
                    popped = self.current_tag_stack.pop()
                    if popped == tag:
                        break

        if tag == "title":
            self.in_title = False
        elif tag == "a" and self.in_link:
            self.in_link = False
            self.process_link()
        elif (tag == "button" or tag == "div" or tag == "span") and self.in_button:
            # We don't want nesting issues to mess up, so only check button closure
            self.in_button = False
            self.process_button()

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data
        elif self.in_link:
            self.link_text_accumulator.append(data)
        elif self.in_button:
            self.button_text_accumulator.append(data)

    def process_link(self):
        link_text = "".join(self.link_text_accumulator).strip().lower()
        attrs_dict = dict(self.link_attrs)
        
        # Check for empty links
        if not link_text and "aria-label" not in attrs_dict and "aria-labelledby" not in attrs_dict:
            # Might contain nested tags (like img), check for img in nested tags later,
            # but standard accessibility requires accessible text.
            self.add_issue("WARNING", "Anchor link has no text content and no aria-label.", self.link_start_line)
            return

        # Check for generic link text
        if link_text in GENERIC_LINK_TEXTS:
            if "aria-label" not in attrs_dict and "aria-labelledby" not in attrs_dict:
                self.add_issue("WARNING", f"Link text '{link_text}' is generic. Consider using more descriptive text or adding 'aria-label'.", self.link_start_line)

    def process_button(self):
        button_text = "".join(self.button_text_accumulator).strip()
        attrs_dict = dict(self.button_attrs)

        if not button_text and "aria-label" not in attrs_dict and "aria-labelledby" not in attrs_dict:
            self.add_issue("ERROR", "Button has no text content and no aria-label.", self.button_start_line)

    def run_post_checks(self):
        # 1. Heading structure checks
        if not self.headings:
            self.add_issue("WARNING", "Document has no headings (<h1>-<h6>).", 1)
        else:
            # Verify h1 exists
            h1s = [tag for tag, line in self.headings if tag == "h1"]
            if not h1s:
                self.add_issue("WARNING", "Document missing a top-level <h1> heading.", 1)
            
            # Check for skips
            prev_level = 0
            for tag, line in self.headings:
                level = int(tag[1])
                if prev_level > 0 and level - prev_level > 1:
                    self.add_issue("WARNING", f"Heading level skipped from h{prev_level} to h{level}.", line)
                prev_level = level

        # 2. Title checks
        if not self.has_title:
            self.add_issue("ERROR", "Document is missing a <title> element.", 1)
        elif not self.title_text.strip():
            self.add_issue("ERROR", "Document <title> is empty.", 1)

        # 3. Label matching checks
        for inp in self.inputs:
            # Check label wrapping
            if inp["has_label_wrap"]:
                continue
            # Check aria label
            if inp["aria-label"] or inp["aria-labelledby"]:
                continue
            
            # Check ID match
            inp_id = inp["id"]
            if not inp_id:
                self.add_issue("ERROR", f"<{inp['type']}> element has no 'id' and is not wrapped in a <label>.", inp["line_no"])
            elif inp_id not in self.label_fors:
                self.add_issue("ERROR", f"<{inp['type']}> element with id '{inp_id}' has no associated <label for='{inp_id}'>.", inp["line_no"])

        # 4. Duplicate ID checks
        for elem_id, lines in self.element_ids.items():
            if len(lines) > 1:
                lines_str = ", ".join(map(str, lines))
                self.add_issue("ERROR", f"Duplicate element ID '{elem_id}' found on lines: {lines_str}.", lines[0])

def analyze_file(file_path):
    print(f"{BOLD}{BLUE}Analyzing: {file_path}{RESET}")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"  {RED}Error reading file: {e}{RESET}")
        return 0, 0

    parser = AccessibilityParser(file_path)
    try:
        parser.feed(content)
        parser.run_post_checks()
    except Exception as e:
        print(f"  {RED}Error parsing HTML: {e}{RESET}")
        return 0, 0

    errors = [issue for issue in parser.issues if issue["severity"] == "ERROR"]
    warnings = [issue for issue in parser.issues if issue["severity"] == "WARNING"]

    # Sort issues by line number
    sorted_issues = sorted(parser.issues, key=lambda x: x["line"])

    if not sorted_issues:
        print(f"  {GREEN}✓ No accessibility issues found!{RESET}")
    else:
        for issue in sorted_issues:
            color = RED if issue["severity"] == "ERROR" else YELLOW
            print(f"  {color}[{issue['severity']}] Line {issue['line']}:{RESET} {issue['message']}")
        
        print(f"\n  Summary: {RED if errors else GREEN}{len(errors)} Errors{RESET}, {YELLOW if warnings else GREEN}{len(warnings)} Warnings{RESET}\n")

    return len(errors), len(warnings)

def main():
    parser = argparse.ArgumentParser(
        description="HTML Accessibility Checker - Analyze HTML files for WCAG accessibility issues."
    )
    parser.add_argument("path", help="HTML file or directory of HTML files to check.")
    args = parser.parse_args()

    # Enable Windows ANSI escape codes support
    if sys.platform == "win32":
        os.system("color")

    target = args.path
    if not os.path.exists(target):
        print(f"{RED}Error: Path '{target}' does not exist.{RESET}", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0
    files_checked = 0

    if os.path.isdir(target):
        for root, _, files in os.walk(target):
            for file in files:
                if file.endswith((".html", ".htm")):
                    full_path = os.path.join(root, file)
                    err, warn = analyze_file(full_path)
                    total_errors += err
                    total_warnings += warn
                    files_checked += 1
        print(f"{BOLD}Total checked: {files_checked} files. Overall: {RED if total_errors else GREEN}{total_errors} Errors{RESET}, {YELLOW if total_warnings else GREEN}{total_warnings} Warnings{RESET}")
    else:
        err, warn = analyze_file(target)
        total_errors = err
        total_warnings = warn

    return 1 if total_errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
