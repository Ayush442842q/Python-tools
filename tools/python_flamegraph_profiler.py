#!/usr/bin/env python3
"""
python_flamegraph_profiler.py - Interactive SVG Flamegraph Profiler

Profiles Python code execution (via tracing) and outputs a self-contained,
interactive SVG flamegraph that can be opened in any web browser.
Allows zooming, searching, and hovering over frames to inspect timing.

Requirements:
    - Python 3.6+ (No external dependencies)
"""

import sys
import os
import time
import argparse
import traceback
import json
import random

class FlameGraphProfiler:
    def __init__(self, ignore_paths=None):
        self.stack = []
        self.call_tree = {} # Path (tuple of frames) -> [time_spent, call_count]
        self.start_times = {} # Frame path -> timestamp
        self.total_time = 0
        self.profiler_file = os.path.abspath(__file__)
        self.ignore_paths = set(os.path.abspath(p) for p in (ignore_paths or []))
        self.ignore_paths.add(self.profiler_file)

    def trace_dispatch(self, frame, event, arg):
        # Ignore calls from this profiler script
        filename = os.path.abspath(frame.f_code.co_filename)
        if filename in self.ignore_paths or "importlib" in filename:
            return self.trace_dispatch

        co = frame.f_code
        func_name = co.co_name
        # Format frame name: class/module.func (filename:line)
        module_name = frame.f_globals.get('__name__', '__main__')
        
        # Try to identify class name if in a method
        if 'self' in frame.f_locals:
            class_name = frame.f_locals['self'].__class__.__name__
            frame_id = f"{module_name}.{class_name}.{func_name}"
        else:
            frame_id = f"{module_name}.{func_name}"
            
        frame_id += f" ({os.path.basename(filename)}:{co.co_firstlineno})"

        if event == 'call':
            self.stack.append(frame_id)
            path = tuple(self.stack)
            self.start_times[path] = time.perf_counter()
        elif event == 'return':
            path = tuple(self.stack)
            if path in self.start_times:
                start = self.start_times.pop(path)
                elapsed = time.perf_counter() - start
                
                # Update call tree
                if path not in self.call_tree:
                    self.call_tree[path] = [0.0, 0]
                self.call_tree[path][0] += elapsed
                self.call_tree[path][1] += 1
                
            if self.stack:
                self.stack.pop()
                
        return self.trace_dispatch

    def start(self):
        self.stack = ["all"]
        self.start_times = {("all",): time.perf_counter()}
        sys.setprofile(self.trace_dispatch)

    def stop(self):
        sys.setprofile(None)
        path = ("all",)
        if path in self.start_times:
            start = self.start_times.pop(path)
            self.total_time = time.perf_counter() - start
            self.call_tree[path] = [self.total_time, 1]

def build_hierarchy(call_tree):
    """Converts the flat call_tree dict into a nested dict structure."""
    root = {"name": "all", "value": 0.0, "count": 1, "children": {}}
    
    # Sort paths by length so we build parents before children
    sorted_paths = sorted(call_tree.keys(), key=len)
    
    for path in sorted_paths:
        if path == ("all",):
            root["value"] = call_tree[path][0]
            root["count"] = call_tree[path][1]
            continue
            
        # Navigate down the tree
        current = root
        for i, frame in enumerate(path):
            if i == 0:
                continue # Skip "all" root
                
            if frame not in current["children"]:
                current["children"][frame] = {
                    "name": frame,
                    "value": 0.0,
                    "count": 0,
                    "children": {}
                }
            current = current["children"][frame]
            
        current["value"] = call_tree[path][0]
        current["count"] = call_tree[path][1]

    # Convert children dictionaries to lists recursively
    def dict_to_list(node):
        node["children"] = list(node["children"].values())
        for child in node["children"]:
            dict_to_list(child)
    dict_to_list(root)
    
    return root

def assign_positions(node, x=0.0, width=100.0, depth=0):
    """Computes x, width, and depth coordinates for each flame node."""
    node["x"] = x
    node["width"] = width
    node["depth"] = depth
    
    # Sort children by value to keep it neat
    children = sorted(node["children"], key=lambda c: c["value"], reverse=True)
    
    current_x = x
    # Only distribute children if parent has width and value
    if node["value"] > 0 and width > 0:
        for child in children:
            child_w = (child["value"] / node["value"]) * width
            assign_positions(child, current_x, child_w, depth + 1)
            current_x += child_w

def collect_flat_nodes(node, result_list):
    """Flattens the tree into a list of nodes for easier SVG rendering."""
    result_list.append(node)
    for child in node["children"]:
        collect_flat_nodes(child, result_list)

