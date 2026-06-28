#!/usr/bin/env python3
"""
CLI Directory Size Treemap
--------------------------
Recursively computes directory sizes and renders a visual, nested ASCII/Unicode
treemap directly in the terminal, representing the relative disk usage of files and folders.

Dependencies:
    - python 3.6+

Usage:
    python tools/directory_size_treemap.py [path] [--width W] [--height H] [--depth D]
"""

import os
import sys
import argparse
from typing import List, Tuple, Dict, Any

# ANSI Escape Sequences
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_GRAY = "\033[90m"
COLOR_MAGENTA = "\033[35m"

# Palette colors to rotate for visual distinctness
BOX_COLORS = [
    "\033[38;5;39m",   # Bright blue
    "\033[38;5;76m",   # Bright green
    "\033[38;5;172m",  # Bright orange
    "\033[38;5;125m",  # Rose
    "\033[38;5;99m",   # Purple
    "\033[38;5;37m",   # Teal
    "\033[38;5;142m",  # Olive
]

def format_size(bytes_sz: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_sz < 1024.0:
            return f"{bytes_sz:.1f} {unit}"
        bytes_sz /= 1024.0
    return f"{bytes_sz:.1f} PB"

def get_directory_tree(path: str, max_depth: int, current_depth: int = 0) -> Tuple[int, Dict[str, Any]]:
    """
    Recursively scan directories to build a size tree.
    Returns: (total_size, tree_node_dict)
    """
    try:
        entries = os.scandir(path)
    except PermissionError:
        return 0, {"name": os.path.basename(path), "size": 0, "type": "dir", "children": []}
    except Exception:
        return 0, {"name": os.path.basename(path), "size": 0, "type": "dir", "children": []}

    total_size = 0
    children = []
    
    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                if current_depth < max_depth:
                    sub_size, sub_node = get_directory_tree(entry.path, max_depth, current_depth + 1)
                    if sub_size > 0:
                        total_size += sub_size
                        children.append(sub_node)
                else:
                    # Beyond max depth, just get directory size recursively without storing children
                    dir_size = get_dir_size_simple(entry.path)
                    total_size += dir_size
                    children.append({
                        "name": entry.name,
                        "size": dir_size,
                        "type": "dir",
                        "children": []
                    })
            else:
                f_size = entry.stat().st_size
                total_size += f_size
                children.append({
                    "name": entry.name,
                    "size": f_size,
                    "type": "file"
                })
        except (PermissionError, FileNotFoundError):
            continue
            
    # Sort children by size descending
    children.sort(key=lambda x: x["size"], reverse=True)
    
    node = {
        "name": os.path.basename(path) or path,
        "size": total_size,
        "type": "dir",
        "children": children
    }
    return total_size, node

def get_dir_size_simple(path: str) -> int:
    """Quickly compute directory size recursively."""
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):
                    try:
                        total += os.path.getsize(fp)
                    except FileNotFoundError:
                        pass
    except Exception:
        pass
    return total

class TreemapScreen:
    """A 2D character canvas representing the terminal screen buffer."""
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        # 2D character buffer
        self.chars = [[' ' for _ in range(w)] for _ in range(h)]
        # 2D color buffer
        self.colors = [[COLOR_RESET for _ in range(w)] for _ in range(h)]
        
    def draw_box(self, x: int, y: int, w: int, h: int, label: str, color_esc: str):
        """Draw Unicode box outline and write label inside."""
        if w < 2 or h < 2:
            return
            
        # Draw corners
        self.chars[y][x] = '┌'
        self.chars[y][x+w-1] = '┐'
        self.chars[y+h-1][x] = '└'
        self.chars[y+h-1][x+w-1] = '┘'
        
        # Draw sides
        for i in range(x + 1, x + w - 1):
            self.chars[y][i] = '─'
            self.chars[y+h-1][i] = '─'
        for j in range(y + 1, y + h - 1):
            self.chars[j][x] = '│'
            self.chars[j][x+w-1] = '│'
            
        # Color borders
        for i in range(x, x + w):
            self.colors[y][i] = color_esc
            self.colors[y+h-1][i] = color_esc
        for j in range(y, y + h):
            self.colors[j][x] = color_esc
            self.colors[j][x+w-1] = color_esc
            
        # Draw label inside
        if w > 4 and h > 2:
            # We have space inside (y+1 to y+h-2) and (x+1 to x+w-2)
            # Truncate label to fit
            max_len = w - 4
            if len(label) > max_len:
                label_show = label[:max_len-2] + ".."
            else:
                label_show = label
                
            # Centered text positioning
            text_x = x + (w - len(label_show)) // 2
            text_y = y + h // 2
            
            for idx, char in enumerate(label_show):
                self.chars[text_y][text_x + idx] = char
                self.colors[text_y][text_x + idx] = COLOR_BOLD + color_esc

    def render(self):
        """Output the buffer to stdout."""
        lines = []
        for r in range(self.h):
            row_str = ""
            current_color = COLOR_RESET
            for c in range(self.w):
                char_color = self.colors[r][c]
                if char_color != current_color:
                    row_str += char_color
                    current_color = char_color
                row_str += self.chars[r][c]
            if current_color != COLOR_RESET:
                row_str += COLOR_RESET
            lines.append(row_str)
        print("\n".join(lines))

