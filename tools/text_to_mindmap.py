#!/usr/bin/env python3
"""
Indented Text to Mindmap & Diagram Generator
Converts structured indented text/outlines or Markdown lists into tree structures:
1. Unicode CLI tree diagram.
2. Mermaid.js mindmap diagram code.
3. Fully styled, interactive, responsive HTML/SVG diagram.

Usage:
    python tools/text_to_mindmap.py outline.txt
    python tools/text_to_mindmap.py outline.txt --format html --output mindmap.html
"""

import argparse
import os
import re
import sys

# ANSI Escape Sequences
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

class TreeNode:
    def __init__(self, text, level):
        self.text = text.strip()
        self.level = level
        self.children = []

def parse_outline(text):
    """
    Parses hierarchical outline text (either space/tab indented or markdown list).
    Returns the root TreeNode.
    """
    lines = text.splitlines()
    nodes = []
    
    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue
        
        # Handle markdown lists like: "- Item", "* Item", "1. Item"
        list_match = re.match(r'^(\s*)([-\*\+]|\d+\.)\s+(.*)$', line)
        if list_match:
            indent = len(list_match.group(1))
            content = list_match.group(3)
        else:
            # Standard indentation
            indent_match = re.match(r'^(\s*)(.*)$', line)
            indent = len(indent_match.group(1).replace('\t', '    '))
            content = indent_match.group(2)
            
        nodes.append(TreeNode(content, indent))

    if not nodes:
        return None

    # Reconstruct the tree hierarchy
    root = TreeNode("Mindmap Root", -1)
    stack = [root]

    for node in nodes:
        while len(stack) > 1 and stack[-1].level >= node.level:
            stack.pop()
        
        stack[-1].children.append(node)
        stack.append(node)

    # If the root has only one top-level node, make that single node the true root
    if len(root.children) == 1:
        return root.children[0]
    return root

def generate_unicode_tree(node, prefix="", is_last=True, is_root=True):
    """Generates a beautiful Unicode vertical tree representation."""
    lines = []
    if is_root:
        lines.append(f"{BOLD}{CYAN}⊙ {node.text}{RESET}")
    else:
        marker = "└── " if is_last else "├── "
        lines.append(f"{prefix}{marker}{node.text}")

    child_prefix = prefix + ("    " if is_last else "│   ")
    child_count = len(node.children)
    
    for i, child in enumerate(node.children):
        lines.extend(generate_unicode_tree(
            child, 
            child_prefix, 
            is_last=(i == child_count - 1), 
            is_root=False
        ))
    return lines

def generate_mermaid_mindmap(node, indent=0):
    """Generates a Mermaid.js mindmap diagram definition."""
    lines = []
    spaces = " " * (indent + 2)
    
    # Clean text to make it Mermaid-friendly
    safe_text = node.text.replace('"', '\\"').replace('(', '[').replace(')', ']')
    
    if indent == 0:
        lines.append("mindmap")
        lines.append(f"  root(( {safe_text} ))")
    else:
        # Style children depending on level
        if not node.children:
            lines.append(f"{spaces}){safe_text}(")
        else:
            lines.append(f"{spaces}::icon(fa fa-chevron-right)\n{spaces}{safe_text}")

    for child in node.children:
        lines.extend(generate_mermaid_mindmap(child, indent + 2))
    return lines

