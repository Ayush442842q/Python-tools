#!/usr/bin/env python3
"""
CSS Responsive Breakpoint Analyzer

Scans CSS files to extract all media queries (@media), normalizes breakpoints,
identifies logical inconsistencies (overlaps, duplicate triggers), and renders
a visual ASCII timeline of the design breakpoints.

Usage:
    python tools/css_responsive_breakpoint_analyzer.py styles.css [options]
"""

import argparse
import os
import re
import sys

# Regex to match @media statements and extract the query part
MEDIA_REGEX = re.compile(r'@media\s+([^{]+)\{', re.IGNORECASE)

# Regex to find pixel/em/rem values in media queries
WIDTH_REGEX = re.compile(r'\b(min-width|max-width)\s*:\s*([\d\.]+)(px|em|rem)\b', re.IGNORECASE)

def convert_to_px(value, unit):
    """Convert em/rem units to px assuming standard 16px base."""
    val = float(value)
    if unit.lower() in ('em', 'rem'):
        return int(val * 16)
    return int(val)

def parse_css_file(filepath):
    """Read a CSS file and extract media queries with their location/rules."""
    results = []
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        return results

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        # Find all media queries with their offsets
        for match in MEDIA_REGEX.finditer(content):
            query = match.group(1).strip()
            
            # Find line number
            char_index = match.start()
            line_no = content[:char_index].count('\n') + 1
            
            # Parse widths
            widths = []
            for w_match in WIDTH_REGEX.finditer(query):
                feature = w_match.group(1).lower()
                val_str = w_match.group(2)
                unit = w_match.group(3).lower()
                px_val = convert_to_px(val_str, unit)
                
                widths.append({
                    "feature": feature,
                    "raw_value": f"{val_str}{unit}",
                    "px_value": px_val
                })
                
            results.append({
                "line": line_no,
                "query": query,
                "breakpoints": widths
            })
    except Exception as e:
        print(f"Error reading CSS file: {e}", file=sys.stderr)
        
    return results

def analyze_breakpoints(queries):
    """Aggregate breakpoints and check for consistency issues."""
    all_bps = []
    px_set = set()
    warnings = []
    
    for q in queries:
        for bp in q['breakpoints']:
            bp_val = bp['px_value']
            all_bps.append({
                "px": bp_val,
                "raw": bp['raw_value'],
                "feature": bp['feature'],
                "line": q['line'],
                "query": q['query']
            })
            px_set.add(bp_val)
            
    # Sort breakpoints by px value
    all_bps.sort(key=lambda x: x['px'])
    sorted_pxs = sorted(list(px_set))
    
    # Check for inconsistencies
    # 1. Look for near-identical breakpoints (e.g. 767px and 768px is common for min/max, but 765px and 768px might be typo)
    for i in range(len(sorted_pxs) - 1):
        diff = sorted_pxs[i+1] - sorted_pxs[i]
        if 0 < diff <= 3:
            # Let's verify if they are min/max pairs (e.g. max-width: 767px and min-width: 768px)
            # This is normal, but if they are both min-width, it's a warning.
            bp1_list = [b for b in all_bps if b['px'] == sorted_pxs[i]]
            bp2_list = [b for b in all_bps if b['px'] == sorted_pxs[i+1]]
            
            # Check if there's overlapping min-widths or max-widths
            features1 = set(b['feature'] for b in bp1_list)
            features2 = set(b['feature'] for b in bp2_list)
            
            if len(features1.intersection(features2)) > 0:
                warnings.append(
                    f"Near-duplicate breakpoints detected: {sorted_pxs[i]}px and {sorted_pxs[i+1]}px. "
                    f"Check lines {', '.join(str(b['line']) for b in bp1_list)} and {', '.join(str(b['line']) for b in bp2_list)}."
                )

    # 2. Check for exact overlap conflicts (e.g. min-width: 768px and max-width: 768px triggers both on exactly 768px)
    for px in sorted_pxs:
        matching = [b for b in all_bps if b['px'] == px]
        mins = [b for b in matching if b['feature'] == 'min-width']
        maxs = [b for b in matching if b['feature'] == 'max-width']
        if mins and maxs:
            warnings.append(
                f"Collision warning: Both min-width and max-width set to {px}px (raw values: "
                f"{', '.join(m['raw'] for m in mins)} vs {', '.join(mx['raw'] for mx in maxs)}). "
                f"They will overlap at exactly {px}px width (Lines: {', '.join(str(b['line']) for b in matching)})."
            )

    return all_bps, sorted_pxs, warnings

def render_timeline(sorted_pxs):
    """Render a visual ASCII representation of breakpoints."""
    if not sorted_pxs:
        return "No responsive width-based breakpoints detected."
        
    timeline = "0px"
    for px in sorted_pxs:
        timeline += f" ──┤ {px}px ├──"
    timeline += " ──> [Desktop/Widescreen]"
    return timeline

def main():
    parser = argparse.ArgumentParser(
        description="Extract, analyze, and visualize responsive breakpoints from CSS stylesheets."
    )
    parser.add_argument("css_file", help="Path to the CSS file to analyze")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show the full list of media query blocks")
                        
    args = parser.parse_args()
    
    queries = parse_css_file(args.css_file)
    if not queries:
        print("No media queries found or error reading file.")
        return 0
        
    all_bps, sorted_pxs, warnings = analyze_breakpoints(queries)
    
    print("=" * 60)
    print(f" CSS RESPONSIVE BREAKPOINT REPORT: {os.path.basename(args.css_file)}")
    print("=" * 60)
    print(f"Total @media blocks found: {len(queries)}")
    print(f"Unique breakpoint values:  {len(sorted_pxs)} distinct widths")
    print("-" * 60)
    
    print("Visual Breakpoint Timeline:")
    print(render_timeline(sorted_pxs))
    print("-" * 60)
    
    if all_bps:
        print("Detected Width Breakpoints:")
        current_px = None
        for bp in all_bps:
            if bp['px'] != current_px:
                current_px = bp['px']
                print(f"\n  [{current_px}px] ({bp['raw']}):")
            print(f"    - {bp['feature']:<10} on line {bp['line']:<4} | Query: {bp['query']}")
        print()
    else:
        print("No explicit min-width/max-width media queries detected (e.g. maybe print or orientation only).")
        
    if warnings:
        print("-" * 60)
        print("⚠️  POTENTIAL ISSUES / RECOMMENDATIONS:")
        for w in warnings:
            print(f"  * {w}")
    else:
        print("-" * 60)
        print("✅ No overlapping range conflicts or duplicates detected!")
        
    if args.verbose:
        print("-" * 60)
        print("Full Media Query Catalog:")
        for q in queries:
            print(f"  Line {q['line']:<4} | {q['query']}")
            
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
