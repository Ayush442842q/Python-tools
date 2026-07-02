#!/usr/bin/env python3
"""
ascii_to_svg - Convert ASCII/Unicode Art and Flowcharts to Vector SVGs

This tool takes a text file containing ASCII or Unicode art (e.g. diagrams, flowcharts,
or Unicode trees) and renders it into a beautifully styled SVG file. It supports
multiple themes (Dracula, Nord, Cyberpunk, Monokai, Matrix, Light), glowing filters,
custom monospace fonts, and a macOS-style window chrome decoration.

Usage:
    python tools/ascii_to_svg.py <input_file> -o <output.svg> [options]

Example:
    python tools/ascii_to_svg.py tools/IDEA.md -o idea_diagram.svg --theme cyberpunk --chrome
"""

import argparse
import sys
from typing import Dict, Any, List

# Premium color themes
THEMES: Dict[str, Dict[str, str]] = {
    "dracula": {
        "bg": "#282a36",
        "text": "#f8f8f2",
        "chrome_bg": "#191a21",
        "chrome_border": "#44475a",
        "glow": "rgba(189, 147, 249, 0.4)",
    },
    "nord": {
        "bg": "#2e3440",
        "text": "#d8dee9",
        "chrome_bg": "#242933",
        "chrome_border": "#3b4252",
        "glow": "rgba(136, 192, 208, 0.3)",
    },
    "cyberpunk": {
        "bg": "#0d0e15",
        "text": "#00f0ff",
        "chrome_bg": "#1a0826",
        "chrome_border": "#ff007f",
        "glow": "rgba(255, 0, 127, 0.6)",
    },
    "matrix": {
        "bg": "#000000",
        "text": "#00ff00",
        "chrome_bg": "#050f05",
        "chrome_border": "#003300",
        "glow": "rgba(0, 255, 0, 0.5)",
    },
    "monokai": {
        "bg": "#272822",
        "text": "#f8f8f2",
        "chrome_bg": "#1e1f1c",
        "chrome_border": "#3e3d32",
        "glow": "rgba(166, 226, 46, 0.3)",
    },
    "light": {
        "bg": "#ffffff",
        "text": "#1a1a1a",
        "chrome_bg": "#f0f0f0",
        "chrome_border": "#e0e0e0",
        "glow": "rgba(0, 0, 0, 0.1)",
    }
}


def escape_html(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def generate_svg(
    lines: List[str],
    theme_name: str = "dracula",
    font_family: str = "Courier New, Courier, monospace",
    font_size: int = 14,
    line_spacing: float = 1.3,
    chrome: bool = False,
    title: str = "Terminal",
    glow: bool = False
) -> str:
    """Generate SVG document content from lines of text."""
    theme = THEMES.get(theme_name.lower(), THEMES["dracula"])
    
    # Calculate dimensions
    max_cols = max(len(line) for line in lines) if lines else 0
    num_lines = len(lines)
    
    # Grid estimation (approximate pixel sizes for characters)
    char_width = font_size * 0.6
    char_height = font_size * line_spacing
    
    padding_x = 24
    padding_y = 24
    header_height = 40 if chrome else 0
    
    content_width = max_cols * char_width
    content_height = num_lines * char_height
    
    width = content_width + (padding_x * 2)
    height = content_height + (padding_y * 2) + header_height
    
    # Enforce minimum sizes
    width = max(width, 300)
    height = max(height, 100)
    
    # Start SVG content
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">')
    
    # Inject styles and filters
    svg.append('  <defs>')
    if glow:
        svg.append('    <filter id="glow-effect" x="-20%" y="-20%" width="140%" height="140%">')
        svg.append(f'      <feGaussianBlur stdDeviation="3" result="blur" />')
        svg.append('      <feMerge>')
        svg.append('        <feMergeNode in="blur" />')
        svg.append('        <feMergeNode in="SourceGraphic" />')
        svg.append('      </feMerge>')
        svg.append('    </filter>')
    svg.append('  </defs>')
    
    # Background rect
    svg.append(f'  <rect width="100%" height="100%" fill="{theme["bg"]}" rx="8" ry="8" />')
    
    # Chrome window header
    if chrome:
        # Header background
        svg.append(f'  <path d="M 0 8 A 8 8 0 0 1 8 0 L {width - 8:.0f} 0 A 8 8 0 0 1 {width:.0f} 8 L {width:.0f} 40 L 0 40 Z" fill="{theme["chrome_bg"]}" stroke="{theme["chrome_border"]}" stroke-width="1" />')
        
        # Chrome control dots (macOS style)
        svg.append('  <circle cx="20" cy="20" r="6" fill="#ff5f56" />')
        svg.append('  <circle cx="40" cy="20" r="6" fill="#ffbd2e" />')
        svg.append('  <circle cx="60" cy="20" r="6" fill="#27c93f" />')
        
        # Title text
        svg.append(f'  <text x="{width/2:.0f}" y="25" fill="{theme["text"]}" font-family="{font_family}" font-size="13" font-weight="bold" text-anchor="middle" opacity="0.8">{escape_html(title)}</text>')
        
    # Text block wrapper
    text_y_start = padding_y + header_height + (font_size * 0.8)
    glow_attr = ' filter="url(#glow-effect)"' if glow else ''
    
    svg.append(f'  <text x="{padding_x}" y="{text_y_start}" fill="{theme["text"]}" font-family="{font_family}" font-size="{font_size}" xml:space="preserve"{glow_attr}>')
    
    for i, line in enumerate(lines):
        escaped_line = escape_html(line)
        dy = 0 if i == 0 else char_height
        svg.append(f'    <tspan x="{padding_x}" dy="{dy:.2f}">{escaped_line}</tspan>')
        
    svg.append('  </text>')
    svg.append('</svg>')
    
    return "\n".join(svg)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ASCII/Unicode Art to styled SVG Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", nargs="?", help="Text file containing ASCII/Unicode art")
    parser.add_argument("-o", "--output", required=True, help="Path to save the generated SVG file")
    parser.add_argument("--theme", default="dracula", choices=list(THEMES.keys()), help="Color theme for the output")
    parser.add_argument("--font", default="Courier New, Courier, monospace", help="Font family to use")
    parser.add_argument("--size", type=int, default=14, help="Font size in pixels")
    parser.add_argument("--spacing", type=float, default=1.3, help="Line spacing multiplier")
    parser.add_argument("--chrome", action="store_true", help="Add macOS style terminal window frame")
    parser.add_argument("--title", default="Terminal Diagram", help="Title for the terminal chrome header")
    parser.add_argument("--glow", action="store_true", help="Apply retro glow effect to the text")
    
    args = parser.parse_args()
    
    input_file = args.input_file
    if not input_file:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            parser.print_help()
            return 1
    else:
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"[!] Error reading input file: {e}", file=sys.stderr)
            return 1
            
    lines = content.splitlines()
    
    # Generate SVG
    svg_content = generate_svg(
        lines,
        theme_name=args.theme,
        font_family=args.font,
        font_size=args.size,
        line_spacing=args.spacing,
        chrome=args.chrome,
        title=args.title,
        glow=args.glow
    )
    
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"[+] Successfully converted to SVG and saved to: {args.output}")
        return 0
    except Exception as e:
        print(f"[!] Error writing output SVG file: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
