#!/usr/bin/env python3
"""
Makefile Analyzer & Linter

Parses and validates Makefiles for common issues, such as:
1. Spaces instead of Tabs in recipe lines (causes "missing separator" error).
2. Undefined variables used in targets/recipes.
3. Missing .PHONY declarations for common command targets (clean, test, run, all, etc.).
4. Circular dependencies among targets.

Also outputs a target dependency tree and summary of defined variables.

Usage:
    python makefile_analyzer.py [path_to_makefile]
"""

import sys
import os
import argparse
import re

def parse_makefile(filepath):
    """
    Parses a Makefile, identifying variables, targets, dependencies, recipes, and lines.
    Returns:
        variables: dict of name -> value
        targets: dict of name -> { 'dependencies': list, 'recipe': list, 'line_num': int }
        errors: list of dicts with 'line', 'line_num', 'type', 'message'
        warnings: list of dicts with 'line', 'line_num', 'type', 'message'
    """
    variables = {}
    targets = {}
    errors = []
    warnings = []
    
    # Track multiline continuations using backslash '\'
    lines_raw = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines_raw = f.readlines()
    except Exception as e:
        print(f"Error opening file '{filepath}': {e}", file=sys.stderr)
        return None
        
    # Standard builtin variables in Make
    builtin_vars = {
        'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'LDLIBS', 
        'MAKE', 'RM', 'AR', 'AS', 'LEX', 'YACC', 'SHELL', 'MAKEFLAGS',
        '@', '<', '^', '*', '?', '%', '+'  # Automatic variables
    }

    # First pass: join multiline statements ending with backslashes
    logical_lines = []
    current_line = ""
    start_line_num = 1
    
    for i, line_content in enumerate(lines_raw):
        line_num = i + 1
        stripped = line_content.rstrip('\r\n')
        
        if stripped.endswith('\\'):
            current_line += stripped[:-1] + " "
        else:
            current_line += stripped
            logical_lines.append((current_line, start_line_num, line_content))
            current_line = ""
            start_line_num = line_num + 1

    current_target = None
    
    for line, line_num, orig_raw in logical_lines:
        stripped = line.strip()
        
        # Skip empty lines and comments (that are not part of recipes)
        if not stripped or (stripped.startswith('#') and not line.startswith('\t')):
            continue
            
        # 1. Check for recipe line (starts with whitespace or tab)
        # In Make, a recipe line MUST start with a Tab character.
        # If it starts with spaces, check if it looks like a command.
        if line.startswith(' '):
            # If we are in a target context and it looks like a shell command/recipe
            # and does NOT start with a tab:
            if current_target and not line.startswith('\t'):
                # Check if it contains some command characters or is inside a recipe
                errors.append({
                    'line_num': line_num,
                    'line': orig_raw,
                    'type': 'TAB_INDENT',
                    'message': f"Recipe line starts with spaces instead of a TAB character. Make will fail with 'missing separator'."
                })
                
        if line.startswith('\t'):
            if current_target:
                targets[current_target]['recipe'].append(line.strip())
                
                # Check for undefined variables in the recipe line
                # Match $(VAR) or ${VAR} syntax
                vars_in_line = re.findall(r'\$[({]([^)}]+)[)}]', line)
                for var_ref in vars_in_line:
                    # Strip modifier prefixes/suffixes like $(VAR:.c=.o) or $(@D)
                    clean_var = re.split(r'[:|/]', var_ref)[0].strip()
                    # Skip automatic variables containing @, <, ^, *, etc.
                    if clean_var not in variables and clean_var not in builtin_vars and not clean_var.startswith('@') and not clean_var.startswith('<'):
                        # Environment variables are also allowed. Check os.environ.
                        if clean_var not in os.environ:
                            warnings.append({
                                'line_num': line_num,
                                'line': orig_raw,
                                'type': 'UNDEFINED_VAR',
                                'message': f"Reference to undefined variable '$({clean_var})' in recipe."
                            })
            else:
                warnings.append({
                    'line_num': line_num,
                    'line': orig_raw,
                    'type': 'ORPHAN_RECIPE',
                    'message': "Recipe command line found outside of any target definition."
                })
            continue

        # 2. Check for variable definitions (e.g. VAR = value, VAR := value, VAR ?= value, VAR += value)
        var_match = re.match(r'^([a-zA-Z0-9_\-]+)\s*([:+?]?=)\s*(.*)$', stripped)
        if var_match:
            var_name = var_match.group(1)
            var_op = var_match.group(2)
            var_val = var_match.group(3)
            variables[var_name] = var_val
            current_target = None  # Reset target context
            continue
            
        # 3. Check for target definition (e.g. target: dependencies)
        # Matches target names, excluding variable assignments, ending with colon
        target_match = re.match(r'^([^:=#\s]+)\s*:(?::)?\s*(.*)$', stripped)
        if target_match:
            target_name = target_match.group(1)
            deps_str = target_match.group(2)
            
            # Split dependencies by space, ignore variables inside dependencies for now
            # (e.g. $(DEPS))
            deps = [d.strip() for d in deps_str.split() if d.strip()]
            
            targets[target_name] = {
                'dependencies': deps,
                'recipe': [],
                'line_num': line_num
            }
            current_target = target_name
            continue
            
        # If it doesn't match any of the above, it might be an unknown directive
        # unless it is an include or conditional (ifeq, ifndef, else, endif, etc.)
        if not stripped.startswith(('ifeq', 'ifneq', 'ifdef', 'ifndef', 'else', 'endif', 'include', '-include')):
            warnings.append({
                'line_num': line_num,
                'line': orig_raw,
                'type': 'UNKNOWN_SYNTAX',
                'message': f"Could not parse line structure: '{stripped[:30]}...'"
            })
            
    return variables, targets, errors, warnings

