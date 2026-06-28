#!/usr/bin/env python3
"""
ASCII Venn Diagram Generator - Render overlapping sets in the terminal

This tool takes 2 or 3 sets of elements, calculates their mathematical relations
(intersections, unions, and relative complements), and draws a text-based Venn diagram 
in the terminal with regional counts. It also lists the specific elements in each region.

Usage:
    python tools/ascii_venn_diagram.py --setA "apple,banana,orange,grape" --setB "orange,grape,pear,peach"
    python tools/ascii_venn_diagram.py -a "1,2,3,4" -b "3,4,5,6" -c "4,5,6,7"
"""

import argparse
import sys
from typing import Set, List, Dict, Any

def parse_set(set_str: str) -> Set[str]:
    """Parses a comma-separated string into a set of trimmed strings."""
    if not set_str:
        return set()
    return {item.strip() for item in set_str.split(',') if item.strip()}

def render_2_sets(a_only: int, b_only: int, ab_both: int) -> str:
    """Renders a 2-circle Venn diagram in ASCII."""
    # A grid of 13 lines x 56 characters
    width = 56
    height = 13
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Draw Circle A (left) and Circle B (right)
    # Equations: (x-cx)^2/rx^2 + (y-cy)^2/ry^2 = 1
    # Center A: (20, 6), rx=14, ry=5
    # Center B: (35, 6), rx=14, ry=5
    cx_a, cy_a, rx_a, ry_a = 20, 6, 14, 5
    cx_b, cy_b, rx_b, ry_b = 35, 6, 14, 5

    for y in range(height):
        for x in range(width):
            val_a = ((x - cx_a) ** 2) / (rx_a ** 2) + ((y - cy_a) ** 2) / (ry_a ** 2)
            val_b = ((x - cx_b) ** 2) / (rx_b ** 2) + ((y - cy_b) ** 2) / (ry_b ** 2)
            
            # Boundary thresholds
            bound_a = 0.9 <= val_a <= 1.1
            bound_b = 0.9 <= val_b <= 1.1
            
            if bound_a and bound_b:
                grid[y][x] = "X"
            elif bound_a:
                grid[y][x] = "A"
            elif bound_b:
                grid[y][x] = "B"

    # Inject labels and counts
    def inject_text(text: str, cx: int, cy: int):
        start_x = cx - len(text) // 2
        for idx, char in enumerate(text):
            if 0 <= start_x + idx < width:
                grid[cy][start_x + idx] = char

    inject_text("Only A", 12, 5)
    inject_text(f"({a_only})", 12, 6)
    
    inject_text("A & B", 27, 5)
    inject_text(f"({ab_both})", 27, 6)
    
    inject_text("Only B", 43, 5)
    inject_text(f"({b_only})", 43, 6)

    # Convert grid to string
    return "\n".join("".join(row) for row in grid)

def render_3_sets(a_only: int, b_only: int, c_only: int, 
                  ab: int, ac: int, bc: int, abc: int) -> str:
    """Renders a 3-circle Venn diagram in ASCII."""
    # A grid of 20 lines x 60 characters
    width = 60
    height = 20
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Circle A (top): Center (30, 6), rx=14, ry=5
    # Circle B (bottom-left): Center (21, 12), rx=14, ry=5
    # Circle C (bottom-right): Center (39, 12), rx=14, ry=5
    cx_a, cy_a, rx_a, ry_a = 30, 6, 14, 5
    cx_b, cy_b, rx_b, ry_b = 21, 12, 14, 5
    cx_c, cy_c, rx_c, ry_c = 39, 12, 14, 5

    for y in range(height):
        for x in range(width):
            val_a = ((x - cx_a) ** 2) / (rx_a ** 2) + ((y - cy_a) ** 2) / (ry_a ** 2)
            val_b = ((x - cx_b) ** 2) / (rx_b ** 2) + ((y - cy_b) ** 2) / (ry_b ** 2)
            val_c = ((x - cx_c) ** 2) / (rx_c ** 2) + ((y - cy_c) ** 2) / (ry_c ** 2)
            
            bound_a = 0.9 <= val_a <= 1.1
            bound_b = 0.9 <= val_b <= 1.1
            bound_c = 0.9 <= val_c <= 1.1

            # Render boundaries
            if bound_a:
                grid[y][x] = "A"
            elif bound_b:
                grid[y][x] = "B"
            elif bound_c:
                grid[y][x] = "C"

    # Inject labels and counts
    def inject_text(text: str, cx: int, cy: int):
        start_x = cx - len(text) // 2
        for idx, char in enumerate(text):
            if 0 <= start_x + idx < width:
                grid[cy][start_x + idx] = char

    # Only regions
    inject_text(f"Only A ({a_only})", 30, 4)
    inject_text(f"Only B ({b_only})", 13, 13)
    inject_text(f"Only C ({c_only})", 47, 13)
    
    # Dual intersections
    inject_text(f"A&B ({ab})", 20, 8)
    inject_text(f"A&C ({ac})", 40, 8)
    inject_text(f"B&C ({bc})", 30, 15)
    
    # Triple intersection
    inject_text(f"All ({abc})", 30, 10)

    # Convert grid to string
    return "\n".join("".join(row) for row in grid)

