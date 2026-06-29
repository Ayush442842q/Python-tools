#!/usr/bin/env python3
"""
CSS Variable Optimizer
Audits CSS files for unused, undefined, and circular custom properties (CSS variables).
"""

import argparse
import os
import re
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Regex patterns
# Strip multi-line comments
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Match CSS variable declarations: --var-name: value;
DECLARATION_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;}]+)")
# Match CSS variable usages: var(--var-name)
USAGE_RE = re.compile(r"var\((--[a-zA-Z0-9_-]+)\)")

def strip_comments(css_content):
    """Strip standard CSS comments."""
    return COMMENT_RE.sub("", css_content)

def parse_css_file(filepath):
    """Parse a CSS file and extract variable declarations and references."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return None, str(e)

    # We need to trace line numbers, so let's do a line-by-line check or a block check
    clean_content = strip_comments(content)
    
    declarations = {}
    references = []  # List of tuples (var_name, referenced_by, line_num)

    lines = content.splitlines()
    for line_idx, line in enumerate(lines):
        line_num = line_idx + 1
        # Skip commented lines entirely if they are single lines
        stripped_line = line.strip()
        if stripped_line.startswith("/*") and stripped_line.endswith("*/"):
            continue

        # Look for declarations
        for match in DECLARATION_RE.finditer(line):
            var_name, val = match.groups()
            # Find usages inside the declared value
            deps = USAGE_RE.findall(val)
            declarations[var_name] = {
                "file": filepath,
                "line": line_num,
                "value": val.strip(),
                "dependencies": deps
            }

        # Look for general usages (not declarations)
        # To avoid double-counting usages inside declarations, let's parse differently.
        # If it's a declaration line, we only extract var()s in the value part.
        decl_match = DECLARATION_RE.search(line)
        if decl_match:
            var_name, val = decl_match.groups()
            for dep in USAGE_RE.findall(val):
                references.append({
                    "name": dep,
                    "by_var": var_name,
                    "file": filepath,
                    "line": line_num
                })
        else:
            # Just a regular CSS line (e.g. color: var(--main-color);)
            for match in USAGE_RE.finditer(line):
                used_var = match.group(1)
                references.append({
                    "name": used_var,
                    "by_var": None, # Used directly in style rule
                    "file": filepath,
                    "line": line_num
                })

    return {"declarations": declarations, "references": references}, None

def detect_cycles(declarations):
    """Detect cycles in variable declarations dependency graph."""
    visited = {}
    rec_stack = {}
    cycles = []

    def dfs(node, path):
        visited[node] = True
        rec_stack[node] = True
        path.append(node)

        for neighbor in declarations.get(node, {}).get("dependencies", []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Cycle found
                cycle_start_idx = path.index(neighbor)
                cycles.append(path[cycle_start_idx:] + [neighbor])

        path.pop()
        rec_stack[node] = False

    for node in declarations:
        if node not in visited:
            dfs(node, [])

    return cycles

def main():
    parser = argparse.ArgumentParser(
        description="Audit CSS stylesheets for unused, undefined, and circular CSS variable references."
    )
    parser.add_argument("path", help="CSS file or directory path to scan")
    parser.add_argument(
        "--exclude-dirs",
        default="node_modules,.git,dist,build,.agents",
        help="Comma-separated list of directories to exclude from recursive scans"
    )

    args = parser.parse_args()
    exclude_dirs = [d.strip() for d in args.exclude_dirs.split(",")]

    target_path = args.path
    if not os.path.exists(target_path):
        print(f"{RED}Error: Path '{target_path}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    css_files = []
    if os.path.isfile(target_path):
        if target_path.endswith(".css"):
            css_files.append(target_path)
    else:
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file.endswith(".css"):
                    css_files.append(os.path.join(root, file))

    if not css_files:
        print(f"{YELLOW}No CSS (.css) files found to scan.{RESET}")
        sys.exit(0)

    all_declarations = {}
    all_references = []

    print(f"{BOLD}{BLUE}Scanning {len(css_files)} CSS file(s) for custom properties...{RESET}\n")

    for filepath in sorted(css_files):
        data, err = parse_css_file(filepath)
        if err:
            print(f"{YELLOW}Skipped {filepath}: {err}{RESET}")
            continue
        
        # Merge declarations
        for var_name, decl in data["declarations"].items():
            if var_name in all_declarations:
                # Duplicate declaration
                prev = all_declarations[var_name]
                print(f"{YELLOW}Warning: Variable '{var_name}' redefined in:{RESET}")
                print(f"  - {prev['file']}:{prev['line']}")
                print(f"  - {decl['file']}:{decl['line']}")
            all_declarations[var_name] = decl
            
        all_references.extend(data["references"])

    # Analyze
    declared_vars = set(all_declarations.keys())
    referenced_vars = set(ref["name"] for ref in all_references)
    
    # 1. Undefined Variables (referenced but never declared)
    undefined_vars = referenced_vars - declared_vars
    
    # 2. Unused Variables
    # Root used variables: variables referenced directly in style rules (by_var is None)
    direct_used = set(ref["name"] for ref in all_references if ref["by_var"] is None)
    
    # Reachability analysis
    reachable = set()
    queue = list(direct_used)
    
    while queue:
        current = queue.pop(0)
        if current in declared_vars and current not in reachable:
            reachable.add(current)
            # Add its dependencies to queue
            deps = all_declarations[current]["dependencies"]
            for dep in deps:
                if dep not in reachable:
                    queue.append(dep)
                    
    unused_vars = declared_vars - reachable

    # 3. Circular Dependencies
    cycles = detect_cycles(all_declarations)

    # Print Report
    print("=" * 60)
    print(f"{BOLD}CSS VARIABLE OPTIMIZATION REPORT{RESET}")
    print("=" * 60)
    print(f"Total Declared Variables  : {len(declared_vars)}")
    print(f"Total Referenced Variables: {len(referenced_vars)}")
    print("-" * 60)

    has_issues = False

    # Print Undefined
    if undefined_vars:
        has_issues = True
        print(f"\n{RED}{BOLD}✘ Undefined Variables ({len(undefined_vars)}):{RESET}")
        print("These variables are used in var() but have no declarations.")
        # Find where they are referenced
        for var_name in sorted(undefined_vars):
            print(f"  {BOLD}{var_name}{RESET}:")
            refs = [r for r in all_references if r["name"] == var_name]
            for r in refs[:5]: # Limit to 5 references for cleaner output
                by_str = f" in '{r['by_var']}'" if r['by_var'] else " in rule"
                print(f"    - {r['file']}:{r['line']}{by_str}")
            if len(refs) > 5:
                print(f"    - ... and {len(refs) - 5} more reference(s)")

    # Print Circular
    if cycles:
        has_issues = True
        print(f"\n{RED}{BOLD}✘ Circular Reference Cycles ({len(cycles)}):{RESET}")
        for idx, cycle in enumerate(cycles):
            cycle_str = " -> ".join(cycle)
            print(f"  Cycle #{idx + 1}: {cycle_str}")

    # Print Unused
    if unused_vars:
        has_issues = True
        print(f"\n{YELLOW}{BOLD}! Unused Variables ({len(unused_vars)}):{RESET}")
        print("These variables are declared but never referenced (or only referenced by other unused variables).")
        for var_name in sorted(unused_vars):
            decl = all_declarations[var_name]
            rel_file = os.path.relpath(decl['file'])
            print(f"  - {BOLD}{var_name}{RESET} ({rel_file}:{decl['line']})")

    print("\n" + "=" * 60)
    if not has_issues:
        print(f"{GREEN}{BOLD}✔ All check passed! No unused, undefined, or circular variables found.{RESET}")
        sys.exit(0)
    else:
        print(f"{YELLOW}Review the warnings above to optimize your stylesheets.{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