def check_phony_targets(targets, warnings):
    """Checks for common action targets that might be missing .PHONY declaration."""
    common_actions = {'clean', 'test', 'run', 'all', 'install', 'build', 'compile', 'dist'}
    
    # Find defined actions
    defined_actions = set(targets.keys()).intersection(common_actions)
    
    # Check if .PHONY target exists and what it depends on
    phony_deps = set()
    if '.PHONY' in targets:
        phony_deps = set(targets['.PHONY']['dependencies'])
        
    for action in defined_actions:
        if action not in phony_deps:
            warnings.append({
                'line_num': targets[action]['line_num'],
                'line': f"{action}: ...",
                'type': 'MISSING_PHONY',
                'message': f"Target '{action}' should be declared as '.PHONY' to prevent conflicts with local files."
            })

def detect_cycles(targets):
    """Detect circular target dependencies using DFS."""
    visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited
    cycles = []
    
    def dfs(node, path):
        visited[node] = 1
        path.append(node)
        
        if node in targets:
            for dep in targets[node]['dependencies']:
                # Skip variable reference dependencies for cycle detection (e.g. $(DEPS))
                if dep.startswith('$'):
                    continue
                    
                if visited.get(dep, 0) == 1:
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])
                elif visited.get(dep, 0) == 0:
                    dfs(dep, path)
                    
        path.pop()
        visited[node] = 2

    for target in targets:
        if visited.get(target, 0) == 0:
            dfs(target, [])
            
    return cycles

def print_dependency_tree(targets, target, indent="", visited=None):
    """Recursively prints the dependency tree for a target."""
    if visited is None:
        visited = set()
        
    if target in visited:
        print(f"{indent}- {target} (circular reference)")
        return
        
    deps = targets[target]['dependencies'] if target in targets else []
    print(f"{indent}- {target}")
    
    visited.add(target)
    for dep in deps:
        if not dep.startswith('$'):
            print_dependency_tree(targets, dep, indent + "  ", visited.copy())

def main():
    parser = argparse.ArgumentParser(
        description="Makefile Linter & Analyzer. Check Makefiles for syntax, style, and cycle bugs.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "makefile",
        nargs="?",
        default="Makefile",
        help="Path to the Makefile to analyze (default: 'Makefile')"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.makefile):
        print(f"Error: Makefile '{args.makefile}' not found.", file=sys.stderr)
        return 1
        
    result = parse_makefile(args.makefile)
    if not result:
        return 1
        
    variables, targets, errors, warnings = result
    
    # Phony analysis
    check_phony_targets(targets, warnings)
    
    # Cycle analysis
    cycles = detect_cycles(targets)
    for cycle in cycles:
        cycle_str = " -> ".join(cycle)
        errors.append({
            'line_num': targets[cycle[0]]['line_num'] if cycle[0] in targets else 0,
            'line': cycle_str,
            'type': 'CIRCULAR_DEP',
            'message': f"Circular dependency detected: {cycle_str}"
        })
        
    # Output report
    print("\n" + "=" * 60)
    print(f"MAKEFILE ANALYSIS: {args.makefile}")
    print("=" * 60)
    
    print(f"Summary:")
    print(f"  - Targets defined:   {len(targets)}")
    print(f"  - Variables defined: {len(variables)}")
    print(f"  - Error issues:      {len(errors)}")
    print(f"  - Warning issues:    {len(warnings)}")
    print("-" * 60)
    
    if errors:
        print("\n\033[91mERRORS:\033[0m")
        for err in errors:
            loc = f"Line {err['line_num']}: " if err['line_num'] else ""
            print(f"  [!] {loc}{err['message']}")
            print(f"      Code: {err['line'].strip()}")
            
    if warnings:
        print("\n\033[93mWARNINGS:\033[0m")
        for warn in warnings:
            loc = f"Line {warn['line_num']}: " if warn['line_num'] else ""
            print(f"  [*] {loc}{warn['message']}")
            print(f"      Code: {warn['line'].strip()}")
            
    if not errors and not warnings:
        print("\n\033[92m[✓] Makefile is clean! No errors or warnings found.\033[0m")
        
    print("-" * 60)
    print("\nTarget Dependency Tree (Entry Targets):")
    # Identify entry-level targets (targets that aren't dependencies of other targets)
    all_deps = set()
    for t_info in targets.values():
        for d in t_info['dependencies']:
            all_deps.add(d)
            
    entry_targets = [t for t in targets if t not in all_deps and not t.startswith('.') and t != 'all']
    if 'all' in targets:
        entry_targets.insert(0, 'all')
        
    if not entry_targets and targets:
        # Fallback to listing all non-dot targets
        entry_targets = [t for t in targets if not t.startswith('.')]
        
    for t in entry_targets[:5]:  # Limit output tree depth for readability
        print_dependency_tree(targets, t)
        
    if len(entry_targets) > 5:
        print(f"  ... and {len(entry_targets) - 5} more targets.")
        
    print("\nDefined Variables:")
    for var, val in sorted(variables.items()):
        val_truncated = val[:40] + "..." if len(val) > 40 else val
        print(f"  {var} = {val_truncated}")
        
    print("=" * 60)
    
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
