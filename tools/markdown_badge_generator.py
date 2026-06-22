#!/usr/bin/env python3
"""
SVG Status Badge Generator - Generate custom shields.io style SVG badges locally.

This tool calculates text dimensions and creates standard-compliant SVG status
badges (like build passing, coverage 100%%) that can be embedded in markdown
documentation. It runs entirely using standard library modules.
"""

import sys
import os
import argparse
import xml.etree.ElementTree as ET

# Default color mapping (Shields.io standard palettes)
COLOR_PALETTE = {
    'brightgreen': '#4c1',
    'green': '#97ca00',
    'yellowgreen': '#a4a61d',
    'yellow': '#dfb317',
    'orange': '#fe7d3f',
    'red': '#e05d44',
    'blue': '#007ec6',
    'lightgrey': '#9f9f9f',
    'grey': '#555',
    'gray': '#555',
    'black': '#000',
    'violet': '#7f00ff'
}

def get_color_code(color_str):
    """Retrieve hex color code from name or pass-through if already hex."""
    color_str = color_str.strip().lower()
    if color_str.startswith('#'):
        return color_str
    # If standard hex without hash, add it
    if len(color_str) in (3, 6) and all(c in '0123456789abcdef' for c in color_str):
        return f"#{color_str}"
    return COLOR_PALETTE.get(color_str, COLOR_PALETTE['grey'])

def estimate_text_width(text):
    """
    Estimate Verdana 11px text width in pixels.
    Uses relative char width scaling for DejaVu/Verdana sans-serif.
    """
    # Base width dictionary at 11px size
    widths = {
        'i': 3, 'l': 3, 't': 4, 'f': 5, 'j': 3, 'r': 5, 'I': 4, '1': 6,
        ' ': 4, '.': 3, ',': 3, '-': 5, '_': 7, ':': 3, ';': 3, '(': 5,
        ')': 5, '[': 4, ']': 4, '{': 5, '}': 5, '/': 5, '\\': 5, '|': 3,
        'w': 10, 'm': 10, 'W': 11, 'M': 11, 'O': 8, 'Q': 8, 'g': 7, 'q': 7
    }
    total = 0.0
    for char in text:
        total += widths.get(char, 7.0)
    # Add safety padding
    return int(total * 1.05) + 4

def generate_badge_svg(label, status, color_name, label_color_name='grey'):
    """
    Generate the SVG markup for the badge as a string.
    """
    val_color = get_color_code(color_name)
    lbl_color = get_color_code(label_color_name)
    
    # Calculate widths
    label_text_width = estimate_text_width(label)
    status_text_width = estimate_text_width(status)
    
    # Padding on left and right of text (standard shields.io is ~10px)
    padding = 10
    
    w1 = label_text_width + (padding * 2)
    w2 = status_text_width + (padding * 2)
    total_width = w1 + w2
    
    # Text centers for scale(.1) transforms
    x1 = int((w1 / 2) * 10)
    x2 = int((w1 + (w2 / 2)) * 10)
    
    label_text_len = label_text_width * 10
    status_text_len = status_text_width * 10
    
    # Build SVG content directly
    svg_template = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total_width}" height="20" role="img" aria-label="{label}: {status}">
  <title>{label}: {status}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{w1}" height="20" fill="{lbl_color}"/>
    <rect x="{w1}" width="{w2}" height="20" fill="{val_color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text x="{x1}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{label_text_len}">{label}</text>
    <text x="{x1}" y="140" transform="scale(.1)" fill="#fff" textLength="{label_text_len}">{label}</text>
    <text x="{x2}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{status_text_len}">{status}</text>
    <text x="{x2}" y="140" transform="scale(.1)" fill="#fff" textLength="{status_text_len}">{status}</text>
  </g>
</svg>"""
    return svg_template

def main():
    parser = argparse.ArgumentParser(
        description="SVG Status Badge Generator - Create custom shields.io style badges offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("label", help="The label text for the left side of the badge (e.g. 'build').")
    parser.add_argument("status", help="The status text for the right side of the badge (e.g. 'passing').")
    parser.add_argument(
        "color", 
        nargs="?", 
        default="brightgreen", 
        help="Color of the right side background (name or hex code). Default: brightgreen."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output filepath. If not specified, outputs SVG markup to stdout."
    )
    parser.add_argument(
        "--label-color", 
        default="grey", 
        help="Color of the left side background (name or hex code). Default: grey."
    )

    args = parser.parse_args()
    
    svg_content = generate_badge_svg(
        label=args.label,
        status=args.status,
        color_name=args.color,
        label_color_name=args.label_color
    )
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            print(f"[+] Badge successfully generated and saved to '{args.output}'", file=sys.stderr)
        except Exception as e:
            print(f"[-] Error writing SVG to file: {e}", file=sys.stderr)
            return 1
    else:
        print(svg_content)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
