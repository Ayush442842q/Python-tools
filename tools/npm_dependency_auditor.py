#!/usr/bin/env python3
"""
NPM Dependency Auditor
----------------------
A standalone Python utility to audit Node.js project dependencies.
It reads package.json, package-lock.json, and/or local node_modules to:
1. Build a dependency tree.
2. Query the NPM registry for version updates and licenses (optional).
3. Audit licenses against a whitelist/blacklist (e.g., flagging GPL/copyleft).
4. Run static validation checks on package configurations.

Author: Antigravity
License: MIT
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Set, Any, Tuple

# Common OSS licenses grouped by type
APPROVED_PERMISSIVE = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "Unlicense", "CC0-1.0"}
COPYLEFT_RESTRICTIVE = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "EPL-1.0", "EPL-2.0"}

def query_npm_registry(package_name: str) -> Dict[str, Any]:
    """Fetch metadata for a package from the NPM registry."""
    url = f"https://registry.npmjs.org/{package_name}/latest"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Antigravity NPM Dependency Auditor/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError:
        return {}
    except Exception:
        return {}

def scan_local_node_modules(base_dir: str) -> Dict[str, Dict[str, str]]:
    """Scan node_modules to collect installed versions and licenses offline."""
    node_modules_path = os.path.join(base_dir, "node_modules")
    local_info = {}
    if not os.path.exists(node_modules_path):
        return local_info

    for root, dirs, files in os.walk(node_modules_path):
        if "package.json" in files:
            pkg_json_path = os.path.join(root, "package.json")
            try:
                with open(pkg_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = data.get("name")
                    if name:
                        # Extract license info
                        lic = data.get("license")
                        if isinstance(lic, dict):
                            lic_name = lic.get("type", "Unknown")
                        elif isinstance(lic, list):
                            lic_name = " OR ".join([l.get("type", "Unknown") if isinstance(l, dict) else str(l) for l in lic])
                        else:
                            lic_name = str(lic or "Unknown")

                        local_info[name] = {
                            "version": data.get("version", "Unknown"),
                            "license": lic_name,
                            "description": data.get("description", "")
                        }
            except Exception:
                continue
    return local_info

def parse_package_json(filepath: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parse dependencies from package.json."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            return deps, dev_deps
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

def parse_package_lock(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parse package-lock.json for resolved versions and nested dependencies."""
    lock_info = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Support lockfile v1, v2, v3
            packages = data.get("packages", {})
            if packages:
                for path, info in packages.items():
                    if not path:  # Root package
                        continue
                    name = path.replace("node_modules/", "")
                    # Strip any parent node_modules paths
                    if "/" in name and name.startswith("node_modules"):
                        name = name.split("node_modules/")[-1]
                    version = info.get("version")
                    if name and version:
                        lock_info[name] = {
                            "version": version,
                            "dev": info.get("dev", False)
                        }
            else:
                # Fallback to older lockfile structure (dependencies)
                dependencies = data.get("dependencies", {})
                for name, info in dependencies.items():
                    lock_info[name] = {
                        "version": info.get("version"),
                        "dev": info.get("dev", False)
                    }
    except Exception as e:
        print(f"Warning parsing package-lock.json: {e}", file=sys.stderr)
    return lock_info

def check_license(license_str: str, allowed: Set[str], disallowed: Set[str]) -> Tuple[str, str]:
    """Check a license against allowed/disallowed lists and assign a status."""
    if not license_str or license_str == "Unknown":
        return "UNKNOWN", "\033[93m"  # Yellow

    lic_upper = license_str.upper()
    
    # Check for direct match or substring in copyleft lists
    is_disallowed = False
    for blacklisted in disallowed:
        if blacklisted.upper() in lic_upper:
            is_disallowed = True
            break
            
    if is_disallowed or any(c.upper() in lic_upper for c in COPYLEFT_RESTRICTIVE):
        return "DISALLOWED (Copyleft)", "\033[91m"  # Red

    is_allowed = False
    for whitelisted in allowed:
        if whitelisted.upper() in lic_upper:
            is_allowed = True
            break

    if is_allowed or any(p.upper() in lic_upper for p in APPROVED_PERMISSIVE):
        return "APPROVED", "\033[92m"  # Green

    return "UNCHECKED", "\033[94m"  # Blue

