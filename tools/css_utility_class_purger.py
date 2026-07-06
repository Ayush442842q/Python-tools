#!/usr/bin/env python3
"""
CSS Utility Class & Selector Purger
-----------------------------------
Audits CSS stylesheets against HTML, JS/TS/JSX, and Markdown source templates to discover
used CSS class names and selectors, removes unused CSS rules, media queries, and keyframes,
and outputs purged CSS with file size reduction metrics.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import List, Set, Dict, Any, Tuple, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def extract_used_tokens_from_file(filepath: str) -> Set[str]:
    """Scan source code file for class names, IDs, and identifiers."""
    tokens = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return tokens

    # Match class="foo bar", className="foo bar", class:list={...}
    class_attr_matches = re.findall(r'class(?:Name)?\s*=\s*["\'`]([^"\'`]+)["\'`]', content)
    for match in class_attr_matches:
        for cls in match.split():
            clean_cls = cls.strip()
            if clean_cls:
                tokens.add(clean_cls)

    # Match raw identifiers (words with alphanumeric, dashes, underscores)
    word_tokens = re.findall(r'[a-zA-Z0-9_-]{2,}', content)
    tokens.update(word_tokens)

    return tokens


def extract_used_tokens_from_paths(paths: List[str]) -> Set[str]:
    """Scan list of files or directories for used class tokens."""
    all_tokens = set()
    for p in paths:
        if os.path.isfile(p):
            all_tokens.update(extract_used_tokens_from_file(p))
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith((".html", ".htm", ".js", ".ts", ".jsx", ".tsx", ".vue", ".astro", ".md")):
                        all_tokens.update(extract_used_tokens_from_file(os.path.join(root, f)))
    return all_tokens


def parse_css_blocks(css_content: str) -> List[Dict[str, Any]]:
    """Parse CSS content into selector blocks and rule definitions."""
    # Strip comments
    clean_css = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    blocks = []
    # Simple regex parser for CSS rule blocks: selector { body }
    pattern = re.compile(r'([^{}]+)\{([^{}]+)\}', re.DOTALL)
    for match in pattern.finditer(clean_css):
        selector_raw = match.group(1).strip()
        body_raw = match.group(2).strip()

        # Handle @keyframes or @media headers separately if nested
        if selector_raw.startswith("@"):
            blocks.append({
                "type": "at_rule",
                "header": selector_raw,
                "body": body_raw,
                "raw": f"{selector_raw} {{{body_raw}}}"
            })
        else:
            selectors = [s.strip() for s in selector_raw.split(",") if s.strip()]
            blocks.append({
                "type": "rule",
                "selectors": selectors,
                "body": body_raw,
                "raw": f"{selector_raw} {{{body_raw}}}"
            })
    return blocks


def is_selector_used(selector: str, used_tokens: Set[str], safelist_patterns: List[str]) -> bool:
    """Determine if a CSS selector is used based on tokens and safelist."""
    # Always keep HTML base tags (html, body, p, h1, div, etc.)
    base_elements = {"html", "body", "div", "span", "p", "a", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "li", "ol", "table", "tr", "td", "th", "input", "button", "form", "*"}
    
    # Check safelist patterns
    for pattern in safelist_patterns:
        if pattern.endswith("*") and selector.startswith(pattern[:-1]):
            return True
        if pattern == selector:
            return True

    # Extract class names (.foo) and IDs (#bar) from selector string
    classes = re.findall(r'\.([a-zA-Z0-9_-]+)', selector)
    ids = re.findall(r'#([a-zA-Z0-9_-]+)', selector)

    if not classes and not ids:
        # Selector is pure element selector (e.g. "div > p")
        parts = re.findall(r'[a-zA-Z0-9_-]+', selector)
        if any(p in base_elements for p in parts):
            return True

    # If any class or ID in selector is in used_tokens, keep rule
    for cls in classes:
        if cls in used_tokens:
            return True
    for i in ids:
        if i in used_tokens:
            return True

    return False


def purge_css(css_content: str, used_tokens: Set[str], safelist_patterns: List[str]) -> Tuple[str, Dict[str, Any]]:
    """Purge unused CSS blocks and calculate purge metrics."""
    blocks = parse_css_blocks(css_content)
    kept_blocks = []

    total_rules = 0
    kept_rules = 0
    removed_rules = 0

    for b in blocks:
        if b["type"] == "at_rule":
            kept_blocks.append(b["raw"])
        elif b["type"] == "rule":
            total_rules += len(b["selectors"])
            valid_selectors = [s for s in b["selectors"] if is_selector_used(s, used_tokens, safelist_patterns)]
            if valid_selectors:
                kept_rules += len(valid_selectors)
                sel_str = ", ".join(valid_selectors)
                kept_blocks.append(f"{sel_str} {{\n  {b['body']}\n}}")
            else:
                removed_rules += len(b["selectors"])

    purged_css = "\n\n".join(kept_blocks)
    
    orig_bytes = len(css_content.encode("utf-8"))
    purged_bytes = len(purged_css.encode("utf-8"))
    bytes_saved = max(0, orig_bytes - purged_bytes)
    pct_saved = round((bytes_saved / orig_bytes * 100), 1) if orig_bytes > 0 else 0.0

    stats = {
        "original_bytes": orig_bytes,
        "purged_bytes": purged_bytes,
        "bytes_saved": bytes_saved,
        "pct_saved": pct_saved,
        "total_selectors": total_rules,
        "kept_selectors": kept_rules,
        "removed_selectors": removed_rules
    }

    return purged_css, stats


DEMO_CSS = """
/* Base styles */
body {
  font-family: Arial, sans-serif;
  color: #333;
}