def generate_flamegraph_svg(tree_root, total_time, output_path):
    """Generates an interactive, standalone SVG flamegraph."""
    flat_nodes = []
    collect_flat_nodes(tree_root, flat_nodes)
    
    max_depth = max(node["depth"] for node in flat_nodes) if flat_nodes else 0
    
    # SVG Layout Constants
    row_height = 24
    width = 1200
    padding_bottom = 60
    header_height = 80
    height = (max_depth + 1) * row_height + header_height + padding_bottom
    
    # Generate warm, fire-like colors based on name hash (for consistency)
    def get_color(name):
        if name == "all":
            return "hsl(20, 80%, 40%)"
        random.seed(hash(name))
        h = random.randint(10, 45) # Red-yellow range
        s = random.randint(65, 95)
        l = random.randint(45, 75)
        return f"hsl({h}, {s}%, {l}%)"

    nodes_json = []
    for i, node in enumerate(flat_nodes):
        nodes_json.append({
            "id": i,
            "name": node["name"],
            "value": node["value"],
            "count": node["count"],
            "depth": node["depth"],
            "x_pct": node["x"],
            "w_pct": node["width"],
            "color": get_color(node["name"])
        })

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; user-select: none;">
    <defs>
        <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#818cf8" />
        </linearGradient>
        <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
            <shadowOffset dx="0" dy="2"/>
            <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#000" flood-opacity="0.3"/>
        </filter>
    </defs>

    <!-- Header Panel -->
    <rect width="{width}" height="{header_height}" fill="#1e293b" />
    <text x="20" y="35" font-size="20" font-weight="bold" fill="url(#headerGrad)">Python Flamegraph Profiler</text>
    <text x="20" y="60" font-size="12" fill="#94a3b8">Total Execution Time: {total_time:.4f}s | Click to zoom. Double-click root to reset zoom.</text>
    
    <!-- Search Box in SVG -->
    <g id="searchGroup" transform="translate({width - 320}, 20)">
        <rect width="300" height="35" rx="6" fill="#0f172a" stroke="#475569" stroke-width="1"/>
        <text x="12" y="22" font-size="12" fill="#64748b" id="searchPlaceholder">Search functions...</text>
        <foreignObject x="10" y="2" width="280" height="30">
            <input xmlns="http://www.w3.org/1999/xhtml" id="searchInput" type="text" placeholder="" style="background: transparent; border: none; color: #f8fafc; font-size: 13px; width: 100%; height: 30px; outline: none; caret-color: #38bdf8;" />
        </foreignObject>
    </g>

    <!-- Main Stack Container -->
    <g id="stackContainer" transform="translate(0, {header_height + 10})">
        <!-- Rendered dynamically via JS for high interactivity -->
    </g>

    <!-- Footer Stats Bar -->
    <rect x="0" y="{height - 40}" width="{width}" height="40" fill="#1e293b" />
    <text x="20" y="{height - 16}" font-size="12" fill="#cbd5e1" id="hoverDetails">Hover over a frame to see performance details</text>

    <script type="text/javascript">
        <![CDATA[
        const nodes = {json.dumps(nodes_json)};
        const totalTime = {total_time};
        const rowHeight = {row_height};
        const svgWidth = {width};
        
        let currentZoomNode = null;
        let searchQuery = "";
        
        const container = document.getElementById('stackContainer');
        const hoverDetails = document.getElementById('hoverDetails');
        const searchInput = document.getElementById('searchInput');
        const searchPlaceholder = document.getElementById('searchPlaceholder');
        
        searchInput.addEventListener('input', (e) => {{
            searchQuery = e.target.value.toLowerCase();
            searchPlaceholder.style.display = searchQuery ? 'none' : 'block';
            render();
        }});
        
        function getZoomScale(node) {{
            if (!node) return {{ scale: 1.0, offset: 0.0 }};
            // Map zoomed node to fill 100% width
            const scale = 100.0 / node.w_pct;
            const offset = -node.x_pct * scale;
            return {{ scale, offset }};
        }}
        
        function render() {{
            // Clear existing SVG stack
            while (container.firstChild) {{
                container.removeChild(container.firstChild);
            }}
            
            const {{ scale, offset }} = getZoomScale(currentZoomNode);
            const activeDepth = currentZoomNode ? currentZoomNode.depth : 0;
            
            nodes.forEach(node => {{
                // Node positioning based on zoom scale
                const x = (node.x_pct * scale + offset) * 0.01 * svgWidth;
                const w = node.w_pct * scale * 0.01 * svgWidth;
                
                // Hide nodes that are out of bounds or above zoomed parent
                if (currentZoomNode && node.depth < activeDepth) {{
                    return; // Skip drawing ancestor levels
                }}
                
                // Hide elements that are too small to see
                if (w < 0.5) return;
                
                const relativeDepth = node.depth - activeDepth;
                // Render blocks starting from bottom up
                const y = ( {max_depth} - node.depth ) * rowHeight;
                
                const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
                group.setAttribute("cursor", "pointer");
                
                // Hover effect
                group.addEventListener('mouseenter', () => {{
                    const pct = ((node.value / totalTime) * 100).toFixed(2);
                    hoverDetails.textContent = `${{node.name}} | Time: ${{node.value.toFixed(5)}}s (${{pct}}%) | Calls: ${{node.count}}`;
                }});
                
                group.addEventListener('mouseleave', () => {{
                    hoverDetails.textContent = "Hover over a frame to see performance details";
                }});
                
                group.addEventListener('click', () => {{
                    currentZoomNode = (currentZoomNode === node) ? null : node;
                    render();
                }});
                
                // Double click root to reset
                if (node.name === "all") {{
                    group.addEventListener('dblclick', () => {{
                        currentZoomNode = null;
                        render();
                    }});
                }}
                
                // Bar Rectangle
                const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                rect.setAttribute("x", x);
                rect.setAttribute("y", y);
                rect.setAttribute("width", w - 0.5);
                rect.setAttribute("height", rowHeight - 1);
                rect.setAttribute("rx", "2");
                
                // Highlight matches in search
                let fill = node.color;
                if (searchQuery && node.name.toLowerCase().includes(searchQuery)) {{
                    fill = "#a855f7"; // Highlight matching in Purple
                }} else if (searchQuery) {{
                    fill = "rgba(100, 116, 139, 0.4)"; // Demote others
                }}
                rect.setAttribute("fill", fill);
                
                // Text label inside bar
                const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                text.setAttribute("x", x + 6);
                text.setAttribute("y", y + 16);
                text.setAttribute("font-size", "11");
                text.setAttribute("fill", searchQuery && node.name.toLowerCase().includes(searchQuery) ? "#fff" : "#0f172a");
                text.setAttribute("font-weight", "500");
                
                // Truncate text if it doesn't fit
                // Simple character estimation: 7px per character
                const maxChars = Math.floor((w - 10) / 6.5);
                let label = node.name;
                if (label.length > maxChars) {{
                    if (maxChars > 5) {{
                        label = label.substring(0, maxChars - 3) + "...";
                    }} else {{
                        label = "";
                    }}
                }}
                text.textContent = label;
                
                group.appendChild(rect);
                if (label) group.appendChild(text);
                container.appendChild(group);
            }});
        }}
        
        // Initial Draw
        render();
        ]]>
    </script>
