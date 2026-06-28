#!/usr/bin/env python3
"""
Pip License Compliance Auditor

Scan project requirements or virtual environment packages, fetch license metadata,
and audit them against allowed/disallowed lists to ensure legal compliance.

Usage:
    python tools/pip_license_auditor.py [options]

Requirements:
    - Python 3.6+
    - Optional: requests (will fall back to urllib if not installed)
"""

import sys
import os
import argparse
import json
import urllib.request
import urllib.error
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Try to use importlib.metadata (Python 3.8+) or pkg_resources (older)
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    try:
        import pkg_resources as importlib_metadata # type: ignore
    except ImportError:
        importlib_metadata = None # type: ignore

# Default license groups
PERMISSIVE_LICENSES = {"mit", "apache", "apache-2.0", "bsd", "bsd-2-clause", "bsd-3-clause", "isc", "unlicense", "wtfpl", "cc0"}
COPYLEFT_LICENSES = {"gpl", "gpl-2.0", "gpl-3.0", "lgpl", "lgpl-2.1", "lgpl-3.0", "agpl", "agpl-3.0", "mpl", "mpl-2.0", "cddl", "epl"}

def normalize_license(license_str: Optional[str]) -> str:
    """Normalize license string for easier categorization."""
    if not license_str:
        return "unknown"
    
    # Strip spaces and convert to lowercase
    lic = license_str.strip().lower()
    
    # Remove common qualifiers / punctuation
    lic = re.sub(r'[\(\)\[\]\.\d\- ]', '', lic)
    
    # Map common variations
    if "mit" in lic:
        return "mit"
    if "apache" in lic:
        return "apache-2.0"
    if "bsd" in lic:
        return "bsd"
    if "gpl" in lic:
        if "lgpl" in lic:
            return "lgpl"
        if "agpl" in lic:
            return "agpl"
        return "gpl"
    if "mozilla" in lic or "mpl" in lic:
        return "mpl"
    if "eclipse" in lic or "epl" in lic:
        return "epl"
    if "commondevelopment" in lic or "cddl" in lic:
        return "cddl"
    if "isc" in lic:
        return "isc"
    if "unlicense" in lic:
        return "unlicense"
    if "publicdomain" in lic or "cc0" in lic:
        return "cc0"
    
    return license_str.strip()

def get_local_packages() -> Dict[str, str]:
    """Retrieve installed packages and their versions from local environment."""
    packages = {}
    if not importlib_metadata:
        return packages
    
    try:
        # For importlib.metadata (Python 3.8+)
        if hasattr(importlib_metadata, "distributions"):
            for dist in importlib_metadata.distributions(): # type: ignore
                packages[dist.metadata["Name"].lower()] = dist.version
        # Fallback for pkg_resources
        elif hasattr(importlib_metadata, "working_set"):
            for dist in importlib_metadata.working_set: # type: ignore
                packages[dist.project_name.lower()] = dist.version
    except Exception as e:
        print(f"Warning: Failed to read local environment packages: {e}", file=sys.stderr)
        
    return packages

def parse_requirements(req_path: str) -> Dict[str, Optional[str]]:
    """Parse requirements.txt file and return package names and optional specifiers."""
    packages = {}
    path = Path(req_path)
    if not path.is_file():
        print(f"Error: Requirements file not found: {req_path}", file=sys.stderr)
        return packages
    
    # Regular expression to extract package name and basic version
    req_re = re.compile(r'^([a-zA-Z0-9_\-\[\]]+)(?:==|>=|<=|>|<|~=)?([^#\s]*)')
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines or other file options (-r, -e, etc)
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            match = req_re.match(line)
            if match:
                pkg_name = match.group(1).lower()
                version = match.group(2).strip() or None
                packages[pkg_name] = version
    return packages