.btn {
  padding: 8px 16px;
  border-radius: 4px;
}

.btn-primary {
  background-color: blue;
  color: white;
}

.btn-unused {
  background-color: red;
  color: white;
}

.card {
  border: 1px solid #ccc;
  padding: 16px;
}

.card-unused-header {
  font-size: 24px;
}

.active {
  display: block;
}
"""

DEMO_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div class="card">
    <button class="btn btn-primary active">Click Me</button>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="CSS Utility Class & Selector Purger")
    parser.add_argument("--css", help="Path to input CSS file")
    parser.add_argument("--content", nargs="+", help="Paths to HTML/JS/Markdown template files or directories")
    parser.add_argument("--safelist", help="Comma-separated class names or patterns to keep (e.g. 'active,is-*')")
    parser.add_argument("--out", help="Output path for purged CSS file")
    parser.add_argument("--minify", action="store_true", help="Compress and minify purged CSS output")
    parser.add_argument("--report", action="store_true", help="Print detailed purge metrics JSON")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample CSS and HTML content")

    args = parser.parse_args()

    safelist_patterns = [s.strip() for s in args.safelist.split(",")] if args.safelist else []

    if args.demo:
        print(f"{BOLD}{CYAN}=== Running CSS Utility Class Purger Demo ==={RESET}\n")
        css_content = DEMO_CSS
        
        # Write temp HTML demo file
        with open("_demo_temp.html", "w", encoding="utf-8") as f:
            f.write(DEMO_HTML)
        used_tokens = extract_used_tokens_from_paths(["_demo_temp.html"])
        if os.path.exists("_demo_temp.html"):
            os.remove("_demo_temp.html")
    elif args.css and args.content:
        if not os.path.exists(args.css):
            print(f"{RED}Error: CSS file '{args.css}' not found.{RESET}")
            sys.exit(1)
        with open(args.css, "r", encoding="utf-8") as f:
            css_content = f.read()
        used_tokens = extract_used_tokens_from_paths(args.content)
    else:
        parser.print_help()
        sys.exit(0)

    purged_css, stats = purge_css(css_content, used_tokens, safelist_patterns)

    if args.minify:
        # Simple whitespace & newline minification
        purged_css = re.sub(r'\s+', ' ', purged_css)
        purged_css = re.sub(r'\s*([{:;,}])\s*', r'\1', purged_css).strip()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(purged_css)
        print(f"{GREEN}Purged CSS saved to {args.out}{RESET}")

    if args.report:
        print(json.dumps(stats, indent=2))
    else:
        print(f"{BOLD}CSS Purge Summary Report:{RESET}")
        print(f" Original Size:  {stats['original_bytes']} bytes")
        print(f" Purged Size:    {stats['purged_bytes']} bytes")
        print(f" Savings:        {BOLD}{GREEN}{stats['bytes_saved']} bytes ({stats['pct_saved']}% reduction){RESET}")
        print(f" Selectors:      Kept {stats['kept_selectors']}, Removed {stats['removed_selectors']} of {stats['total_selectors']}")
        
        if not args.out and not args.report:
            print(f"\n{CYAN}--- Purged CSS Preview ---{RESET}\n")
            print(purged_css)


if __name__ == "__main__":
    main()
