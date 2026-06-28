#!/usr/bin/env python3
"""
Virtual Environment Dependency Drift Detector
Compares installed packages in a Python virtual environment (venv) against
a dependency file (e.g., requirements.txt) and highlights discrepancies:
- Installed packages that are missing from requirements.txt (extraneous)
- Packages in requirements.txt that are not installed in the venv (missing)
- Installed packages whose versions do not match requirement specifications (mismatch)

License: MIT
"""

import sys
import os
import re
import argparse
import subprocess

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}[i] {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}[✗] Error: {msg}{Colors.ENDC}", file=sys.stderr)

def clean_package_name(name):
    """Normalize package names to match pip formatting (lowercase, dashes to underscores)."""
    return name.strip().lower().replace('_', '-')

def parse_requirements(req_path):
    """Parses a requirements.txt file and returns a dictionary of package -> specifier."""
    if not os.path.exists(req_path):
        raise FileNotFoundError(f"Requirements file not found: {req_path}")
        
    requirements = {}
    
    with open(req_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Ignore comments and empty lines
            if not line or line.startswith('#') or line.startswith('-r'):
                continue
                
            # Parse package name and version specs
            # Matches package names, extras, and version specifiers
            match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)\s*(==|>=|<=|>|<|!=|~=)?\s*(.*)$', line)
            if match:
                pkg_name = clean_package_name(match.group(1))
                operator = match.group(2) or ''
                version = match.group(3).strip() if match.group(3) else ''
                
                # Strip environment markers if present (e.g., ; python_version >= '3.6')
                if ';' in version:
                    version = version.split(';')[0].strip()
                
                requirements[pkg_name] = {
                    'raw': line,
                    'operator': operator,
                    'version': version,
                    'line_num': line_num
                }
            else:
                print_warning(f"Could not parse requirements line {line_num}: {line}")
                
    return requirements

def get_venv_python(venv_path):
    """Locate the Python executable inside the virtual environment."""
    # Check Windows structure
    win_py = os.path.join(venv_path, 'Scripts', 'python.exe')
    if os.path.exists(win_py):
        return win_py
        
    # Check Unix structure
    unix_py = os.path.join(venv_path, 'bin', 'python')
    if os.path.exists(unix_py):
        return unix_py
        
    return None

