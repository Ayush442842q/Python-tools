#!/usr/bin/env python3
"""
SVG Color Palette Extractor & Theme Replacer

Parses SVG vector graphics to extract all hex, RGB, and named CSS colors from attributes
like `fill`, `stroke`, `stop-color`, and inline `style` rules. Displays a color palette
visualizer in the terminal and allows bulk color swapping, palette conversion (e.g., light
to dark mode), or color inversion.

Usage:
    # Extract and display unique colors in an SVG
    python svg_color_theme_replacer.py icon.svg

    # Replace specific colors (hex or CSS name) and save output
    python svg_color_theme_replacer.py icon.svg -r "#ffffff:#1a1a1a" "blue:#ff007f" -o themed_icon.svg

    # Invert all colors (lightness inversion) for dark/light mode toggle
    python svg_color_theme_replacer.py icon.svg --invert -o inverted_icon.svg
"""

import os
import sys
import re
import argparse
import xml.etree.ElementTree as ET

# Register standard SVG namespaces to prevent ElementTree prefixing tags with ns0:
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

COLOR_HEX_RE = re.compile(r'#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})\b')
COLOR_RGB_RE = re.compile(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', re.IGNORECASE)

# Standard CSS Color name mapping to Hex (subset of common names)
CSS_NAMES_TO_HEX = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "lime": "#00ff00",
    "blue": "#0000ff", "yellow": "#ffff00", "cyan": "#00ffff", "magenta": "#ff00ff",
    "silver": "#c0c0c0", "gray": "#808080", "maroon": "#800000", "olive": "#808000",
    "green": "#008000", "purple": "#800080", "teal": "#008080", "navy": "#000080",
    "orange": "#ffa500", "pink": "#ffc0cb", "gold": "#ffd700", "brown": "#a52a2a"
}

def normalize_color(color_str):
    """Normalizes any color representation into a 6-character lowercase hex string."""
    color_str = color_str.strip().lower()
    
    if color_str == 'none' or color_str.startswith('url('):
        return None
        
    # Check CSS Names
    if color_str in CSS_NAMES_TO_HEX:
        return CSS_NAMES_TO_HEX[color_str]
        
    # Check 6-char hex
    if color_str.startswith('#'):
        hex_val = color_str[1:]
        if len(hex_val) == 3:
            return "#" + "".join(c*2 for c in hex_val)
        if len(hex_val) == 6:
            return color_str
            
    # Check RGB format
    rgb_match = COLOR_RGB_RE.match(color_str)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
        
    return None

def parse_style_attribute(style_str):
    """Parses a style string into a dictionary of property-value pairs."""
    rules = {}
    if not style_str:
        return rules
    for declaration in style_str.split(';'):
        if ':' in declaration:
            prop, val = declaration.split(':', 1)
            rules[prop.strip().lower()] = val.strip()
    return rules

def build_style_attribute(style_dict):
    """Rebuilds a style string from a dictionary."""
    return ";".join(f"{k}:{v}" for k, v in style_dict.items())

def rgb_to_hsv(r, g, b):
    r, g, b = r/255.0, g/255.0, b/255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    s = 0 if mx == 0 else (df/mx)*100
    v = mx*100
    return h, s, v

def hsv_to_rgb(h, s, v):
    h = h / 360.0
    s = s / 100.0
    v = v / 100.0
    if s == 0.0:
        r = g = b = v
    else:
        i = int(h*6.0)
        f = (h*6.0) - i
        p = v*(1.0 - s)
        q = v*(1.0 - s*f)
        t = v*(1.0 - s*(1.0-f))
        i = i % 6
        if i == 0: r, g, b = v, t, p
        elif i == 1: r, g, b = q, v, p
        elif i == 2: r, g, b = p, v, t
        elif i == 3: r, g, b = p, q, v
        elif i == 4: r, g, b = t, p, v
        elif i == 5: r, g, b = v, p, q
    return int(r*255), int(g*255), int(b*255)

def invert_hex_color(hex_str):
    """Inverts the lightness/brightness value of a color (in HSV space) for light/dark swapping."""
    norm = normalize_color(hex_str)
    if not norm:
        return hex_str
    r = int(norm[1:3], 16)
    g = int(norm[3:5], 16)
    b = int(norm[5:7], 16)
    
    h, s, v = rgb_to_hsv(r, g, b)
    # Invert the value (lightness)
    inverted_v = 100 - v
    # Shift saturation slightly to look natural
    inverted_r, inverted_g, inverted_b = hsv_to_rgb(h, s, inverted_v)
    return f"#{inverted_r:02x}{inverted_g:02x}{inverted_b:02x}"

