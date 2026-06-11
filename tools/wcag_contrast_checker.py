#!/usr/bin/env python3
"""
WCAG Contrast Checker & Palette Generator

Calculates the WCAG 2.1 contrast ratio between foreground and background colors
and generates accessible color palettes based on a seed color. Prints true-color
swatches in terminals supporting 24-bit color.

Usage:
    python tools/wcag_contrast_checker.py #0070f3 #ffffff
    python tools/wcag_contrast_checker.py --seed #3498db
"""

import argparse
import colorsys
import os
import re
import sys

# ANSI Escape Sequences
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"


def parse_hex(hex_str):
    """Parses a hex color string into (R, G, B) tuple on 0-255 scale."""
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    if len(hex_str) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return r, g, b


def to_hex(rgb):
    """Converts a (R, G, B) tuple to a hex string."""
    return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"


def get_ansi_bg_fg(bg_rgb, fg_rgb, text):
    """Formats text with terminal true-color background and foreground colors."""
    br, bg, bb = bg_rgb
    fr, fg, fb = fg_rgb
    # 48;2;r;g;b is background, 38;2;r;g;b is foreground
    return f"\033[48;2;{br};{bg};{bb}m\033[38;2;{fr};{fg};{fb}m {text} \033[0m"


def get_ansi_swatch(rgb):
    """Returns a colored block using the specified RGB color."""
    r, g, b = rgb
    return f"\033[48;2;{r};{g};{b}m      \033[0m"


def relative_luminance(rgb):
    """Calculates relative luminance of a color based on W3C formula."""
    # Scale to 0-1
    rs = rgb[0] / 255.0
    gs = rgb[1] / 255.0
    bs = rgb[2] / 255.0

    # Apply gamma compression coefficients
    rc = rs / 12.92 if rs <= 0.04045 else ((rs + 0.055) / 1.055) ** 2.4
    gc = gs / 12.92 if gs <= 0.04045 else ((gs + 0.055) / 1.055) ** 2.4
    bc = bs / 12.92 if bs <= 0.04045 else ((bs + 0.055) / 1.055) ** 2.4

    return 0.2126 * rc + 0.7152 * gc + 0.0722 * bc


def contrast_ratio(rgb1, rgb2):
    """Calculates the contrast ratio between two colors."""
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    
    # L1 must be the lighter color
    if l1 < l2:
        l1, l2 = l2, l1
        
    return (l1 + 0.05) / (l2 + 0.05)


def check_wcag_standards(ratio):
    """Evaluates contrast ratio against WCAG AA and AAA standards."""
    results = {
        "AA_normal": ratio >= 4.5,
        "AA_large": ratio >= 3.0,
        "AAA_normal": ratio >= 7.0,
        "AAA_large": ratio >= 4.5
    }
    return results


