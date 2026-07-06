#!/usr/bin/env python3
import os
import re
import argparse
import sys
from collections import defaultdict

# Simple ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

# Define Tailwind class categories to detect conflicts.
# Key is category name, value is list of prefixes/patterns.
# We will match classes that share the same prefix group under the same modifier prefix (e.g., md:hover:).
TAILWIND_GROUPS = {
    "display": ["block", "inline-block", "inline", "flex", "inline-flex", "grid", "inline-grid", "table", "hidden"],
    "position": ["static", "fixed", "absolute", "relative", "sticky"],
    "float": ["float-right", "float-left", "float-none"],
    "visibility": ["visible", "invisible", "collapse"],
    "flex-direction": ["flex-row", "flex-row-reverse", "flex-col", "flex-col-reverse"],
    "flex-wrap": ["flex-wrap", "flex-wrap-reverse", "flex-nowrap"],
    "justify-content": ["justify-start", "justify-end", "justify-center", "justify-between", "justify-around", "justify-evenly"],
    "align-items": ["items-start", "items-end", "items-center", "items-baseline", "items-stretch"],
    "align-content": ["content-start", "content-end", "content-center", "content-between", "content-around", "content-stretch"],
    "align-self": ["self-auto", "self-start", "self-end", "self-center", "self-stretch", "self-baseline"],
    "overflow": ["overflow-auto", "overflow-hidden", "overflow-clip", "overflow-visible", "overflow-scroll", "overflow-x-auto", "overflow-x-hidden", "overflow-x-clip", "overflow-x-visible", "overflow-x-scroll", "overflow-y-auto", "overflow-y-hidden", "overflow-y-clip", "overflow-y-visible", "overflow-y-scroll"],
}

# Prefix-based groups (e.g., classes starting with 'p-', 'm-').
# We match based on the exact start prefix (after splitting by '-')
PREFIX_GROUPS = {
    # Padding & Margin
    "p": ["p", "px", "py", "pt", "pb", "pl", "pr"],
    "m": ["m", "mx", "my", "mt", "mb", "ml", "mr"],
    # Width & Height
    "w": ["w"],
    "h": ["h"],
    "max-w": ["max-w"],
    "max-h": ["max-h"],
    "min-w": ["min-w"],
    "min-h": ["min-h"],
    # Typography
    "font-size": ["text"],  # text-xs, text-sm, text-base, text-lg, text-xl... (Note: text-color is also text-, we handle it)
    "font-weight": ["font"], # font-thin, font-normal, font-bold...
    "tracking": ["tracking"],
    "leading": ["leading"],
    "text-align": ["text-left", "text-center", "text-right", "text-justify", "text-start", "text-end"],
    # Backgrounds
    "bg-color": ["bg"],
    "bg-opacity": ["bg-opacity"],
    "bg-size": ["bg-auto", "bg-cover", "bg-contain"],
    # Borders
    "border-width": ["border"],
    "border-color": ["border"],
    "rounded": ["rounded"],
    # Opacity
    "opacity": ["opacity"],
    # Z-Index
    "z-index": ["z"],
}

def parse_tailwind_class(class_name):
    """
    Parses a tailwind class into its modifiers and the base class.
    Example: 'md:hover:p-4' -> (['md', 'hover'], 'p-4')
    """
    parts = class_name.split(':')
    modifiers = parts[:-1]
    base = parts[-1]
    return tuple(sorted(modifiers)), base

def get_class_category(base_class):
    """
    Categorizes the base tailwind class. Returns (category_name, specific_key)
    """
    # 1. Exact match in TAILWIND_GROUPS
    for cat, items in TAILWIND_GROUPS.items():
        if base_class in items:
            return cat, cat

    # 2. Check prefix matches
    # Splitting by hyphen helps check prefixes, e.g., 'max-w-xs' -> 'max-w' prefix
    parts = base_class.split('-')
    
    # Check compound prefixes first like 'max-w', 'min-h', 'bg-opacity'
    if len(parts) >= 2:
        compound = f"{parts[0]}-{parts[1]}"
        if compound in PREFIX_GROUPS:
            return compound, compound
            
    # Check single prefixes like 'p', 'm', 'w', 'h', 'z', 'bg', 'text'
    if parts[0] in PREFIX_GROUPS:
        # Resolve 'text' which could be font size or color (text-sm vs text-red-500)
        if parts[0] == "text":
            # Font sizes are text-xs, text-sm, text-base, text-lg, text-xl, text-2xl, etc.
            # Colors are text-red-500, text-gray-50, text-black, etc.
            if len(parts) >= 2 and parts[1] in ["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl", "7xl", "8xl", "9xl"]:
                return "font-size", "font-size"
            else:
                return "text-color", "text-color"
        
        # Resolve 'bg' which could be bg-color or bg-opacity
        if parts[0] == "bg":
            if len(parts) >= 2 and parts[1] == "opacity":
                return "bg-opacity", "bg-opacity"
            else:
                return "bg-color", "bg-color"
                
        # Resolve 'border' which could be border-width or border-color
        if parts[0] == "border":
            if len(parts) >= 2 and parts[1] in ["0", "2", "4", "8", "x", "y", "t", "b", "l", "r"]:
                return "border-width", "border-width"
            else:
                return "border-color", "border-color"

        # General prefix match
        # Let's map specific sub-prefixes
        for cat, prefixes in PREFIX_GROUPS.items():
            if parts[0] in prefixes:
                # E.g. p, px, py should map to specific sub-categories or general spacing
                # For spacing conflicts, we conflict within the exact same prefix:
                # p-4 vs p-5 (conflict)
                # px-4 vs px-6 (conflict)
                return cat, parts[0]

    return None, None