def replace_color_in_str(val_str, mapping, invert_all=False):
    """Inspects a string value and applies mapping replacements or inversion."""
    normalized = normalize_color(val_str)
    if normalized:
        if invert_all:
            return invert_hex_color(normalized)
        if normalized in mapping:
            return mapping[normalized]
            
    # Check nested regex matches inside larger text (e.g. style attributes)
    # Check hex colors
    def hex_repl(match):
        hex_color = normalize_color(match.group(0))
        if invert_all:
            return invert_hex_color(hex_color)
        return mapping.get(hex_color, match.group(0))
        
    res = COLOR_HEX_RE.sub(hex_repl, val_str)
    
    # Check RGB colors
    def rgb_repl(match):
        raw_rgb = match.group(0)
        hex_color = normalize_color(raw_rgb)
        if invert_all:
            return invert_hex_color(hex_color)
        return mapping.get(hex_color, raw_rgb)
        
    res = COLOR_RGB_RE.sub(rgb_repl, res)
    return res

def scan_and_replace_svg(tree, mapping, invert_all=False):
    """Traverses SVG element tree, extracts colors, and optionally modifies them in place."""
    color_counts = {}
    color_attributes = ['fill', 'stroke', 'stop-color', 'color']
    
    for elem in tree.iter():
        # 1. Process attributes directly
        for attr in color_attributes:
            val = elem.get(attr)
            if val:
                norm = normalize_color(val)
                if norm:
                    color_counts[norm] = color_counts.get(norm, 0) + 1
                    
                if mapping or invert_all:
                    new_val = replace_color_in_str(val, mapping, invert_all)
                    elem.set(attr, new_val)
                    
        # 2. Process inline styles
        style_val = elem.get('style')
        if style_val:
            style_dict = parse_style_attribute(style_val)
            style_changed = False
            
            for attr in color_attributes:
                if attr in style_dict:
                    val = style_dict[attr]
                    norm = normalize_color(val)
                    if norm:
                        color_counts[norm] = color_counts.get(norm, 0) + 1
                        
                    if mapping or invert_all:
                        new_val = replace_color_in_str(val, mapping, invert_all)
                        style_dict[attr] = new_val
                        style_changed = True
                        
            if style_changed:
                elem.set('style', build_style_attribute(style_dict))
                
    return color_counts

def render_color_bar(hex_str, count, use_color=True):
    """Prints a visual ASCII representation of a color in the terminal."""
    if not hex_str.startswith('#') or len(hex_str) != 7:
        return f"  {hex_str:<10} (Count: {count})"
        
    r = int(hex_str[1:3], 16)
    g = int(hex_str[3:5], 16)
    b = int(hex_str[5:7], 16)
    
    if use_color:
        # Standard TrueColor ANSI ESCAPE sequence
        block = f"\033[48;2;{r};{g};{b}m      \033[0m"
        return f"  {block}  {hex_str}  (Used {count} times)"
    else:
        return f"  [HEX]     {hex_str}  (Used {count} times)"

def main():
    parser = argparse.ArgumentParser(
        description="SVG Color Palette Extractor and Theme Replacer."
    )
    parser.add_argument('file', help="SVG file to parse")
    parser.add_argument(
        '-r', '--replace', nargs='*', default=[],
        help="Replacement pairs in 'old:new' format (e.g., '#ffffff:#000' or 'red:#ff00ff')"
    )
    parser.add_argument(
        '--invert', action='store_true',
        help="Automatically invert the lightness of all colors (useful for dark mode transformation)"
    )
    parser.add_argument('-o', '--output', help="File path to save the modified SVG (defaults to overwriting input file if replacements are provided)")
    parser.add_argument('--no-color', action='store_true', help="Disable terminal ANSI colors")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)

    # ANSI color checking
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt'
    COLOR_CYAN = "\033[96m" if use_color else ""
    COLOR_GREEN = "\033[92m" if use_color else ""
    COLOR_RESET = "\033[0m" if use_color else ""

    # Parse replacements
    replacements_map = {}
    for pair in args.replace:
        if ':' in pair:
            old, new = pair.split(':', 1)
            norm_old = normalize_color(old)
            if norm_old:
                replacements_map[norm_old] = new.strip()
            else:
                print(f"Warning: Could not parse replacement color '{old}'", file=sys.stderr)

    try:
        tree = ET.parse(args.file)
    except Exception as e:
        print(f"Error parsing SVG XML: {e}", file=sys.stderr)
        sys.exit(1)

    # First pass / modification pass
    color_counts = scan_and_replace_svg(tree, replacements_map, args.invert)

    print(f"{COLOR_CYAN}=== SVG Color Palette Extractor ==={COLOR_RESET}")
    print(f"Source file: {args.file}")
    print(f"Found {len(color_counts)} unique colors:\n")

    for color, count in sorted(color_counts.items(), key=lambda x: x[1], reverse=True):
        print(render_color_bar(color, count, use_color))
        
    # Write output if changes are requested
    if replacements_map or args.invert:
        out_path = args.output if args.output else args.file
        print(f"\n{COLOR_CYAN}Applying color transformations...{COLOR_RESET}")
        if replacements_map:
            for k, v in replacements_map.items():
                print(f"  Swap: {k} → {v}")
        if args.invert:
            print("  Operation: Lightness inversion (dark/light theme mapping)")
            
        try:
            tree.write(out_path, encoding='utf-8', xml_declaration=True)
            print(f"\n{COLOR_GREEN}✔ Saved themed SVG successfully to: {out_path}{COLOR_RESET}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
