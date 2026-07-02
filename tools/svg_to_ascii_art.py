#!/usr/bin/env python3
"""
SVG to ASCII / Unicode Vector Art Renderer
Parses vector geometric primitives (lines, circles, rectangles, polygons) from an SVG
file and renders them into crisp ASCII/Unicode character grids using Bresenham's algorithms.
"""

import sys
import os
import argparse
import xml.etree.ElementTree as ET
import math
from typing import List, Tuple, Dict, Any, Optional

# Color utilities for terminal formatting
RESET = "\033[0m"
COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "black": "\033[30m",
}

class Canvas:
    def __init__(self, width: int, height: int, unicode_mode: bool = True):
        self.width = width
        self.height = height
        self.unicode_mode = unicode_mode
        self.grid = [[" " for _ in range(width)] for _ in range(height)]
        self.color_grid = [[RESET for _ in range(width)] for _ in range(height)]

    def draw_pixel(self, x: int, y: int, char: str, color: str = RESET):
        if 0 <= x < self.width and 0 <= y < self.height:
            # Only overwrite spaces or less significant characters
            self.grid[y][x] = char
            self.color_grid[y][x] = color

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, char: Optional[str] = None, color: str = RESET):
        """Bresenham's Line Generation Algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        # Determine line character based on slope if not specified
        if char is None:
            if not self.unicode_mode:
                char = "*"
            else:
                if dx == 0:
                    char = "│"
                elif dy == 0:
                    char = "─"
                elif (x1 - x0) * (y1 - y0) > 0:
                    char = "╲"
                else:
                    char = "╱"

        while True:
            # Choose specific unicode characters for better line joints
            plot_char = char
            if self.unicode_mode and char in ["│", "─", "╲", "╱"]:
                # Simple slope detection for individual pixels
                if dx > 2 * dy:
                    plot_char = "─"
                elif dy > 2 * dx:
                    plot_char = "│"

            self.draw_pixel(x0, y0, plot_char, color)
            
            if x0 == x1 and y0 == y1:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_rect(self, x: int, y: int, w: int, h: int, color: str = RESET):
        if self.unicode_mode:
            # Draw corners
            self.draw_pixel(x, y, "┌", color)
            self.draw_pixel(x + w - 1, y, "┐", color)
            self.draw_pixel(x, y + h - 1, "└", color)
            self.draw_pixel(x + w - 1, y + h - 1, "┘", color)
            
            # Draw edges
            for px in range(x + 1, x + w - 1):
                self.draw_pixel(px, y, "─", color)
                self.draw_pixel(px, y + h - 1, "─", color)
            for py in range(y + 1, y + h - 1):
                self.draw_pixel(x, py, "│", color)
                self.draw_pixel(x + w - 1, py, "│", color)
        else:
            for px in range(x, x + w):
                self.draw_pixel(px, y, "-", color)
                self.draw_pixel(px, y + h - 1, "-", color)
            for py in range(y + 1, y + h - 1):
                self.draw_pixel(x, py, "|", color)
                self.draw_pixel(x + w - 1, py, "|", color)

    def draw_circle(self, xc: int, yc: int, r: int, color: str = RESET):
        """Bresenham's Circle Drawing Algorithm."""
        x = 0
        y = r
        d = 3 - 2 * r
        
        char = "@" if not self.unicode_mode else "o"
        
        while y >= x:
            self.draw_pixel(xc + x, yc + y, char, color)
            self.draw_pixel(xc - x, yc + y, char, color)
            self.draw_pixel(xc + x, yc - y, char, color)
            self.draw_pixel(xc - x, yc - y, char, color)
            self.draw_pixel(xc + y, yc + x, char, color)
            self.draw_pixel(xc - y, yc + x, char, color)
            self.draw_pixel(xc + y, yc - x, char, color)
            self.draw_pixel(xc - y, yc - x, char, color)
            x += 1
            if d > 0:
                y -= 1
                d = d + 4 * (x - y) + 10
            else:
                d = d + 4 * x + 6

    def render(self) -> str:
        lines = []
        for y in range(self.height):
            line_parts = []
            for x in range(self.width):
                char = self.grid[y][x]
                color = self.color_grid[y][x]
                if color != RESET and sys.stdout.isatty():
                    line_parts.append(f"{color}{char}{RESET}")
                else:
                    line_parts.append(char)
            lines.append("".join(line_parts))
        return "\n".join(lines)

def parse_points(points_str: str) -> List[Tuple[float, float]]:
    """Parse points string from polyline/polygon into a list of float tuples."""
    pairs = points_str.replace(",", " ").split()
    points = []
    for i in range(0, len(pairs), 2):
        if i + 1 < len(pairs):
            try:
                points.append((float(pairs[i]), float(pairs[i+1])))
            except ValueError:
                pass
    return points

