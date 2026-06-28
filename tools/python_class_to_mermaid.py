#!/usr/bin/env python3
"""
Python Class to Mermaid Visualizer
Parses Python source files using abstract syntax trees (AST), extracts classes,
their base classes, instance/class attributes, and method signatures, and
generates standard Mermaid.js class diagram syntax.
"""

import ast
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_RED = ""
    COLOR_CYAN = ""

class ClassVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        # class_name -> { "bases": [...], "methods": [...], "attributes": [...] }
        self.classes: Dict[str, Dict[str, List]] = {}
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        self.current_class = class_name
        
        # Get base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else base.attr)
            else:
                bases.append(ast.dump(base))
                
        self.classes[class_name] = {
            "bases": bases,
            "methods": [],
            "attributes": []
        }
        
        # Discover class-level attributes
        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        if attr_name not in self.classes[class_name]["attributes"]:
                            self.classes[class_name]["attributes"].append(attr_name)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    attr_name = child.target.id
                    if attr_name not in self.classes[class_name]["attributes"]:
                        self.classes[class_name]["attributes"].append(attr_name)

        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self.current_class:
            return
            
        method_name = node.name
        
        # Exclude common built-in special methods except __init__
        if method_name.startswith("__") and method_name.endswith("__") and method_name != "__init__":
            return
            
        # Get arguments list
        args = []
        for arg in node.args.args:
            if arg.arg != "self":
                args.append(arg.arg)
        args_str = ", ".join(args)
        
        # Store method
        self.classes[self.current_class]["methods"].append((method_name, args_str))
        
        # Look for instance attributes set inside this method (usually __init__)
        if method_name == "__init__":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Attribute):
                            if isinstance(target.value, ast.Name) and target.value.id == "self":
                                attr_name = target.attr
                                if attr_name not in self.classes[self.current_class]["attributes"]:
                                    self.classes[self.current_class]["attributes"].append(attr_name)

def determine_visibility(name: str) -> str:
    """Returns Mermaid visibility symbol based on Python naming conventions."""
    if name.startswith("__") and not name.endswith("__"):
        return "-"  # Private
    elif name.startswith("_"):
        return "#"  # Protected
    return "+"  # Public

def generate_mermaid_syntax(all_classes: Dict[str, Dict[str, List]]) -> str:
    """Formats discovered classes into Mermaid diagram syntax."""
    lines = ["classDiagram"]
    
    # Store all class names to detect inheritance within target files
    target_class_names = set(all_classes.keys())
    
    # Track relationships to avoid duplicates
    relationships = set()
    
    for class_name, data in all_classes.items():
        # Define class members
        lines.append(f"    class {class_name} {{")
        
        # Attributes
        for attr in data["attributes"]:
            vis = determine_visibility(attr)
            lines.append(f"        {vis}{attr}")
            
        # Methods
        for m_name, args in data["methods"]:
            vis = determine_visibility(m_name)
            lines.append(f"        {vis}{m_name}({args})")
            
        lines.append("    }")
        
        # Bases / Inheritance
        for base in data["bases"]:
            rel = f"    {base} <|-- {class_name}"
            if rel not in relationships:
                relationships.add(rel)
                
    # Add relationships
    for r in sorted(list(relationships)):
        lines.append(r)
        
    return "\n".join(lines)

def parse_file(filepath: str) -> Dict[str, Dict[str, List]]:
    """Parses a single file and extracts classes."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        visitor = ClassVisitor(filepath)
        visitor.visit(tree)
        return visitor.classes
    except Exception as e:
        print(f"{COLOR_RED}Error parsing file {filepath}: {e}{COLOR_RESET}", file=sys.stderr)
        return {}

def scan_directory(dir_path: str, excludes: List[str]) -> Dict[str, Dict[str, List]]:
    """Scans a directory recursively for Python files."""
    all_classes = {}
    for root, dirs, files in os.walk(dir_path):
        # Exclude directories
        dirs[:] = [d for d in dirs if not any(ex in os.path.join(root, d) for ex in excludes)]
        
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                if any(ex in full_path for ex in excludes):
                    continue
                file_classes = parse_file(full_path)
                all_classes.update(file_classes)
    return all_classes

def main():
    parser = argparse.ArgumentParser(
        description="Extract Python class hierarchies and generate Mermaid.js diagrams."
    )
    parser.add_argument(
        "-f", "--file", help="Analyze a single Python file"
    )
    parser.add_argument(
        "-d", "--dir", help="Recursively analyze a directory of Python files"
    )
    parser.add_argument(
        "-o", "--output", help="Output file path (saves Mermaid content)"
    )
    parser.add_argument(
        "--exclude", action="append", default=[".git", "__pycache__", "venv", "env"],
        help="Directories or files to exclude (can be specified multiple times)"
    )
    
    args = parser.parse_args()
    
    if not args.file and not args.dir:
        # Default to current directory if no input is specified
        args.dir = "."
        
    all_classes = {}
    
    if args.file:
        if not os.path.isfile(args.file):
            print(f"{COLOR_RED}Error: File '{args.file}' does not exist.{COLOR_RESET}")
            sys.exit(1)
        print(f"{COLOR_CYAN}Analyzing file: {args.file}...{COLOR_RESET}")
        all_classes = parse_file(args.file)
    elif args.dir:
        if not os.path.isdir(args.dir):
            print(f"{COLOR_RED}Error: Directory '{args.dir}' does not exist.{COLOR_RESET}")
            sys.exit(1)
        print(f"{COLOR_CYAN}Analyzing directory: {args.dir} (excluding {args.exclude})...{COLOR_RESET}")
        all_classes = scan_directory(args.dir, args.exclude)
        
    if not all_classes:
        print(f"{COLOR_YELLOW}No Python classes found in target.{COLOR_RESET}")
        sys.exit(0)
        
    mermaid_out = generate_mermaid_syntax(all_classes)
    
    print(f"\n{COLOR_BOLD}{COLOR_GREEN}=== Generated Mermaid Class Diagram ==={COLOR_RESET}\n")
    print(mermaid_out)
    print(f"\n{COLOR_BOLD}{COLOR_GREEN}======================================={COLOR_RESET}\n")
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(mermaid_out)
            print(f"{COLOR_GREEN}Successfully wrote Mermaid diagram to {args.output}{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error writing output file: {e}{COLOR_RESET}", file=sys.stderr)

if __name__ == "__main__":
    main()
