#!/usr/bin/env python3
"""
HTML Form Auditor
Parses HTML files and audits all <form> elements for accessibility, usability, and security issues.
"""

import argparse
from html.parser import HTMLParser
import os
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current_form = None
        self.label_stack = []
        self.labels_by_for = {}
        self.labels_nesting_inputs = [] # list of input IDs nested in labels
        self.has_nested_label_input = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        
        if tag == "form":
            self.current_form = {
                "line": self.getpos()[0],
                "action": attr_dict.get("action", ""),
                "method": attr_dict.get("method", "get").lower(),
                "inputs": [],
                "buttons": [],
                "labels": [],
                "has_csrf": False
            }
            self.forms.append(self.current_form)
            
        elif tag == "label":
            for_id = attr_dict.get("for")
            if for_id:
                self.labels_by_for[for_id] = self.getpos()[0]
            self.label_stack.append({
                "line": self.getpos()[0],
                "for": for_id,
                "nested_inputs": []
            })
            if self.current_form:
                self.current_form["labels"].append(attr_dict)

        elif tag in ("input", "select", "textarea"):
            input_type = attr_dict.get("type", "text").lower() if tag == "input" else tag
            input_name = attr_dict.get("name", "")
            input_id = attr_dict.get("id", "")
            
            input_info = {
                "tag": tag,
                "type": input_type,
                "name": input_name,
                "id": input_id,
                "line": self.getpos()[0],
                "aria_label": attr_dict.get("aria-label"),
                "aria_labelledby": attr_dict.get("aria-labelledby"),
                "has_parent_label": len(self.label_stack) > 0
            }
            
            if self.current_form:
                self.current_form["inputs"].append(input_info)
                # Check for CSRF tokens
                if input_name and any(csrf_word in input_name.lower() for csrf_word in ("csrf", "xsrf", "token")):
                    self.current_form["has_csrf"] = True
                    
            if self.label_stack:
                self.label_stack[-1]["nested_inputs"].append(input_info)

        elif tag == "button":
            btn_type = attr_dict.get("type", "submit").lower()
            if self.current_form:
                self.current_form["buttons"].append({
                    "type": btn_type,
                    "line": self.getpos()[0]
                })

    def handle_endtag(self, tag):
        if tag == "form":
            self.current_form = None
        elif tag == "label" and self.label_stack:
            label = self.label_stack.pop()
            # If the label has nested inputs, mark them as having parent label
            for input_info in label["nested_inputs"]:
                if input_info["id"]:
                    self.labels_nesting_inputs.append(input_info["id"])

def audit_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()
    except Exception as e:
        return None, str(e)

    parser = FormParser()
    parser.feed(html_content)
    
    findings = []
    
    for form in parser.forms:
        form_findings = {
            "line": form["line"],
            "action": form["action"],
            "method": form["method"],
            "accessibility": [],
            "usability": [],
            "security": []
        }
        
        # 1. Usability Audits
        # Check for submit button
        has_submit = False
        for btn in form["buttons"]:
            if btn["type"] == "submit":
                has_submit = True
                break
        for inp in form["inputs"]:
            if inp["type"] == "submit" or inp["type"] == "image":
                has_submit = True
                break
                
        if not has_submit:
            form_findings["usability"].append("Form is missing a submit button (e.g. <button type=\"submit\"> or <input type=\"submit\">).")

        # Check inputs for missing name attributes
        for inp in form["inputs"]:
            if inp["type"] in ("submit", "image", "button", "reset"):
                continue
            if not inp["name"]:
                form_findings["usability"].append(f"Line {inp['line']}: <{inp['tag']}> field is missing a 'name' attribute (value won't be submitted).")

        # 2. Accessibility Audits
        for inp in form["inputs"]:
            if inp["type"] in ("submit", "hidden", "button", "reset", "image"):
                continue
            
            # Check if input has label
            has_label = False
            # Check if matching label by for-id
            if inp["id"] and (inp["id"] in parser.labels_by_for or inp["id"] in parser.labels_nesting_inputs):
                has_label = True
            # Check if input is nested inside label
            if inp["has_parent_label"]:
                has_label = True
            # Check aria attributes
            if inp["aria_label"] or inp["aria_labelledby"]:
                has_label = True
                
            if not has_label:
                form_findings["accessibility"].append(
                    f"Line {inp['line']}: <{inp['tag']}> field (id='{inp['id']}', name='{inp['name']}') is missing an accessible label or aria-label."
                )

        # 3. Security Audits
        # Check for password sent over HTTP
        has_password = False
        for inp in form["inputs"]:
            if inp["type"] == "password":
                has_password = True
                break
                
        if has_password:
            action = form["action"].lower()
            if action.startswith("http://"):
                form_findings["security"].append("CRITICAL: Password form submits to insecure HTTP endpoint.")
            elif not action.startswith("https://") and action != "" and not action.startswith("/") and not action.startswith("."):
                form_findings["security"].append("Warning: Password form action is not explicitly HTTPS.")

        # Check for CSRF field in POST forms
        if form["method"] == "post" and not form["has_csrf"]:
            form_findings["security"].append("Warning: POST form does not contain a CSRF token input field.")

        # Only add to results if there are warnings
        if form_findings["accessibility"] or form_findings["usability"] or form_findings["security"]:
            findings.append(form_findings)

    return findings, None