def analyze_class_string(class_str):
    """
    Analyzes a class string (from class="..." or className="...") and returns list of conflicts found.
    Each conflict is a dict: {category, class1, class2, modifiers}
    """
    classes = [c.strip() for c in class_str.split() if c.strip()]
    parsed = []
    
    # Parse all classes first
    for c in classes:
        mods, base = parse_tailwind_class(c)
        cat, subkey = get_class_category(base)
        if cat:
            parsed.append((c, mods, cat, subkey, base))

    conflicts = []
    # Group parsed classes by (modifiers, category, subkey)
    grouped = defaultdict(list)
    for c, mods, cat, subkey, base in parsed:
        # For spacing classes, conflicts occur when we have multiple values for the exact same subkey
        # e.g., p-4 and p-5 conflict (same subkey 'p')
        # px-4 and px-6 conflict (same subkey 'px')
        # Let's group by (modifiers, cat, subkey)
        # Note: display classes conflict if they have the same modifiers and category
        grouped[(mods, cat, subkey)].append(c)

    for (mods, cat, subkey), items in grouped.items():
        if len(items) > 1:
            # We have a conflict! E.g. ['p-4', 'p-6']
            # De-duplicate identical classes (e.g. 'p-4 p-4')
            unique_items = list(set(items))
            if len(unique_items) > 1:
                conflicts.append({
                    "category": cat,
                    "subkey": subkey,
                    "modifiers": ":".join(mods) if mods else "none",
                    "classes": unique_items
                })
                
    return conflicts

def extract_classes_from_file(file_path):
    """
    Statically extracts class strings from html/jsx/tsx/vue files.
    Matches class="..." and className="..."
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
        return []

    # Regex matches:
    # 1. class="..." or className="..."
    # 2. class='...' or className='...'
    # 3. class={`...`} or className={`...`} (common in React)
    pattern = re.compile(r'(?:class|className)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|\{\s*`([^`]*)`\s*\})')
    
    class_strings = []
    for match in pattern.finditer(content):
        # Find which group matched
        class_str = match.group(1) or match.group(2) or match.group(3)
        if class_str:
            # Get line number of match
            line_no = content.count('\n', 0, match.start()) + 1
            class_strings.append((line_no, class_str.strip()))
            
    return class_strings

def audit_file(file_path, verbose=False):
    """
    Audits a single file and prints conflicts.
    """
    class_strings = extract_classes_from_file(file_path)
    if not class_strings:
        return 0

    file_conflicts = []
    for line_no, class_str in class_strings:
        conflicts = analyze_class_string(class_str)
        if conflicts:
            file_conflicts.append((line_no, class_str, conflicts))

    if file_conflicts:
        print(f"\n{COLOR_CYAN}{COLOR_BOLD}File: {file_path}{COLOR_RESET}")
        for line_no, class_str, conflicts in file_conflicts:
            print(f"  {COLOR_YELLOW}Line {line_no}:{COLOR_RESET} Found {len(conflicts)} class conflicts")
            if verbose:
                print(f"    Raw class string: \"{class_str}\"")
            for c in conflicts:
                mods_prefix = f"[{c['modifiers']}] " if c['modifiers'] != 'none' else ""
                conflict_classes = " vs ".join(f"'{cls}'" for cls in c['classes'])
                print(f"    - {COLOR_RED}Conflict in {c['category']}:{COLOR_RESET} {mods_prefix}{conflict_classes}")
        return len(file_conflicts)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Statically audit files for conflicting Tailwind CSS utility classes."
    )
    parser.add_argument("path", help="Path to a file or directory to scan")
    parser.add_argument(
        "-e", "--extensions", 
        default="html,js,jsx,ts,tsx,vue", 
        help="Comma-separated file extensions to scan (default: html,js,jsx,ts,tsx,vue)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output with raw class strings")
    args = parser.parse_args()

    extensions = [f".{ext.strip().lower()}" for ext in args.extensions.split(",")]
    
    if not os.path.exists(args.path):
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting Tailwind CSS Conflict Auditor...{COLOR_RESET}")
    print(f"Scanning target: {args.path}")
    print(f"Target extensions: {', '.join(extensions)}")
    print("-" * 60)

    total_files_scanned = 0
    total_files_with_conflicts = 0
    total_conflicts_count = 0

    if os.path.isfile(args.path):
        total_files_scanned += 1
        conflicts = audit_file(args.path, args.verbose)
        if conflicts > 0:
            total_files_with_conflicts += 1
            total_conflicts_count += conflicts
    else:
        for root, _, files in os.walk(args.path):
            # Skip node_modules and .git
            if "node_modules" in root or ".git" in root:
                continue
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() in extensions:
                    total_files_scanned += 1
                    conflicts = audit_file(os.path.join(root, file), args.verbose)
                    if conflicts > 0:
                        total_files_with_conflicts += 1
                        total_conflicts_count += conflicts

    print("-" * 60)
    print(f"{COLOR_BOLD}Audit Summary:{COLOR_RESET}")
    print(f"  Files scanned: {total_files_scanned}")
    print(f"  Files with conflicts: {total_files_with_conflicts}")
    if total_files_with_conflicts > 0:
        print(f"  {COLOR_RED}Result: Found conflicts in codebase.{COLOR_RESET}")
        sys.exit(1)
    else:
        print(f"  {COLOR_GREEN}Result: No conflicts found! Codebase is clean.{COLOR_RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
