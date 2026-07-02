#!/usr/bin/env python3
"""
Markdown Image Alt-Text & Accessibility Auditor

Scans markdown (.md) documents to identify and audit image references (both Markdown
syntax `![alt](url)` and HTML `<img>` tags). Checks for missing alt text, poor placeholder
descriptions (e.g. "image", "screenshot", "untitled"), and broken local file paths.
Features an interactive wizard to prompt the user for descriptions and patch files in-place.

Usage:
    # Check all files in current directory
    python markdown_image_alt_checker.py .

    # Check and start interactive wizard to fix alt texts in-place
    python markdown_image_alt_checker.py . --wizard
"""

import os
import re
import sys
import argparse

# Regex to match markdown images: ![alt](url)
# Group 1: alt text, Group 2: image URL
MD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

# Regex to match HTML image tags: <img ... alt="..." ...> or similar
# We capture the whole tag first and extract attributes
HTML_IMAGE_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
HTML_ALT_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)

BAD_ALT_PLACEHOLDERS = {
    "", "image", "img", "screenshot", "untitled", "picture", "photo", "alt",
    "alt text", "alttext", "placeholder", "logo", "drawing", "graph"
}

def clean_alt(text):
    return text.strip().lower().replace('_', ' ').replace('-', ' ')

def is_bad_alt(alt):
    cleaned = clean_alt(alt)
    return cleaned in BAD_ALT_PLACEHOLDERS or len(cleaned) < 3

