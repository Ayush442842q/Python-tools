#!/usr/bin/env python3
"""Python Class Hierarchy Visualizer

Scan a Python project, parse class definitions and inheritance paths using AST,
and render class hierarchy trees in the terminal or as Mermaid class diagrams.
"""

import argparse
import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


class ClassNode:
    def __init__(self, name: str, module_path: str, bases: List[str], doc: Optional[str], methods: List[str]):
        self.name = name
        self.module_path = module_path
        # Full identifier is module.class
        self.full_name = f"{module_path}.{name}" if module_path else name
        self.bases = bases
        self.doc = doc
        self.methods = methods
        self.children: Set[str] = set()  # set of child full_names


def get_base_name(node: ast.expr) -> str:
    """Helper to extract a string representation of a base class node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{get_base_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        # Handle generic bases like Base[T]
        return get_base_name(node.value)
    elif isinstance(node, ast.Call):
        # Handle Base(...) dynamic calls
        return get_base_name(node.func)
    return "Unknown"


class ProjectClassAnalyzer:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.classes: Dict[str, ClassNode] = {}  # full_name -> ClassNode
        # Maps short name to potential full names
        self.short_to_full: Dict[str, List[str]] = defaultdict(list)

    def scan(self, exclude_dirs: List[str]):
        """Recursively scan root_dir for Python files and parse them."""
        for root, dirs, files in os.walk(self.root_dir):
            # Apply exclusions in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    self._parse_file(file_path)

        self._resolve_inheritance()

    def _parse_file(self, file_path: Path):
        """Parse class definitions from a Python file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            # Silent fallback, or simple stderr message
            print(f"{COLOR_YELLOW}Warning: Failed to parse {file_path}: {e}{COLOR_RESET}", file=sys.stderr)
            return

        # Calculate module dot path
        try:
            rel_path = file_path.relative_to(self.root_dir)
            parts = list(rel_path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module_path = ".".join(parts)
        except ValueError:
            module_path = file_path.stem

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract methods
                methods = []
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        # Filter out helper/private methods unless specified
                        methods.append(sub.name)

                doc = ast.get_docstring(node)
                bases = [get_base_name(b) for b in node.bases]
                
                class_node = ClassNode(
                    name=node.name,
                    module_path=module_path,
                    bases=bases,
                    doc=doc,
                    methods=methods
                )
                
                self.classes[class_node.full_name] = class_node
                self.short_to_full[node.name].append(class_node.full_name)

    def _resolve_inheritance(self):
        """Link classes by resolving bases string names into full names."""
        for full_name, node in self.classes.items():
            resolved_bases = []
            for base in node.bases:
                # Find matching classes
                if base in self.classes:
                    resolved_bases.append(base)
                elif base in self.short_to_full:
                    # Match by short name (take first matches or exact module match if simple)
                    candidates = self.short_to_full[base]
                    # Simple heuristic: if base is defined in same module or parents, choose it
                    match_found = False
                    for cand in candidates:
                        cand_mod = cand.rsplit(".", 1)[0]
                        if cand_mod == node.module_path:
                            resolved_bases.append(cand)
                            match_found = True
                            break
                    if not match_found:
                        # Fallback to the first found candidate
                        resolved_bases.append(candidates[0])
                else:
                    # External class, keep it as external placeholder
                    resolved_bases.append(f"external.{base}")

            # Update parent-child links
            for base_full in resolved_bases:
                if base_full in self.classes:
                    self.classes[base_full].children.add(full_name)
                elif base_full.startswith("external."):
                    # Create an external placeholder node
                    ext_name = base_full.split(".", 1)[1]
                    if base_full not in self.classes:
                        ext_node = ClassNode(ext_name, "external", [], "External base class", [])
                        self.classes[base_full] = ext_node
                    self.classes[base_full].children.add(full_name)


def print_tree(
    node_name: str,
    classes: Dict[str, ClassNode],
    prefix: str = "",
    is_last: bool = True,
    visited: Optional[Set[str]] = None,
    show_methods: bool = False
):
    """Print ASCII tree of class hierarchy."""
    if visited is None:
        visited = set()

    node = classes.get(node_name)
    if not node:
        return

    # Check for cycles
    if node_name in visited:
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{COLOR_RED}{node.name} (Circular Dependency!){COLOR_RESET}")
        return

    visited.add(node_name)

    connector = "└── " if is_last else "├── "
    label = f"{COLOR_BOLD}{COLOR_GREEN}{node.name}{COLOR_RESET}"
    if node.module_path == "external":
        label = f"{COLOR_YELLOW}{node.name} [External]{COLOR_RESET}"
    elif node.module_path:
        label = f"{label} {COLOR_GREY}({node.module_path}){COLOR_RESET}"

    print(f"{prefix}{connector}{label}")

    # Print methods if requested
    new_prefix = prefix + ("    " if is_last else "│   ")
    if show_methods and node.methods:
        method_prefix = new_prefix + "  "
        for i, method in enumerate(sorted(node.methods)):
            is_last_method = (i == len(node.methods) - 1)
            method_connector = "└── " if is_last_method else "├── "
            print(f"{method_prefix}{COLOR_BLUE}def {method}(){COLOR_RESET}")

    children = sorted(list(node.children))
    for i, child_name in enumerate(children):
        is_last_child = (i == len(children) - 1)
        print_tree(child_name, classes, new_prefix, is_last_child, visited.copy(), show_methods)


def generate_mermaid(classes: Dict[str, ClassNode], show_methods: bool) -> str:
    """Generate Mermaid classDiagram markup."""
    lines = ["classDiagram"]
    
    # Declare classes and methods
    for full_name, node in sorted(classes.items()):
        class_id = full_name.replace(".", "_")
        lines.append(f"    class {class_id} {{\"")
        if node.module_path == "external":
            lines.append(f"        <<External>>")
        elif node.doc:
            # Clean docstring for line breaks
            first_line = node.doc.strip().split("\n")[0].replace('"', '\\"')
            lines.append(f"        note: {first_line}")
            
        if show_methods and node.methods:
            for method in sorted(node.methods):
                lines.append(f"        +{method}()")
        lines.append("    }")
        
        # Link label
        lines.append(f"    link {class_id} \"#\" \"{node.full_name}\"")
        
    lines.append("")
    
    # Declare inheritance relationships (Parent <|-- Child)
    for full_name, node in sorted(classes.items()):
        child_id = full_name.replace(".", "_")
        # Invert relationship to trace bases
        for base in node.bases:
            # Attempt to find resolved base ID
            resolved_base_id = None
            if base in classes:
                resolved_base_id = base.replace(".", "_")
            else:
                # Search short names
                for c_full, c_node in classes.items():
                    if c_node.name == base:
                        resolved_base_id = c_full.replace(".", "_")
                        break
            
            if not resolved_base_id:
                # External class placeholder id
                resolved_base_id = f"external_{base}"
                
            lines.append(f"    {resolved_base_id} <|-- {child_id}")
            
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Python Class Hierarchy Visualizer - Render project class structures."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Root directory of the Python project to scan (default: current directory)"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=["tests", "venv", ".venv", "build", "dist", "__pycache__"],
        help="Directory names to exclude from scanning"
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        help="Output in Mermaid classDiagram format instead of ASCII tree"
    )
    parser.add_argument(
        "--methods",
        action="store_true",
        help="Show class methods in the visualization"
    )
    args = parser.parse_args()

    root_path = Path(args.directory).resolve()
    if not root_path.is_dir():
        print(f"{COLOR_RED}Error: Path '{root_path}' is not a directory.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{COLOR_GREY}Scanning for Python classes in {root_path}...{COLOR_RESET}", file=sys.stderr)
    analyzer = ProjectClassAnalyzer(root_path)
    analyzer.scan(args.exclude)

    if not analyzer.classes:
        print(f"{COLOR_YELLOW}No Python class definitions found in the target directory.{COLOR_RESET}")
        sys.exit(0)

    if args.mermaid:
        print(generate_mermaid(analyzer.classes, args.methods))
        sys.exit(0)

    # Find root nodes for ASCII tree (nodes that have children, but no parent classes in project classes list)
    # We resolve this by counting how many project classes point to a class as base
    has_parent = set()
    for full_name, node in analyzer.classes.items():
        for child in node.children:
            has_parent.add(child)

    roots = [full_name for full_name in analyzer.classes if full_name not in has_parent]
    
    # Sort roots
    roots = sorted(roots, key=lambda x: analyzer.classes[x].name)

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Python Class Hierarchy Tree ==={COLOR_RESET}\n")
    
    for i, root in enumerate(roots):
        is_last = (i == len(roots) - 1)
        # Ensure it actually has children or is a main user class (not external placeholder roots)
        node = analyzer.classes[root]
        if node.module_path == "external" and not node.children:
            continue
        print_tree(root, analyzer.classes, prefix="", is_last=is_last, show_methods=args.methods)
        
    print()


if __name__ == "__main__":
    main()
