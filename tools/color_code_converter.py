#!/usr/bin/env python3
"""
Color Code Converter
Converts color values between Hex, RGB, HSL, and CMYK color spaces.
"""

import argparse
import sys
import re

def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#').strip()
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    if len(hex_str) != 6:
        raise ValueError("Hex color must be 3 or 6 hexadecimal characters (e.g., #FFF or #FFFFFF).")
    try:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
    except ValueError:
        raise ValueError("Invalid hexadecimal characters in hex color.")
    return r, g, b

def rgb_to_hsl(r, g, b):
    r_frac = r / 255.0
    g_frac = g / 255.0
    b_frac = b / 255.0
    c_max = max(r_frac, g_frac, b_frac)
    c_min = min(r_frac, g_frac, b_frac)
    delta = c_max - c_min

    l = (c_max + c_min) / 2.0

    if delta == 0:
        h = 0.0
        s = 0.0
    else:
        if l < 0.5:
            s = delta / (c_max + c_min)
        else:
            s = delta / (2.0 - c_max - c_min)

        if c_max == r_frac:
            h = (g_frac - b_frac) / delta + (6.0 if g_frac < b_frac else 0.0)
        elif c_max == g_frac:
            h = (b_frac - r_frac) / delta + 2.0
        else:
            h = (r_frac - g_frac) / delta + 4.0
        h *= 60.0

    return round(h), round(s * 100), round(l * 100)

def hsl_to_rgb(h, s, l):
    h = h % 360
    s /= 100.0
    l /= 100.0

    if s == 0:
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p

        if l < 0.5:
            q = l * (1 + s)
        else:
            q = l + s - l * s
        p = 2 * l - q

        r = hue_to_rgb(p, q, h / 360.0 + 1/3)
        g = hue_to_rgb(p, q, h / 360.0)
        b = hue_to_rgb(p, q, h / 360.0 - 1/3)

    return round(r * 255), round(g * 255), round(b * 255)

def rgb_to_cmyk(r, g, b):
    if (r, g, b) == (0, 0, 0):
        return 0, 0, 0, 100

    r_frac = r / 255.0
    g_frac = g / 255.0
    b_frac = b / 255.0

    k = 1.0 - max(r_frac, g_frac, b_frac)
    c = (1.0 - r_frac - k) / (1.0 - k)
    m = (1.0 - g_frac - k) / (1.0 - k)
    y = (1.0 - b_frac - k) / (1.0 - k)

    return round(c * 100), round(m * 100), round(y * 100), round(k * 100)

def cmyk_to_rgb(c, m, y, k):
    c /= 100.0
    m /= 100.0
    y /= 100.0
    k /= 100.0

    r = 255 * (1.0 - c) * (1.0 - k)
    g = 255 * (1.0 - m) * (1.0 - k)
    b = 255 * (1.0 - y) * (1.0 - k)

    return round(r), round(g), round(b)

def parse_csv_ints(s, count):
    # Extracts integers or floats and strips percentage signs
    parts = [p.strip().rstrip('%') for p in re.split(r'[,/\s]+', s.strip()) if p.strip()]
    if len(parts) != count:
        raise ValueError(f"Expected {count} values, got {len(parts)}.")
    return [float(p) for p in parts]