def fetch_license_from_pypi(package_name: str, version: Optional[str] = None) -> Tuple[str, str]:
    """Fetch license and version info from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'pip-license-auditor/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            info = data.get("info", {})
            license_str = info.get("license") or "Unknown"
            
            # Sometimes PyPI license field is empty or contains the entire license text, 
            # check Classifiers as a fallback
            classifiers = info.get("classifiers", [])
            for classifier in classifiers:
                if classifier.startswith("License ::"):
                    parts = classifier.split("::")
                    if len(parts) > 1:
                        # Use classifiers if main license field is too long or empty
                        cls_license = parts[-1].strip()
                        if license_str == "Unknown" or len(license_str) > 100:
                            license_str = cls_license
                            break
                            
            return license_str, info.get("version", version or "unknown")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "Package not found on PyPI", "unknown"
        return f"HTTP Error {e.code}", "unknown"
    except Exception as e:
        return f"Error: {e}", "unknown"

def audit_packages(packages: Dict[str, Optional[str]], whitelist: Set[str], blacklist: Set[str], scan_pypi: bool) -> List[dict]:
    """Audit parsed packages against licenses."""
    results = []
    local_packages = get_local_packages() if not scan_pypi else {}
    
    total = len(packages)
    for idx, (pkg_name, req_version) in enumerate(packages.items(), 1):
        print(f"Auditing [{idx}/{total}]: {pkg_name}...", end="", flush=True)
        
        license_str = "Unknown"
        resolved_version = req_version or "unknown"
        
        # Method 1: Check local installation first if available
        if importlib_metadata and not scan_pypi:
            try:
                # Find local distribution
                dist = None
                try:
                    dist = importlib_metadata.distribution(pkg_name)
                except Exception:
                    # Try with normalized name (e.g., replacing dashes with underscores)
                    try:
                        dist = importlib_metadata.distribution(pkg_name.replace('-', '_'))
                    except Exception:
                        pass
                
                if dist:
                    resolved_version = dist.version
                    # Inspect metadata
                    metadata = dist.metadata
                    # License info in metadata can be in "License" or "Classifier" headers
                    license_str = metadata.get("License") or "Unknown"
                    if license_str == "Unknown" or len(license_str) > 100:
                        # Fallback to classifiers
                        classifiers = metadata.get_all("Classifier") or []
                        for classifier in classifiers:
                            if classifier.startswith("License ::"):
                                parts = classifier.split("::")
                                if len(parts) > 1:
                                    license_str = parts[-1].strip()
                                    break
            except Exception:
                pass
                
        # Method 2: If local failed or --online flag is active, fetch from PyPI
        if license_str == "Unknown" or license_str.startswith("Error") or scan_pypi:
            # Query PyPI
            pypi_lic, pypi_ver = fetch_license_from_pypi(pkg_name, req_version)
            if pypi_lic != "Package not found on PyPI" and not pypi_lic.startswith("HTTP Error"):
                license_str = pypi_lic
                if resolved_version == "unknown":
                    resolved_version = pypi_ver
                    
        normalized = normalize_license(license_str)
        
        # Decide compliance status
        status = "APPROVED"
        reason = ""
        
        if blacklist:
            # Check if normalized or raw license is blacklisted
            if normalized in blacklist or license_str.lower() in blacklist:
                status = "FAILED"
                reason = "Blacklisted license"
        elif whitelist:
            # If whitelist exists, it must be on whitelist
            if normalized not in whitelist and license_str.lower() not in whitelist:
                status = "FAILED"
                reason = "Not on whitelist"
        else:
            # Default audit logic: warn if copyleft
            if normalized in COPYLEFT_LICENSES:
                status = "WARNING"
                reason = "Copyleft license (review compliance)"
            elif normalized == "unknown":
                status = "WARNING"
                reason = "Could not identify license"
                
        print(f" {status} ({license_str})")
        
        results.append({
            "package": pkg_name,
            "version": resolved_version,
            "license": license_str,
            "normalized": normalized,
            "status": status,
            "reason": reason
        })
        
    return results

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit project dependencies (requirements.txt or virtual environment) for license compliance.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--requirements", "-r",
        help="Path to requirements.txt file to audit"
    )
    group.add_argument(
        "--local", "-l",
        action="store_true",
        help="Audit currently installed packages in the local Python environment"
    )
    
    parser.add_argument(
        "--online", "-o",
        action="store_true",
        help="Force querying PyPI API even for local packages"
    )
    parser.add_argument(
        "--whitelist", "-w",
        help="Comma-separated list of allowed licenses (e.g. mit,apache-2.0,bsd)"
    )
    parser.add_argument(
        "--blacklist", "-b",
        help="Comma-separated list of prohibited licenses (e.g. gpl,agpl)"
    )
    parser.add_argument(
        "--json-output", "-j",
        help="Save report to a JSON file"
    )
    parser.add_argument(
        "--markdown", "-m",
        help="Save report as a Markdown table"
    )
    
    args = parser.parse_args()
    
    # Parse white/black lists
    whitelist = set()
    if args.whitelist:
        whitelist = {x.strip().lower() for x in args.whitelist.split(",")}
        
    blacklist = set()
    if args.blacklist:
        blacklist = {x.strip().lower() for x in args.blacklist.split(",")}
        
    # Get packages to scan
    packages = {}
    if args.requirements:
        packages = parse_requirements(args.requirements)
        if not packages:
            return 1
    elif args.local:
        local = get_local_packages()
        if not local:
            print("Error: No packages found in local environment or importlib.metadata is unavailable.", file=sys.stderr)
            return 1
        packages = {k: v for k, v in local.items()}
    else:
        # Try requirements.txt in current folder, fallback to local venv
        default_req = Path("requirements.txt")
        if default_req.is_file():
            print(f"No source specified. Defaulting to local '{default_req}' file...")
            packages = parse_requirements(str(default_req))
        else:
            print("No source specified. Defaulting to local installed environment...")
            local = get_local_packages()
            if not local:
                print("Error: No package sources available to audit.", file=sys.stderr)
                return 1
            packages = {k: v for k, v in local.items()}
            
    print(f"Starting license compliance audit for {len(packages)} packages...")
    results = audit_packages(packages, whitelist, blacklist, args.online)
    
    # Print summary
    approved = sum(1 for r in results if r["status"] == "APPROVED")
    warnings = sum(1 for r in results if r["status"] == "WARNING")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    
    print("\n" + "="*50)
    print("AUDIT SUMMARY")
    print("="*50)
    print(f"Total Packages Scanned: {len(results)}")
    print(f"Approved:               {approved}")
    print(f"Warnings:               {warnings}")
    print(f"Failed/Non-compliant:   {failed}")
    print("="*50)
    
    # Display failed or warning packages
    issues = [r for r in results if r["status"] in ("FAILED", "WARNING")]
    if issues:
        print("\nIDENTIFIED ISSUES:")
        print(f"{'Package':<25} {'Version':<10} {'Status':<10} {'License':<20} {'Reason'}")
        print("-" * 85)
        for issue in issues:
            print(f"{issue['package']:<25} {issue['version']:<10} {issue['status']:<10} {issue['license'][:20]:<20} {issue['reason']}")
            
    # Output file handling
    if args.json_output:
        try:
            with open(args.json_output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4)
            print(f"\nSaved JSON report to {args.json_output}")
        except Exception as e:
            print(f"Error saving JSON file: {e}", file=sys.stderr)
            
    if args.markdown:
        try:
            with open(args.markdown, 'w', encoding='utf-8') as f:
                f.write("# Dependency License Compliance Report\n\n")
                f.write(f"Generated packages audit summary:\n\n")
                f.write(f"- **Total Packages**: {len(results)}\n")
                f.write(f"- **Approved**: {approved}\n")
                f.write(f"- **Warnings**: {warnings}\n")
                f.write(f"- **Failed**: {failed}\n\n")
                
                f.write("## Detailed Audit Results\n\n")
                f.write("| Package | Version | License | Normalized | Status | Reason |\n")
                f.write("| --- | --- | --- | --- | --- | --- |\n")
                for r in results:
                    f.write(f"| {r['package']} | {r['version']} | {r['license']} | {r['normalized']} | {r['status']} | {r['reason']} |\n")
            print(f"Saved Markdown report to {args.markdown}")
        except Exception as e:
            print(f"Error saving Markdown file: {e}", file=sys.stderr)
            
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
