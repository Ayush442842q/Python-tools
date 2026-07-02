#!/usr/bin/env python3
"""
Python Sys Path Doctor - Inspect sys.path, analyze shadowing risks, and trace package import resolutions.
"""

import sys
import os
import importlib.util
import argparse
from pathlib import Path

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

# Common Standard Library module names to check for shadowing
STDLIB_MODULES = [
    'json', 'csv', 'email', 'socket', 'math', 'random', 'time', 'datetime',
    'sys', 'os', 're', 'subprocess', 'shutil', 'hashlib', 'sqlite3', 'logging',
    'threading', 'argparse', 'urllib', 'http', 'xml', 'uuid', 'collections'
]

def check_sys_path():
    """Analyze all entries in sys.path."""
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    print(f"{c_bold}=== sys.path Entry Diagnosis ==={c_reset}")
    seen = set()
    warnings = []
    
    for idx, path_entry in enumerate(sys.path):
        if not path_entry:
            # Empty entry represents current working directory
            resolved_path = os.getcwd()
            display_name = f"'' (Current Directory: {resolved_path})"
        else:
            resolved_path = os.path.abspath(path_entry)
            display_name = path_entry
            
        print(f"[{idx:2d}] {display_name}", end=" -> ")
        
        path_obj = Path(resolved_path)
        
        if resolved_path in seen:
            print(f"{c_yellow}Duplicate entry{c_reset}")
            warnings.append(f"Entry {idx} is a duplicate of a previous path: {resolved_path}")
            continue
            
        seen.add(resolved_path)
        
        if not path_obj.exists():
            print(f"{c_red}Dangling/Non-existent path{c_reset}")
            warnings.append(f"Entry {idx} does not exist on disk: {resolved_path}")
        elif not path_obj.is_dir():
            print(f"{c_red}Exists but is not a directory{c_reset}")
            warnings.append(f"Entry {idx} points to a file, not a directory: {resolved_path}")
        else:
            # Check permissions
            if not os.access(resolved_path, os.R_OK):
                print(f"{c_red}No read permission{c_reset}")
                warnings.append(f"Entry {idx} is not readable (permission denied): {resolved_path}")
            else:
                # Check if it is a site-packages directory, stdlib, or custom
                if 'site-packages' in resolved_path or 'dist-packages' in resolved_path:
                    print(f"{c_green}Valid (Third-party Site Packages){c_reset}")
                elif 'lib-dynload' in resolved_path or (resolved_path.startswith(sys.prefix) and 'lib' in resolved_path):
                    print(f"{c_blue}Valid (Standard Library / Python internal){c_reset}")
                else:
                    print(f"{c_yellow}Valid (User / Custom Application Path){c_reset}")
                    
    return warnings

def detect_stdlib_shadowing():
    """Detect if files in local directories shadow standard library modules."""
    c_red = get_color('red')
    c_yellow = get_color('yellow')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    print(f"\n{c_bold}=== Standard Library Shadowing Checks ==={c_reset}")
    shadowing_found = False
    
    # We inspect the current directory and any user-defined sys.path entries before stdlib
    user_paths = []
    for p in sys.path:
        if not p:
            user_paths.append(os.getcwd())
        else:
            abs_p = os.path.abspath(p)
            # Stop when we hit system site-packages or stdlib folder
            if 'site-packages' in abs_p or 'dist-packages' in abs_p or 'lib-dynload' in abs_p:
                break
            user_paths.append(abs_p)
            
    for p_dir in user_paths:
        if not os.path.isdir(p_dir):
            continue
        for mod in STDLIB_MODULES:
            # Look for mod.py or mod/ directory with __init__.py
            candidate_file = os.path.join(p_dir, f"{mod}.py")
            candidate_dir = os.path.join(p_dir, mod, "__init__.py")
            
            if os.path.isfile(candidate_file):
                print(f"[{c_red}SHADOWING{c_reset}] File '{candidate_file}' shadows stdlib module '{mod}'")
                shadowing_found = True
            elif os.path.isfile(candidate_dir):
                print(f"[{c_red}SHADOWING{c_reset}] Folder '{os.path.join(p_dir, mod)}' shadows stdlib module '{mod}'")
                shadowing_found = True
                
    if not shadowing_found:
        print("No standard library shadowing conflicts detected in user paths.")

