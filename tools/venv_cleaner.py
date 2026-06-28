#!/usr/bin/env python3
"""
Python Virtual Environment Space Analyzer & Cleaner
Scans a Python virtual environment to identify storage waste and cleans it up.
"""

import os
import sys
import shutil
import argparse
from typing import List, Tuple, Dict

# ANSI colors
COLORS = {
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "RESET": "\033[0m"
}

def format_size(size_bytes: int) -> str:
    """Format bytes size into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def is_virtual_env(path: str) -> bool:
    """Verify if the directory at path is a Python virtual environment."""
    if not os.path.isdir(path):
        return False
    # Check for pyvenv.cfg
    if os.path.exists(os.path.join(path, "pyvenv.cfg")):
        return True
    # Check for Scripts (Windows) or bin (UNIX)
    if os.path.isdir(os.path.join(path, "Scripts")) or os.path.isdir(os.path.join(path, "bin")):
        return True
    return False

def get_dir_size(path: str) -> Tuple[int, int]:
    """Calculate the total size and file count of a directory recursively."""
    total_size = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip symlinks to avoid double-counting or infinite recursion
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except OSError:
                    pass
    return total_size, file_count

def scan_site_packages(venv_path: str) -> List[Tuple[str, int, int]]:
    """Scan site-packages for installed packages and their disk sizes."""
    site_packages_paths = []
    
    # Check common locations for site-packages
    # UNIX: lib/pythonX.Y/site-packages
    lib_path = os.path.join(venv_path, "lib")
    if os.path.isdir(lib_path):
        for py_dir in os.listdir(lib_path):
            sp_path = os.path.join(lib_path, py_dir, "site-packages")
            if os.path.isdir(sp_path):
                site_packages_paths.append(sp_path)

    # Windows: Lib/site-packages
    windows_sp = os.path.join(venv_path, "Lib", "site-packages")
    if os.path.isdir(windows_sp):
        site_packages_paths.append(windows_sp)

    packages = []
    for sp in site_packages_paths:
        try:
            for item in os.listdir(sp):
                item_path = os.path.join(sp, item)
                # Ignore system/standard folders
                if item in ("__pycache__", "easy_install.py", "site.py", "_distutils_findspec.py"):
                    continue
                if os.path.isdir(item_path):
                    size, count = get_dir_size(item_path)
                    packages.append((item, size, count))
                else:
                    try:
                        size = os.path.getsize(item_path)
                        packages.append((item, size, 1))
                    except OSError:
                        pass
        except OSError:
            pass
            
    # Sort packages by size descending
    packages.sort(key=lambda x: x[1], reverse=True)
    return packages

def scan_waste(venv_path: str) -> Dict[str, List[str]]:
    """Scan virtual environment for waste (pycache, pyc, build directories, empty dirs)."""
    waste = {
        "pycache": [],
        "pyc": [],
        "empty_dirs": []
    }
    
    for root, dirs, files in os.walk(venv_path, topdown=False):
        # 1. Check for __pycache__ folders
        for d in dirs:
            if d == "__pycache__":
                waste["pycache"].append(os.path.join(root, d))
                
        # 2. Check for .pyc and .pyo files
        for f in files:
            if f.endswith(('.pyc', '.pyo')):
                waste["pyc"].append(os.path.join(root, f))
                
        # 3. Check for empty directories (excluding core dirs)
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    waste["empty_dirs"].append(dir_path)
            except OSError:
                pass
                
    return waste

def clean_items(paths: List[str], dry_run: bool) -> Tuple[int, int]:
    """Delete files/directories and return (success_count, freed_bytes)."""
    success_count = 0
    freed_bytes = 0
    
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            if os.path.isdir(path):
                # Calculate size before delete
                for root, _, files in os.walk(path):
                    for f in files:
                        try:
                            freed_bytes += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
                if not dry_run:
                    shutil.rmtree(path)
                success_count += 1
            else:
                try:
                    freed_bytes += os.path.getsize(path)
                except OSError:
                    pass
                if not dry_run:
                    os.remove(path)
                success_count += 1
        except Exception as e:
            print(f"Error cleaning {path}: {e}", file=sys.stderr)
            
    return success_count, freed_bytes

def main():
    parser = argparse.ArgumentParser(
        description="Python Virtual Environment Space Analyzer & Cleaner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/venv_cleaner.py .venv --dry-run
  python tools/venv_cleaner.py my_env --yes
        """
    )
    parser.add_argument("venv_dir", nargs="?", default=".venv", help="Path to Python virtual environment (default: .venv)")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Scan and report potential savings without deleting files")
    parser.add_argument("-y", "--yes", action="store_true", help="Perform cleanup without interactive confirmation prompt")
    parser.add_argument("--list-packages", action="store_true", help="List installed packages sorted by size")

    args = parser.parse_args()

    # Find venv directory if not explicitly provided or doesn't exist
    venv_dir = args.venv_dir
    if not os.path.exists(venv_dir):
        # Look for other common names
        for alt in ["venv", "env", "virtualenv"]:
            if os.path.exists(alt) and is_virtual_env(alt):
                venv_dir = alt
                break

    if not os.path.exists(venv_dir):
        print(f"Error: Directory '{args.venv_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    if not is_virtual_env(venv_dir):
        print(f"Warning: '{venv_dir}' does not look like a standard virtual environment (no pyvenv.cfg or bin/Scripts directory).", file=sys.stderr)
        confirm = input("Do you want to scan this directory anyway? (y/N): ").strip().lower()
        if confirm != 'y':
            sys.exit(0)

    print(f"\nScanning Virtual Environment: {COLORS['BOLD']}{venv_dir}{COLORS['RESET']}")
    
    # Get general sizes
    total_size, total_files = get_dir_size(venv_dir)
    print(f"Total Size: {COLORS['BLUE']}{format_size(total_size)}{COLORS['RESET']} ({total_files:,} files)")

    # Scan for cleanup targets
    print("Scanning for byte-code cache and empty folders...")
    waste = scan_waste(venv_dir)
    
    # Calculate potential savings
    pycache_size = sum(get_dir_size(p)[0] for p in waste["pycache"])
    pyc_size = sum(os.path.getsize(f) for f in waste["pyc"] if os.path.exists(f))
    total_waste_size = pycache_size + pyc_size
    total_waste_count = len(waste["pycache"]) + len(waste["pyc"]) + len(waste["empty_dirs"])

    print("\n--- Potential Savings ---")
    print(f"__pycache__ directories:  {len(waste['pycache']):4} folders, size: {format_size(pycache_size)}")
    print(f"Isolated .pyc/.pyo files: {len(waste['pyc']):4} files,   size: {format_size(pyc_size)}")
    print(f"Empty directories:        {len(waste['empty_dirs']):4} folders")
    print(f"Total Cleanup Potential:  {COLORS['GREEN']}{format_size(total_waste_size)}{COLORS['RESET']}")

    # List packages if requested
    if args.list_packages:
        print("\n--- Top Installed Packages by Size ---")
        packages = scan_site_packages(venv_dir)
        if not packages:
            print("No packages found in site-packages.")
        else:
            for name, size, count in packages[:15]:
                print(f"  {name:<30} {format_size(size):>10} ({count:,} files)")
            if len(packages) > 15:
                print(f"  ... and {len(packages) - 15} more packages.")

    if total_waste_count == 0:
        print("\nNo cleanup needed. Environment is already clean!")
        sys.exit(0)

    # Perform cleanup
    if args.dry_run:
        print(f"\n{COLORS['YELLOW']}Dry-run active. No files were deleted.{COLORS['RESET']}")
        sys.exit(0)

    if not args.yes:
        confirm = input(f"\nDo you want to proceed with the cleanup? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cleanup cancelled.")
            sys.exit(0)

    print("\nCleaning...")
    
    cleaned_dirs, freed_pycache = clean_items(waste["pycache"], args.dry_run)
    cleaned_pyc, freed_pyc = clean_items(waste["pyc"], args.dry_run)
    cleaned_empty, _ = clean_items(waste["empty_dirs"], args.dry_run)
    
    total_freed = freed_pycache + freed_pyc
    
    print(f"{COLORS['GREEN']}Cleanup Complete!{COLORS['RESET']}")
    print(f"  Removed {cleaned_dirs} __pycache__ directories")
    print(f"  Removed {cleaned_pyc} compiled python files")
    print(f"  Removed {cleaned_empty} empty directories")
    print(f"Total space freed: {COLORS['BOLD']}{format_size(total_freed)}{COLORS['RESET']}")

if __name__ == "__main__":
    main()
