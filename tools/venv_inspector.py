#!/usr/bin/env python3
"""
Python Virtual Environment (venv) Inspector - Scan, analyze size, and list installed packages in local venvs.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
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

def get_human_size(size_bytes):
    """Convert bytes to human-readable size string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_dir_size(path):
    """Recursively calculate directory size in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except PermissionError:
        pass
    except FileNotFoundError:
        pass
    return total

def parse_pyvenv_cfg(cfg_path):
    """Parse key-value pairs from pyvenv.cfg."""
    config = {}
    try:
        with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '=' in line:
                    k, v = line.split('=', 1)
                    config[k.strip()] = v.strip()
    except Exception:
        pass
    return config

def get_site_packages_dirs(venv_path):
    """Locate site-packages directories inside a virtual environment path."""
    site_packages = []
    p = Path(venv_path)
    
    # Windows standard layout: Lib/site-packages
    win_path = p / "Lib" / "site-packages"
    if win_path.exists():
        site_packages.append(win_path)
        
    # Unix standard layout: lib/pythonX.Y/site-packages
    unix_lib = p / "lib"
    if unix_lib.exists() and unix_lib.is_dir():
        try:
            for py_dir in unix_lib.iterdir():
                if py_dir.is_dir() and py_dir.name.startswith("python"):
                    sp = py_dir / "site-packages"
                    if sp.exists():
                        site_packages.append(sp)
        except Exception:
            pass
            
    return site_packages

def get_installed_packages(site_packages_paths):
    """Read metadata inside site-packages to find installed packages and versions."""
    packages = []
    seen = set()
    
    for sp_path in site_packages_paths:
        try:
            # Look for *.dist-info or *.egg-info directories
            for entry in sp_path.iterdir():
                if entry.is_dir() and (entry.name.endswith(".dist-info") or entry.name.endswith(".egg-info")):
                    name_ver = entry.name[:-10] # Strip suffix
                    if '-' in name_ver:
                        parts = name_ver.split('-')
                        # package names can contain dashes, so last token is usually the version
                        version = parts[-1]
                        name = "-".join(parts[:-1])
                        
                        # Dedup packages found in multiple places
                        pkg_key = f"{name.lower()}=={version}"
                        if pkg_key not in seen:
                            seen.add(pkg_key)
                            packages.append((name, version))
        except Exception:
            pass
            
    return sorted(packages, key=lambda x: x[0].lower())

def find_virtual_envs(root_path, max_depth=3):
    """Recursively search for virtual environments up to a max depth."""
    venvs = []
    root = Path(root_path)
    
    # Exclude standard large/unrelated project folders to keep search fast
    exclude_dirs = {'.git', '.svn', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.idea', '.vscode'}
    
    def _search(current_dir, current_depth):
        if current_depth > max_depth:
            return
            
        try:
            # Check if this directory is a venv itself
            cfg_path = current_dir / "pyvenv.cfg"
            if cfg_path.exists() and cfg_path.is_file():
                venvs.append(current_dir)
                return  # Don't recurse inside a venv
                
            for entry in current_dir.iterdir():
                if entry.is_dir():
                    # If directory name matches some excluded dirs, check if it's actually a venv.
                    # Only skip if it's NOT a venv.
                    if entry.name in exclude_dirs:
                        cfg_in_exclude = entry / "pyvenv.cfg"
                        if cfg_in_exclude.exists():
                            venvs.append(entry)
                        continue
                    _search(entry, current_depth + 1)
        except PermissionError:
            pass
        except Exception:
            pass
            
    _search(root, 1)
    return venvs

def main():
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_cyan = get_color('cyan')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    parser = argparse.ArgumentParser(description="Python Virtual Environment Inspector - Scan local directories to details venv settings, size, and packages.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-d", "--depth", type=int, default=3, help="Max recursion depth for scan (default: 3)")
    parser.add_argument("-p", "--packages", action="store_true", help="List installed packages for each virtual environment found")
    parser.add_argument("--details", help="Provide absolute or relative path to a single venv to show detailed package audit")
    parser.add_argument("--delete", help="Path of a virtual environment to securely delete (free up space)")

    args = parser.parse_args()

    # Handle delete command
    if args.delete:
        target = Path(args.delete)
        if not target.exists():
            print(f"{c_red}Error: Path '{target}' does not exist.{c_reset}")
            return
        
        cfg = target / "pyvenv.cfg"
        if not cfg.exists():
            print(f"{c_yellow}Warning: Path does not seem to contain a 'pyvenv.cfg' file. Are you sure this is a venv?{c_reset}")
            confirm = input("Type 'yes' to proceed with deletion anyway: ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                return
                
        print(f"Deleting virtual environment: {target}...")
        try:
            shutil.rmtree(target)
            print(f"{c_green}Successfully deleted virtual environment.{c_reset}")
        except Exception as e:
            print(f"{c_red}Failed to delete: {str(e)}{c_reset}")
        return

    # Handle single venv details command
    if args.details:
        target = Path(args.details)
        cfg_path = target / "pyvenv.cfg"
        if not cfg_path.exists():
            print(f"{c_red}Error: '{target}' is not a valid virtual environment (missing pyvenv.cfg).{c_reset}")
            return
            
        cfg = parse_pyvenv_cfg(cfg_path)
        py_version = cfg.get('version', 'Unknown')
        home_path = cfg.get('home', 'Unknown')
        
        print(f"{c_bold}Virtual Environment Details:{c_reset}")
        print(f"  • Path:           {target.resolve()}")
        print(f"  • Python Version: {py_version}")
        print(f"  • Home/Source:    {home_path}")
        
        size = get_dir_size(target)
        print(f"  • Disk Space:     {get_human_size(size)}")
        
        sp_dirs = get_site_packages_dirs(target)
        pkgs = get_installed_packages(sp_dirs)
        
        print(f"\n{c_bold}Installed Packages ({len(pkgs)}):{c_reset}")
        print("-" * 45)
        for name, ver in pkgs:
            print(f"  {name:<30} {c_green}{ver}{c_reset}")
        print("-" * 45)
        return

    # Scan mode
    scan_root = Path(args.directory).resolve()
    print(f"Scanning {c_cyan}{scan_root}{c_reset} for Python virtual environments (max depth: {args.depth})...")
    venvs = find_virtual_envs(scan_root, args.depth)

    if not venvs:
        print(f"\n{c_yellow}No Python virtual environments found.{c_reset}")
        return

    print(f"\nFound {c_bold}{len(venvs)}{c_reset} virtual environment(s):\n")
    print(f"{'Path':<50} {'Py Version':<12} {'Size':<10} {'Packages':<8}")
    print("=" * 85)

    total_space = 0
    for v in venvs:
        cfg = parse_pyvenv_cfg(v / "pyvenv.cfg")
        py_ver = cfg.get('version', 'Unknown')
        
        size_bytes = get_dir_size(v)
        total_space += size_bytes
        size_str = get_human_size(size_bytes)
        
        sp_dirs = get_site_packages_dirs(v)
        pkgs = get_installed_packages(sp_dirs)
        pkg_count = len(pkgs)
        
        # Display short path relative to scan root
        try:
            rel_path = v.relative_to(scan_root)
            display_path = "./" + str(rel_path)
        except ValueError:
            display_path = str(v)
            
        if len(display_path) > 48:
            display_path = "..." + display_path[-45:]
            
        print(f"{display_path:<50} {py_ver:<12} {size_str:<10} {pkg_count:<8}")
        
        if args.packages:
            for p_name, p_ver in pkgs:
                print(f"    - {p_name} ({p_ver})")
            if pkg_count > 0:
                print()

    print("=" * 85)
    print(f"{c_bold}Total disk space used by venvs: {c_green}{get_human_size(total_space)}{c_reset}")
    print("\nTo see details for an environment, run:")
    print("  python venv_inspector.py --details <path_to_venv>")
    print("To delete an environment to reclaim space, run:")
    print("  python venv_inspector.py --delete <path_to_venv>")

if __name__ == "__main__":
    main()