</svg>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

def main():
    parser = argparse.ArgumentParser(description="Profile a Python script and generate an interactive SVG Flamegraph.")
    parser.add_argument("script", nargs="?", help="Path to the Python script to profile")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments to pass to the target script")
    parser.add_argument("-o", "--output", default="flamegraph.svg", help="Output path for the SVG flamegraph (default: flamegraph.svg)")
    parser.add_argument("-c", "--command", help="Inline Python code snippet to profile directly")
    
    args = parser.parse_args()

    if not args.script and not args.command:
        parser.print_help()
        sys.exit(1)

    profiler = FlameGraphProfiler()

    if args.command:
        print(f"Profiling statement: {args.command}")
        # Run statement
        globals_dict = {"__name__": "__main__"}
        profiler.start()
        try:
            exec(args.command, globals_dict)
        except Exception:
            traceback.print_exc()
        finally:
            profiler.stop()
    else:
        script_path = os.path.abspath(args.script)
        if not os.path.exists(script_path):
            print(f"Error: Script file '{args.script}' not found.", file=sys.stderr)
            sys.exit(1)

        # Setup target sys.argv
        sys.argv = [script_path] + args.script_args
        
        # Add target script's directory to sys.path so imports work
        script_dir = os.path.dirname(script_path)
        sys.path.insert(0, script_dir)

        print(f"Profiling script: {script_path} with args {args.script_args}")
        profiler.ignore_paths.add(script_path)
        
        globals_dict = {
            "__name__": "__main__",
            "__file__": script_path,
        }

        # Read the code
        with open(script_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        # Compile code
        try:
            compiled_code = compile(code_content, script_path, "exec")
        except Exception as e:
            print(f"Error compiling script: {e}", file=sys.stderr)
            sys.exit(1)

        # Execute code under profiler
        profiler.start()
        try:
            exec(compiled_code, globals_dict)
        except SystemExit:
            pass # Gracefully handle exit calls in target script
        except Exception:
            traceback.print_exc()
        finally:
            profiler.stop()

    print(f"Profiling completed in {profiler.total_time:.5f} seconds.")
    print("Building call tree hierarchy...")
    
    hierarchy = build_hierarchy(profiler.call_tree)
    assign_positions(hierarchy)
    
    output_file = os.path.abspath(args.output)
    print(f"Writing SVG flamegraph: {output_file}")
    generate_flamegraph_svg(hierarchy, profiler.total_time, output_file)
    print("Done! Open the SVG file in your web browser to view the interactive flamegraph.")

if __name__ == "__main__":
    main()