def parse_color(style_or_attr: str) -> str:
    """Map SVG color values (hex, names) to closest ANSI terminal colors."""
    val = style_or_attr.lower().strip()
    if not val or val == "none":
        return RESET
        
    for name, code in COLORS.items():
        if name in val:
            return code
            
    # Simple hex check
    if val.startswith("#"):
        # Roughly map common colors
        # #ff0000 -> red, #00ff00 -> green, #0000ff -> blue
        r = int(val[1:3], 16) if len(val) >= 7 else 0
        g = int(val[3:5], 16) if len(val) >= 7 else 0
        b = int(val[5:7], 16) if len(val) >= 7 else 0
        
        if r > 128 and g < 100 and b < 100: return COLORS["red"]
        if g > 128 and r < 100 and b < 100: return COLORS["green"]
        if b > 128 and r < 100 and g < 100: return COLORS["blue"]
        if r > 128 and g > 128 and b < 100: return COLORS["yellow"]
        if r > 128 and b > 128 and g < 100: return COLORS["magenta"]
        if g > 128 and b > 128 and r < 100: return COLORS["cyan"]
        
    return RESET

def parse_path_commands(d_attr: str) -> List[Tuple[str, List[float]]]:
    """Extremely simplified path commands parser."""
    # Match letters and numbers/coordinates
    tokens = re.findall(r'([a-df-zS-Z])|(-?\d+\.?\d*)', d_attr)
    commands = []
    
    curr_cmd = None
    curr_args = []
    
    for tok in tokens:
        if tok[0]:  # It's a command letter
            if curr_cmd:
                commands.append((curr_cmd, curr_args))
            curr_cmd = tok[0]
            curr_args = []
        elif tok[1]:  # It's a coordinate
            curr_args.append(float(tok[1]))
            
    if curr_cmd:
        commands.append((curr_cmd, curr_args))
        
    return commands