def trace_import(module_name):
    """Trace where a module would be imported from."""
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    print(f"\n{c_bold}=== Trace Import: {module_name} ==={c_reset}")
    
    # Find all places it could resolve
    candidates = []
    
    for idx, path_entry in enumerate(sys.path):
        search_dir = os.path.abspath(path_entry) if path_entry else os.getcwd()
        if not os.path.isdir(search_dir):
            continue
            
        # Check for simple file import
        file_path = os.path.join(search_dir, f"{module_name}.py")
        pyc_path = os.path.join(search_dir, f"{module_name}.pyc")
        so_path = os.path.join(search_dir, f"{module_name}.so")
        pyd_path = os.path.join(search_dir, f"{module_name}.pyd")
        
        # Check for folder packages
        pkg_dir = os.path.join(search_dir, module_name)
        pkg_init = os.path.join(pkg_dir, "__init__.py")
        
        if os.path.isfile(file_path):
            candidates.append((idx, file_path, "Python source file"))
        elif os.path.isfile(pkg_init):
            candidates.append((idx, pkg_dir, "Python Package (directory)"))
        elif os.path.isfile(so_path):
            candidates.append((idx, so_path, "C extension (.so)"))
        elif os.path.isfile(pyd_path):
            candidates.append((idx, pyd_path, "C extension (.pyd)"))
        elif os.path.isfile(pyc_path):
            candidates.append((idx, pyc_path, "Compiled bytecode"))

    # Also check if standard library/built-in has it
    spec = None
    try:
        spec = importlib.util.find_spec(module_name)
    except Exception as e:
        print(f"Error checking spec: {e}")
        
    if spec:
        spec_origin = spec.origin if spec.origin else "Built-in / Namespace"
        spec_type = "Built-in / System spec"
        
        # Verify if origin matches any of our physical candidates
        already_listed = False
        for _, path_found, _ in candidates:
            if spec.origin and os.path.abspath(path_found) == os.path.abspath(spec.origin):
                already_listed = True
                
        if not already_listed:
            candidates.append(("System Spec", spec_origin, spec_type))

    if not candidates:
        print(f"{c_red}No resolution found for module '{module_name}'. It cannot be imported in the current environment.{c_reset}")
        return
        
    print(f"Import precedence list for '{module_name}':")
    for i, (entry_idx, path, desc) in enumerate(candidates, 1):
        indicator = c_green if i == 1 else c_yellow
        prefix = f"[{entry_idx}]" if isinstance(entry_idx, int) else f"[{entry_idx}]"
        print(f"  {i}. {indicator}* ACTIVE{c_reset} if i==1 else '  '" if i == 1 else "     ", end="")
        print(f"{prefix} {path} ({desc})")

def main():
    parser = argparse.ArgumentParser(
        description="Inspect sys.path, check for import conflicts, and trace modules."
    )
    parser.add_argument('--trace', help="Trace resolution path of a specific module (e.g. --trace requests).")
    parser.add_argument('--no-shadow-checks', action='store_true', help="Disable standard library shadowing check.")
    
    args = parser.parse_args()
    
    c_red = get_color('red')
    c_green = get_color('green')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    warnings = check_sys_path()
    
    if not args.no_shadow_checks:
        detect_stdlib_shadowing()
        
    if args.trace:
        trace_import(args.trace)
        
    print("\n" + "=" * 60)
    print(f"{c_bold}Diagnostics Summary:{c_reset}")
    if warnings:
        print(f"  - {c_red}Found {len(warnings)} warning(s):{c_reset}")
        for w in warnings:
            print(f"    * {w}")
    else:
        print(f"  - {c_green}All checks passed! No sys.path warnings or issues.{c_reset}")
    print("=" * 60)

if __name__ == '__main__':
    main()
