#!/usr/bin/env python3
"""
Multi-Language Source Code Dependency & Import Grapher

Scans source code files across multiple programming languages (Python, JavaScript/TypeScript,
HTML, C/C++, Go) in a project directory, extracts module import/dependency relationships,
and renders an ASCII dependency tree, Mermaid.js diagram, or DOT graph.
"""

import os
import sys
import re
import json
import argparse
from typing import Dict, List, Set, Tuple, Optional

# Colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Language Regex Patterns for imports/dependencies
PATTERNS = {
    'python': [
        re.compile(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import', re.MULTILINE),
        re.compile(r'^\s*import\s+([a-zA-Z0-9_\.]+)', re.MULTILINE)
    ],
    'javascript': [
        re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'),
        re.compile(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
    ],
    'html': [
        re.compile(r'<script\s+[^>]*src=[\'"]([^\'"]+)[\'"]'),
        re.compile(r'<link\s+[^>]*href=[\'"]([^\'"]+)[\'"]')
    ],
    'cpp': [
        re.compile(r'^\s*#include\s+["<]([^">]+)[">]', re.MULTILINE)
    ],
    'go': [
        re.compile(r'import\s+["\']([^"\']+)["\']')
    ]
}


def get_language(filename: str) -> Optional[str]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.py']:
        return 'python'
    elif ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs']:
        return 'javascript'
    elif ext in ['.html', '.htm']:
        return 'html'
    elif ext in ['.c', '.cpp', '.h', '.hpp']:
        return 'cpp'
    elif ext in ['.go']:
        return 'go'
    return None


def extract_dependencies(filepath: str, root_dir: str) -> Set[str]:
    lang = get_language(filepath)
    if not lang or lang not in PATTERNS:
        return set()

    deps = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        for pattern in PATTERNS[lang]:
            for match in pattern.finditer(content):
                dep_target = match.group(1).strip()
                deps.add(dep_target)
    except Exception:
        pass
    return deps


class DependencyGraph:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.nodes: Dict[str, Set[str]] = {}

    def build(self):
        for root, _, files in os.walk(self.root_dir):
            for fname in files:
                lang = get_language(fname)
                if lang:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, self.root_dir).replace('\\', '/')
                    deps = extract_dependencies(full_path, self.root_dir)
                    self.nodes[rel_path] = deps

    def print_ascii_tree(self):
        print(f"\n{BOLD}{CYAN}=== Project Code Dependency Graph ==={RESET}")
        for node, deps in sorted(self.nodes.items()):
            print(f"{BOLD}{node}{RESET}")
            if not deps:
                print("  └── (no dependencies)")
            else:
                dep_list = sorted(list(deps))
                for idx, d in enumerate(dep_list):
                    prefix = "  └── " if idx == len(dep_list) - 1 else "  ├── "
                    print(f"{prefix}{GREEN}{d}{RESET}")

    def export_mermaid(self) -> str:
        lines = ["graph TD"]
        for node, deps in sorted(self.nodes.items()):
            clean_node = node.replace('.', '_').replace('/', '_').replace('-', '_')
            lines.append(f'  {clean_node}["{node}"]')
            for d in sorted(list(deps)):
                clean_dep = d.replace('.', '_').replace('/', '_').replace('-', '_')
                lines.append(f'  {clean_node} --> {clean_dep}["{d}"]')
        return "\n".join(lines)

    def export_dot(self) -> str:
        lines = ["digraph CodeDependencies {", "  rankdir=LR;", "  node [shape=box, style=rounded];"]
        for node, deps in sorted(self.nodes.items()):
            for d in sorted(list(deps)):
                lines.append(f'  "{node}" -> "{d}";')
        lines.append("}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract source code dependencies and render module graphs.")
    parser.add_argument("project_dir", nargs="?", default=".", help="Root directory of project codebase (default: current dir)")
    parser.add_argument("--format", choices=["ascii", "mermaid", "dot", "json"], default="ascii",
                        help="Output format: 'ascii' tree, 'mermaid' diagram, 'dot' graphviz, or 'json'")
    parser.add_argument("-o", "--output", help="Save output diagram/graph to file")

    args = parser.parse_args()

    graph = DependencyGraph(args.project_dir)
    graph.build()

    output_str = ""
    if args.format == "mermaid":
        output_str = graph.export_mermaid()
    elif args.format == "dot":
        output_str = graph.export_dot()
    elif args.format == "json":
        output_str = json.dumps({k: sorted(list(v)) for k, v in graph.nodes.items()}, indent=2)
    else:
        graph.print_ascii_tree()
        return

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"{GREEN}✓ Dependency graph saved to '{args.output}'{RESET}")
    else:
        print(output_str)


if __name__ == '__main__':
    main()
