#!/usr/bin/env python3
"""JS/TS Dependency Visualizer & Circular Reference Detector

Scans JavaScript/TypeScript codebases, parses ES6 static/dynamic imports and
CommonJS requirements, resolves imports relative to files, checks for circular
dependencies, and renders a Mermaid.js flowchart or interactive HTML dependency graph.
"""

import argparse
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Set, Tuple, Optional

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

# Regular expressions for imports
IMPORT_PATTERNS = [
    # Static imports: import x from './y' or import './y'
    re.compile(r'\bimport\s+(?:[^"\';\n]*\s+from\s+)?[\'"]([^\'"]+)[\'"]', re.MULTILINE),
    # Dynamic imports: import('./y')
    re.compile(r'\bimport\(\s*[\'"]([^\'"]+)[\'"]\s*\)', re.MULTILINE),
    # CommonJS requires: require('./y')
    re.compile(r'\brequire\(\s*[\'"]([^\'"]+)[\'"]\s*\)', re.MULTILINE),
    # Re-exports: export { x } from './y' or export * from './y'
    re.compile(r'\bexport\s+(?:[^"\';\n]*\s+from\s+)?[\'"]([^\'"]+)[\'"]', re.MULTILINE)
]


def resolve_import_path(current_file: Path, import_str: str, root_dir: Path) -> Optional[Path]:
    """Resolve import paths, checking for typical JS/TS extensions."""
    if not import_str.startswith('.'):
        return None  # Ignore external node_modules or alias paths (non-relative)
        
    base_dir = current_file.parent
    target_path = (base_dir / import_str).resolve()
    
    # List of possible extensions to probe in priority order
    extensions = [
        "", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        "/index.ts", "/index.tsx", "/index.js", "/index.jsx"
    ]
    
    for ext in extensions:
        candidate = Path(str(target_path) + ext)
        if candidate.is_file():
            return candidate
            
    return None  # Unresolved local import


def scan_file_dependencies(file_path: Path, root_dir: Path) -> List[Path]:
    """Parse dependencies inside a JS/TS file."""
    dependencies = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
        
    for pattern in IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            import_str = match.group(1)
            resolved = resolve_import_path(file_path, import_str, root_dir)
            if resolved and resolved != file_path:
                dependencies.append(resolved)
                
    return dependencies


def detect_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    """Detect circular dependency cycles in a directed graph using DFS."""
    cycles = []
    visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited
    path = []

    def dfs(node: str):
        visited[node] = 1
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if visited.get(neighbor, 0) == 1:
                # Cycle found, trace back
                cycle_start_idx = path.index(neighbor)
                cycles.append(path[cycle_start_idx:] + [neighbor])
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor)
                
        path.pop()
        visited[node] = 2

    for node in graph:
        if visited.get(node, 0) == 0:
            dfs(node)
            
    return cycles


def generate_mermaid(graph: Dict[str, List[str]], root_dir: Path) -> str:
    """Generate a Mermaid.js diagram representing the dependency tree."""
    lines = ["graph TD"]
    
    # Map absolute paths to short relative names
    def short_name(path_str: str) -> str:
        rel = Path(path_str).relative_to(root_dir)
        return str(rel).replace("\\", "/")

    # Generate node link definitions
    for source, targets in graph.items():
        src_name = short_name(source)
        if not targets:
            lines.append(f'    id_{hash(src_name) & 0xffffffff}["{src_name}"]')
        for target in targets:
            tgt_name = short_name(target)
            src_id = f"id_{hash(src_name) & 0xffffffff}"
            tgt_id = f"id_{hash(tgt_name) & 0xffffffff}"
            lines.append(f'    {src_id}["{src_name}"] --> {tgt_id}["{tgt_name}"]')
            
    return "\n".join(lines)


def generate_html_viewer(mermaid_graph: str, cycles: List[List[str]], output_file: Path):
    cycle_items = ""
    if cycles:
        cycle_items += "<h2>⚠️ Circular Dependencies Detected</h2><ul>"
        for cycle in cycles:
            cycle_str = " &rarr; ".join(cycle)
            cycle_items += f'<li class="cycle-item">{cycle_str}</li>'
        cycle_items += "</ul>"
    else:
        cycle_items += "<h2 style='color:#10b981;'>✅ No Circular Dependencies</h2>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JS/TS Codebase Dependency Map</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            margin-top: 0;
            color: #38bdf8;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
        }}
        .report-section {{
            margin-bottom: 30px;
        }}
        ul {{
            padding-left: 20px;
        }}
        .cycle-item {{
            color: #ef4444;
            font-family: monospace;
            font-size: 14px;
            margin-bottom: 8px;
            background-color: rgba(239, 68, 68, 0.1);
            padding: 8px 12px;
            border-radius: 4px;
            border-left: 3px solid #ef4444;
            list-style-type: none;
        }}
        .diagram-container {{
            background-color: #0b0f19;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 20px;
            overflow: auto;
            display: flex;
            justify-content: center;
        }}
    </style>
    <!-- Mermaid CDN -->
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'dark',
            flowchart: {{ useMaxWidth: false }}
        }});
    </script>
