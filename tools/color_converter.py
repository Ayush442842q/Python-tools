#!/usr/bin/env python3
"""
Color Converter & WCAG Contrast Checker
Converts color codes between HEX, RGB, HSL, and CMYK, and calculates WCAG contrast ratios.
"""

import sys
import re
import argparse

def hex_to_rgb(hex_str):
    """Convert HEX string to RGB tuple."""
    hex_str = hex_str.lstrip('#').strip()
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    if len(hex_str) != 6:
        raise ValueError("HEX color must be 3 or 6 hex digits long.")
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return r, g, b

def rgb_to_hex(r, g, b):
    """Convert RGB tuple to HEX string."""
    return f"#{r:02x}{g:02x}{b:02x}"

def rgb_to_hsl(r, g, b):
    """Convert RGB (0-255) to HSL."""
    r_pct = r / 255.0
    g_pct = g / 255.0
    b_pct = b / 255.0
    
    max_c = max(r_pct, g_pct, b_pct)
    min_c = min(r_pct, g_pct, b_pct)
    delta = max_c - min_c
    
    l = (max_c + min_c) / 2.0
    
    if delta == 0:
        h = 0.0
        s = 0.0
    else:
        if l < 0.5:
            s = delta / (max_c + min_c)
        else:
            s = delta / (2.0 - max_c - min_c)
            
        if max_c == r_pct:
            h = (g_pct - b_pct) / delta + (6.0 if g_pct < b_pct else 0.0)
        elif max_c == g_pct:
            h = (b_pct - r_pct) / delta + 2.0
        else:
            h = (r_pct - g_pct) / delta + 4.0
        h /= 6.0
        
    return round(h * 360), round(s * 100), round(l * 100)

def hsl_to_rgb(h, s, l):
    """Convert HSL to RGB."""
    h_pct = h / 360.0
    s_pct = s / 100.0
    l_pct = l / 100.0
    
    if s_pct == 0:
        r = g = b = l_pct
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
            
        q = l_pct * (1 + s_pct) if l_pct < 0.5 else l_pct + s_pct - l_pct * s_pct
        p = 2 * l_pct - q
        
        r = hue_to_rgb(p, q, h_pct + 1/3)
        g = hue_to_rgb(p, q, h_pct)
        b = hue_to_rgb(p, q, h_pct - 1/3)
        
    return round(r * 255), round(g * 255), round(b * 255)

def rgb_to_cmyk(r, g, b):
    """Convert RGB to CMYK."""
    if (r, g, b) == (0, 0, 0):
        return 0, 0, 0, 100
        
    r_pct = r / 255.0
    g_pct = g / 255.0
    b_pct = b / 255.0
    
    k = 1.0 - max(r_pct, g_pct, b_pct)
    c = (1.0 - r_pct - k) / (1.0 - k) if (1.0 - k) != 0 else 0
    m = (1.0 - g_pct - k) / (1.0 - k) if (1.0 - k) != 0 else 0
    y = (1.0 - b_pct - k) / (1.0 - k) if (1.0 - k) != 0 else 0
    
    return round(c * 100), round(m * 100), round(y * 100), round(k * 100)

def cmyk_to_rgb(c, m, y, k):
    """Convert CMYK to RGB."""
    c_pct = c / 100.0
    m_pct = m / 100.0
    y_pct = y / 100.0
    k_pct = k / 100.0
    
    r = round(255 * (1.0 - c_pct) * (1.0 - k_pct))
    g = round(255 * (1.0 - m_pct) * (1.0 - k_pct))
    b = round(255 * (1.0 - y_pct) * (1.0 - k_pct))
    return r, g, b

def get_relative_luminance(r, g, b):
    """Calculate relative luminance according to W3C formula."""
    rs = r / 255.0
    gs = g / 255.0
    bs = b / 255.0
    
    r_lum = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
    g_lum = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
    b_lum = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * r_lum + 0.7152 * g_lum + 0.0722 * b_lum

