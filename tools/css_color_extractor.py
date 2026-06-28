#!/usr/bin/env python3
"""
CSS Color Extractor

Scans CSS files to extract, count, and de-duplicate all declared colors (Hex, RGB, RGBA, HSL, HSLA).
Avoids false positives by only searching the value portion of CSS properties (after the colon).
Can export a stylesheet with the extracted colors declared as CSS custom variables.

Usage:
    python tools/css_color_extractor.py -i styles.css
    python tools/css_color_extractor.py -i src/**/*.css --export-vars theme.css
    cat styles.css | python tools/css_color_extractor.py
"""

import argparse
import glob
import json
import os
import re
import sys

# Regular expressions for CSS colors
HEX_COLOR_PATTERN = re.compile(r'#([0-9a-fA-F]{3,4}){1,2}\b')
RGB_COLOR_PATTERN = re.compile(r'\brgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*(?:[01]|0?\.\d+)\s*)?\)')
HSL_COLOR_PATTERN = re.compile(r'\bhsla?\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*(?:[01]|0?\.\d+)\s*)?\)')

# List of standard CSS named colors to search for
NAMED_COLORS = {
    'aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black',
    'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse',
    'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue',
    'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgreen', 'darkgrey', 'darkkhaki',
    'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon',
    'darkseagreen', 'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise',
    'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue',
    'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite',
    'gold', 'goldenrod', 'gray', 'green', 'greenyellow', 'grey', 'honeydew', 'hotpink',
    'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen',
    'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow',
    'lightgray', 'lightgreen', 'lightgrey', 'lightpink', 'lightsalmon', 'lightseagreen',
    'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue', 'lightyellow',
    'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue',
    'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslate99', 'mediumslateblue',
    'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream',
    'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab',
    'orange', 'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise',
    'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue',
    'purple', 'rebeccapurple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon',
    'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue',
    'slategray', 'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal',
    'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke',
    'yellow', 'yellowgreen', 'transparent'
}

NAMED_COLOR_PATTERN = re.compile(r'\b(' + '|'.join(NAMED_COLORS) + r')\b', re.IGNORECASE)

def extract_colors_from_css(css_text, include_named=False):
    """
    Parses CSS text line-by-line and extracts colors from the property value side.
    Returns a dict mapping color string to a list of details: [(line_num, line_content)]
    """
    found_colors = {}
    
    lines = css_text.splitlines()
    for idx, line in enumerate(lines):
        line_num = idx + 1
        clean_line = line.strip()
        
        # Skip comments or selectors
        if not clean_line or clean_line.startswith('/*') or clean_line.startswith('*'):
            continue
            
        # We only want to look at the value portion of declarations
        if ':' in clean_line:
            parts = clean_line.split(':', 1)
            value_part = parts[1]
            
            # Find hex colors
            for match in HEX_COLOR_PATTERN.finditer(value_part):
                color = match.group(0)
                found_colors.setdefault(color, []).append((line_num, clean_line))
                
            # Find rgb/rgba colors
            for match in RGB_COLOR_PATTERN.finditer(value_part):
                color = match.group(0)
                found_colors.setdefault(color, []).append((line_num, clean_line))
                
            # Find hsl/hsla colors
            for match in HSL_COLOR_PATTERN.finditer(value_part):
                color = match.group(0)
                found_colors.setdefault(color, []).append((line_num, clean_line))
                
            # Find named colors
            if include_named:
                for match in NAMED_COLOR_PATTERN.finditer(value_part):
                    color = match.group(0).lower()
                    found_colors.setdefault(color, []).append((line_num, clean_line))
                    
    return found_colors

