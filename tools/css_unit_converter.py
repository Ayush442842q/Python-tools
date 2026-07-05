#!/usr/bin/env python3
"""
CSS Length Unit Converter & Transformer
---------------------------------------
Parses CSS files or length declarations and converts units (px, rem, em, %, vh, vw, pt)
based on customizable root font size (default: 16px), viewport dimensions (default: 1920x1080),
or DPI settings with inline annotations and file transformation options.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Regex for matching CSS length values
CSS_LENGTH_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9_#])(-?\d*(?:\.\d+)?)\s*(px|rem|em|vh|vw|pt|in|cm|mm)(?![a-zA-Z0-9_])',
    re.IGNORECASE
)


class CSSUnitConverter:
    def __init__(self, base_px: float = 16.0, vw_base: float = 1920.0, vh_base: float = 1080.0, dpi: float = 96.0):
        self.base_px = base_px
        self.vw_base = vw_base
        self.vh_base = vh_base
        self.dpi = dpi

    def to_px(self, val: float, unit: str) -> float:
        unit = unit.lower()
        if unit == 'px':
            return val
        elif unit in ('rem', 'em'):
            return val * self.base_px
        elif unit == 'vw':
            return (val / 100.0) * self.vw_base
        elif unit == 'vh':
            return (val / 100.0) * self.vh_base
        elif unit == 'pt':
            return val * (self.dpi / 72.0)
        elif unit == 'in':
            return val * self.dpi
        elif unit == 'cm':
            return val * (self.dpi / 2.54)
        elif unit == 'mm':
            return val * (self.dpi / 25.4)
        return val

    def from_px(self, px_val: float, target_unit: str) -> float:
        target_unit = target_unit.lower()
        if target_unit == 'px':
            return px_val
        elif target_unit in ('rem', 'em'):
            return px_val / self.base_px
        elif target_unit == 'vw':
            return (px_val / self.vw_base) * 100.0
        elif target_unit == 'vh':
            return (px_val / self.vh_base) * 100.0
        elif target_unit == 'pt':
            return px_val / (self.dpi / 72.0)
        elif target_unit == 'in':
            return px_val / self.dpi
        elif target_unit == 'cm':
            return px_val / (self.dpi / 2.54)
        elif target_unit == 'mm':
            return px_val / (self.dpi / 25.4)
        return px_val

    def convert_single(self, val: float, from_unit: str, to_unit: str) -> float:
        px = self.to_px(val, from_unit)
        return self.from_px(px, to_unit)

    def convert_css_content(self, css: str, target_unit: str = "rem", precision: int = 4) -> Tuple[str, int]:
        """Convert all length units in CSS string to target_unit."""
        count = 0

        def replace_match(match):
            nonlocal count
            num_str, unit = match.group(1), match.group(2)
            if not num_str or num_str == '-':
                return match.group(0)
            val = float(num_str)
            if val == 0:
                return "0"
            
            converted = self.convert_single(val, unit, target_unit)
            count += 1
            
            # Format number nicely
            formatted_val = f"{converted:.{precision}f}".rstrip('0').rstrip('.')
            if formatted_val == "-0":
                formatted_val = "0"
            return f"{formatted_val}{target_unit}"

        converted_css = CSS_LENGTH_PATTERN.sub(replace_match, css)
        return converted_css, count


def main():
    parser = argparse.ArgumentParser(
        description="CSS Length Unit Converter & Transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python tools/css_unit_converter.py --value 24 --from px --to rem
  python tools/css_unit_converter.py --css "font-size: 16px; margin: 32px 16px;" --to rem
  python tools/css_unit_converter.py --file style.css --to rem --out style.rem.css
"""
    )

    parser.add_argument("--value", type=float, help="Single numerical value to convert")
    parser.add_argument("--from", dest="from_unit", default="px", help="Unit of input value (default: px)")
    parser.add_argument("--to", dest="to_unit", default="rem", help="Target unit to convert to (default: rem)")
    parser.add_argument("--css", help="CSS declaration string to convert inline")
    parser.add_argument("--file", help="Path to input CSS file")
    parser.add_argument("--out", help="Path to output CSS file")
    parser.add_argument("--base", type=float, default=16.0, help="Base root font size in px (default: 16.0)")
    parser.add_argument("--vw", type=float, default=1920.0, help="Viewport width in px (default: 1920.0)")
    parser.add_argument("--vh", type=float, default=1080.0, help="Viewport height in px (default: 1080.0)")
    parser.add_argument("--precision", type=int, default=4, help="Decimal precision (default: 4)")

    args = parser.parse_args()

    converter = CSSUnitConverter(base_px=args.base, vw_base=args.vw, vh_base=args.vh)

    if args.value is not None:
        result = converter.convert_single(args.value, args.from_unit, args.to_unit)
        formatted = f"{result:.{args.precision}f}".rstrip('0').rstrip('.')
        print(f"\n{BOLD}{CYAN}=== Single Value Conversion ==={RESET}")
        print(f"Input:  {BOLD}{args.value}{args.from_unit}{RESET} (base: {args.base}px)")
        print(f"Output: {GREEN}{BOLD}{formatted}{args.to_unit}{RESET}\n")
        return

    if args.css:
        converted, count = converter.convert_css_content(args.css, target_unit=args.to_unit, precision=args.precision)
        print(f"\n{BOLD}{CYAN}=== CSS String Conversion ==={RESET}")
        print(f"Original:  {args.css}")
        print(f"Converted: {GREEN}{BOLD}{converted}{RESET} ({count} replacements made)\n")
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' not found.{RESET}")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()

        converted, count = converter.convert_css_content(content, target_unit=args.to_unit, precision=args.precision)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(converted)
            print(f"{GREEN}✓ Transformed {count} units in '{args.file}' -> '{args.out}'{RESET}")
        else:
            print(f"\n{BOLD}{CYAN}=== Transformed CSS Output ({count} units updated) ==={RESET}\n")
            print(converted)
        return

    # Demo mode if no args provided
    demo_css = """
    .card {
        width: 480px;
        padding: 24px;
        margin: 16px auto;
        font-size: 14px;
        border-radius: 8px;
    }
    """
    converted, count = converter.convert_css_content(demo_css, target_unit="rem")
    print(f"\n{BOLD}{CYAN}=== CSS Unit Converter (Demo) ==={RESET}")
    print(f"Root Font Base: {args.base}px | Target Unit: rem\n")
    print(f"{BOLD}Before:{RESET}{demo_css}")
    print(f"{BOLD}After:{RESET}{GREEN}{converted}{RESET}\n")


if __name__ == "__main__":
    main()