def get_contrast_ratio(lum1, lum2):
    """Calculate contrast ratio between two relative luminances."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)

def parse_color(color_str):
    """Parse color string in HEX, RGB, or HSL format."""
    color_str = color_str.strip().lower()
    
    # HEX pattern
    if color_str.startswith('#') or re.match(r'^[0-9a-f]{3}$|^[0-9a-f]{6}$', color_str):
        return hex_to_rgb(color_str)
        
    # RGB pattern: rgb(255, 0, 128)
    rgb_match = re.match(r'^rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$', color_str)
    if rgb_match:
        vals = tuple(map(int, rgb_match.groups()))
        if all(0 <= v <= 255 for v in vals):
            return vals
            
    # HSL pattern: hsl(360, 100%, 50%)
    hsl_match = re.match(r'^hsl\s*\(\s*(\d+)\s*,\s*(\d+)%?\s*,\s*(\d+)%?\s*\)$', color_str)
    if hsl_match:
        h, s, l = map(int, hsl_match.groups())
        if 0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100:
            return hsl_to_rgb(h, s, l)
            
    raise ValueError(f"Could not parse color: '{color_str}'")

def print_color_info(r, g, b, label="Color"):
    """Print conversions of RGB color."""
    hex_val = rgb_to_hex(r, g, b)
    h, s, l = rgb_to_hsl(r, g, b)
    c, m, y, k = rgb_to_cmyk(r, g, b)
    
    print(f"=== {label} ===")
    print(f"  HEX:  {hex_val.upper()}")
    print(f"  RGB:  rgb({r}, {g}, {b})")
    print(f"  HSL:  hsl({h}, {s}%, {l}%)")
    print(f"  CMYK: cmyk({c}%, {m}%, {y}%, {k}%)")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Color Converter & WCAG Contrast Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("color", nargs="?", help="Input color code (HEX, rgb(r,g,b), or hsl(h,s,l))")
    parser.add_argument("--contrast", "-c", nargs=2, metavar=("COLOR1", "COLOR2"), help="Check WCAG contrast ratio between two colors")
    
    args = parser.parse_args()
    
    if args.contrast:
        try:
            c1_r, c1_g, c1_b = parse_color(args.contrast[0])
            c2_r, c2_g, c2_b = parse_color(args.contrast[1])
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        lum1 = get_relative_luminance(c1_r, c1_g, c1_b)
        lum2 = get_relative_luminance(c2_r, c2_g, c2_b)
        
        ratio = get_contrast_ratio(lum1, lum2)
        
        print_color_info(c1_r, c1_g, c1_b, "Color 1 (Foreground)")
        print_color_info(c2_r, c2_g, c2_b, "Color 2 (Background)")
        
        print(f"Relative Luminance 1: {lum1:.5f}")
        print(f"Relative Luminance 2: {lum2:.5f}")
        print(f"Contrast Ratio:       {ratio:.2f}:1")
        print("-" * 40)
        
        # WCAG 2.1 Pass/Fail status
        print("WCAG 2.1 Compliance Requirements:")
        print(f"  Normal Text (under 18pt):")
        print(f"    - AA (4.5:1): {'PASS' if ratio >= 4.5 else 'FAIL'}")
        print(f"    - AAA (7.0:1): {'PASS' if ratio >= 7.0 else 'FAIL'}")
        print(f"  Large Text (18pt+ or 14pt+ bold):")
        print(f"    - AA (3.0:1): {'PASS' if ratio >= 3.0 else 'FAIL'}")
        print(f"    - AAA (4.5:1): {'PASS' if ratio >= 4.5 else 'FAIL'}")
        
        return 0
        
    if not args.color:
        parser.print_help()
        return 0
        
    try:
        r, g, b = parse_color(args.color)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    print_color_info(r, g, b, "Conversions")
    return 0

if __name__ == "__main__":
    sys.exit(main())
