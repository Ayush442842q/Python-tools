#!/usr/bin/env python3
"""
Text-to-ASCII Flowchart Generator
Parses a simple DSL of nodes and connectors to generate clean, aligned
flowchart diagrams in the console using ASCII/Unicode box-drawing characters.
"""

import os
import sys
import re
import argparse

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
    except Exception:
        pass

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


class Canvas:
    """A character cell buffer for drawing text-based diagrams."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[' ' for _ in range(width)] for _ in range(height)]
        
    def set(self, x, y, char):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = char
            
    def draw_str(self, x, y, string):
        for i, char in enumerate(string):
            self.set(x + i, y, char)
            
    def draw_box(self, x1, y1, x2, y2, style='unicode'):
        if style == 'double':
            tl, tr, bl, br, h, v = '╔', '╗', '╚', '╝', '═', '║'
        elif style == 'ascii':
            tl, tr, bl, br, h, v = '+', '+', '+', '+', '-', '|'
        else: # unicode single
            tl, tr, bl, br, h, v = '┌', '┐', '└', '┘', '─', '│'
            
        for x in range(x1 + 1, x2):
            self.set(x, y1, h)
            self.set(x, y2, h)
        for y in range(y1 + 1, y2):
            self.set(x1, y, v)
            self.set(x2, y, v)
        self.set(x1, y1, tl)
        self.set(x2, y1, tr)
        self.set(x1, y2, bl)
        self.set(x2, y2, br)

    def draw_connector(self, x1, y1, x2, y2, style='unicode'):
        if style == 'double':
            h, v = '═', '║'
            c_rd, c_ur, c_dr, c_ru = '╗', '╚', '╔', '╝'
        elif style == 'ascii':
            h, v = '-', '|'
            c_rd, c_ur, c_dr, c_ru = '+', '+', '+', '+'
        else: # unicode single
            h, v = '─', '│'
            c_rd, c_ur, c_dr, c_ru = '┐', '└', '┌', '┘'
            
        if y1 == y2:
            # Straight horizontal
            dx = 1 if x2 > x1 else -1
            for x in range(x1, x2, dx):
                self.set(x, y1, h)
        elif x1 == x2:
            # Straight vertical
            dy = 1 if y2 > y1 else -1
            for y in range(y1, y2, dy):
                self.set(x1, y, v)
        else:
            # Orthogonal step-route: horizontal to mid-point, vertical, then horizontal
            mid_x = (x1 + x2) // 2
            
            # 1. Horizontal from start to mid-point
            dx = 1 if mid_x > x1 else -1
            for x in range(x1, mid_x, dx):
                self.set(x, y1, h)
            
            # 2. Corner at (mid_x, y1)
            if y2 > y1:
                corner_y1 = c_rd if mid_x > x1 else '┐'
            else:
                corner_y1 = c_ru if mid_x > x1 else '┘'
            self.set(mid_x, y1, corner_y1)
            
            # 3. Vertical from y1 to y2
            dy = 1 if y2 > y1 else -1
            for y in range(y1 + dy, y2, dy):
                self.set(mid_x, y, v)
                
            # 4. Corner at (mid_x, y2)
            if y2 > y1:
                corner_y2 = c_dr if x2 > mid_x else '┌'
            else:
                corner_y2 = c_ur if x2 > mid_x else '└'
            self.set(mid_x, y2, corner_y2)
            
            # 5. Horizontal from mid-point to end-point
            dx = 1 if x2 > mid_x else -1
            for x in range(mid_x + dx, x2, dx):
                self.set(x, y2, h)
                
        # Draw Arrow Head
        if x2 > x1:
            self.set(x2, y2, '►' if style != 'ascii' else '>')
        elif x2 < x1:
            self.set(x2, y2, '◄' if style != 'ascii' else '<')
        elif y2 > y1:
            self.set(x2, y2, '▼' if style != 'ascii' else 'v')
        else:
            self.set(x2, y2, '▲' if style != 'ascii' else '^')

    def render(self):
        return "\n".join("".join(row) for row in self.grid)

def parse_dsl(dsl_text):
    """Parses a diagram DSL string into a dictionary of nodes and list of edges."""
    nodes = {}
    edges = []
    
    # Split input by lines
    lines = [line.strip() for line in dsl_text.splitlines() if line.strip()]
    
    for line in lines:
        # Check if it defines a chain of connectors: NodeA -> NodeB -> NodeC
        parts = line.split("->")
        prev_node = None
        for part in parts:
            part = part.strip()
            # Match "NodeName [Label Content]" or just "NodeName"
            match = re.match(r'^(\w+)(?:\s*\[(.*?)\])?$', part)
            if not match:
                raise ValueError(f"Syntax Error: Invalid Node definition '{part}'")
            
            node_name = match.group(1)
            node_label = match.group(2)
            
            if node_label is not None:
                nodes[node_name] = node_label
            elif node_name not in nodes:
                nodes[node_name] = node_name # Fallback label is its name
                
            if prev_node:
                edges.append((prev_node, node_name))
            prev_node = node_name
            
    return nodes, edges

def layout_graph(nodes, edges):
    """Calculates column and row indexes for nodes to build a grid layout."""
    # Build adjacency list
    adj = {n: [] for n in nodes}
    in_degree = {n: 0 for n in nodes}
    for u, v in edges:
        if u in adj and v in adj:
            adj[u].append(v)
            in_degree[v] += 1
            
    # Find sources
    sources = [n for n in nodes if in_degree[n] == 0]
    if not sources:
        sources = [sorted(nodes.keys())[0]] if nodes else []
        
    # BFS to assign columns (levels)
    col_map = {}
    queue = list(sources)
    for s in sources:
        col_map[s] = 0
        
    while queue:
        curr = queue.pop(0)
        curr_col = col_map[curr]
        for neighbor in adj[curr]:
            new_col = max(col_map.get(neighbor, 0), curr_col + 1)
            col_map[neighbor] = new_col
            queue.append(neighbor)
            
    # Assign default 0 for isolated nodes
    for n in nodes:
        if n not in col_map:
            col_map[n] = 0
            
    # Row assignments: stack nodes sequentially per column
    cols = {}
    for n, col in col_map.items():
        cols.setdefault(col, []).append(n)
        
    row_map = {}
    for col, nodes_in_col in cols.items():
        nodes_in_col.sort()
        for idx, n in enumerate(nodes_in_col):
            row_map[n] = idx
            
    return col_map, row_map

def generate_flowchart(dsl_text, style='unicode'):
    """Main function to parse and draw the text flowchart."""
    nodes, edges = parse_dsl(dsl_text)
    if not nodes:
        return "Empty diagram definition."
        
    col_map, row_map = layout_graph(nodes, edges)
    
    max_col = max(col_map.values()) if col_map else 0
    max_row = max(row_map.values()) if row_map else 0
    
    # Calculate column widths dynamically based on max label size in that column
    col_widths = {}
    for col in range(max_col + 1):
        nodes_in_col = [n for n in nodes if col_map[n] == col]
        if nodes_in_col:
            max_label_len = max(len(nodes[n]) for n in nodes_in_col)
            col_widths[col] = max_label_len + 4 # Padding for margins
        else:
            col_widths[col] = 10
            
    # Calculate grid layouts coordinates
    col_gap = 6
    row_gap = 2
    row_height = 3
    
    col_starts = {}
    curr_x = 2
    for col in range(max_col + 1):
        col_starts[col] = curr_x
        curr_x += col_widths[col] + col_gap
        
    row_starts = {}
    for row in range(max_row + 1):
        row_starts[row] = 1 + row * (row_height + row_gap)
        
    canvas_w = curr_x + 2
    canvas_h = 1 + (max_row + 1) * (row_height + row_gap) + 1
    
    canvas = Canvas(canvas_w, canvas_h)
    
    # Coordinates mapping for drawing lines
    node_coords = {} # name -> (x1, y1, x2, y2, cx, cy)
    
    # Draw Nodes
    for name, label in nodes.items():
        col = col_map[name]
        row = row_map[name]
        
        x1 = col_starts[col]
        x2 = x1 + col_widths[col] - 1
        y1 = row_starts[row]
        y2 = y1 + row_height - 1
        
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        node_coords[name] = (x1, y1, x2, y2, cx, cy)
        
        # Draw the box
        canvas.draw_box(x1, y1, x2, y2, style)
        
        # Center the label inside the box
        lbl_x = x1 + (col_widths[col] - len(label)) // 2
        lbl_y = y1 + 1
        canvas.draw_str(lbl_x, lbl_y, label)
        
    # Draw Edges
    for u, v in edges:
        if u not in node_coords or v not in node_coords:
            continue
            
        x1_u, y1_u, x2_u, y2_u, cx_u, cy_u = node_coords[u]
        x1_v, y1_v, x2_v, y2_v, cx_v, cy_v = node_coords[v]
        
        col_u, col_v = col_map[u], col_map[v]
        row_u, row_v = row_map[u], row_map[v]
        
        # Route from border to border
        if col_u < col_v:
            # left to right
            start_x, start_y = x2_u + 1, cy_u
            end_x, end_y = x1_v - 1, cy_v
        elif col_u > col_v:
            # right to left
            start_x, start_y = x1_u - 1, cy_u
            end_x, end_y = x2_v + 1, cy_v
        else: # col_u == col_v
            if row_u < row_v:
                # top to bottom
                start_x, start_y = cx_u, y2_u + 1
                end_x, end_y = cx_v, y1_v - 1
            else:
                # bottom to top
                start_x, start_y = cx_u, y1_u - 1
                end_x, end_y = cx_v, y2_v + 1
                
        canvas.draw_connector(start_x, start_y, end_x, end_y, style)
        
    return canvas.render()

def main():
    parser = argparse.ArgumentParser(
        description="Text-to-ASCII Flowchart Generator: Render clean console flowchart diagrams from text DSLs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
DSL Syntax:
  NodeName [Display Label] -> AnotherNode [Another Label] -> NodeC
  NodeB -> NodeD [Error Handle]

Examples:
  python tools/ascii_flowchart_generator.py --diagram "A [Start] -> B [Process Data] -> C [Finish]"
  python tools/ascii_flowchart_generator.py --file workflow.txt --style double
"""
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--diagram", "-d", help="Inline flowchart DSL string description")
    group.add_argument("--file", "-f", help="Path to input text file containing flowchart DSL description")
    parser.add_argument("--style", "-s", choices=["unicode", "double", "ascii"], default="unicode",
                        help="Box drawing boundary style (default: unicode)")

    args = parser.parse_args()

    try:
        if args.diagram:
            dsl_text = args.diagram
        else:
            if not os.path.exists(args.file):
                print(f"\033[31mError: File '{args.file}' not found.\033[0m", file=sys.stderr)
                sys.exit(1)
            with open(args.file, 'r', encoding='utf-8') as f:
                dsl_text = f.read()

        flowchart = generate_flowchart(dsl_text, style=args.style)
        print(flowchart)
        
    except Exception as e:
        print(f"\033[31mError generating flowchart: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