def hsl_to_rgb(h, s, l):
    """Wrapper to convert HSL (0-1 scale) to RGB (0-255 scale)."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def rgb_to_hsl(rgb):
    """Wrapper to convert RGB (0-255 scale) to HSL (0-1 scale)."""
    r, g, b = rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def generate_palettes(seed_hex):
    """Generates standard design color palettes from a seed color."""
    rgb = parse_hex(seed_hex)
    h, s, l = rgb_to_hsl(rgb)
    
    palettes = {
        "Seed Color": [rgb],
        "Complementary": [
            rgb,
            hsl_to_rgb((h + 0.5) % 1.0, s, l)
        ],
        "Analogous": [
            hsl_to_rgb((h - 0.083) % 1.0, s, l),
            rgb,
            hsl_to_rgb((h + 0.083) % 1.0, s, l)
        ],
        "Triadic": [
            rgb,
            hsl_to_rgb((h + 0.333) % 1.0, s, l),
            hsl_to_rgb((h + 0.666) % 1.0, s, l)
        ],
        "Split-Complementary": [
            rgb,
            hsl_to_rgb((h + 0.416) % 1.0, s, l),
            hsl_to_rgb((h + 0.583) % 1.0, s, l)
        ],
        "Monochromatic": [
            hsl_to_rgb(h, s, max(0.15, l - 0.25)),
            hsl_to_rgb(h, s, max(0.3, l - 0.12)),
            rgb,
            hsl_to_rgb(h, s, min(0.9, l + 0.12)),
            hsl_to_rgb(h, s, min(0.95, l + 0.25))
        ]
    }
    return palettes


def main():
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI color escape sequences on Windows

    parser = argparse.ArgumentParser(
        description="WCAG Contrast Checker & Palette Generator - Validate color contrast ratios for accessibility and build harmonized palettes"
    )
    parser.add_argument("colors", nargs="*", help="Foreground and Background hex colors (e.g. #0070f3 #ffffff)")
    parser.add_argument("-s", "--seed", help="Generate accessible palettes using this color as a seed")
    parser.add_argument("-t", "--text", default="Aa Bb Cc 123", help="Custom text for visual preview")
    args = parser.parse_args()

    # Case 1: Check contrast of two colors
    if len(args.colors) >= 2:
        try:
            fg_rgb = parse_hex(args.colors[0])
            bg_rgb = parse_hex(args.colors[1])
        except ValueError as e:
            print(f"{CLR_RED}Error: {e}{CLR_RESET}")
            return 1

        ratio = contrast_ratio(fg_rgb, bg_rgb)
        wcag = check_wcag_standards(ratio)

        print("=" * 60)
        print(f"{CLR_GREEN}{CLR_BOLD}WCAG accessibility contrast check{CLR_RESET}")
        print("=" * 60)
        print(f"Foreground Color:  {to_hex(fg_rgb)}  {get_ansi_swatch(fg_rgb)}")
        print(f"Background Color:  {to_hex(bg_rgb)}  {get_ansi_swatch(bg_rgb)}")
        print(f"Contrast Ratio:    {CLR_BOLD}{CLR_CYAN}{ratio:.2f} : 1{CLR_RESET}")
        print("-" * 60)

        # Print compliance
        def format_status(passed):
            return f"{CLR_GREEN}PASS{CLR_RESET}" if passed else f"{CLR_RED}FAIL{CLR_RESET}"

        print(f"WCAG 2.1 compliance results:")
        print(f"  Normal Text (AA)  [>= 4.5:1] : {format_status(wcag['AA_normal'])}")
        print(f"  Normal Text (AAA) [>= 7.0:1] : {format_status(wcag['AAA_normal'])}")
        print(f"  Large Text (AA)   [>= 3.0:1] : {format_status(wcag['AA_large'])}")
        print(f"  Large Text (AAA)  [>= 4.5:1] : {format_status(wcag['AAA_large'])}")
        print("-" * 60)

        # Visual preview
        print("Live Terminal Preview:")
        print("  " + get_ansi_bg_fg(bg_rgb, fg_rgb, args.text))
        print("=" * 60)

    # Case 2: Seed palette generation
    seed_color = args.seed
    if not seed_color and not args.colors:
        # Default fallback
        seed_color = "#3498db"

    if seed_color or len(args.colors) == 1:
        color_to_use = seed_color if seed_color else args.colors[0]
        try:
            parse_hex(color_to_use)  # Validation
        except ValueError as e:
            print(f"{CLR_RED}Error: {e}{CLR_RESET}")
            return 1

        print("=" * 60)
        print(f"{CLR_GREEN}{CLR_BOLD}ACCESSIBLE PALETTE GENERATOR (Seed: {color_to_use}){CLR_RESET}")
        print("=" * 60)

        palettes = generate_palettes(color_to_use)
        for name, swatch_list in palettes.items():
            print(f"\n{CLR_BOLD}{CLR_YELLOW}Palette: {name}{CLR_RESET}")
            print("-" * 60)
            for idx, rgb in enumerate(swatch_list):
                hex_val = to_hex(rgb)
                swatch = get_ansi_swatch(rgb)
                
                # Check accessibility against white (#fff) and dark (#111)
                white_ratio = contrast_ratio(rgb, (255, 255, 255))
                dark_ratio = contrast_ratio(rgb, (17, 17, 17))
                
                white_lbl = f"on White: {white_ratio:.1f}:1"
                dark_lbl = f"on Dark: {dark_ratio:.1f}:1"
                
                # Format labels with safety colors
                white_color = CLR_GREEN if white_ratio >= 4.5 else CLR_YELLOW if white_ratio >= 3.0 else CLR_RESET
                dark_color = CLR_GREEN if dark_ratio >= 4.5 else CLR_YELLOW if dark_ratio >= 3.0 else CLR_RESET

                print(f"  Color {idx+1}: {hex_val}  {swatch}  {white_color}{white_lbl:<18}{CLR_RESET} | {dark_color}{dark_lbl:<18}{CLR_RESET}")
        
        print("\n" + "=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
