#!/usr/bin/env python3
"""
Tailwind CSS Unused Class Purger

Scans HTML, Javascript, Typescript, and template source files recursively to find used Tailwind CSS utility classes,
then parses an input CSS file containing all Tailwind rules, purges unused rules, and outputs a minified,
pruned stylesheet.

Usage:
    python tools/tailwind_unused_purger.py --content src/ --css tailwind.css --output main.purged.css
"""

import argparse
import os
import re
import sys

# Color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

# Regex to match Tailwind class patterns inside quotes, class attributes, or templates
# e.g., class="bg-blue-500 hover:bg-blue-600 md:w-1/2 [clip-path:circle()]"
CLASS_CANDIDATE_RE = re.compile(r"[a-zA-Z0-9\-\:\/\[\]\.\%\#]+")

def scan_content_for_classes(content_dirs, extensions):
    """
    Scans files in target directories with given extensions and returns a set of unique potential class names.
    """
    used_classes = set()
    ext_list = [f".{ext.strip().lower()}" for ext in extensions.split(",")]

    print(f"Scanning files in {COLOR_CYAN}{', '.join(content_dirs)}{COLOR_RESET} with extensions {COLOR_CYAN}{', '.join(ext_list)}{COLOR_RESET}...")
    
    file_count = 0
    for content_dir in content_dirs:
        if not os.path.exists(content_dir):
            continue
        if os.path.isfile(content_dir):
            files = [content_dir]
            content_dir = os.path.dirname(content_dir)
        else:
            files = []
            for root, _, filenames in os.walk(content_dir):
                for f in filenames:
                    if any(f.lower().endswith(ext) for ext in ext_list):
                        files.append(os.path.join(root, f))

        for filepath in files:
            file_count += 1
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                # Find all potential words that could be CSS classes
                for match in CLASS_CANDIDATE_RE.finditer(text):
                    used_classes.add(match.group(0))
            except Exception as e:
                print(f"  Warning: Failed to read {filepath}: {e}", file=sys.stderr)

    print(f"Scanned {file_count} files. Found {len(used_classes)} unique class candidates.")
    return used_classes

def clean_selector_to_class(selector):
    """
    Converts a CSS selector like `.md\:hover\:bg-blue-500::before` into its clean class name `md:hover:bg-blue-500`.
    """
    # Remove pseudo-elements, pseudo-classes (e.g. :hover, :focus, ::after, ::before, [attr])
    selector = re.split(r":|\[|\s|>|\+|\~", selector)[0]
    
    # Check if it is a class selector
    if not selector.startswith("."):
        return None

    class_name = selector[1:]  # strip leading dot
    
    # Decode CSS escapes (e.g. \: to :, \/ to /, \[ to [, \] to ], \. to .)
    class_name = class_name.replace(r"\:", ":").replace(r"\/", "/").replace(r"\[", "[").replace(r"\]", "]").replace(r"\.", ".").replace(r"\%", "%")
    
    # Strip double escapes just in case
    class_name = class_name.replace("\\", "")
    
    return class_name