def generate_html_mindmap(root_node):
    """Generates a standalone, beautiful HTML/CSS mindmap page with zooming, panning, and modern styling."""
    
    def serialize_node(node):
        """Recursively serialize TreeNodes to JSON."""
        return {
            "name": node.text,
            "children": [serialize_node(c) for c in node.children]
        }

    import json
    json_data = json.dumps(serialize_node(root_node), indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Mindmap: {root_node.text}</title>
    <!-- Outfit Google Font -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <!-- D3.js Library for Tree rendering -->
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #151d30;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-color: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.4);
            --line-color: #2e3b56;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            overflow: hidden;
            width: 100vw;
            height: 100vh;
        }}

        #header {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 10;
            background: rgba(21, 29, 48, 0.85);
            backdrop-filter: blur(12px);
            border: 1px solid var(--line-color);
            padding: 15px 25px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}

        #header h1 {{
            font-size: 1.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        #header p {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        #controls {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 10;
            display: flex;
            gap: 10px;
        }}

        .btn {{
            background: var(--card-bg);
            border: 1px solid var(--line-color);
            color: var(--text-primary);
            padding: 10px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }}

        .btn:hover {{
            background: var(--accent-color);
            border-color: var(--accent-color);
            box-shadow: 0 0 15px var(--accent-glow);
        }}

        #canvas {{
            width: 100%;
            height: 100%;
            cursor: grab;
        }}

        #canvas:active {{
            cursor: grabbing;
        }}

        .node circle {{
            fill: var(--card-bg);
            stroke: var(--accent-color);
            stroke-width: 3px;
            transition: all 0.3s ease;
        }}

        .node:hover circle {{
            fill: var(--accent-color);
            box-shadow: 0 0 20px var(--accent-glow);
        }}

        .node text {{
            font-size: 12px;
            font-weight: 600;
            fill: var(--text-primary);
            paint-order: stroke;
            stroke: var(--bg-color);
            stroke-width: 4px;
            stroke-linejoin: round;
        }}

        .node--leaf text {{
            font-weight: 400;
            fill: var(--text-secondary);
        }}

        .link {{
            fill: none;
            stroke: var(--line-color);
            stroke-width: 2px;
            stroke-linecap: round;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>{root_node.text}</h1>
        <p>Interactive Mindmap • Drag to pan • Scroll to zoom</p>
    </div>

    <div id="controls">
        <button class="btn" onclick="resetZoom()">Reset View</button>
    </div>

    <svg id="canvas"></svg>

    <script>
        const data = {json_data};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#canvas")
            .attr("width", width)
            .attr("height", height);

        const g = svg.append("g");

        // Set up zoom and pan
        const zoom = d3.zoom()
            .scaleExtent([0.1, 3])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});

        svg.call(zoom);

        function resetZoom() {{
            svg.transition().duration(750).call(
                zoom.transform, 
                d3.zoomIdentity.translate(width / 4, height / 2).scale(0.8)
            );
        }}

        // Setup tree layout (horizontal tree)
        const tree = d3.tree().nodeSize([40, 240]);

        const root = d3.hierarchy(data);
        tree(root);

        // Render links
        g.append("g")
            .attr("class", "links")
            .selectAll(".link")
            .data(root.links())
            .enter().append("path")
            .attr("class", "link")
            .attr("d", d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x));

        // Render nodes
        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll(".node")
            .data(root.descendants())
            .enter().append("g")
            .attr("class", d => "node " + (d.children ? "node--internal" : "node--leaf"))
            .attr("transform", d => `translate(${{d.y}}, ${{d.x}})`);

        node.append("circle")
            .attr("r", 6);

        node.append("text")
            .attr("dy", "0.31em")
            .attr("x", d => d.children ? -12 : 12)
            .attr("text-anchor", d => d.children ? "end" : "start")
            .text(d => d.data.name);

        // Initial positioning
        resetZoom();

        // Responsive resize
        window.addEventListener('resize', () => {{
            svg.attr("width", window.innerWidth).attr("height", window.innerHeight);
        }});
    </script>
</body>
</html>
"""
    return html_content

def main():
    parser = argparse.ArgumentParser(
        description="Convert structured indented outlines into clean mindmaps and Mermaid diagrams."
    )
    parser.add_argument("input", nargs="?", help="Path to input text outline file. If omitted, reads from stdin.")
    parser.add_argument(
        "-f", "--format", 
        choices=["text", "mermaid", "html"], 
        default="text",
        help="Output format: 'text' (default), 'mermaid' code, or 'html' page"
    )
    parser.add_argument("-o", "--output", help="Output file path (saves format output to file).")
    
    args = parser.parse_args()

    # Read content
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"{RED}[ERROR] File '{args.input}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(0)
        content = sys.stdin.read()

    if not content.strip():
        print(f"{RED}[ERROR] Input content is empty.{RESET}", file=sys.stderr)
        sys.exit(1)

    root_node = parse_outline(content)
    if not root_node:
        print(f"{RED}[ERROR] Could not parse outline tree.{RESET}", file=sys.stderr)
        sys.exit(1)

    # Generate format output
    if args.format == "text":
        result = "\n".join(generate_unicode_tree(root_node))
    elif args.format == "mermaid":
        result = "\n".join(generate_mermaid_mindmap(root_node))
    elif args.format == "html":
        result = generate_html_mindmap(root_node)

    # Save or print
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"{GREEN}[PASS] Mindmap successfully written to: {args.output}{RESET}")
        except Exception as e:
            print(f"{RED}[ERROR] Failed to save output: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        print(result)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(1)
