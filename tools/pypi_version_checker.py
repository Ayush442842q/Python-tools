#!/usr/bin/env python3
"""
PyPI Version Checker & Dependency Update Utility
Queries the PyPI API to check if installed or listed packages have updates available.
"""
import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime

# Simple version parsing and comparison (pure Python, PEP 440-like subset)
def parse_version(ver_str):
    """
    Parse version string into a tuple of components: (major, minor, patch, pre_release_type, pre_release_num).
    Ensures easy comparison.
    """
    # Clean version string (remove leading v, etc.)
    ver_str = ver_str.strip().lstrip('v')
    
    # Check for basic release components
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$", ver_str)
    if not match:
        return (0, 0, 0, 'z', 0)  # Unknown format
        
    major = int(match.group(1))
    minor = int(match.group(2)) if match.group(2) else 0
    patch = int(match.group(3)) if match.group(3) else 0
    extra = match.group(4).lower() if match.group(4) else ""
    
    # Simple prerelease classifier
    pre_type = 'z'  # 'z' means final release, which sorts after pre-releases
    pre_num = 0
    
    pre_match = re.search(r"(a|b|rc|alpha|beta|pre|preview|dev)(\d*)", extra)
    if pre_match:
        t = pre_match.group(1)
        if t in ('a', 'alpha'):
            pre_type = 'a'
        elif t in ('b', 'beta'):
            pre_type = 'b'
        elif t in ('rc', 'pre', 'preview'):
            pre_type = 'rc'
        elif t == 'dev':
            pre_type = 'dev'
            
        pre_num = int(pre_match.group(2)) if pre_match.group(2) else 0
        
    return (major, minor, patch, pre_type, pre_num)

def is_version_newer(current_ver, latest_ver):
    """Return True if latest_ver is newer than current_ver."""
    return parse_version(latest_ver) > parse_version(current_ver)

def get_pypi_info(package_name):
    """Fetch package metadata from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    headers = {"User-Agent": "PyPI-Version-Checker/1.0 (Python standalone utility)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            info = data.get("info", {})
            releases = data.get("releases", {})
            
            latest_version = info.get("version", "")
            release_date = ""
            
            # Find upload time for the latest version
            if latest_version in releases and releases[latest_version]:
                upload_time = releases[latest_version][0].get("upload_time_iso_8601", "")
                if upload_time:
                    try:
                        dt = datetime.strptime(upload_time.split('T')[0], "%Y-%m-%d")
                        release_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        release_date = upload_time.split('T')[0]
                        
            return {
                "name": info.get("name", package_name),
                "latest_version": latest_version,
                "release_date": release_date,
                "summary": info.get("summary", ""),
                "home_page": info.get("home_page", info.get("project_url", ""))
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": "Package not found on PyPI"}
        return {"error": f"HTTP Error {e.code}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def parse_requirements(file_path):
    """Parse a requirements.txt file and extract packages and current versions."""
    packages = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Ignore comments, empty lines, and editables
                if not line or line.startswith('#') or line.startswith('-e'):
                    continue
                
                # Split at version specifiers
                # Matches ==, >=, <=, ~=, >, <, !=
                match = re.match(r"^([a-zA-Z0-9_\-\[\]]+)\s*(?:(==|>=|<=|~=|!=|>|<)\s*([a-zA-Z0-9_\-\.\+abrc]+))?.*$", line)
                if match:
                    pkg_name = match.group(1)
                    specifier = match.group(2) if match.group(2) else ""
                    version = match.group(3) if match.group(3) else ""
                    packages.append((pkg_name, version, specifier))
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        
    return packages

def main():
    parser = argparse.ArgumentParser(description="Check PyPI packages for newer versions.")
    parser.add_argument("packages", nargs="*", help="Specific packages to check (e.g. requests flask)")
    parser.add_argument("-r", "--requirements", help="Path to requirements.txt file to parse")
    parser.add_argument("-s", "--show-all", action="store_true", help="Show all packages, not just outdated ones")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print extra details like package summary")
    
    args = parser.parse_args()
    
    targets = []
    
    # If a requirements file is specified
    if args.requirements:
        targets.extend(parse_requirements(args.requirements))
    # If package names are provided directly
    elif args.packages:
        for pkg in args.packages:
            # Check if package arg contains version (e.g. requests==2.28.1)
            parts = re.split(r"==|>=|<=|~=", pkg)
            if len(parts) == 2:
                targets.append((parts[0].strip(), parts[1].strip(), "=="))
            else:
                targets.append((pkg.strip(), "", ""))
    # Default: try to find requirements.txt in current directory
    else:
        import os
        if os.path.exists("requirements.txt"):
            print("No packages specified. Found requirements.txt in current directory.")
            targets.extend(parse_requirements("requirements.txt"))
        else:
            parser.print_help()
            sys.exit(0)
            
    if not targets:
        print("No packages to check.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Checking {len(targets)} packages against PyPI...\n")
    
    # Header
    print(f"{'Package':<25} | {'Current':<15} | {'Latest':<15} | {'Status':<12} | {'Release Date'}")
    print("-" * 80)
    
    outdated_count = 0
    
    for pkg_name, current_ver, specifier in targets:
        pypi_info = get_pypi_info(pkg_name)
        
        if "error" in pypi_info:
            print(f"{pkg_name:<25} | {current_ver or 'N/A':<15} | {'N/A':<15} | {pypi_info['error']:<12} | -")
            continue
            
        latest_ver = pypi_info["latest_version"]
        release_date = pypi_info["release_date"]
        
        status = "Up-to-date"
        is_outdated = False
        
        if current_ver:
            if is_version_newer(current_ver, latest_ver):
                status = "OUTDATED"
                is_outdated = True
                outdated_count += 1
        else:
            status = "Check (No Local)"
            current_ver = "-"
            
        # Display
        if args.show_all or is_outdated or current_ver == "-":
            print(f"{pkg_name:<25} | {current_ver:<15} | {latest_ver:<15} | {status:<12} | {release_date}")
            if args.verbose and pypi_info["summary"]:
                print(f"  Summary: {pypi_info['summary']}")
                if pypi_info["home_page"]:
                    print(f"  Homepage: {pypi_info['home_page']}")
                print()
                
    print("-" * 80)
    print(f"Status check finished. Outdated packages found: {outdated_count}")

if __name__ == "__main__":
    main()
