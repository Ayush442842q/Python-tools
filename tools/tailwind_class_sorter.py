#!/usr/bin/env python3
"""
Tailwind CSS Class Sorter & Deduplicator

Parses HTML, JSX, TSX, and Vue files to locate Tailwind CSS class strings, removes
duplicate classes, and sorts them according to the official Tailwind CSS recommended
ordering (Layout -> Flex/Grid -> Spacing -> Sizing -> Typography -> Backgrounds -> Borders -> Effects -> etc.).
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Official Tailwind CSS class ordering categories mapped to regex or prefixes
# Order is: Layout -> Flexbox/Grid -> Spacing -> Sizing -> Typography -> Backgrounds -> Borders -> Effects -> Filters -> Transitions -> Transforms -> Interactive -> SVG -> Custom
TAILWIND_ORDER = [
    # 1. Layout
    r'^(?:container|columns-|break-|box-decoration-|box-border|box-content|block|inline-block|inline|flex|inline-flex|table|inline-table|table-row|table-cell|hidden|float-|clear-|isolate|object-|overflow-|overscroll-|position-|static|fixed|absolute|relative|sticky|inset-|top-|right-|bottom-|left-|visible|invisible|z-)',
    # 2. Flexbox & Grid
    r'^(?:flex-row|flex-col|flex-wrap|flex-1|flex-auto|flex-initial|flex-none|flex-grow|flex-shrink|order-|grid-cols-|col-span-|col-start|col-end|grid-rows-|row-span-|row-start|row-end|grid-flow-|auto-cols-|auto-rows-|gap-|justify-|content-|items-|self-|place-content-|place-items-|place-self)',
    # 3. Spacing
    r'^(?:p-|px-|py-|pt-|pr-|pb-|pl-|m-|mx-|my-|mt-|mr-|mb-|ml-|space-x-|space-y-)',
    # 4. Sizing
    r'^(?:w-|h-|min-w-|min-h-|max-w-|max-h-)',
    # 5. Typography
    r'^(?:font-|tracking-|leading-|text-|align-|whitespace-|break-|content-|list-|marker-|underline|overline|line-through|no-underline|uppercase|lowercase|capitalize|normal-case|italic|not-italic)',
    # 6. Backgrounds
    r'^(?:bg-)',
    # 7. Borders
    r'^(?:border-|rounded-|divide-|ring-|outline-)',
    # 8. Effects
    r'^(?:shadow|opacity-|mix-blend-|bg-blend-)',
    # 9. Filters
    r'^(?:blur|brightness-|contrast-|drop-shadow|grayscale|hue-rotate-|invert|saturate-|sepia|backdrop-)',
    # 10. Transitions & Animation
    r'^(?:transition|duration-|ease-|delay-|animate-)',
    # 11. Transforms
    r'^(?:scale-|rotate-|translate-|skew-|origin-)',
    # 12. Interactive
    r'^(?:cursor-|user-select-|pointer-events-|resize|will-change-)',
    # 13. SVG
    r'^(?:fill-|stroke-)',
]

# Responsive prefixes (sm, md, lg, xl, 2xl) and states (hover, focus, active, disabled, dark, group-hover, peer-focus, etc.)
RESPONSIVE_PREFIXES = ['sm', 'md', 'lg', 'xl', '2xl']
STATE_PREFIXES = ['hover', 'focus', 'active', 'visited', 'disabled', 'checked', 'group-hover', 'group-focus', 'peer-hover', 'peer-focus', 'dark', 'motion-safe', 'motion-reduce', 'print']

def get_class_sort_key(class_name: str) -> Tuple[int, int, int, str]:
    """
    Computes a sorting key tuple for a Tailwind CSS class.
    Sorting weight logic:
    1. Responsive Prefix index (no responsive prefix = 0, 'sm' = 1, etc.)
    2. State / Pseudo prefix index (no state prefix = 0, 'dark' = 1, 'hover' = 2, etc.)
    3. Category index based on TAILWIND_ORDER
    4. Alphabetical tie-breaker on base class name
    """
    parts = class_name.split(':')
    base_class = parts[-1]
    prefixes = parts[:-1]
    
    # 1. Resolve responsive prefix weight
    resp_weight = 0
    for p in prefixes:
        if p in RESPONSIVE_PREFIXES:
            resp_weight = RESPONSIVE_PREFIXES.index(p) + 1
            break
            
    # 2. Resolve state prefix weight
    state_weight = 0
    for p in prefixes:
        if p in STATE_PREFIXES:
            state_weight = STATE_PREFIXES.index(p) + 1
            break
            
    # 3. Resolve category index weight based on TAILWIND_ORDER
    cat_weight = len(TAILWIND_ORDER) # Default to last if not matched
    for idx, pattern in enumerate(TAILWIND_ORDER):
        if re.match(pattern, base_class):
            cat_weight = idx
            break
            
    return (resp_weight, state_weight, cat_weight, base_class)

def sort_tailwind_classes(classes_str: str) -> str:
    """Extracts, deduplicates, and sorts Tailwind CSS classes from a space-separated string."""
    raw_classes = [c.strip() for c in classes_str.split() if c.strip()]
    if not raw_classes:
        return ""
        
    # Deduplicate while preserving order roughly
    seen = set()
    deduped_classes = []
    for c in raw_classes:
        if c not in seen:
            seen.add(c)
            deduped_classes.append(c)
            
    # Sort using key function
    sorted_classes = sorted(deduped_classes, key=get_class_sort_key)
    return " ".join(sorted_classes)

def process_file(file_path: Path, dry_run: bool) -> Tuple[bool, int]:
    """
    Parses a file and sorts Tailwind CSS classes inside class attributes.
    Returns (modified_status, change_count).
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(color_text(f"Error reading file '{file_path}': {e}", COLOR_RED))
        return False, 0
        
    change_count = 0
    
    # Matches class="..." or className="..." or class='...' or className='...'
    # Or class={`...`} or className={`...`} in JSX/TSX
    patterns = [
        # HTML class="class-1 class-2"
        (r'\bclass(?:Name)?\s*=\s*"([^"]+)"', 'class="VAL"'),
        # HTML class='class-1 class-2'
        (r"\bclass(?:Name)?\s*=\s*'([^']+)'", "class='VAL'"),
        # JSX class={`class-1 class-2`}
        (r'\bclass(?:Name)?\s*=\s*\{\`([^\`]+)\`\}', 'class={`VAL`}')
    ]
    
    new_content = content
    for regex_str, replacement_tpl in patterns:
        matches = re.finditer(regex_str, new_content)
        
        # Track offsets during replacement to prevent drift
        offset = 0
        for m in matches:
            original_match = m.group(0)
            original_val = m.group(1)
            
            # Skip if it looks like a variable template in JSX (has ${var})
            if "${" in original_val:
                continue
                
            sorted_val = sort_tailwind_classes(original_val)
            if sorted_val != original_val:
                # Replace value in the template
                new_match = replacement_tpl.replace("VAL", sorted_val)
                # Keep className prefix if original was className
                if "className" in original_match:
                    new_match = new_match.replace("class=", "className=").replace("class{", "className{")
                    
                start = m.start() + offset
                end = m.end() + offset
                
                new_content = new_content[:start] + new_match + new_content[end:]
                offset += len(new_match) - len(original_match)
                change_count += 1
                
    modified = change_count > 0
    if modified and not dry_run:
        try:
            file_path.write_text(new_content, encoding='utf-8')
        except Exception as e:
            print(color_text(f"Error writing to file '{file_path}': {e}", COLOR_RED))
            return False, 0
            
    return modified, change_count

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tailwind CSS Class Sorter & Deduplicator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to scan and sort.")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Preview changes without modifying files.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details for every modified file.")
    parser.add_argument("-e", "--extensions", default=".html,.jsx,.tsx,.vue", help="Comma-separated file extensions to scan (default: .html,.jsx,.tsx,.vue)")
    
    args = parser.parse_args()
    
    target_extensions = [ext.strip().lower() for ext in args.extensions.split(",")]
    files_to_process: List[Path] = []
    
    for path_str in args.paths:
        p = Path(path_str)
        if p.is_file():
            if p.suffix.lower() in target_extensions:
                files_to_process.append(p)
        elif p.is_dir():
            for root, _, files in os.walk(p):
                for f in files:
                    file_path = Path(root) / f
                    if file_path.suffix.lower() in target_extensions:
                        files_to_process.append(file_path)
                        
    if not files_to_process:
        print("No files found matching the search criteria.")
        return 0
        
    print(f"Scanning {len(files_to_process)} file(s) for Tailwind CSS classes...")
    if args.dry_run:
        print(color_text("[DRY RUN] No files will be modified.", COLOR_YELLOW))
    print("-" * 80)
    
    modified_count = 0
    total_replacements = 0
    
    for f in files_to_process:
        modified, changes = process_file(f, args.dry_run)
        if modified:
            modified_count += 1
            total_replacements += changes
            if args.verbose or args.dry_run:
                status = "Would modify" if args.dry_run else "Modified"
                print(f" {color_text('✓', COLOR_GREEN)} {status}: {f} ({changes} locations sorted)")
                
    print("-" * 80)
    print(f"Scan complete.")
    print(f"Total files checked:   {len(files_to_process)}")
    print(f"Total files modified:  {modified_count}")
    print(f"Total class locations: {total_replacements}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