</head>
<body>
    <div class="container">
        <h1>JS/TS Module Dependency Map</h1>
        
        <div class="report-section">
            {cycle_items}
        </div>

        <h2>Module Flowchart</h2>
        <div class="diagram-container">
            <pre class="mermaid">
{mermaid_graph}
            </pre>
        </div>
    </div>
</body>
</html>
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze JS/TS imports/exports and check for circular references."
    )
    parser.add_argument("directory", help="Codebase directory to scan")
    parser.add_argument("--exclude", nargs="*", default=[], help="Directories to ignore (e.g. node_modules dist)")
    parser.add_argument("--export-html", help="Save visual dependency tree to HTML file")
    
    args = parser.parse_args()

    root_path = Path(args.directory).resolve()
    if not root_path.exists() or not root_path.is_dir():
        print(f"{COLOR_RED}Error: Directory '{args.directory}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{COLOR_BOLD}Scanning JS/TS files in '{root_path}'...{COLOR_RESET}")

    # Standard exclusions
    default_excludes = {"node_modules", "dist", "build", ".next", ".git"}
    excludes = default_excludes.union(set(args.exclude))

    extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
    files_to_scan = []

    for root, dirs, files in os.walk(root_path):
        # In-place modification to skip excluded directories in walk
        dirs[:] = [d for d in dirs if d not in excludes]
        
        for file in files:
            p = Path(root) / file
            if p.suffix.lower() in extensions:
                files_to_scan.append(p)

    print(f"Scanning {len(files_to_scan)} source files...\n")

    # Build dependency graph
    graph: Dict[str, List[str]] = {}
    for file in files_to_scan:
        deps = scan_file_dependencies(file, root_path)
        # Store as string paths for easier mapping
        graph[str(file)] = [str(d) for d in deps]

    # Detect Cycles
    cycles = detect_cycles(graph)

    # Format graph paths relative to display
    rel_graph = {}
    for src, tgts in graph.items():
        rel_src = str(Path(src).relative_to(root_path)).replace("\\", "/")
        rel_graph[rel_src] = [str(Path(t).relative_to(root_path)).replace("\\", "/") for t in tgts]

    # Display circular references
    if cycles:
        print(f"{COLOR_BOLD}{COLOR_RED}⚠️ WARNING: {len(cycles)} Circular Dependency Cycles Found:{COLOR_RESET}")
        for i, cycle in enumerate(cycles, 1):
            rel_cycle = [str(Path(p).relative_to(root_path)).replace("\\", "/") for p in cycle]
            cycle_str = f" {COLOR_YELLOW} -> {COLOR_RED}".join(rel_cycle)
            print(f" {i}. {COLOR_RED}{cycle_str}{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}✔ No circular dependencies detected.{COLOR_RESET}")

    # Print summary list of files and imports
    print(f"\n{COLOR_BOLD}Module Dependency Overview:{COLOR_RESET}")
    for src, tgts in rel_graph.items():
        if tgts:
            print(f"- {COLOR_CYAN}{src}{COLOR_RESET} imports:")
            for tgt in tgts:
                print(f"  &rarr; {tgt}")
        else:
            print(f"- {COLOR_GRAY}{src} (no imports){COLOR_RESET}")

    # Generate outputs
    mermaid_data = generate_mermaid(graph, root_path)
    
    if args.export_html:
        # Convert absolute cycles to relative for HTML output
        rel_cycles_list = []
        for cycle in cycles:
            rel_cycle = [str(Path(p).relative_to(root_path)).replace("\\", "/") for p in cycle]
            rel_cycles_list.append(rel_cycle)
            
        try:
            generate_html_viewer(mermaid_data, rel_cycles_list, Path(args.export_html))
            print(f"\n{COLOR_GREEN}{COLOR_BOLD}Success: Visual dependency map exported to '{args.export_html}'!{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error writing HTML file: {e}{COLOR_RESET}", file=sys.stderr)


if __name__ == "__main__":
    main()