def main():
    parser = argparse.ArgumentParser(
        description="CSS Color Extractor - Scan CSS files and extract/de-duplicate colors."
    )
    parser.add_argument(
        '-i', '--input',
        nargs='*',
        help='Input CSS file paths. Supports glob patterns (e.g. "styles/**/*.css"). If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-n', '--named',
        action='store_true',
        help='Include standard CSS named colors (like red, blue, transparent) in the extraction.'
    )
    parser.add_argument(
        '--export-vars',
        help='Path to save a CSS file declaring all extracted colors as CSS custom properties (variables).'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output the extracted colors and locations in JSON format.'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for files (default: utf-8)'
    )

    args = parser.parse_args()

    css_sources = {}

    # Load inputs
    if args.input:
        expanded_paths = []
        for pattern in args.input:
            matches = glob.glob(pattern, recursive=True)
            if matches:
                expanded_paths.extend(matches)
            else:
                expanded_paths.append(pattern)
                
        for path in expanded_paths:
            if not os.path.exists(path):
                print(f"[WARNING] File '{path}' does not exist, skipping.", file=sys.stderr)
                continue
            try:
                with open(path, 'r', encoding=args.encoding, errors='replace') as f:
                    css_sources[path] = f.read()
            except Exception as e:
                print(f"[ERROR] Failed to read CSS file '{path}': {e}", file=sys.stderr)
                return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for CSS input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            css_sources["stdin"] = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not css_sources:
        print("[ERROR] No valid CSS sources loaded.", file=sys.stderr)
        return 1

    # Merge colors from all sources
    all_colors = {}
    for source_name, content in css_sources.items():
        source_colors = extract_colors_from_css(content, include_named=args.named)
        for color, occurrences in source_colors.items():
            for line_num, line_content in occurrences:
                all_colors.setdefault(color, []).append({
                    "file": source_name,
                    "line": line_num,
                    "content": line_content
                })

    if args.json:
        # Print structured JSON output
        print(json.dumps(all_colors, indent=2))
        return 0

    # Print human-readable report
    total_unique = len(all_colors)
    total_occurrences = sum(len(occ) for occ in all_colors.values())
    
    print(f"=== CSS COLOR EXTRACTION REPORT ===")
    print(f"Total Unique Colors: {total_unique}")
    print(f"Total Declarations:  {total_occurrences}")
    print("=" * 60)
    
    # Sort colors by frequency of occurrence (descending)
    sorted_colors = sorted(all_colors.items(), key=lambda x: len(x[1]), reverse=True)
    
    for color, occs in sorted_colors:
        print(f"\nColor: {color:<20} | Occurrences: {len(occs)}")
        print("-" * 50)
        # Print top 5 occurrences for brevity
        for occ in occs[:5]:
            print(f"  {occ['file']}:{occ['line']} -> {occ['content']}")
        if len(occs) > 5:
            print(f"  ... and {len(occs) - 5} more")

    # Optionally export CSS variables
    if args.export_vars:
        try:
            var_lines = [":root {"]
            # Clean up color names to make valid CSS variable names
            for idx, (color, _) in enumerate(sorted_colors):
                # Replace invalid chars like #, (, ), %, commas with dashes
                var_name = color.lower()
                var_name = var_name.replace('#', '')
                var_name = re.sub(r'[^a-z0-9-]', '-', var_name)
                var_name = re.sub(r'-+', '-', var_name).strip('-')
                
                # Make sure it doesn't start with a number
                if var_name and var_name[0].isdigit():
                    var_name = f"color-{var_name}"
                elif not var_name:
                    var_name = f"color-{idx+1}"
                    
                var_lines.append(f"  --color-{var_name}: {color};")
            var_lines.append("}")
            
            output_content = "\n".join(var_lines) + "\n"
            
            with open(args.export_vars, 'w', encoding=args.encoding) as f:
                f.write(output_content)
                
            print(f"\n[OK] Exported {len(sorted_colors)} CSS variables to '{args.export_vars}'.")
        except Exception as e:
            print(f"[ERROR] Failed to write variables file '{args.export_vars}': {e}", file=sys.stderr)
            return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