def main():
    parser = argparse.ArgumentParser(
        description="SVG to ASCII / Unicode Vector Art Renderer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python svg_to_ascii_art.py -f my_logo.svg
  python svg_to_ascii_art.py -f file.svg -w 60 -h 30 --no-color
  python svg_to_ascii_art.py -f file.svg --ascii-only
        """
    )
    parser.add_argument("-f", "--file", type=str, help="Path to SVG file")
    parser.add_argument("-w", "--width", type=int, default=80, help="Terminal canvas width (default: 80)")
    parser.add_argument("-h", "--height", type=int, default=40, help="Terminal canvas height (default: 40)")
    parser.add_argument("--ascii-only", action="store_true", help="Restrict output to standard 7-bit ASCII characters")
    parser.add_argument("--no-color", action="store_true", help="Disable color outputs")
    parser.add_argument("--demo", action="store_true", help="Render a built-in vector demo shape")
    
    args = parser.parse_args()

    svg_content = ""
    if args.demo:
        # A simple SVG sample representing a house and sun
        svg_content = """<svg viewBox="0 0 100 100">
            <circle cx="80" cy="20" r="10" stroke="yellow" />
            <rect x="20" y="50" width="40" height="30" stroke="cyan" />
            <line x1="15" y1="50" x2="40" y2="25" stroke="magenta" />
            <line x1="40" y1="25" x2="65" y2="50" stroke="magenta" />
            <line x1="15" y1="50" x2="65" y2="50" stroke="magenta" />
        </svg>"""
    elif args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            svg_content = f.read()
    else:
        # Read from stdin
        if not sys.stdin.isatty():
            svg_content = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(0)

    if not svg_content.strip():
        print("No SVG input provided.", file=sys.stderr)
        sys.exit(1)

    try:
        # Remove namespace prefixes from tags to simplify matching
        svg_clean = re.sub(r'\sxmlns="[^"]+"', '', svg_content)
        root = ET.fromstring(svg_clean)
    except Exception as e:
        print(f"XML Parsing Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Calculate boundaries (viewBox or bounding box of elements)
    viewbox = root.attrib.get("viewBox")
    min_x, min_y, max_x, max_y = 0.0, 0.0, 100.0, 100.0
    
    if viewbox:
        parts = viewbox.split()
        if len(parts) == 4:
            min_x, min_y = float(parts[0]), float(parts[1])
            max_x, max_y = min_x + float(parts[2]), min_y + float(parts[3])
            
    # 2. Setup canvas mapping functions
    # Map vector coordinate (vx, vy) to terminal coordinate (tx, ty)
    def map_coords(vx: float, vy: float) -> Tuple[int, int]:
        tx = int(((vx - min_x) / (max_x - min_x)) * (args.width - 1))
        # Account for typical 2:1 character aspect ratio by scaling height
        ty = int(((vy - min_y) / (max_y - min_y)) * (args.height - 1))
        return tx, ty

    # 3. Process elements
    canvas = Canvas(args.width, args.height, unicode_mode=not args.ascii_only)
    
    # Traverse shapes recursively
    for el in root.iter():
        tag = el.tag.split("}")[-1] # strip namespace if still present
        
        # Color extraction
        color = RESET
        if not args.no_color:
            stroke = el.attrib.get("stroke") or ""
            fill = el.attrib.get("fill") or ""
            style = el.attrib.get("style") or ""
            color = parse_color(stroke or fill or style)

        if tag == "rect":
            x = float(el.attrib.get("x", 0))
            y = float(el.attrib.get("y", 0))
            w = float(el.attrib.get("width", 0))
            h = float(el.attrib.get("height", 0))
            
            tx0, ty0 = map_coords(x, y)
            tx1, ty1 = map_coords(x + w, y + h)
            canvas.draw_rect(tx0, ty0, max(1, tx1 - tx0), max(1, ty1 - ty0), color)
            
        elif tag == "circle":
            cx = float(el.attrib.get("cx", 0))
            cy = float(el.attrib.get("cy", 0))
            r = float(el.attrib.get("r", 0))
            
            tcx, tcy = map_coords(cx, cy)
            # radius mapping (using X scale as base)
            tr = int((r / (max_x - min_x)) * (args.width - 1))
            canvas.draw_circle(tcx, tcy, max(1, tr), color)
            
        elif tag == "line":
            x1 = float(el.attrib.get("x1", 0))
            y1 = float(el.attrib.get("y1", 0))
            x2 = float(el.attrib.get("x2", 0))
            y2 = float(el.attrib.get("y2", 0))
            
            tx0, ty0 = map_coords(x1, y1)
            tx1, ty1 = map_coords(x2, y2)
            canvas.draw_line(tx0, ty0, tx1, ty1, color=color)
            
        elif tag in ["polyline", "polygon"]:
            pts_str = el.attrib.get("points", "")
            pts = parse_points(pts_str)
            if len(pts) >= 2:
                t_pts = [map_coords(px, py) for px, py in pts]
                for i in range(len(t_pts) - 1):
                    canvas.draw_line(t_pts[i][0], t_pts[i][1], t_pts[i+1][0], t_pts[i+1][1], color=color)
                if tag == "polygon":
                    canvas.draw_line(t_pts[-1][0], t_pts[-1][1], t_pts[0][0], t_pts[0][1], color=color)
                    
        elif tag == "path":
            d = el.attrib.get("d", "")
            cmds = parse_path_commands(d)
            curr_pos = (0.0, 0.0)
            start_pos = (0.0, 0.0)
            
            for cmd, vals in cmds:
                cmd_upper = cmd.upper()
                is_relative = cmd.islower()
                
                if cmd_upper == "M": # MoveTo
                    if len(vals) >= 2:
                        x = vals[0] + (curr_pos[0] if is_relative else 0)
                        y = vals[1] + (curr_pos[1] if is_relative else 0)
                        curr_pos = (x, y)
                        start_pos = (x, y)
                        
                elif cmd_upper == "L": # LineTo
                    for i in range(0, len(vals), 2):
                        if i + 1 < len(vals):
                            x = vals[i] + (curr_pos[0] if is_relative else 0)
                            y = vals[i+1] + (curr_pos[1] if is_relative else 0)
                            tx0, ty0 = map_coords(curr_pos[0], curr_pos[1])
                            tx1, ty1 = map_coords(x, y)
                            canvas.draw_line(tx0, ty0, tx1, ty1, color=color)
                            curr_pos = (x, y)
                            
                elif cmd_upper == "H": # Horizontal LineTo
                    for val in vals:
                        x = val + (curr_pos[0] if is_relative else 0)
                        tx0, ty0 = map_coords(curr_pos[0], curr_pos[1])
                        tx1, ty1 = map_coords(x, curr_pos[1])
                        canvas.draw_line(tx0, ty0, tx1, ty1, color=color)
                        curr_pos = (x, curr_pos[1])
                        
                elif cmd_upper == "V": # Vertical LineTo
                    for val in vals:
                        y = val + (curr_pos[1] if is_relative else 0)
                        tx0, ty0 = map_coords(curr_pos[0], curr_pos[1])
                        tx1, ty1 = map_coords(curr_pos[0], y)
                        canvas.draw_line(tx0, ty0, tx1, ty1, color=color)
                        curr_pos = (curr_pos[0], y)
                        
                elif cmd_upper == "Z": # ClosePath
                    tx0, ty0 = map_coords(curr_pos[0], curr_pos[1])
                    tx1, ty1 = map_coords(start_pos[0], start_pos[1])
                    canvas.draw_line(tx0, ty0, tx1, ty1, color=color)
                    curr_pos = start_pos

    # 4. Output the rendered canvas
    print(canvas.render())

if __name__ == "__main__":
    main()