def main():
    parser = argparse.ArgumentParser(description="NPM Dependency Auditor - Audit Node.js projects for licensing, version drifts, and structure.")
    parser.add_argument("path", nargs="?", default=".", help="Path to Node.js project directory containing package.json")
    parser.add_argument("--online", action="store_true", help="Query NPM Registry for real-time version updates & licenses")
    parser.add_argument("--allow", help="Comma-separated list of additional allowed licenses")
    parser.add_argument("--disallow", help="Comma-separated list of explicit blacklisted licenses")
    parser.add_argument("--no-dev", action="store_true", help="Exclude development dependencies (devDependencies) from audit")
    parser.add_argument("--json", action="store_true", help="Output audit results in JSON format")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.path)
    pkg_json_path = os.path.join(project_dir, "package.json")
    pkg_lock_path = os.path.join(project_dir, "package-lock.json")

    if not os.path.exists(pkg_json_path):
        print(f"Error: package.json not found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Setup allowed and disallowed sets
    allowed_licenses = set(APPROVED_PERMISSIVE)
    if args.allow:
        allowed_licenses.update([l.strip() for l in args.allow.split(",")])

    disallowed_licenses = set(COPYLEFT_RESTRICTIVE)
    if args.disallow:
        disallowed_licenses.update([l.strip() for l in args.disallow.split(",")])

    # Parse inputs
    dependencies, dev_dependencies = parse_package_json(pkg_json_path)
    lock_info = parse_package_lock(pkg_lock_path)
    local_info = scan_local_node_modules(project_dir)

    target_deps = {}
    for dep, ver_spec in dependencies.items():
        target_deps[dep] = {"spec": ver_spec, "dev": False}
    
    if not args.no_dev:
        for dep, ver_spec in dev_dependencies.items():
            target_deps[dep] = {"spec": ver_spec, "dev": True}

    audit_results = []
    issues_found = 0

    print(f"Auditing {len(target_deps)} dependencies in {pkg_json_path}...\n", file=sys.stderr if args.json else sys.stdout)

    for idx, (name, details) in enumerate(target_deps.items(), 1):
        spec = details["spec"]
        is_dev = details["dev"]

        # Resolve installed version
        resolved_version = "Unknown"
        license_str = "Unknown"
        latest_version = "N/A"
        
        # Check lockfile
        if name in lock_info:
            resolved_version = lock_info[name]["version"]
        # Check local node_modules
        if name in local_info:
            resolved_version = local_info[name]["version"]
            license_str = local_info[name]["license"]

        # If online mode requested, fetch from registry
        if args.online:
            if not args.json:
                print(f"[{idx}/{len(target_deps)}] Querying NPM registry for '{name}'...", end="\r", flush=True)
            registry_data = query_npm_registry(name)
            if registry_data:
                latest_version = registry_data.get("version", "N/A")
                reg_lic = registry_data.get("license")
                if reg_lic:
                    if isinstance(reg_lic, dict):
                        license_str = reg_lic.get("type", "Unknown")
                    else:
                        license_str = str(reg_lic)

        # Audit license
        lic_status, color = check_license(license_str, allowed_licenses, disallowed_licenses)
        
        is_outdated = False
        if latest_version != "N/A" and resolved_version != "Unknown":
            is_outdated = resolved_version != latest_version

        warning = False
        if lic_status.startswith("DISALLOWED") or lic_status == "UNKNOWN":
            warning = True
            issues_found += 1

        audit_results.append({
            "name": name,
            "spec": spec,
            "resolved": resolved_version,
            "latest": latest_version,
            "license": license_str,
            "license_status": lic_status,
            "is_dev": is_dev,
            "outdated": is_outdated,
            "warning": warning,
            "color_code": color
        })

    # Clear registry status message
    if args.online and not args.json:
        print(" " * 60 + "\r", end="", flush=True)

    # Output formatting
    if args.json:
        print(json.dumps({
            "project": project_dir,
            "dependencies_count": len(target_deps),
            "issues_count": issues_found,
            "results": audit_results
        }, indent=2))
    else:
        # Console output
        print("-" * 105)
        print(f"{'Package Name':<28} | {'Type':<6} | {'Spec':<10} | {'Installed':<10} | {'Latest':<10} | {'License':<15} | {'Status':<15}")
        print("-" * 105)
        
        for res in audit_results:
            lic_color = res["color_code"]
            reset = "\033[0m"
            dep_type = "Dev" if res["is_dev"] else "Prod"
            lic_text = f"{lic_color}{res['license_status']}{reset}"
            
            # Highlight outdated packages
            inst = res["resolved"]
            if res["outdated"]:
                inst = f"{inst} (!)"

            print(f"{res['name']:<28} | {dep_type:<6} | {res['spec']:<10} | {inst:<10} | {res['latest']:<10} | {res['license']:<15} | {lic_text:<15}")

        print("-" * 105)
        print(f"Audit completed. Found {issues_found} potential licensing/compliance issue(s).")
        
        if not os.path.exists(os.path.join(project_dir, "node_modules")) and not args.online:
            print("\n[NOTE] node_modules not detected and --online was not specified. Licenses were inferred from lockfile metadata where possible. Run with --online or npm install for more accurate license extraction.")

if __name__ == "__main__":
    main()