def layout_treemap(x: int, y: int, w: int, h: int, items: List[Dict[str, Any]], screen: TreemapScreen, color_idx: int = 0):
    """
    Recursively split the screen space using a squarify-like binary partitioning.
    """
    if not items or w <= 2 or h <= 2:
        return
        
    total_size = sum(item["size"] for item in items)
    if total_size == 0:
        return
        
    # Base case: if single item, draw it
    if len(items) == 1:
        item = items[0]
        color = BOX_COLORS[color_idx % len(BOX_COLORS)]
        label = f"{item['name']} ({format_size(item['size'])})"
        screen.draw_box(x, y, w, h, label, color)
        return
        
    # Split items into two subgroups with balanced sizes
    left_items = []
    right_items = []
    left_sum = 0
    
    for item in items:
        # If we already have items and this one will push us far beyond half
        if left_sum > 0 and left_sum + item["size"]/2 > total_size / 2:
            right_items.append(item)
        else:
            left_items.append(item)
            left_sum += item["size"]
            
    if not left_items:
        left_items = items[:1]
        right_items = items[1:]
        left_sum = left_items[0]["size"]
        
    if not right_items:
        right_items = []
        
    # Determine split orientation based on cell aspect ratio (char cells are approx twice as tall as they are wide)
    # Adjusting aspect ratio so boxes look squarer
    aspect_w = w
    aspect_h = h * 2.2
    
    if aspect_w > aspect_h:
        # Split horizontally (vertical line)
        split_w = max(1, int(w * (left_sum / total_size)))
        # Keep split width within reasonable limits
        split_w = min(w - 1, split_w)
        layout_treemap(x, y, split_w, h, left_items, screen, color_idx)
        layout_treemap(x + split_w, y, w - split_w, h, right_items, screen, color_idx + 1)
    else:
        # Split vertically (horizontal line)
        split_h = max(1, int(h * (left_sum / total_size)))
        split_h = min(h - 1, split_h)
        layout_treemap(x, y, w, split_h, left_items, screen, color_idx)
        layout_treemap(x, y + split_h, w, h - split_h, right_items, screen, color_idx + 1)

def main():
    parser = argparse.ArgumentParser(
        description="CLI Directory Size Treemap: Renders a nested visual representation of disk storage."
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to analyze (default: current directory)")
    parser.add_argument("--width", type=int, default=80, help="Canvas width in characters (default: 80)")
    parser.add_argument("--height", type=int, default=24, help="Canvas height in characters (default: 24)")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Directory scan depth limit (default: 2)")
    parser.add_argument("-t", "--threshold", type=float, default=0.5, 
                        help="Size percentage threshold below which files are grouped in 'Others' (default: 0.5%%)")
    
    args = parser.parse_args()
    
    target_dir = os.path.abspath(args.path)
    if not os.path.isdir(target_dir):
        print(f"{COLOR_RED}Error: '{args.path}' is not a directory.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{COLOR_BOLD}Scanning '{target_dir}' to depth {args.depth} for space usage...{COLOR_RESET}")
    total_bytes, tree = get_directory_tree(target_dir, args.depth)
    
    if total_bytes == 0:
        print(f"{COLOR_YELLOW}Directory is empty or size could not be computed.{COLOR_RESET}")
        sys.exit(0)
        
    print(f"Total space: {COLOR_GREEN}{format_size(total_bytes)}{COLOR_RESET}")
    
    # Process children, group small items under "Others"
    children = tree.get("children", [])
    filtered_children = []
    others_bytes = 0
    others_count = 0
    
    threshold_bytes = total_bytes * (args.threshold / 100.0)
    
    for child in children:
        if child["size"] >= threshold_bytes:
            filtered_children.append(child)
        else:
            others_bytes += child["size"]
            others_count += 1
            
    if others_bytes > 0:
        filtered_children.append({
            "name": f"[Others ({others_count} items)]",
            "size": others_bytes,
            "type": "other"
        })
        
    # Render treemap
    screen = TreemapScreen(args.width, args.height)
    layout_treemap(0, 0, args.width, args.height, filtered_children, screen)
    
    print(f"\n{COLOR_BOLD}Treemap Representation:{COLOR_RESET}")
    screen.render()

if __name__ == "__main__":
    main()
