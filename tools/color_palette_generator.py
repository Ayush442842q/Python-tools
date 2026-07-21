#!/usr/bin/env python3
"""
Color Palette Generator

Generate cohesive color palettes (monochromatic, analogous, complementary, triadic, tetradic)
from a seed HEX color. Visualizes the palettes in the terminal and exports them to CSS,
JSON, or Tailwind CSS configurations.
"""

import argparse
import colorsys
import os
import sys
from typing import Dict, List, Tuple

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass

# ANSI styling
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        raise ValueError("Invalid hex color format. Use #RGB or #RRGGBB.")
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)

def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"

def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    # Normalize RGB to [0, 1]
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0, s * 100.0, l * 100.0

def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    # Map back to [0, 1]
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))

def color_swatch(r: int, g: int, b: int) -> str:
    """Returns a string containing a colored block using ANSI 24-bit background color escape codes."""
    if not supports_color():
        return "[   ]"
    return f"\033[48;2;{r};{g};{b}m      \033[0m"

def print_palette(title: str, colors: List[Tuple[int, int, int]]):
    print(f"\n{COLOR_BOLD}{title}{COLOR_RESET}")
    for rgb in colors:
        hex_val = rgb_to_hex(*rgb)
        hsl_val = rgb_to_hsl(*rgb)
        swatch = color_swatch(*rgb)
        print(f"  {swatch}  {hex_val.upper()}  |  RGB: {rgb[0]:3}, {rgb[1]:3}, {rgb[2]:3}  |  HSL: {int(hsl_val[0]):3}°, {int(hsl_val[1]):3}%, {int(hsl_val[2]):3}%")

def generate_monochromatic(h: float, s: float, l: float) -> List[Tuple[int, int, int]]:
    # Generate 5 shades from light to dark
    shades = [15, 30, 45, 60, 75, 90]
    # Center around current lightness
    return [hsl_to_rgb(h, s, shade) for shade in shades]

def generate_analogous(h: float, s: float, l: float) -> List[Tuple[int, int, int]]:
    # Neighbors of Hue at -30, 0, +30 degrees
    hues = [(h - 30) % 360, h, (h + 30) % 360]
    return [hsl_to_rgb(hue, s, l) for hue in hues]

def generate_complementary(h: float, s: float, l: float) -> List[Tuple[int, int, int]]:
    # Complementary is +180 degrees
    hues = [h, (h + 180) % 360]
    return [hsl_to_rgb(hue, s, l) for hue in hues]

def generate_triadic(h: float, s: float, l: float) -> List[Tuple[int, int, int]]:
    # Three points at 0, 120, 240 degrees
    hues = [h, (h + 120) % 360, (h + 240) % 360]
    return [hsl_to_rgb(hue, s, l) for hue in hues]

def generate_tetradic(h: float, s: float, l: float) -> List[Tuple[int, int, int]]:
    # Four points at 0, 90, 180, 270 degrees (or 0, 60, 180, 240)
    hues = [h, (h + 60) % 360, (h + 180) % 360, (h + 240) % 360]
    return [hsl_to_rgb(hue, s, l) for hue in hues]

def export_css(palettes: Dict[str, List[Tuple[int, int, int]]]) -> str:
    lines = [":root {"]
    for p_name, colors in palettes.items():
        lines.append(f"  /* {p_name.capitalize()} Palette */")
        for idx, color in enumerate(colors):
            hex_val = rgb_to_hex(*color)
            lines.append(f"  --{p_name}-{idx + 1}: {hex_val};")
    lines.append("}")
    return "\n".join(lines)

def export_tailwind(palettes: Dict[str, List[Tuple[int, int, int]]]) -> str:
    lines = ["module.exports = {", "  theme: {", "    extend: {", "      colors: {"]
    for p_name, colors in palettes.items():
        lines.append(f"        {p_name}: {{")
        for idx, color in enumerate(colors):
            hex_val = rgb_to_hex(*color)
            lines.append(f"          '{idx + 1}00': '{hex_val}',")
        lines.append("        },")
    lines.append("      }")
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)

def export_json(palettes: Dict[str, List[Tuple[int, int, int]]]) -> str:
    export_data = {}
    for p_name, colors in palettes.items():
        export_data[p_name] = [rgb_to_hex(*c) for c in colors]
    import json
    return json.dumps(export_data, indent=2)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Color Palette Generator - Generate cohesive color schemes from a HEX color.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("color", help="Seed HEX color code (e.g., '#3498db' or '3498db')")
    parser.add_argument("-e", "--export", choices=['css', 'tailwind', 'json'], help="Export format to print to stdout instead of visualization")
    parser.add_argument("-o", "--output", help="Save exported content to a file")
    
    args = parser.parse_args()
    
    # Clean and parse seed color
    try:
        r, g, b = hex_to_rgb(args.color)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    h, s, l = rgb_to_hsl(r, g, b)
    
    palettes = {
        "seed": [(r, g, b)],
        "monochromatic": generate_monochromatic(h, s, l),
        "complementary": generate_complementary(h, s, l),
        "analogous": generate_analogous(h, s, l),
        "triadic": generate_triadic(h, s, l),
        "tetradic": generate_tetradic(h, s, l),
    }
    
    if args.export:
        if args.export == 'css':
            output_content = export_css(palettes)
        elif args.export == 'tailwind':
            output_content = export_tailwind(palettes)
        else:
            output_content = export_json(palettes)
            
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_content)
                print(f"[+] Palette successfully exported to {args.output}")
            except Exception as e:
                print(f"Error writing to file: {e}", file=sys.stderr)
                return 2
        else:
            print(output_content)
    else:
        # Standard visualization output
        banner = f"""{COLOR_CYAN}{COLOR_BOLD}
   ┌────────────────────────────────────────────────────────┐
   │                 COLOR PALETTE GENERATOR                │
   │           Generate & Visualize Harmonies               │
   └────────────────────────────────────────────────────────┘{COLOR_RESET}"""
        print(banner)
        
        print_palette("Seed Color", palettes["seed"])
        print_palette("Monochromatic (Shades/Tints)", palettes["monochromatic"])
        print_palette("Complementary", palettes["complementary"])
        print_palette("Analogous (Adjacent Colors)", palettes["analogous"])
        print_palette("Triadic (120 Degree Harmonies)", palettes["triadic"])
        print_palette("Tetradic (Double Complementary)", palettes["tetradic"])
        
        print("\nTo export this palette, run:")
        print(f"  python color_palette_generator.py {args.color} --export [css|tailwind|json]")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