def parse_and_purge_css(input_css_path, used_classes, keep_all_base_tags=True):
    """
    Parses a CSS file, extracts rules, and filters them based on used classes.
    """
    if not os.path.exists(input_css_path):
        print(f"{COLOR_RED}Error: Input CSS file '{input_css_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    with open(input_css_path, "r", encoding="utf-8") as f:
        raw_css = f.read()

    # Basic CSS parser state machine
    # We find blocks of `selectors { rules }`
    # It also handles @media or @keyframes blocks by matching braces
    purged_css = []
    
    # Matches patterns like: `selector { rules }`
    # We use a scanner to handle nested brackets (like @media containing rules)
    pos = 0
    length = len(raw_css)
    
    brace_depth = 0
    current_block = []
    
    media_query_header = None
    media_query_content = []

    print("Purging CSS stylesheet...")

    # We do a simple top-level token split of rules using regex for robustness
    # A standard Tailwind file is structured as:
    # 1. Base styles (body, html, h1, etc.)
    # 2. Components
    # 3. Utilities (which we want to purge)
    # We can detect rules using regex: `([^\{\}]+)\{([^\{\}]+)\}`
    # Since Tailwind utility classes have no nested rules except media queries, we can parse them.
    
    # First, let's strip comments
    clean_css = re.sub(r"\/\*.*?\*\/", "", raw_css, flags=re.DOTALL)
    
    # Find all rules (including media query wrappers)
    # We can use a regex-based parser that handles media queries
    # Format matches:
    # @media ... { rules }
    # or just rule { properties }
    
    # To keep it clean and robust, we match blocks
    # We scan for CSS rules and resolve their selectors
    # Regular expressions for CSS rule matching
    rule_pattern = re.compile(r"([^{]+)\{([^}]+)\}")
    
    # Let's extract media queries separately if needed, or parse them line-by-line
    # We will do a line-by-line or char-by-char scanner to keep nesting intact!
    
    purged_lines = []
    
    # Let's split by @media blocks and standard rules
    # An easy way to purge CSS utilities is to process the contents of any rule `{ ... }`
    # If the rule selector contains class names, we verify if they are in used_classes.
    # Otherwise we keep base styles (tags like body, HTML, etc.).
    
    # Scan characters
    current_selector = ""
    current_body = ""
    in_selector = True
    
    i = 0
    nest_depth = 0
    buffer = ""
    
    while i < length:
        char = raw_css[i]
        if char == "{":
            nest_depth += 1
            if nest_depth == 1:
                current_selector = buffer.strip()
                buffer = ""
            else:
                buffer += char
        elif char == "}":
            nest_depth -= 1
            if nest_depth == 0:
                current_body = buffer.strip()
                buffer = ""
                # Process the block
                purged_rule = process_css_block(current_selector, current_body, used_classes, keep_all_base_tags)
                if purged_rule:
                    purged_lines.append(purged_rule)
                current_selector = ""
                current_body = ""
            else:
                buffer += char
        else:
            buffer += char
        i += 1

    return "\n".join(purged_lines)

def process_css_block(selector, body, used_classes, keep_all_base_tags):
    """
    Determines whether a CSS block (rules/media query) should be kept, and purges selectors inside it if necessary.
    """
    # If it is a media query, parse its inner rules recursively
    if selector.startswith("@media") or selector.startswith("@supports"):
        # Parse nested rules inside media query body
        inner_rules = []
        # Re-parse body
        i = 0
        length = len(body)
        nest_depth = 0
        buffer = ""
        current_sel = ""
        while i < length:
            char = body[i]
            if char == "{":
                nest_depth += 1
                if nest_depth == 1:
                    current_sel = buffer.strip()
                    buffer = ""
                else:
                    buffer += char
            elif char == "}":
                nest_depth -= 1
                if nest_depth == 0:
                    current_b = buffer.strip()
                    buffer = ""
                    purged_inner = process_css_block(current_sel, current_b, used_classes, keep_all_base_tags)
                    if purged_inner:
                        inner_rules.append(purged_inner)
                    current_sel = ""
                else:
                    buffer += char
            else:
                buffer += char
            i += 1
        
        if inner_rules:
            # Format media query rule
            return f"{selector} {{\n  " + "\n  ".join(inner_rules).replace("\n", "\n  ") + "\n}"
        return None

    # For standard rule blocks, check selectors
    selectors = [s.strip() for s in selector.split(",")]
    kept_selectors = []

    for sel in selectors:
        if not sel:
            continue
            
        # Ignore keyframes / font-face
        if sel.startswith("@"):
            kept_selectors.append(sel)
            continue
            
        # Parse selector to class name
        class_name = clean_selector_to_class(sel)
        
        if class_name is None:
            # It's not a class (e.g. tag selector 'body', 'html', or '*' or '#id')
            if keep_all_base_tags:
                kept_selectors.append(sel)
        else:
            # It is a class, check if it was found in contents
            # We also check for variations of brackets or dynamic classes
            if class_name in used_classes:
                kept_selectors.append(sel)

    if kept_selectors:
        # Reconstruct block
        joined_selectors = ", ".join(kept_selectors)
        # Minify rules in body: remove unnecessary spaces/newlines
        minified_body = re.sub(r"\s+", " ", body).strip()
        return f"{joined_selectors} {{ {minified_body} }}"
        
    return None

def main():
    parser = argparse.ArgumentParser(description="Tailwind CSS Unused Class Purger")
    parser.add_argument(
        "--content",
        default=".",
        help="Comma-separated directories/files to scan for used classes (default: .)"
    )
    parser.add_argument(
        "--css",
        required=True,
        help="Path to the input CSS file containing all Tailwind styles"
    )
    parser.add_argument(
        "--output",
        default="purged_tailwind.css",
        help="Path to output pruned CSS file (default: purged_tailwind.css)"
    )
    parser.add_argument(
        "--extensions",
        default="html,js,ts,jsx,tsx,vue,py,php,json,md",
        help="Comma-separated list of file extensions to search (default: html,js,ts,jsx,tsx,vue,py,php,json,md)"
    )
    parser.add_argument(
        "--keep-base",
        action="store_true",
        default=True,
        help="Keep all base tags/element selectors (body, h1, etc.)"
    )

    args = parser.parse_args()

    content_dirs = [d.strip() for d in args.content.split(",")]
    
    # 1. Scan codebase for class references
    used_classes = scan_content_for_classes(content_dirs, args.extensions)
    
    # 2. Load input CSS size for reporting
    if not os.path.exists(args.css):
        print(f"{COLOR_RED}Error: Input CSS file '{args.css}' does not exist.{COLOR_RESET}")
        return 1
        
    input_size = os.path.getsize(args.css)

    # 3. Purge unused styles
    purged_css_content = parse_and_purge_css(args.css, used_classes, args.keep_base)

    # 4. Save to output path
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(purged_css_content)

    output_size = os.path.getsize(args.output)
    
    # 5. Report metrics
    saving = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0
    
    print("\n" + "=" * 80)
    print(f"{COLOR_BOLD}Tailwind Purge Summary:{COLOR_RESET}")
    print(f"  Input CSS:  {args.css} ({input_size / 1024:.2f} KB)")
    print(f"  Output CSS: {args.output} ({output_size / 1024:.2f} KB)")
    print(f"  Reduction:  {COLOR_GREEN}{saving:.1f}%{COLOR_RESET} space saved")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
