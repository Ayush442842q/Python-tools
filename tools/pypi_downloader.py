#!/usr/bin/env python3
"""
PyPI Offline Package Downloader
Downloads a package and all its recursive dependencies from PyPI to a local directory
for offline/air-gapped installation.
Generates an offline installation script (install.bat and install.sh).
Uses standard libraries only.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from typing import Dict, List, Set, Any, Tuple, Optional

# Simple environment marker parser
def evaluate_marker(marker_str: str, python_version: str = "3.8", platform: str = "linux") -> bool:
    """
    Very basic marker evaluation. Handles simple markers like:
    python_version < "3.7"
    sys_platform == "win32"
    extra == "security" (we ignore extras by default)
    """
    if not marker_str:
        return True
    
    # We generally ignore extra dependencies
    if "extra ==" in marker_str or "extra !=" in marker_str:
        return False
        
    # Check platform markers
    if "sys_platform" in marker_str:
        is_win = "win" in platform.lower()
        if "win32" in marker_str:
            return is_win if "==" in marker_str else not is_win
            
    # Check python version
    py_match = re.search(r"python_version\s*(<=|>=|<|>|==)\s*['\"]([^'\"]+)['\"]", marker_str)
    if py_match:
        op, ver = py_match.groups()
        curr_ver = [int(x) for x in python_version.split('.')]
        target_ver = [int(x) for x in ver.split('.')]
        # Pad versions to match length
        while len(curr_ver) < len(target_ver): curr_ver.append(0)
        while len(target_ver) < len(curr_ver): target_ver.append(0)
        
        if op == "==": return curr_ver == target_ver
        elif op == "<": return curr_ver < target_ver
        elif op == "<=": return curr_ver <= target_ver
        elif op == ">": return curr_ver > target_ver
        elif op == ">=": return curr_ver >= target_ver
        
    return True


def parse_requirement(req_str: str) -> Tuple[str, Optional[str]]:
    """
    Parses a PEP 508 requirement string.
    Returns (package_name, environment_marker_string).
    Examples:
      requests (>=2.0) -> ('requests', None)
      requests; python_version < "3.8" -> ('requests', 'python_version < "3.8"')
    """
    # Remove whitespace
    req_str = req_str.strip()
    
    # Split marker
    marker = None
    if ";" in req_str:
        req_str, marker = req_str.split(";", 1)
        marker = marker.strip()
        
    # Extract package name (first alphanumeric sequence plus dashes/underscores/dots)
    match = re.match(r"^([a-zA-Z0-9_\-\.]+)", req_str)
    if not match:
        return req_str.strip(), marker
        
    name = match.group(1).lower().replace('_', '-').strip()
    return name, marker


class PyPIDownloader:
    """Recursive PyPI packages and dependencies downloader."""
    def __init__(self, dest_dir: str, python_version: str = "3.8", platform: str = "win32", py_impl: str = "cp"):
        self.dest_dir = dest_dir
        self.python_version = python_version
        self.platform = platform
        self.py_impl = py_impl
        self.downloaded_packages: Set[str] = set()
        self.pending_packages: List[str] = []
        self.requirements_list: List[str] = []
        
        os.makedirs(dest_dir, exist_ok=True)

    def fetch_package_json(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Queries PyPI JSON API for package metadata."""
        url = f"https://pypi.org/pypi/{urllib.parse.quote(package_name)}/json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PyPI-Offline-Downloader'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"[-] Error fetching metadata for '{package_name}': {e}", file=sys.stderr)
            return None

    def find_best_release(self, releases: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Finds the best matching release file (wheels matching target platform, or source distribution fallback).
        """
        wheels = []
        sdist = None
        
        for rel in releases:
            pkg_type = rel.get("packagetype", "")
            filename = rel.get("filename", "")
            
            if pkg_type == "bdist_wheel":
                wheels.append(rel)
            elif pkg_type == "sdist":
                sdist = rel
                
        # Filter wheels by compatibility
        # Wheel name: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
        compat_wheels = []
        for w in wheels:
            filename = w["filename"]
            parts = filename[:-4].split('-')
            if len(parts) < 5:
                continue
            
            py_tag, abi_tag, plat_tag = parts[-3], parts[-2], parts[-1]
            
            # Simple check for Python version tags (e.g. py3, cp38, cp3)
            py_ver_nodot = self.python_version.replace(".", "")
            py_compat = (
                py_tag == "py2.py3" or
                py_tag == "py3" or
                py_tag == f"py{py_ver_nodot[0]}" or
                py_tag == f"{self.py_impl}{py_ver_nodot}" or
                py_tag == f"{self.py_impl}{py_ver_nodot[0]}"
            )
            
            # Simple check for platform tags (e.g. win_amd64, manylinux)
            plat_compat = (
                plat_tag == "any" or
                self.platform in plat_tag or
                (self.platform == "win32" and "win" in plat_tag) or
                (self.platform == "linux" and "linux" in plat_tag) or
                (self.platform == "darwin" and "macosx" in plat_tag)
            )
            
            if py_compat and plat_compat:
                compat_wheels.append(w)
                
        if compat_wheels:
            # Sort by file size or prefer binary wheel
            return compat_wheels[0]
            
        # Fall back to source distribution if no matching wheel
        return sdist

    def download_file(self, url: str, filename: str):
        """Downloads a file with a command-line progress bar."""
        filepath = os.path.join(self.dest_dir, filename)
        if os.path.exists(filepath):
            print(f"[#] File already downloaded: {filename}")
            return
            
        print(f"[*] Downloading {filename}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_downloaded = 0
                block_size = 8192
                
                with open(filepath, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        bytes_downloaded += len(buffer)
                        f.write(buffer)
                        
                        # Progress bar
                        if total_size > 0:
                            percent = int(bytes_downloaded * 100 / total_size)
                            bar = '#' * (percent // 5) + '-' * (20 - (percent // 5))
                            sys.stdout.write(f"\r[{bar}] {percent}% ({bytes_downloaded // 1024} KB / {total_size // 1024} KB)")
                            sys.stdout.flush()
                print("\n[+] Download complete!")
        except Exception as e:
            print(f"\n[-] Error downloading file from {url}: {e}", file=sys.stderr)
            if os.path.exists(filepath):
                os.remove(filepath)

    def process_package(self, package_name: str):
        """Downloads metadata, resolves dependencies, and downloads the best matching release."""
        clean_name, _ = parse_requirement(package_name)
        if clean_name in self.downloaded_packages:
            return
            
        print(f"\n[+] Processing package: {clean_name}")
        metadata = self.fetch_package_json(clean_name)
        if not metadata:
            return
            
        info = metadata.get("info", {})
        version = info.get("version", "")
        print(f"[*] Latest Version: {version}")
        
        # Add to requirements list
        self.requirements_list.append(f"{clean_name}=={version}")
        
        # Find best matching file
        releases = metadata.get("urls", [])
        best_release = self.find_best_release(releases)
        
        if best_release:
            self.download_file(best_release["url"], best_release["filename"])
            self.downloaded_packages.add(clean_name)
        else:
            print(f"[-] No matching wheels or source distributions found for '{clean_name}' on target setup.")
            return

        # Parse dependencies
        requires_dist = info.get("requires_dist", [])
        if requires_dist:
            print(f"[*] Analyzing dependencies for {clean_name}...")
            for req in requires_dist:
                dep_name, marker = parse_requirement(req)
                # Evaluate markers to check if needed for target environment
                if evaluate_marker(marker, self.python_version, self.platform):
                    if dep_name not in self.downloaded_packages and dep_name not in self.pending_packages:
                        print(f"  -> Found dependency: {dep_name} (Marker: {marker})")
                        self.pending_packages.append(dep_name)

    def run(self, initial_package: str):
        """Starts recursive package downloads."""
        self.pending_packages.append(initial_package)
        while self.pending_packages:
            pkg = self.pending_packages.pop(0)
            self.process_package(pkg)
            
        self.write_installer_scripts()

    def write_installer_scripts(self):
        """Generates offline requirements file and installation scripts."""
        # Write requirements.txt
        req_path = os.path.join(self.dest_dir, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as f:
            for req in sorted(self.requirements_list):
                f.write(f"{req}\n")
        print(f"\n[+] Created requirements file: {req_path}")
        
        # Write install.bat (Windows)
        bat_path = os.path.join(self.dest_dir, "install.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("echo Installing offline packages...\n")
            f.write("pip install --no-index --find-links=. -r requirements.txt\n")
            f.write("pause\n")
        print(f"[+] Created Windows installer script: {bat_path}")
        
        # Write install.sh (Linux/macOS)
        sh_path = os.path.join(self.dest_dir, "install.sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write("echo \"Installing offline packages...\"\n")
            f.write("pip install --no-index --find-links=. -r requirements.txt\n")
        # Try to make executable
        try:
            os.chmod(sh_path, 0o755)
        except Exception:
            pass
        print(f"[+] Created Linux/macOS installer script: {sh_path}")


def main():
    parser = argparse.ArgumentParser(
        description="PyPI Offline Package Downloader - Download packages and dependencies recursively for offline installations."
    )
    parser.add_argument("package", help="Name of PyPI package to download (e.g. requests)")
    parser.add_argument(
        "-d", "--dir",
        help="Destination directory to save packages. Defaults to 'pypi_downloads/<package>'"
    )
    parser.add_argument(
        "--py-version",
        dest="py_version",
        default="3.8",
        help="Target Python version (default: 3.8)"
    )
    parser.add_argument(
        "--platform",
        default="win32",
        choices=["win32", "linux", "darwin"],
        help="Target OS platform (default: win32)"
    )
    parser.add_argument(
        "--impl",
        default="cp",
        help="Target Python implementation (default: cp for CPython)"
    )
    
    args = parser.parse_args()
    
    dest_dir = args.dir or f"pypi_downloads_{args.package}"
    
    print(f"[*] Target Python Version: {args.py_version}")
    print(f"[*] Target Platform: {args.platform}")
    print(f"[*] Destination Directory: {dest_dir}")
    
    downloader = PyPIDownloader(
        dest_dir=dest_dir,
        python_version=args.py_version,
        platform=args.platform,
        py_impl=args.impl
    )
    
    downloader.run(args.package)
    print("\n[+] All tasks finished! Offline package bundle is ready.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
