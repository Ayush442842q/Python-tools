#!/usr/bin/env python3
"""
CSS Specificity Calculator & Selector Auditor
Parses CSS stylesheets, computes the specificity score (IDs, Classes, Elements)
for every selector, flags specificity hotspots, and detects redundant rules.

Usage:
    python tools/css_specificity_calculator.py style.css
    python tools/css_specificity_calculator.py style.css --min-specificity 0,1,0
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Tuple

# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


def calculate_specificity(selector: str) -> Tuple[int, int, int]:
    """
    Calculates CSS specificity (IDs, Classes/Attributes/Pseudo-classes, Elements/Pseudo-elements).
    Returns (A, B, C) tuple.
    """
    clean_selector = selector.strip()
    if not clean_selector:
        return (0, 0, 0)
        
    # Count IDs (starts with #)
    ids = len(re.findall(r"#[a-zA-Z0-9_-]+", clean_selector))
    
    # Count classes, attributes, pseudo-classes
    # e.g., .class, [attr=val], :hover
    # Note: we ignore pseudo-elements (like ::before, ::after) here and count them as elements (C)
    # Also ignore :not, :is, :where pseudo-class containers themselves, but count their contents
    # For simplicity, we match:
    # Classes: \.[a-zA-Z0-9_-]+
    # Attributes: \[[^\]]+\]
    # Pseudo-classes: :[a-zA-Z0-9_-]+ (excluding pseudo-elements starting with ::)
    
    # Strip pseudo-elements first to avoid double-counting
    temp_selector = re.sub(r"::[a-zA-Z0-9_-]+", "", clean_selector)
    
    classes = len(re.findall(r"\.[a-zA-Z0-9_-]+", temp_selector))
    attributes = len(re.findall(r"\[[^\]]+\]", temp_selector))
    
    # Find pseudo-classes (single colon, not followed by another colon)
    # and exclude common pseudo-elements that might be written with single colon (e.g. :before)
    pseudo_elements_single_colon = {":before", ":after", ":first-line", ":first-letter"}
    pseudo_classes_raw = re.findall(r":[a-zA-Z0-9_-]+", temp_selector)
    pseudo_classes = 0
    for pc in pseudo_classes_raw:
        if pc.lower() not in pseudo_elements_single_colon and pc.lower() not in {":not", ":is", ":where", ":has"}:
            pseudo_classes += 1
            
    b_score = classes + attributes + pseudo_classes
    
    # Count elements & pseudo-elements
    # Pseudo-elements: ::before, ::after, ::first-line, ::first-letter, ::selection, etc.
    # plus single-colon legacy pseudo-elements
    pseudo_elems_count = len(re.findall(r"::[a-zA-Z0-9_-]+", clean_selector))
    for pc in pseudo_classes_raw:
        if pc.lower() in pseudo_elements_single_colon:
            pseudo_elems_count += 1
            
    # Elements: tag names
    # Remove IDs, classes, attributes, pseudo-classes, and combinators, then count remaining words
    stripped = re.sub(r"#[a-zA-Z0-9_-]+", " ", clean_selector)
    stripped = re.sub(r"\.[a-zA-Z0-9_-]+", " ", stripped)
    stripped = re.sub(r"\[[^\]]+\]", " ", stripped)
    stripped = re.sub(r":[a-zA-Z0-9_-]+", " ", stripped)
    stripped = re.sub(r"[+>~*]", " ", stripped)
    
    elements = 0
    for word in stripped.split():
        if word.strip() and not word.startswith("-") and not re.match(r"^\d+$", word):
            elements += 1
            
    c_score = elements + pseudo_elems_count
    
    return (ids, b_score, c_score)


def parse_css_file(file_path: str) -> List[Tuple[str, Tuple[int, int, int], int]]:
    """
    Parses a CSS file to extract selectors and calculate specificity.
    Returns list of (selector, specificity, line_number).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print_colored(f"[!] Error reading file: {e}", COLOR_FAIL)
        sys.exit(1)
        
    # Strip comments /* ... */
    # We replace comments with spaces of equal length to preserve line numbers
    def comment_replacer(match):
        return "\n" * match.group(0).count("\n")
    clean_content = re.sub(r"/\*.*?\*/", comment_replacer, content, flags=re.DOTALL)
    
    selectors: List[Tuple[str, Tuple[int, int, int], int]] = []
    
    # Find CSS rulesets
    # Regex to find rule blocks: anything before {
    # Handles nested blocks like media queries by skipping them or tracking brace depth
    brace_depth = 0
    buffer = []
    line_count = 1
    
    selector_buffer = ""
    selector_line = 1
    
    for idx, char in enumerate(clean_content):
        if char == "\n":
            line_count += 1
            
        if char == "{":
            if brace_depth == 0:
                selector_buffer = "".join(buffer).strip()
                selector_line = line_count - selector_buffer.count("\n")
            brace_depth += 1
            buffer = []
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                # Process selector buffer
                # Check if it is a media query or import
                if selector_buffer and not selector_buffer.startswith("@"):
                    # Split grouped selectors, e.g. "h1, h2"
                    for sel in selector_buffer.split(","):
                        sel_strip = sel.strip()
                        if sel_strip:
                            spec = calculate_specificity(sel_strip)
                            selectors.append((sel_strip, spec, selector_line))
                selector_buffer = ""
            buffer = []
        else:
            buffer.append(char)
            
    return selectors