def main():
    parser = argparse.ArgumentParser(
        description="Convert color values between Hex, RGB, HSL, and CMYK color spaces.",
        epilog="Examples:\n"
               "  python color_code_converter.py --hex \"#FF5733\"\n"
               "  python color_code_converter.py --rgb \"255, 87, 51\"\n"
               "  python color_code_converter.py --hsl \"11, 100, 60\"\n"
               "  python color_code_converter.py --cmyk \"0, 66, 80, 0\"\n"
               "  python color_code_converter.py \"#00ff00\"",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-x", "--hex", help="Hex color string (e.g. #FFA500 or FFF)")
    group.add_argument("-r", "--rgb", help="RGB color string (e.g. '255, 165, 0')")
    group.add_argument("-l", "--hsl", help="HSL color string (e.g. '36, 100%%, 50%%')")
    group.add_argument("-c", "--cmyk", help="CMYK color string (e.g. '0, 35, 100, 0')")
    parser.add_argument("color", nargs="?", help="Positional fallback for auto-detecting color string")

    args = parser.parse_args()

    # Determine input type
    rgb = None
    input_desc = ""

    try:
        if args.hex:
            rgb = hex_to_rgb(args.hex)
            input_desc = f"Hex: {args.hex}"
        elif args.rgb:
            vals = parse_csv_ints(args.rgb, 3)
            r, g, b = [int(v) for v in vals]
            if not all(0 <= val <= 255 for val in (r, g, b)):
                raise ValueError("RGB values must be in the range [0, 255].")
            rgb = (r, g, b)
            input_desc = f"RGB: {r}, {g}, {b}"
        elif args.hsl:
            vals = parse_csv_ints(args.hsl, 3)
            h, s, l = vals
            if not (0 <= h <= 360):
                raise ValueError("Hue (H) must be in the range [0, 360].")
            if not (0 <= s <= 100 and 0 <= l <= 100):
                raise ValueError("Saturation (S) and Lightness (L) must be in the range [0, 100].")
            rgb = hsl_to_rgb(h, s, l)
            input_desc = f"HSL: {round(h)}, {round(s)}%, {round(l)}%"
        elif args.cmyk:
            vals = parse_csv_ints(args.cmyk, 4)
            c, m, y, k = vals
            if not all(0 <= val <= 100 for val in (c, m, y, k)):
                raise ValueError("CMYK values must be in the range [0, 100].")
            rgb = cmyk_to_rgb(c, m, y, k)
            input_desc = f"CMYK: {round(c)}%, {round(m)}%, {round(y)}%, {round(k)}%"
        elif args.color:
            # Auto-detection
            cleaned = args.color.strip()
            # 1. Hex?
            if cleaned.startswith('#') or len(cleaned) in (3, 6) and all(c in '0123456789abcdefABCDEF' for c in cleaned):
                try:
                    rgb = hex_to_rgb(cleaned)
                    input_desc = f"Hex (Auto-detected): {cleaned}"
                except ValueError:
                    pass
            
            # 2. RGB? (starts with rgb or matches 3 numbers)
            if rgb is None and ('rgb' in cleaned.lower() or ',' in cleaned):
                # Clean up functional wrapper like rgb(...)
                s = re.sub(r'rgb[a]?\((.*)\)', r'\1', cleaned, flags=re.IGNORECASE)
                try:
                    vals = parse_csv_ints(s, 3)
                    r, g, b = [int(v) for v in vals]
                    if all(0 <= val <= 255 for val in (r, g, b)):
                        rgb = (r, g, b)
                        input_desc = f"RGB (Auto-detected): {r}, {g}, {b}"
                except ValueError:
                    pass
            
            # 3. HSL?
            if rgb is None and ('hsl' in cleaned.lower() or '%' in cleaned):
                s = re.sub(r'hsl[a]?\((.*)\)', r'\1', cleaned, flags=re.IGNORECASE)
                try:
                    vals = parse_csv_ints(s, 3)
                    h, s_val, l_val = vals
                    if (0 <= h <= 360) and (0 <= s_val <= 100) and (0 <= l_val <= 100):
                        rgb = hsl_to_rgb(h, s_val, l_val)
                        input_desc = f"HSL (Auto-detected): {round(h)}, {round(s_val)}%, {round(l_val)}%"
                except ValueError:
                    pass

            # 4. CMYK?
            if rgb is None:
                s = re.sub(r'cmyk\((.*)\)', r'\1', cleaned, flags=re.IGNORECASE)
                try:
                    vals = parse_csv_ints(s, 4)
                    c, m, y, k = vals
                    if all(0 <= val <= 100 for val in (c, m, y, k)):
                        rgb = cmyk_to_rgb(c, m, y, k)
                        input_desc = f"CMYK (Auto-detected): {round(c)}%, {round(m)}%, {round(y)}%, {round(k)}%"
                except ValueError:
                    pass

            # If all failed, try a last-ditch hex parse without # or simple commas
            if rgb is None:
                try:
                    # Let's try 3-number comma separated
                    vals = parse_csv_ints(cleaned, 3)
                    r, g, b = [int(v) for v in vals]
                    if all(0 <= val <= 255 for val in (r, g, b)):
                        rgb = (r, g, b)
                        input_desc = f"RGB (Auto-detected): {r}, {g}, {b}"
                except ValueError:
                    pass

            if rgb is None:
                raise ValueError(f"Could not parse or auto-detect color format: '{args.color}'")
        else:
            parser.print_help()
            sys.exit(0)

        # Do conversions
        r, g, b = rgb
        hex_val = rgb_to_hex(r, g, b)
        h, s, l = rgb_to_hsl(r, g, b)
        c, m, y, k = rgb_to_cmyk(r, g, b)

        print(f"[PASS] Successfully parsed input color: {input_desc}")
        print("-" * 40)
        print(f"  Hex  : {hex_val}")
        print(f"  RGB  : rgb({r}, {g}, {b})")
        print(f"  HSL  : hsl({h}, {s}%, {l}%)")
        print(f"  CMYK : cmyk({c}%, {m}%, {y}%, {k}%)")
        print("-" * 40)

    except Exception as e:
        print(f"[ERROR] {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
