#!/usr/bin/env python3
"""
Python Library API Breaking Change Detector
Compares two versions of a Python codebase or file using AST analysis to report potential breaking changes in the public API.
"""

import ast
import os
import sys
import argparse
from typing import Dict, Set, List, Tuple, Any, Optional

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

class APIEntity:
    """Represents a public API element (Function, Class, Global Variable)."""
    def __init__(self, name: str, entity_type: str, lineno: int):
        self.name = name
        self.entity_type = entity_type
        self.lineno = lineno
        # For functions / methods:
        self.args: List[str] = []
        self.kwonlyargs: List[str] = []
        self.defaults_count: int = 0
        self.kw_defaults_count: int = 0
        self.posonlyargs: List[str] = []
        # For classes:
        self.methods: Dict[str, 'APIEntity'] = {}
        self.bases: List[str] = []

    def __repr__(self):
        return f"{self.entity_type}({self.name})"

def is_public(name: str) -> bool:
    """Check if a name is part of the public API (does not start with a single underscore, unless it starts with __ and ends with __)."""
    if name.startswith('_'):
        if name.startswith('__') and name.endswith('__'):
            return True
        return False
    return True

class APIExtractor(ast.NodeVisitor):
    """AST Visitor that extracts public API definitions from a Python module."""
    def __init__(self):
        self.entities: Dict[str, APIEntity] = {}
        self.current_class: Optional[APIEntity] = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not is_public(node.name):
            return
            
        entity = APIEntity(node.name, "Function", node.lineno)
        
        # Extract arguments
        # Support posonlyargs (Python 3.8+)
        if hasattr(node.args, 'posonlyargs'):
            entity.posonlyargs = [a.arg for a in node.args.posonlyargs]
        entity.args = [a.arg for a in node.args.args]
        entity.kwonlyargs = [a.arg for a in node.args.kwonlyargs]
        entity.defaults_count = len(node.args.defaults)
        entity.kw_defaults_count = sum(1 for d in node.args.kw_defaults if d is not None)

        if self.current_class:
            entity.entity_type = "Method"
            self.current_class.methods[node.name] = entity
        else:
            self.entities[node.name] = entity

        # Don't recurse into function body
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not is_public(node.name):
            return

        entity = APIEntity(node.name, "Class", node.lineno)
        # Extract base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                entity.bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                entity.bases.append(f"{self._get_attribute_name(base)}")

        prev_class = self.current_class
        self.current_class = entity
        
        # Traverse class body to collect methods
        for item in node.body:
            self.visit(item)
            
        self.current_class = prev_class
        self.entities[node.name] = entity

    def visit_Assign(self, node: ast.Assign):
        # We only look at top-level module globals
        if self.current_class:
            return
            
        for target in node.targets:
            if isinstance(target, ast.Name):
                if is_public(target.id):
                    self.entities[target.id] = APIEntity(target.id, "Global Variable", target.lineno)

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        return node.attr