def main():
    parser = argparse.ArgumentParser(
        description="CSS Specificity Calculator & Selector Auditor.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the CSS stylesheet")
    parser.add_argument("--min-specificity", "-m", help="Filter results with specificity >= score (format: A,B,C)")
    parser.add_argument("--limit", "-l", type=int, default=30, help="Limit output to top N selectors (default: 30)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print_colored(f"[!] File not found: {args.file}", COLOR_FAIL)
        sys.exit(1)
        
    print_colored(f"[*] Analyzing CSS file '{args.file}'...", COLOR_CYAN)
    selectors = parse_css_file(args.file)
    
    if not selectors:
        print_colored("[*] No selectors found in CSS stylesheet.", COLOR_WARNING)
        sys.exit(0)
        
    # Parse min specificity filter if provided
    min_score = (0, 0, 0)
    if args.min_specificity:
        try:
            min_score = tuple(map(int, args.min_specificity.split(",")))
            if len(min_score) != 3:
                raise ValueError
        except ValueError:
            print_colored("[!] Invalid format for --min-specificity. Must be A,B,C (e.g. 0,1,0)", COLOR_FAIL)
            sys.exit(1)
            
    # Filter and sort by specificity (highest to lowest)
    filtered = [
        (sel, spec, line) for sel, spec, line in selectors
        if spec >= min_score
    ]
    
    # Sort key: ID (A) desc, Class (B) desc, Element (C) desc, Line number asc
    sorted_selectors = sorted(filtered, key=lambda x: (x[1][0], x[1][1], x[1][2]), reverse=True)
    
    print_colored(f"\n{COLOR_BOLD}=== CSS Specificity Audit ==={COLOR_END}", COLOR_HEADER)
    print(f"Total unique selectors analyzed: {len(selectors)}")
    print(f"Showing top {min(args.limit, len(sorted_selectors))} sorted by specificity:\n")
    
    # Print table header
    header = f"{'Specificity':<15} | {'Line':<6} | Selector"
    print_colored("-" * 60, COLOR_BLUE)
    print_colored(header, COLOR_BOLD + COLOR_HEADER)
    print_colored("-" * 60, COLOR_BLUE)
    
    hotspots = 0
    
    for sel, spec, line in sorted_selectors[:args.limit]:
        spec_str = f"({spec[0]}, {spec[1]}, {spec[2]})"
        
        # Color coding specificity hotspots (e.g., ID specificity > 1)
        if spec[0] >= 2:
            spec_color = COLOR_FAIL + COLOR_BOLD
            hotspots += 1
        elif spec[0] == 1:
            spec_color = COLOR_WARNING
        else:
            spec_color = COLOR_GREEN
            
        row = f"{spec_str:<15} | {line:<6} | {sel}"
        if sys.stdout.isatty():
            print(f"{spec_color}{spec_str:<15}{COLOR_END} | {line:<6} | {sel}")
        else:
            print(row)
            
    print_colored("-" * 60, COLOR_BLUE)
    
    # General audit observations
    print_colored(f"\n{COLOR_BOLD}=== Audit Insights ==={COLOR_END}", COLOR_HEADER)
    
    # Check for ID selector overload
    id_selectors = [s for s in selectors if s[1][0] > 0]
    id_ratio = (len(id_selectors) / len(selectors)) * 100 if selectors else 0
    
    if id_ratio > 10:
        print_colored(f"[!] High ID Selector usage ({id_ratio:.1f}%). Suggest using class selectors to improve reusability.", COLOR_WARNING)
    else:
        print_colored(f"[+] Good selector modularity: ID selectors make up only {id_ratio:.1f}% of stylesheet.", COLOR_GREEN)
        
    if hotspots > 0:
        print_colored(f"[!] Found {hotspots} specificity hotspots (multiple ID selectors or excessive specificity).", COLOR_WARNING)
    else:
        print_colored("[+] No excessive specificity nesting/hotspots detected.", COLOR_GREEN)
        
    # Check for duplicate selectors
    seen = {}
    duplicates = {}
    for sel, spec, line in selectors:
        if sel in seen:
            duplicates.setdefault(sel, []).append(line)
        else:
            seen[sel] = line
            
    if duplicates:
        print_colored(f"[!] Detected {len(duplicates)} duplicate selectors (rules defined multiple times):", COLOR_WARNING)
        for sel, lines in list(duplicates.items())[:5]:
            orig_line = seen[sel]
            print(f"  - '{sel}' originally on Line {orig_line}, duplicated on Line(s): {', '.join(map(str, lines))}")
        if len(duplicates) > 5:
            print(f"  ... and {len(duplicates) - 5} more.")
    else:
        print_colored("[+] No duplicate selectors detected.", COLOR_GREEN)


if __name__ == "__main__":
    main()