def print_element_list(title: str, elements: Set[str], color_code: str = "\033[92m"):
    """Formats and prints elements of a set."""
    elem_str = ", ".join(sorted(list(elements))) if elements else "None"
    count = len(elements)
    print(f"{color_code}{title:<25} ({count}):\033[0m {elem_str}")

def main():
    parser = argparse.ArgumentParser(
        description="Calculate set relationships and render a beautiful ASCII Venn diagram in the terminal."
    )
    parser.add_argument('-a', '--setA', required=True, help='Comma-separated values for Set A')
    parser.add_argument('-b', '--setB', required=True, help='Comma-separated values for Set B')
    parser.add_argument('-c', '--setC', default=None, help='Optional comma-separated values for Set C')
    parser.add_argument('--nameA', default='A', help='Label name for Set A')
    parser.add_argument('--nameB', default='B', help='Label name for Set B')
    parser.add_argument('--nameC', default='C', help='Label name for Set C')

    args = parser.parse_args()

    set_a = parse_set(args.setA)
    set_b = parse_set(args.setB)
    
    if args.setC is None:
        # 2-set Venn diagram
        only_a = set_a - set_b
        only_b = set_b - set_a
        both_ab = set_a & set_b
        union_ab = set_a | set_b
        
        print("\n\033[95m================== VENN DIAGRAM (2 SETS) ==================\033[0m")
        diagram = render_2_sets(len(only_a), len(only_b), len(both_ab))
        print(diagram)
        print("\033[95m===========================================================\033[0m\n")
        
        print_element_list(f"Only Set {args.nameA}", only_a, "\033[94m")
        print_element_list(f"Only Set {args.nameB}", only_b, "\033[96m")
        print_element_list(f"Intersection ({args.nameA} & {args.nameB})", both_ab, "\033[92m")
        print_element_list("Union (All Elements)", union_ab, "\033[93m")
        
    else:
        # 3-set Venn diagram
        set_c = parse_set(args.setC)
        
        only_a = set_a - set_b - set_c
        only_b = set_b - set_a - set_c
        only_c = set_c - set_a - set_b
        
        ab_only = (set_a & set_b) - set_c
        ac_only = (set_a & set_c) - set_b
        bc_only = (set_b & set_c) - set_a
        
        abc_all = set_a & set_b & set_c
        union_all = set_a | set_b | set_c
        
        print("\n\033[95m===================== VENN DIAGRAM (3 SETS) =====================\033[0m")
        diagram = render_3_sets(
            len(only_a), len(only_b), len(only_c),
            len(ab_only), len(ac_only), len(bc_only), len(abc_all)
        )
        print(diagram)
        print("\033[95m=================================================================\033[0m\n")
        
        print_element_list(f"Only Set {args.nameA}", only_a, "\033[94m")
        print_element_list(f"Only Set {args.nameB}", only_b, "\033[96m")
        print_element_list(f"Only Set {args.nameC}", only_c, "\033[95m")
        print_element_list(f"Intersection {args.nameA} & {args.nameB} (no {args.nameC})", ab_only, "\033[92m")
        print_element_list(f"Intersection {args.nameA} & {args.nameC} (no {args.nameB})", ac_only, "\033[92m")
        print_element_list(f"Intersection {args.nameB} & {args.nameC} (no {args.nameA})", bc_only, "\033[92m")
        print_element_list(f"All Sets ({args.nameA} & {args.nameB} & {args.nameC})", abc_all, "\033[93m")
        print_element_list("Union (All Elements)", union_all, "\033[97m")

if __name__ == '__main__':
    main()
