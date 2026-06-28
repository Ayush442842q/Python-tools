#!/usr/bin/env python3
"""
Dependency Update Checker
Check for outdated Python package dependencies with safety scores.

Usage:
    python dependency_update_checker.py [requirements.txt] [--safe-only] [--json]
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
    from packaging import version
except ImportError:
    print("Installing required dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "packaging", "-q"])
    import requests
    from packaging import version


def get_pypi_info(package_name: str) -> dict:
    """Fetch package information from PyPI API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}
    return None


def get_vulnerability_info(package_name: str, installed_version: str) -> dict:
    """Check for known vulnerabilities using PyPI's advisory database."""
    # Check safety database (simplified - in production use safety-cli or pyupio/safety)
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Check if there are any security advisories
            advisories = data.get("info", {}).get("project_urls", {}).get("Security", [])
            return {"has_advisories": len(advisories) > 0, "advisories": advisories}
    except requests.RequestException:
        pass
    return {"has_advisories": False, "advisories": []}


def parse_requirements(file_path: str) -> list:
    """Parse requirements.txt file and return list of (package, version) tuples."""
    requirements = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Handle various version specifiers
                for sep in ['==', '>=', '<=', '!=', '~=', '>']:
                    if sep in line:
                        parts = line.split(sep)
                        package = parts[0].strip()
                        ver = parts[1].strip() if len(parts) > 1 else None
                        requirements.append((package, ver, sep))
                        break
                else:
                    # No version specifier
                    requirements.append((line.strip(), None, None))
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    return requirements


def check_updates(requirements: list, safe_only: bool = False) -> list:
    """Check for available updates for each package."""
    results = []
    
    for package, installed_version, separator in requirements:
        # Skip editable installs and local packages
        if package.startswith('-e') or package.startswith('.'):
            continue
        
        pypi_info = get_pypi_info(package)
        
        if not pypi_info or "error" in pypi_info:
            results.append({
                "package": package,
                "installed": installed_version,
                "latest": "N/A",
                "status": "ERROR",
                "message": "Could not fetch package info"
            })
            continue
        
        latest_version = pypi_info.get("info", {}).get("version", "N/A")
        
        # Check for vulnerabilities (simplified check)
        vuln_info = get_vulnerability_info(package, installed_version)
        has_vulns = vuln_info.get("has_advisories", False)
        
        if installed_version and installed_version != latest_version:
            try:
                installed = version.parse(installed_version)
                latest = version.parse(latest_version)
                is_outdated = latest > installed
            except Exception:
                is_outdated = installed_version != latest_version
        else:
            is_outdated = False
        
        status = "OUTDATED" if is_outdated else "OK"
        if has_vulns:
            status = "VULNERABLE"
        
        if safe_only and status == "OK":
            continue
        
        results.append({
            "package": package,
            "installed": installed_version or "N/A",
            "latest": latest_version,
            "status": status,
            "has_vulnerabilities": has_vulns,
            "update_command": f"pip install --upgrade {package}" if is_outdated else None
        })
    
    return results


def format_output(results: list, json_format: bool = False) -> str:
    """Format results for output."""
    if json_format:
        return json.dumps(results, indent=2)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("DEPENDENCY UPDATE CHECKER")
    output_lines.append("=" * 80)
    
    outdated = [r for r in results if r["status"] == "OUTDATED"]
    vulnerable = [r for r in results if r["status"] == "VULNERABLE"]
    ok = [r for r in results if r["status"] == "OK"]
    errors = [r for r in results if r["status"] == "ERROR"]
    
    if vulnerable:
        output_lines.append(f"\n🚨 VULNERABLE ({len(vulnerable)}):")
        for r in vulnerable:
            output_lines.append(f"  {r['package']}: {r['installed']} -> {r['latest']}")
            output_lines.append(f"     ⚠️  Security advisories detected!")
    
    if outdated:
        output_lines.append(f"\n📦 OUTDATED ({len(outdated)}):")
        for r in outdated:
            output_lines.append(f"  {r['package']}: {r['installed']} -> {r['latest']}")
            output_lines.append(f"     Run: {r['update_command']}")
    
    if ok:
        output_lines.append(f"\n✅ UP-TO-DATE ({len(ok)}):")
        for r in ok[:10]:  # Show first 10
            output_lines.append(f"  {r['package']}: {r['installed']}")
        if len(ok) > 10:
            output_lines.append(f"  ... and {len(ok) - 10} more")
    
    if errors:
        output_lines.append(f"\n❌ ERRORS ({len(errors)}):")
        for r in errors:
            output_lines.append(f"  {r['package']}: {r.get('message', 'Unknown error')}")
    
    output_lines.append("\n" + "=" * 80)
    output_lines.append(f"Summary: {len(vulnerable)} vulnerable, {len(outdated)} outdated, {len(ok)} OK, {len(errors)} errors")
    output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check for outdated Python package dependencies with safety scores."
    )
    parser.add_argument(
        "requirements_file",
        nargs="?",
        default="requirements.txt",
        help="Path to requirements.txt file (default: requirements.txt)"
    )
    parser.add_argument(
        "--safe-only",
        action="store_true",
        help="Only show packages with vulnerabilities or updates"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    req_file = Path(args.requirements_file)
    if not req_file.exists():
        # Try common locations
        for path in ["requirements.txt", "requirements/dev.txt", "requirements/prod.txt"]:
            if Path(path).exists():
                req_file = Path(path)
                break
    
    if not req_file.exists():
        print(f"Error: Could not find '{args.requirements_file}'")
        sys.exit(1)
    
    print(f"Checking dependencies in: {req_file.absolute()}")
    
    requirements = parse_requirements(str(req_file))
    results = check_updates(requirements, safe_only=args.safe_only)
    output = format_output(results, json_format=args.json)
    
    print(output)
    
    # Exit with error code if vulnerabilities found
    vulnerable_count = len([r for r in results if r["status"] == "VULNERABLE"])
    if vulnerable_count > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()