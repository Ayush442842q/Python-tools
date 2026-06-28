#!/usr/bin/env python3
"""
pip Dependency Tree Builder
Queries installed Python packages in the current environment to print a complete hierarchical
dependency tree (similar to pipdeptree) with version requirements, highlighting missing or circular dependencies.
Uses standard library `importlib.metadata` (Python 3.8+).
"""

import argparse
import re
import sys

# Try importing standard library metadata package
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    # Fallback for Python < 3.8 (though rare nowadays)
    try:
        import importlib_distpath as importlib_metadata
    except ImportError:
        print("Error: This tool requires Python 3.8+ or the 'importlib_metadata' backport.", file=sys.stderr)
        sys.exit(1)

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_CYAN = "\033[96m"
CLR_BOLD = "\033[1m"

def clean_req_name(req_str):
    """
    Parses a requirement string (e.g., 'requests (>=2.20.0)', 'Flask>=1.0; extra == "dev"')
    and returns (package_name, version_specs, is_extra).
    """
    # Remove markers (e.g., ; extra == '...' or python_version > '3')
    marker_split = req_str.split(';', 1)
    base_req = marker_split[0].strip()
    has_marker = len(marker_split) > 1
    
    # Extract package name and version specs
    # Match package name (word characters, dots, dashes, underscores)
    match = re.match(r'^([a-zA-Z0-9_\-\.]+)(.*)$', base_req)
    if not match:
        return base_req, "", has_marker
        
    pkg_name = match.group(1).strip()
    specs = match.group(2).strip()
    
    # Clean up specs parentheses
    if specs.startswith('(') and specs.endswith(')'):
        specs = specs[1:-1].strip()
        
    return pkg_name, specs, has_marker

def build_dependency_graph(include_extras=False):
    """Scan all installed distributions and construct a dependency graph."""
    dists = list(importlib_metadata.distributions())
    
    # Map lowercase package name to distribution details
    installed_pkgs = {}
    for dist in dists:
        # Some packages have empty names (uncommon)
        name = dist.metadata.get('Name')
        if name:
            installed_pkgs[name.lower()] = {
                'name': name,
                'version': dist.version,
                'requires': dist.requires or []
            }
            
    # Build graph
    # graph[pkg_lower] = list of (dep_pkg_name_lower, original_name, version_specs, is_extra)
    graph = {}
    for pkg_lower, info in installed_pkgs.items():
        dependencies = []
        for req in info['requires']:
            dep_name, specs, is_extra = clean_req_name(req)
            if is_extra and not include_extras:
                continue
            dependencies.append((dep_name.lower(), dep_name, specs))
        graph[pkg_lower] = dependencies
        
    return installed_pkgs, graph

def render_tree(pkg_lower, graph, installed_pkgs, prefix="", is_last=True, visited=None, depth=0, max_depth=10):
    """Recursively renders dependency tree using Unicode box-drawing characters."""
    if visited is None:
        visited = set()
        
    if depth > max_depth:
        return
        
    # Check if package is installed
    dist_info = installed_pkgs.get(pkg_lower)
    
    # Determine branch character
    connector = "└── " if is_last else "├── "
    
    if not dist_info:
        # Missing dependency
        print(f"{prefix}{connector}{CLR_RED}{pkg_lower} [Missing]{CLR_RESET}")
        return

    pkg_display_name = dist_info['name']
    pkg_ver = dist_info['version']
    
    # Check for circular dependency
    if pkg_lower in visited:
        print(f"{prefix}{connector}{CLR_YELLOW}{pkg_display_name}=={pkg_ver} [Circular]{CLR_RESET}")
        return
        
    print(f"{prefix}{connector}{CLR_GREEN}{pkg_display_name}{CLR_RESET}=={pkg_ver}")
    
    # Get dependencies
    deps = graph.get(pkg_lower, [])
    if not deps:
        return
        
    # Recurse children
    visited.add(pkg_lower)
    next_prefix = prefix + ("    " if is_last else "│   ")
    
    for idx, (dep_lower, dep_name, specs) in enumerate(deps):
        last_child = (idx == len(deps) - 1)
        # Check if dep is installed to show spec match
        dep_dist = installed_pkgs.get(dep_lower)
        dep_suffix = f" [{specs}]" if specs else ""
        
        # We render a branch for the child
        child_connector = "└── " if last_child else "├── "
        if not dep_dist:
            print(f"{next_prefix}{child_connector}{CLR_RED}{dep_name}{dep_suffix} [Missing]{CLR_RESET}")
        elif dep_lower in visited:
            print(f"{next_prefix}{child_connector}{CLR_YELLOW}{dep_name}=={dep_dist['version']}{dep_suffix} [Circular]{CLR_RESET}")
        else:
            # Recurse into child
            render_tree(
                dep_lower, 
                graph, 
                installed_pkgs, 
                prefix=next_prefix, 
                is_last=last_child, 
                visited=visited.copy(), 
                depth=depth + 1,
                max_depth=max_depth
            )

def main():
    parser = argparse.ArgumentParser(description="pip Dependency Tree - Visualizes python package dependencies")
    parser.add_argument("-p", "--package", help="Only show tree for this specific package (case-insensitive)")
    parser.add_argument("-e", "--extras", action="store_true", help="Include optional 'extra' dependencies")
    parser.add_argument("-d", "--max-depth", type=int, default=8, help="Maximum tree rendering depth (default: 8)")
    parser.add_argument("--list-only", action="store_true", help="List all installed packages and their versions without tree structure")
    
    args = parser.parse_args()
    
    print(f"Scanning installed package distributions...")
    installed_pkgs, graph = build_dependency_graph(include_extras=args.extras)
    
    if args.list_only:
        print("\nInstalled Packages:")
        print("=" * 45)
        for _, info in sorted(installed_pkgs.items()):
            print(f"{info['name']:<30} {info['version']}")
        return 0
        
    # If a specific package is selected
    if args.package:
        target = args.package.lower()
        if target not in installed_pkgs:
            print(f"Error: Package '{args.package}' is not installed.", file=sys.stderr)
            # Find close matches
            matches = [name for name in installed_pkgs if target in name]
            if matches:
                print(f"Did you mean: {', '.join(matches)}?", file=sys.stderr)
            return 1
            
        print(f"\nDependency Tree for '{args.package}':")
        print("=" * 60)
        render_tree(target, graph, installed_pkgs, max_depth=args.max_depth)
        print("=" * 60 + "\n")
        return 0
        
    # Render all top-level packages (packages that are not dependencies of any other package)
    # Find all packages that are requested as dependencies
    dependency_pkgs = set()
    for deps in graph.values():
        for dep_lower, _, _ in deps:
            dependency_pkgs.add(dep_lower)
            
    top_level_pkgs = [pkg for pkg in installed_pkgs if pkg not in dependency_pkgs]
    
    if not top_level_pkgs:
        # If all packages have circular references or everything is a dependency, just fall back to rendering all
        top_level_pkgs = list(installed_pkgs.keys())
        
    print(f"\n{CLR_BOLD}Installed Package Dependency Tree:{CLR_RESET}")
    print("=" * 60)
    
    # Sort top level packages alphabetically
    sorted_top = sorted(top_level_pkgs)
    for idx, pkg in enumerate(sorted_top):
        is_last = (idx == len(sorted_top) - 1)
        render_tree(pkg, graph, installed_pkgs, is_last=is_last, max_depth=args.max_depth)
        
    print("=" * 60 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