def main():
    parser = argparse.ArgumentParser(
        description="Scan HTML files to audit all <form> elements for accessibility, usability, and security issues."
    )
    parser.add_argument("path", help="HTML file or directory path to scan")
    parser.add_argument(
        "--exclude-dirs",
        default="node_modules,.git,dist,build,.agents",
        help="Comma-separated list of directories to exclude from recursive scans"
    )

    args = parser.parse_args()
    exclude_dirs = [d.strip() for d in args.exclude_dirs.split(",")]

    target_path = args.path
    if not os.path.exists(target_path):
        print(f"{RED}Error: Path '{target_path}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    html_files = []
    if os.path.isfile(target_path):
        if target_path.endswith((".html", ".htm", ".xhtml")):
            html_files.append(target_path)
    else:
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file.endswith((".html", ".htm", ".xhtml")):
                    html_files.append(os.path.join(root, file))

    if not html_files:
        print(f"{YELLOW}No HTML (.html/.htm) files found to scan.{RESET}")
        sys.exit(0)

    print(f"{BOLD}{BLUE}Scanning {len(html_files)} HTML file(s) for form audits...{RESET}\n")

    total_issues = 0
    files_with_issues = 0

    for filepath in sorted(html_files):
        findings, err = audit_file(filepath)
        if err:
            print(f"{YELLOW}Skipped {filepath}: {err}{RESET}")
            continue
        
        if findings:
            files_with_issues += 1
            rel_path = os.path.relpath(filepath)
            print(f"{BOLD}{UNDERLINE_IF_POSSIBLE(rel_path)}{RESET}")
            
            for form in findings:
                print(f"  {BOLD}Form at Line {form['line']}{RESET} (action='{form['action']}', method='{form['method']}')")
                
                if form["security"]:
                    print(f"    {RED}Security Issues:{RESET}")
                    for issue in form["security"]:
                        print(f"      - {issue}")
                        total_issues += 1
                
                if form["usability"]:
                    print(f"    {YELLOW}Usability Issues:{RESET}")
                    for issue in form["usability"]:
                        print(f"      - {issue}")
                        total_issues += 1
                        
                if form["accessibility"]:
                    print(f"    {BLUE}Accessibility Issues:{RESET}")
                    for issue in form["accessibility"]:
                        print(f"      - {issue}")
                        total_issues += 1
                print()

    print("=" * 60)
    if total_issues > 0:
        print(f"{RED}{BOLD}Scan complete. Found {total_issues} issues across {files_with_issues} files.{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}✔ Scan complete. All forms are valid, accessible, and follow best practices!{RESET}")
        sys.exit(0)

def UNDERLINE_IF_POSSIBLE(text):
    return f"\033[4m{text}\033[24m"

if __name__ == "__main__":
    main()