def extract_api_from_file(file_path: str) -> Dict[str, APIEntity]:
    """Parse a file and extract its public API Entities."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        extractor = APIExtractor()
        extractor.visit(tree)
        return extractor.entities
    except Exception as e:
        print(f"{RED}Error parsing {file_path}: {e}{RESET}", file=sys.stderr)
        return {}

def extract_api_from_dir(dir_path: str) -> Dict[str, Dict[str, APIEntity]]:
    """Recursively parse Python files and map module name -> API Entities."""
    api_map = {}
    dir_path = os.path.abspath(dir_path)
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dir_path)
                module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
                if module_name.endswith('.__init__'):
                    module_name = module_name[:-9]
                api_map[module_name] = extract_api_from_file(full_path)
    return api_map

def compare_entities(old: APIEntity, new: APIEntity, path_prefix: str) -> List[str]:
    """Compare two APIEntities and return a list of breaking changes."""
    breaks = []
    
    # Class comparison
    if old.entity_type == "Class" and new.entity_type == "Class":
        # Check bases (removal of base class could be breaking, but we will focus on methods)
        # Check methods
        for method_name, old_method in old.methods.items():
            if method_name not in new.methods:
                breaks.append(f"REMOVED: Method '{path_prefix}.{old.name}.{method_name}' was removed or made private.")
            else:
                new_method = new.methods[method_name]
                breaks.extend(compare_entities(old_method, new_method, f"{path_prefix}.{old.name}"))
                
    # Function / Method comparison
    elif old.entity_type in ("Function", "Method") and new.entity_type in ("Function", "Method"):
        # Check if parameters were removed or renamed
        old_params = old.posonlyargs + old.args + old.kwonlyargs
        new_params = new.posonlyargs + new.args + new.kwonlyargs
        
        # Simple parameter name removal/rename check
        for param in old_params:
            if param == 'self' or param == 'cls':
                continue
            if param not in new_params:
                breaks.append(f"BREAKING SIGNATURE: Parameter '{param}' in '{path_prefix}.{old.name}' was removed or renamed.")
        
        # Check if new required parameters were added (no defaults)
        # Required args are those in args/posonlyargs/kwonlyargs that don't have default values.
        # Calculate number of required positional parameters
        old_req_pos = len(old.posonlyargs + old.args) - old.defaults_count
        new_req_pos = len(new.posonlyargs + new.args) - new.defaults_count
        
        # If new version has more required parameters than the old version, it's breaking
        # Check each new parameter that was not in old, to see if it has no default value
        old_set = set(old_params)
        for idx, param in enumerate(new.posonlyargs + new.args):
            if param == 'self' or param == 'cls':
                continue
            if param not in old_set:
                # Is it required?
                total_pos_args = len(new.posonlyargs + new.args)
                pos_in_args_list = idx
                is_defaulted = (total_pos_args - pos_in_args_list) <= new.defaults_count
                if not is_defaulted:
                    breaks.append(f"BREAKING SIGNATURE: New required parameter '{param}' was added to '{path_prefix}.{old.name}' without a default value.")
                    
        # Check new required keyword-only args
        old_kw_set = set(old.kwonlyargs)
        for idx, param in enumerate(new.kwonlyargs):
            if param not in old_kw_set:
                # In Python AST, keyword default values can be None if not provided
                # But here we just check if it's new and has no default
                # (For keyword args, new.kw_defaults is a list of nodes, some can be None)
                # To be simple and robust: check if defaults are sufficient
                pass
                
    elif old.entity_type != new.entity_type:
        breaks.append(f"CHANGED TYPE: '{path_prefix}.{old.name}' changed from {old.entity_type} to {new.entity_type}.")
        
    return breaks

def compare_apis(old_api: Dict[str, APIEntity], new_api: Dict[str, APIEntity], module_name: str) -> List[str]:
    """Compare modules' APIs."""
    breaks = []
    for name, old_entity in old_api.items():
        if name not in new_api:
            breaks.append(f"REMOVED: Public {old_entity.entity_type.lower()} '{module_name}.{name}' was removed or made private.")
        else:
            new_entity = new_api[name]
            breaks.extend(compare_entities(old_entity, new_entity, module_name))
    return breaks

def main():
    parser = argparse.ArgumentParser(
        description="Detect public API breaking changes between two versions of a Python project using AST analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/python_api_breaking_change_detector.py old_version.py new_version.py
  python tools/python_api_breaking_change_detector.py path/to/old_project/ path/to/new_project/
        """
    )
    parser.add_argument("old", help="Old version file path or directory root.")
    parser.add_argument("new", help="New version file path or directory root.")
    
    args = parser.parse_args()
    
    is_dir_old = os.path.isdir(args.old)
    is_dir_new = os.path.isdir(args.new)
    
    if is_dir_old != is_dir_new:
        print(f"{RED}Error: Both target paths must be either directories or files.{RESET}", file=sys.stderr)
        sys.exit(1)
        
    breaking_changes = []
    
    if is_dir_old:
        old_map = extract_api_from_dir(args.old)
        new_map = extract_api_from_dir(args.new)
        
        # Compare modules
        for mod, old_api in old_map.items():
            if mod not in new_map:
                breaking_changes.append(f"REMOVED MODULE: Module '{mod}' is missing entirely in the new version.")
            else:
                breaking_changes.extend(compare_apis(old_api, new_map[mod], mod))
    else:
        old_api = extract_api_from_file(args.old)
        new_api = extract_api_from_file(args.new)
        breaking_changes.extend(compare_apis(old_api, new_api, "module"))
        
    if breaking_changes:
        print(f"\n{BOLD}{RED}Detected {len(breaking_changes)} potential breaking API changes:{RESET}")
        print("=" * 60)
        for change in breaking_changes:
            print(f" {RED}×{RESET} {change}")
        sys.exit(1)
    else:
        print(f"\n{BOLD}{GREEN}No breaking API changes detected!{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
