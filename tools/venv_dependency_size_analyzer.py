#!/usr/bin/env python3
"""
Python Virtual Environment Dependency Size Analyzer

Scans a Python virtual environment's site-packages directory, calculates the disk
space occupied by each installed package (and its subdirectories), and prints a
sorted list or a hierarchical tree showing own vs. cumulative package sizes.
"""

import os
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

# ANSI Colors for formatting
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def format_size(bytes_size: int) -> str:
    """Formats raw bytes into a human-readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def get_default_site_packages() -> Optional[Path]:
    """Attempts to find the active virtual environment's site-packages folder."""
    # Check if running in a virtual environment
    if hasattr(sys, 'real_prefix') or (sys.base_prefix != sys.prefix):
        prefix = Path(sys.prefix)
        # Search for site-packages in common venv layouts
        paths = [
            prefix / "Lib" / "site-packages",  # Windows
            prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",  # POSIX
            prefix / "local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"  # Debian/Ubuntu alternative
        ]
        for p in paths:
            if p.is_dir():
                return p
    
    # Fallback: check sys.path for anything ending in site-packages
    for path_str in sys.path:
        p = Path(path_str)
        if p.name == "site-packages" and p.is_dir():
            return p
            
    return None

class PackageInfo:
    def __init__(self, name: str, version: str, path: Path):
        self.name = name
        self.version = version
        self.path = path
        self.files: Set[Path] = set()
        self.own_size: int = 0
        self.dependencies: Set[str] = set()
        self.cumulative_size: int = 0
        self.is_resolved: bool = False

    def calculate_size(self, site_packages: Path) -> None:
        """Calculates size of the files owned by this package."""
        size = 0
        
        # 1. Try to read from RECORD file if it exists
        record_path = self.path / "RECORD"
        if record_path.is_file():
            try:
                with open(record_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.split(",")
                        if parts:
                            file_rel = parts[0]
                            # Resolve path relative to site-packages (or metadata dir if absolute/dots)
                            file_path = (site_packages / file_rel).resolve()
                            if file_path.is_file() and file_path.is_relative_to(site_packages.resolve()):
                                self.files.add(file_path)
            except Exception:
                pass

        # 2. If RECORD didn't yield files, scan corresponding package directories based on naming
        if not self.files:
            # Clean name for directory matching
            clean_name = self.name.lower().replace("-", "_")
            # Look for top-level directory and single module files
            for child in site_packages.iterdir():
                child_name = child.name.lower()
                if child.is_dir():
                    if child_name == clean_name or child_name.startswith(clean_name + "_"):
                        self.add_directory_files(child)
                elif child.is_file():
                    if child_name == f"{clean_name}.py":
                        self.files.add(child)
                        
            # Also include the metadata directory itself
            self.add_directory_files(self.path)
            
        # Sum the sizes of all unique files
        for f in self.files:
            try:
                size += f.stat().st_size
            except Exception:
                pass
        self.own_size = size

    def add_directory_files(self, directory: Path) -> None:
        """Helper to add all files in a directory recursively."""
        try:
            for root, _, files in os.walk(directory):
                for f in files:
                    self.files.add(Path(root) / f)
        except Exception:
            pass

    def parse_dependencies(self) -> None:
        """Parses requirements from METADATA or PKG-INFO."""
        metadata_path = self.path / "METADATA"
        if not metadata_path.is_file():
            metadata_path = self.path / "PKG-INFO"
            
        if metadata_path.is_file():
            try:
                with open(metadata_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Requires-Dist:"):
                            # Format: Requires-Dist: requests (>=2.0) ; extra == 'socks'
                            req_part = line.split("Requires-Dist:")[1].strip()
                            # Parse out package name (alphanumeric, dashes, underscores)
                            match = re.match(r"^([a-zA-Z0-9_\-]+)", req_part)
                            if match:
                                dep_name = match.group(1).lower().replace("_", "-")
                                # Skip conditional/extra deps for simplicity, or just include all dependencies
                                if ";" not in req_part or "extra ==" not in req_part:
                                    self.dependencies.add(dep_name)
            except Exception:
                pass

def scan_packages(site_packages: Path) -> Dict[str, PackageInfo]:
    """Scans site-packages directory and builds PackageInfo database."""
    packages: Dict[str, PackageInfo] = {}
    
    # Locate all metadata directories (.dist-info or .egg-info)
    for path in site_packages.iterdir():
        if path.is_dir() and (path.suffix in (".dist-info", ".egg-info")):
            # Parse package name and version from directory name: e.g. requests-2.28.1.dist-info
            name_ver = path.stem
            parts = name_ver.split("-")
            if len(parts) >= 2:
                # Name can contain dashes, reconstruct it
                version = parts[-1]
                name = "-".join(parts[:-1]).lower().replace("_", "-")
                
                pkg_info = PackageInfo(name, version, path)
                pkg_info.calculate_size(site_packages)
                pkg_info.parse_dependencies()
                packages[name] = pkg_info
                
    return packages

def resolve_cumulative_sizes(packages: Dict[str, PackageInfo]) -> None:
    """Calculates transitive dependency sizes recursively."""
    visited: Set[str] = set()
    
    def calculate_cumulative(pkg_name: str) -> int:
        if pkg_name not in packages:
            return 0
        pkg = packages[pkg_name]
        if pkg.is_resolved:
            return pkg.cumulative_size
            
        # Prevent infinite loops in circular dependencies
        if pkg_name in visited:
            return pkg.own_size
        visited.add(pkg_name)
        
        total = pkg.own_size
        for dep in pkg.dependencies:
            # Map underscores/case normalization
            normalized_dep = dep.lower().replace("_", "-")
            if normalized_dep in packages:
                total += calculate_cumulative(normalized_dep)
                
        pkg.cumulative_size = total
        pkg.is_resolved = True
        visited.remove(pkg_name)
        return total

    for name in packages:
        calculate_cumulative(name)

def print_tree(packages: Dict[str, PackageInfo], pkg_name: str, indent: str = "", is_last: bool = True, visited: Optional[Set[str]] = None) -> None:
    """Helper to print hierarchical dependency tree with sizes."""
    if visited is None:
        visited = set()
        
    if pkg_name not in packages:
        return

    pkg = packages[pkg_name]
    marker = "└── " if is_last else "├── "
    
    name_str = color_text(f"{pkg.name} ({pkg.version})", COLOR_BOLD + COLOR_CYAN)
    own_sz = format_size(pkg.own_size)
    cum_sz = format_size(pkg.cumulative_size)
    size_str = f" [Own: {color_text(own_sz, COLOR_GREEN)} | Cum: {color_text(cum_sz, COLOR_YELLOW)}]"
    
    print(f"{indent}{marker}{name_str}{size_str}")
    
    if pkg_name in visited:
        # Circular dep warning
        print(f"{indent}    └── {color_text('(... circular reference ...)', COLOR_RED)}")
        return
        
    visited.add(pkg_name)
    next_indent = indent + ("    " if is_last else "│   ")
    
    # Filter dependencies present in our installed packages list
    installed_deps = [d.lower().replace("_", "-") for d in pkg.dependencies]
    installed_deps = [d for d in installed_deps if d in packages]
    # Sort dependencies by cumulative size descending
    installed_deps.sort(key=lambda x: packages[x].cumulative_size, reverse=True)
    
    for i, dep in enumerate(installed_deps):
        print_tree(packages, dep, next_indent, i == len(installed_deps) - 1, visited.copy())

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Python Virtual Environment Dependency Size Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-p", "--path", help="Path to site-packages directory (auto-detected if omitted)")
    parser.add_argument("-t", "--tree", help="View dependency tree of a specific package")
    parser.add_argument("-s", "--sort", choices=["own", "cumulative"], default="cumulative", help="Sort packages list by own or cumulative size (default: cumulative)")
    parser.add_argument("-n", "--limit", type=int, default=30, help="Limit flat list output to top N packages (default: 30)")
    
    args = parser.parse_args()
    
    # Resolve site-packages path
    site_packages_path = None
    if args.path:
        site_packages_path = Path(args.path)
    else:
        site_packages_path = get_default_site_packages()
        
    if not site_packages_path or not site_packages_path.is_dir():
        print(color_text("Error: Could not locate a valid site-packages directory.", COLOR_RED), file=sys.stderr)
        print("Please activate your virtual environment or specify the path explicitly using -p/--path.", file=sys.stderr)
        return 1
        
    print(f"Analyzing virtual environment site-packages: {color_text(str(site_packages_path.resolve()), COLOR_BOLD)}")
    print("-" * 80)
    
    packages = scan_packages(site_packages_path)
    if not packages:
        print("No installed packages (metadata folders .dist-info or .egg-info) found in site-packages.")
        return 0
        
    resolve_cumulative_sizes(packages)
    
    # Handle tree visualization
    if args.tree:
        target = args.tree.lower().replace("_", "-")
        if target not in packages:
            print(color_text(f"Error: Package '{args.tree}' not found in site-packages.", COLOR_RED), file=sys.stderr)
            return 1
        print(f"Dependency size tree for {color_text(args.tree, COLOR_BOLD + COLOR_CYAN)}:")
        print_tree(packages, target)
        print("-" * 80)
        return 0

    # Handle list visualization
    sort_key = "own_size" if args.sort == "own" else "cumulative_size"
    sorted_pkgs = sorted(packages.values(), key=lambda x: getattr(x, sort_key), reverse=True)
    
    print(f"Top {args.limit} Installed Packages (Sorted by {args.sort.upper()} size):")
    print(f"{COLOR_BOLD}{'PACKAGE':<30} | {'VERSION':<12} | {'OWN SIZE':<12} | {'CUMULATIVE SIZE'}{COLOR_RESET}")
    print("-" * 80)
    
    for pkg in sorted_pkgs[:args.limit]:
        own_sz = format_size(pkg.own_size)
        cum_sz = format_size(pkg.cumulative_size)
        
        # Style coloring based on size threshold
        size_color = COLOR_RESET
        if pkg.own_size > 10 * 1024 * 1024: # >10MB
            size_color = COLOR_RED
        elif pkg.own_size > 2 * 1024 * 1024: # >2MB
            size_color = COLOR_YELLOW
        else:
            size_color = COLOR_GREEN
            
        print(f"{pkg.name:<30} | {pkg.version:<12} | {color_text(own_sz, size_color):<12} | {color_text(cum_sz, COLOR_CYAN)}")
        
    print("-" * 80)
    print(f"Total Packages Scanned: {len(packages)}")
    total_size = sum(pkg.own_size for pkg in packages.values())
    print(f"Total Size of site-packages: {color_text(format_size(total_size), COLOR_BOLD + COLOR_GREEN)}")
    print("To visualize a specific package's dependencies, run with: --tree <package-name>")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