def get_installed_packages(python_bin):
    """Run pip list/freeze using the venv python to get installed packages."""
    print_info(f"Querying virtual environment via: {python_bin}")
    try:
        # Run pip freeze or pip list --format=json. pip list JSON is highly structured.
        result = subprocess.run(
            [python_bin, '-m', 'pip', 'list', '--format=json'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        installed_list = json_data = json_loads = json_parse = None
        # Parse output JSON
        import json
        installed = {}
        for item in json.loads(result.stdout):
            pkg_name = clean_package_name(item['name'])
            installed[pkg_name] = item['version']
        return installed
    except Exception as e:
        print_warning("Failed to run 'pip list' in JSON format. Falling back to 'pip freeze' output parser...")
        # Fallback to pip freeze
        try:
            result = subprocess.run(
                [python_bin, '-m', 'pip', 'freeze'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            installed = {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if '==' in line:
                    parts = line.split('==')
                    pkg_name = clean_package_name(parts[0])
                    installed[pkg_name] = parts[1]
                elif '@' in line:
                    # VCS reference
                    parts = line.split('@')
                    pkg_name = clean_package_name(parts[0])
                    installed[pkg_name] = '<VCS URL>'
            return installed
        except Exception as ex:
            raise RuntimeError(f"Could not retrieve packages from venv: {ex}")

def compare_dependencies(requirements, installed, ignore_system=True):
    """Compares requirements specs with installed packages."""
    drift_found = False
    
    missing = []
    extraneous = []
    mismatched = []
    
    # System packages that can be safely ignored in venv if not in requirements.txt
    system_packages = {'pip', 'setuptools', 'wheel', 'distribute'}
    
    # 1. Check for missing or mismatched packages
    for pkg_name, req_info in requirements.items():
        if pkg_name not in installed:
            missing.append((pkg_name, req_info))
            drift_found = True
        else:
            inst_ver = installed[pkg_name]
            req_ver = req_info['version']
            op = req_info['operator']
            
            # Basic version comparison (simplistic equality check; can extend with packaging.version if needed)
            if op == '==' and inst_ver != req_ver:
                mismatched.append((pkg_name, req_info, inst_ver))
                drift_found = True
            elif op == '~=':
                # e.g., ~=2.28.1 matches 2.28.X but not 2.29.0
                req_parts = req_ver.split('.')
                inst_parts = inst_ver.split('.')
                if len(req_parts) >= 2 and len(inst_parts) >= 2:
                    if req_parts[:-1] != inst_parts[:len(req_parts)-1]:
                        mismatched.append((pkg_name, req_info, inst_ver))
                        drift_found = True
            # For other complex operators, print info for manual inspection or warning
            
    # 2. Check for extraneous packages
    for pkg_name, inst_ver in installed.items():
        if pkg_name not in requirements:
            if ignore_system and pkg_name in system_packages:
                continue
            extraneous.append((pkg_name, inst_ver))
            drift_found = True
            
    return drift_found, missing, mismatched, extraneous

def main():
    parser = argparse.ArgumentParser(
        description="Detect discrepancies between virtual environment packages and requirements.txt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check current directory's venv and requirements.txt
  python venv_drift_detector.py
  
  # Specify a custom venv and requirements file
  python venv_drift_detector.py -e .my_venv -r config/requirements.txt
        """
    )
    
    parser.add_argument("-e", "--env", help="Path to Python virtual environment directory (auto-detects if omitted)")
    parser.add_argument("-r", "--requirements", default="requirements.txt", help="Path to requirements file (default: requirements.txt)")
    parser.add_argument("--include-system", action="store_true", help="Include pip, setuptools, and wheel in comparison")
    
    args = parser.parse_args()

    requirements_file = args.requirements
    
    if not os.path.exists(requirements_file):
        print_error(f"Requirements file not found: {requirements_file}")
        sys.exit(1)

    # Auto-detect venv
    venv_dir = args.env
    if not venv_dir:
        # Check standard names
        standard_names = ['.venv', 'venv', 'env', '.env']
        for name in standard_names:
            if os.path.isdir(name) and get_venv_python(name):
                venv_dir = name
                break
                
    if not venv_dir:
        # Check if we are currently running inside a virtual environment
        if hasattr(sys, 'real_prefix') or (sys.base_prefix != sys.prefix):
            venv_dir = sys.prefix
            print_info(f"Running inside active venv: {venv_dir}")
        else:
            print_error("No virtual environment specified and none auto-detected (.venv, venv, env not found).")
            print_info("Please specify one with the -e/--env option.")
            sys.exit(1)

    python_bin = get_venv_python(venv_dir)
    if not python_bin:
        # Fallback to sys.executable if venv_dir matches sys.prefix
        if venv_dir == sys.prefix:
            python_bin = sys.executable
        else:
            print_error(f"Could not locate Python executable inside: {venv_dir}")
            sys.exit(1)

    print_info(f"Virtual environment directory: {venv_dir}")
    print_info(f"Requirements specification file: {requirements_file}")

    try:
        requirements = parse_requirements(requirements_file)
        installed = get_installed_packages(python_bin)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

    drift_found, missing, mismatched, extraneous = compare_dependencies(
        requirements, installed, ignore_system=not args.include_system
    )

    if not drift_found:
        print_success("No drift detected! Virtual environment matches requirements file perfectly.")
        sys.exit(0)

    # Report Drift
    if missing:
        print_header(f"Missing Packages ({len(missing)}) - In requirements but NOT installed")
        for pkg, req in missing:
            print(f"  {Colors.RED}✘ {pkg}{Colors.ENDC} (Line {req['line_num']}: {req['raw']})")

    if mismatched:
        print_header(f"Version Mismatches ({len(mismatched)})")
        for pkg, req, inst_ver in mismatched:
            print(f"  {Colors.YELLOW}! {pkg}{Colors.ENDC}: installed={Colors.RED}{inst_ver}{Colors.ENDC}, required={Colors.GREEN}{req['operator']}{req['version']}{Colors.ENDC} (Line {req['line_num']})")

    if extraneous:
        print_header(f"Extraneous Packages ({len(extraneous)}) - Installed but NOT in requirements")
        for pkg, inst_ver in extraneous:
            print(f"  {Colors.BLUE}+ {pkg}{Colors.ENDC}=={inst_ver}")

    # Recommendations
    print_header("Suggested Resolutions")
    if missing or mismatched:
        print(f"To sync installed packages with requirements file, run:")
        print(f"  {Colors.BOLD}{python_bin} -m pip install -r {requirements_file}{Colors.ENDC}\n")
    if extraneous:
        print(f"To save virtual environment changes back to requirements file, run:")
        print(f"  {Colors.BOLD}{python_bin} -m pip freeze > {requirements_file}{Colors.ENDC}\n")
        print(f"To uninstall extraneous packages, run:")
        extraneous_pkgs = " ".join(pkg for pkg, _ in extraneous)
        print(f"  {Colors.BOLD}{python_bin} -m pip uninstall {extraneous_pkgs}{Colors.ENDC}\n")

    sys.exit(1)

if __name__ == "__main__":
    main()
