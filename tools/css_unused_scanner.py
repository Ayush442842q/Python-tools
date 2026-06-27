#!/usr/bin/env python3
"""
CSS Unused Selector Scanner

Audits your codebase to find unused/dead CSS classes and IDs. Parses a CSS file 
to extract all class and ID selectors, then recursively scans files in a target 
directory (HTML, JS, Python, templates, etc.) to check if they are referenced.

Usage:
    python tools/css_unused_scanner.py <css_file> <search_dir> [options]
"""

import sys
import os
import re
import argparse

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

def print_banner():
    banner = f"""
{MAGENTA}{BOLD}=========================================================
     🎨   CSS UNUSED SELECTOR AUDITOR & CLEANER  🎨
========================================================={RESET}
"""
    print(banner)

def extract_css_selectors(css_path):
    """Parses CSS file and extracts all class names and IDs."""
    if not os.path.exists(css_path):
        print(f"{RED}Error: CSS file '{css_path}' not found.{RESET}", file=sys.stderr)
        return set(), set()

    with open(css_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Strip CSS comments: /* ... */
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    classes = set()
    ids = set()

    # Match selectors before block starts: e.g. .class-name, #id-name, etc.
    # We find blocks of selectors separated by comma or curly brace start
    selector_blocks = re.findall(r'([^{]+)\s*\{', content)
    
    for block in selector_blocks:
        # Split individual selectors in group, e.g. ".btn, .btn-primary"
        selectors = re.split(r'\s*,\s*', block)
        for selector in selectors:
            selector = selector.strip()
            
            # Find classes: .className
            # Match standard CSS class rules (starts with dot, letters/numbers/dashes/underscores)
            class_matches = re.findall(r'\.([a-zA-Z_-][a-zA-Z0-9_-]*)', selector)
            for m in class_matches:
                classes.add(m)
                
            # Find IDs: #idName
            id_matches = re.findall(r'#([a-zA-Z_-][a-zA-Z0-9_-]*)', selector)
            for m in id_matches:
                ids.add(m)

    return classes, ids

def scan_codebase(directory, extensions):
    """Recursively reads files in directory with matching extensions."""
    file_contents = []
    scanned_count = 0

    for root, _, files in os.walk(directory):
        # Ignore common dependency and system directories
        if any(ignored in root for ignored in ["node_modules", ".git", "__pycache__", "venv", ".next", "dist", "build"]):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_contents.append(f.read())
                    scanned_count += 1
                except Exception as e:
                    print(f"{YELLOW}Warning: Could not read '{file_path}': {e}{RESET}")

    return file_contents, scanned_count

def audit_selectors(css_classes, css_ids, file_contents):
    """Checks if each CSS selector is used in the scanned files."""
    unused_classes = []
    unused_ids = []
    
    # Join all file contents to scan in one massive pass for speed
    full_text = "\n\n".join(file_contents)

    print(f"🔍 Analyzing references across files...")
    
    # Audit classes
    for c in sorted(css_classes):
        # Match using word boundaries to avoid false substring matches
        # e.g., if we have ".btn", we don't want it matched inside ".btn-primary"
        pattern = re.compile(rf'\b{re.escape(c)}\b')
        if not pattern.search(full_text):
            unused_classes.append(c)

    # Audit IDs
    for i in sorted(css_ids):
        pattern = re.compile(rf'\b{re.escape(i)}\b')
        if not pattern.search(full_text):
            unused_ids.append(i)

    return unused_classes, unused_ids

def main():
    parser = argparse.ArgumentParser(
        description="CSS Unused Selector Scanner - Scan your codebase to identify unused CSS selectors.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("css_file", help="Path to the CSS file to audit")
    parser.add_argument("search_dir", help="Directory containing source files to search (e.g. src/)")
    parser.add_argument("--extensions", "-e", default=".html,.js,.jsx,.tsx,.vue,.py,.php,.twig", 
                        help="Comma-separated file extensions to scan (default: html,js,jsx,tsx,vue,py,php,twig)")
    
    args = parser.parse_args()
    print_banner()

    target_extensions = [ext.strip().lower() if ext.startswith('.') else f".{ext.strip().lower()}" 
                         for ext in args.extensions.split(',')]

    print(f"🎨 Parsing CSS file : {BOLD}{args.css_file}{RESET}")
    css_classes, css_ids = extract_css_selectors(args.css_file)
    
    total_selectors = len(css_classes) + len(css_ids)
    print(f"   Found {BOLD}{len(css_classes)}{RESET} classes and {BOLD}{len(css_ids)}{RESET} IDs (Total: {total_selectors} selectors).")

    if total_selectors == 0:
        print(f"{YELLOW}No class or ID selectors found in the CSS file. Aborting.{RESET}")
        return 0

    print(f"\n📂 Scanning directory: {BOLD}{args.search_dir}{RESET}")
    print(f"   Filtering files   : {', '.join(target_extensions)}")
    
    file_contents, files_scanned = scan_codebase(args.search_dir, target_extensions)
    print(f"   Successfully loaded {BOLD}{files_scanned}{RESET} files.")

    if files_scanned == 0:
        print(f"{RED}Error: No source files found with the specified extensions in '{args.search_dir}'.{RESET}", file=sys.stderr)
        return 1

    unused_classes, unused_ids = audit_selectors(css_classes, css_ids, file_contents)
    total_unused = len(unused_classes) + len(unused_ids)
    
    dead_pct = (total_unused / total_selectors) * 100 if total_selectors > 0 else 0.0

    print(f"\n{BOLD}📋 CSS Audit Results Summary:{RESET}")
    print(f"  Total Selectors Extracted : {total_selectors}")
    print(f"  Unused Selectors Found    : {RED if total_unused > 0 else GREEN}{total_unused} ({dead_pct:.1f}% dead code){RESET}")
    print(f"    • Unused Classes: {len(unused_classes)}")
    print(f"    • Unused IDs    : {len(unused_ids)}")

    if total_unused > 0:
        print(f"\n{RED}{BOLD}🚨 Unused Selectors Details:{RESET}")
        
        if unused_classes:
            print(f"  {BOLD}Classes ({len(unused_classes)}):{RESET}")
            for c in unused_classes[:30]:  # Limit output length in terminal
                print(f"    • .{c}")
            if len(unused_classes) > 30:
                print(f"    ... and {len(unused_classes) - 30} more classes.")

        if unused_ids:
            print(f"\n  {BOLD}IDs ({len(unused_ids)}):{RESET}")
            for i in unused_ids[:30]:
                print(f"    • #{i}")
            if len(unused_ids) > 30:
                print(f"    ... and {len(unused_ids) - 30} more IDs.")
    else:
        print(f"\n{GREEN}🎉 Perfect! All CSS selectors are referenced in your codebase.{RESET}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