def audit_file(file_path):
    """Audits a single markdown file for alt text issues."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [{"line": 0, "type": "error", "message": f"Could not read file: {e}"}]
        
    file_dir = os.path.dirname(file_path)
    
    for line_num, line in enumerate(lines, start=1):
        # 1. Check Markdown images
        for match in MD_IMAGE_RE.finditer(line):
            alt_text, img_url = match.groups()
            alt_text_clean = alt_text.strip()
            
            # Check for bad alt text
            if is_bad_alt(alt_text_clean):
                issue_type = "missing" if not alt_text_clean else "placeholder"
                issues.append({
                    "line": line_num,
                    "type": issue_type,
                    "tag_type": "markdown",
                    "raw": match.group(0),
                    "alt": alt_text,
                    "url": img_url,
                    "message": f"Markdown image has {issue_type} alt text: '{alt_text}'"
                })
                
            # Check for broken local link
            if not (img_url.startswith('http://') or img_url.startswith('https://') or img_url.startswith('mailto:')):
                # Remove query params or anchors if any
                clean_url = img_url.split('?')[0].split('#')[0]
                # Decode url-encoded paths
                import urllib.parse
                clean_url = urllib.parse.unquote(clean_url)
                
                # Check absolute vs relative paths
                if clean_url.startswith('/'):
                    # Often absolute relative to project root, skip or soft warning
                    continue
                
                local_path = os.path.normpath(os.path.join(file_dir, clean_url))
                if not os.path.exists(local_path):
                    issues.append({
                        "line": line_num,
                        "type": "broken",
                        "tag_type": "markdown",
                        "raw": match.group(0),
                        "alt": alt_text,
                        "url": img_url,
                        "message": f"Broken local link: '{img_url}' (resolves to: {local_path})"
                    })

        # 2. Check HTML <img> images
        for match in HTML_IMAGE_RE.finditer(line):
            raw_tag = match.group(0)
            img_url = match.group(1)
            
            # Find alt attribute within the tag
            alt_match = HTML_ALT_RE.search(raw_tag)
            alt_text = alt_match.group(1) if alt_match else None
            
            if alt_text is None:
                issues.append({
                    "line": line_num,
                    "type": "missing",
                    "tag_type": "html",
                    "raw": raw_tag,
                    "alt": "",
                    "url": img_url,
                    "message": "HTML img tag is missing 'alt' attribute entirely."
                })
            elif is_bad_alt(alt_text):
                issues.append({
                    "line": line_num,
                    "type": "placeholder",
                    "tag_type": "html",
                    "raw": raw_tag,
                    "alt": alt_text,
                    "url": img_url,
                    "message": f"HTML img tag has placeholder alt text: '{alt_text}'"
                })
                
    return issues

def fix_alt_in_file(file_path, line_num, old_raw, tag_type, alt_text, url):
    """Patches a single line in a file with new alt text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        line_idx = line_num - 1
        line_content = lines[line_idx]
        
        if tag_type == "markdown":
            new_raw = f"![{alt_text}]({url})"
        else:
            # For HTML tag, replace alt attribute value or insert it
            if 'alt=' in old_raw:
                new_raw = re.sub(r'alt=["\'][^"\']*["\']', f'alt="{alt_text}"', old_raw)
            else:
                new_raw = old_raw.replace('<img', f'<img alt="{alt_text}"')
                
        # Do the string substitution
        new_line = line_content.replace(old_raw, new_raw)
        lines[line_idx] = new_line
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    except Exception as e:
        print(f"Error patching file: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Audit Markdown files for image alt text accessibility and broken paths."
    )
    parser.add_argument('paths', nargs='*', default=['.'], help="Directories/files to audit")
    parser.add_argument('-w', '--wizard', action='store_true', help="Run interactive fix wizard")
    parser.add_argument('--no-color', action='store_true', help="Disable terminal colors")
    args = parser.parse_args()

    # ANSI Color setup
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt'
    COLOR_RED = "\033[91m" if use_color else ""
    COLOR_YELLOW = "\033[93m" if use_color else ""
    COLOR_GREEN = "\033[92m" if use_color else ""
    COLOR_CYAN = "\033[96m" if use_color else ""
    COLOR_RESET = "\033[0m" if use_color else ""

    markdown_files = []
    
    for path in args.paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                if any(exclude in root for exclude in ['.git', 'node_modules', 'venv', '.venv', '.gemini']):
                    continue
                for f in files:
                    if f.endswith('.md'):
                        markdown_files.append(os.path.join(root, f))
        elif os.path.isfile(path) and path.endswith('.md'):
            markdown_files.append(path)

    if not markdown_files:
        print(f"{COLOR_YELLOW}No Markdown (.md) files found in the specified path(s).{COLOR_RESET}")
        sys.exit(0)

    print(f"{COLOR_CYAN}Scanning {len(markdown_files)} Markdown files for image accessibility...{COLOR_RESET}\n")

    issues_found = 0
    broken_links = 0
    all_reports = {}

    for f in markdown_files:
        report = audit_file(f)
        if report:
            all_reports[f] = report
            issues_found += sum(1 for r in report if r["type"] in ("missing", "placeholder"))
            broken_links += sum(1 for r in report if r["type"] == "broken")

    # Print Report
    for file_path, file_issues in sorted(all_reports.items()):
        print(f"{COLOR_CYAN}File: {file_path}{COLOR_RESET}")
        for issue in file_issues:
            line_lbl = f"Line {issue['line']}:"
            msg = issue['message']
            if issue['type'] == 'broken':
                print(f"  {COLOR_RED}{line_lbl:<9} [BROKEN] {COLOR_RESET} {msg}")
            else:
                print(f"  {COLOR_YELLOW}{line_lbl:<9} [ACCESSIBILITY] {COLOR_RESET} {msg}")
        print()

    print(f"{COLOR_CYAN}=== Scan Results ==={COLOR_RESET}")
    print(f"Total Accessibility Issues (Missing/Placeholder Alt): {COLOR_RED}{issues_found}{COLOR_RESET}")
    print(f"Total Broken Local Links:                             {COLOR_RED}{broken_links}{COLOR_RESET}")

    if issues_found == 0 and broken_links == 0:
        print(f"\n{COLOR_GREEN}✔ Perfect! All images have valid alt text and links resolve.{COLOR_RESET}")
        sys.exit(0)

    # Wizard Mode
    if args.wizard and issues_found > 0:
        print(f"\n{COLOR_CYAN}Starting Interactive Wizard...{COLOR_RESET}")
        print("Type your new alt text and press Enter. To skip an image, press Enter with empty input.\n")
        
        for file_path, file_issues in sorted(all_reports.items()):
            # Filter only accessibility issues, we can't auto-fix broken links easily
            fixable_issues = [i for i in file_issues if i["type"] in ("missing", "placeholder")]
            if not fixable_issues:
                continue
                
            print(f"Editing: {file_path}")
            
            for issue in fixable_issues:
                print(f"\n{COLOR_YELLOW}--- Line {issue['line']} ---{COLOR_RESET}")
                print(f"  Raw Tag: {issue['raw']}")
                print(f"  URL:     {issue['url']}")
                print(f"  Current: '{issue['alt']}'")
                
                try:
                    new_alt = input(f"  {COLOR_GREEN}Enter new alt text:{COLOR_RESET} ").strip()
                    if new_alt:
                        # Patch in-place
                        success = fix_alt_in_file(
                            file_path, issue['line'], issue['raw'],
                            issue['tag_type'], new_alt, issue['url']
                        )
                        if success:
                            print(f"  {COLOR_GREEN}✔ Updated alt text successfully!{COLOR_RESET}")
                            # Update our local copy so future patches on same line work if they exist
                            issue['raw'] = f"![{new_alt}]({issue['url']})" if issue['tag_type'] == "markdown" else f'<img alt="{new_alt}" src="{issue["url"]}">'
                        else:
                            print(f"  {COLOR_RED}✘ Failed to update.{COLOR_RESET}")
                    else:
                        print("  Skipped.")
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{COLOR_YELLOW}Wizard cancelled.{COLOR_RESET}")
                    sys.exit(0)
                    
        print(f"\n{COLOR_GREEN}Wizard finished processing.{COLOR_RESET}")
    else:
        if issues_found > 0:
            print(f"\n{COLOR_YELLOW}Tip: Run this tool with '--wizard' to repair alt-text accessibility interactively.{COLOR_RESET}")
            
    # Exit code reflecting accessibility compliance
    sys.exit(1 if (issues_found > 0 or broken_links > 0) else 0)

if __name__ == '__main__':
    main()
