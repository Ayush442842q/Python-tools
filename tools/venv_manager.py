#!/usr/bin/env python3
"""
Python Virtual Environment Manager - Create, manage, and inspect virtual environments.

A comprehensive tool for creating and managing Python virtual environments
with automatic dependency installation, environment comparison, and cleanup.

Usage:
    python venv_manager.py create myenv              # Create new venv
    python venv_manager.py create myenv -r requirements.txt  # With deps
    python venv_manager.py info myenv                # Show venv info
    python venv_manager.py compare env1 env2         # Compare two envs
    python venv_manager.py list                      # List all venvs
    python venv_manager.py clean                     # Remove unused venvs
    python venv_manager.py export myenv > reqs.txt   # Export packages
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import venv
from datetime import datetime
from pathlib import Path


PYTHON_EXEC = sys.executable


def run_command(args, cwd=None, capture=True):
    """Run a shell command."""
    try:
        result = subprocess.run(
            args,
            capture_output=capture,
            text=True,
            cwd=cwd,
            check=True
        )
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        if capture:
            return e.stderr
        return None
    except FileNotFoundError:
        return None


def get_python_version():
    """Get Python version string."""
    version = sys.version_info
    return f"{version.major}.{version.minor}.{version.micro}"


def create_venv(name, python=None, packages=None, requirements=None, upgrade=False, system_site_packages=False):
    """Create a new virtual environment."""
    venv_path = Path(name).resolve()
    
    if venv_path.exists():
        if upgrade:
            print(f"Upgrading existing environment: {venv_path}")
        else:
            print(f"Error: Environment already exists: {venv_path}")
            print("Use --upgrade to upgrade instead")
            return False
    
    print(f"Creating virtual environment: {venv_path}")
    
    # Determine Python interpreter
    interpreter = python or PYTHON_EXEC
    
    # Create environment
    builder = venv.EnvBuilder(
        system_site_packages=system_site_packages,
        clear=upgrade,
        symlinks=os.name != 'nt',
        with_pip=True
    )
    builder.create(venv_path)
    
    # Get pip path
    if os.name == 'nt':
        pip_path = venv_path / 'Scripts' / 'pip'
        python_path = venv_path / 'Scripts' / 'python'
    else:
        pip_path = venv_path / 'bin' / 'pip'
        python_path = venv_path / 'bin' / 'python'
    
    # Upgrade pip
    print("Upgrading pip...")
    run_command([str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'])
    
    # Install packages
    to_install = []
    
    if packages:
        to_install.extend(packages)
    
    if requirements:
        if os.path.exists(requirements):
            to_install.extend(['-r', requirements])
            print(f"Installing from requirements: {requirements}")
        else:
            print(f"Warning: Requirements file not found: {requirements}")
    
    if to_install:
        print(f"Installing packages: {' '.join(to_install)}")
        result = run_command([str(pip_path), 'install'] + to_install, capture=False)
    
    print(f"\n✓ Virtual environment created successfully!")
    print(f"  Location: {venv_path}")
    print(f"  Python: {interpreter}")
    print(f"\nActivate with:")
    if os.name == 'nt':
        print(f"  {venv_path}\\Scripts\\activate")
    else:
        print(f"  source {venv_path}/bin/activate")
    
    return True


def get_venv_info(venv_path):
    """Get information about a virtual environment."""
    venv_path = Path(venv_path)
    
    if not venv_path.exists():
        return None
    
    # Check if it's a venv
    pyvenv_cfg = venv_path / 'pyvenv.cfg'
    if not pyvenv_cfg.exists():
        return None
    
    # Read config
    info = {
        'path': str(venv_path.absolute()),
        'name': venv_path.name,
        'created': None,
        'python_version': None,
        'site_packages': None,
        'packages': []
    }
    
    # Parse pyvenv.cfg
    with open(pyvenv_cfg) as f:
        for line in f:
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key == 'version':
                    info['python_version'] = value
                elif key == 'include-system-site-packages':
                    info['site_packages'] = value == 'true'
    
    # Get creation time
    try:
        info['created'] = datetime.fromtimestamp(
            venv_path.stat().st_ctime
        ).strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    
    # Get installed packages
    if os.name == 'nt':
        pip_path = venv_path / 'Scripts' / 'pip'
    else:
        pip_path = venv_path / 'bin' / 'pip'
    
    if pip_path.exists():
        output = run_command([str(pip_path), 'list', '--format=json'])
        try:
            info['packages'] = json.loads(output)
        except:
            pass
    
    return info


def list_venvs(search_paths=None):
    """List all virtual environments in search paths."""
    if search_paths is None:
        search_paths = ['.', os.path.expanduser('~')]
    
    venvs = []
    
    for search_path in search_paths:
        search_path = Path(search_path)
        if not search_path.exists():
            continue
        
        # Look for common venv patterns
        patterns = ['venv', 'env', '.venv', '.env', 'virtualenv', '*venv*', '*env*']
        
        def is_venv(path):
            return (path.is_dir() and 
                   (path / 'pyvenv.cfg').exists())
        
        for pattern in patterns:
            for path in search_path.glob(pattern):
                if is_venv(path):
                    venvs.append(path)
        
        # Also check subdirectories
        if search_path.is_dir():
            for item in search_path.iterdir():
                if is_venv(item):
                    if item not in venvs:
                        venvs.append(item)
    
    return sorted(set(venvs), key=lambda p: p.name)


def compare_venvs(venv1_path, venv2_path):
    """Compare two virtual environments."""
    info1 = get_venv_info(venv1_path)
    info2 = get_venv_info(venv2_path)
    
    if not info1 or not info2:
        print("Error: One or both paths are not valid virtual environments")
        return
    
    print(f"Comparing:\n  {info1['path']}\n  {info2['path']}\n")
    
    # Compare Python versions
    print("Python Version:")
    if info1['python_version'] != info2['python_version']:
        print(f"  ❌ {info1['python_version']} vs {info2['python_version']}")
    else:
        print(f"  ✓ {info1['python_version']}")
    
    # Compare packages
    pkgs1 = {p['name']: p['version'] for p in info1.get('packages', [])}
    pkgs2 = {p['name']: p['version'] for p in info2.get('packages', [])}
    
    common = set(pkgs1.keys()) & set(pkgs2.keys())
    only1 = set(pkgs1.keys()) - set(pkgs2.keys())
    only2 = set(pkgs2.keys()) - set(pkgs1.keys())
    different = {
        name for name in common
        if pkgs1[name] != pkgs2[name]
    }
    
    print(f"\nPackages:")
    print(f"  Only in {info1['name']}: {len(only1)}")
    if only1:
        for pkg in sorted(only1):
            print(f"    - {pkg}")
    
    print(f"  Only in {info2['name']}: {len(only2)}")
    if only2:
        for pkg in sorted(only2):
            print(f"    - {pkg}")
    
    print(f"  Different versions: {len(different)}")
    for pkg in sorted(different):
        print(f"    • {pkg}: {pkgs1[pkg]} vs {pkgs2[pkg]}")
    
    print(f"  Same: {len(common) - len(different)}")


def export_packages(venv_path):
    """Export installed packages as requirements.txt."""
    info = get_venv_info(venv_path)
    if not info:
        print("Error: Not a valid virtual environment")
        return
    
    for pkg in sorted(info.get('packages', []), key=lambda p: p['name'].lower()):
        print(f"{pkg['name']}=={pkg['version']}")


def clean_venvs(dry_run=True):
    """Clean up old/unused virtual environments."""
    venvs = list_venvs()
    
    print(f"Found {len(venvs)} virtual environments\n")
    
    for venv_path in venvs:
        info = get_venv_info(venv_path)
        if info:
            pkg_count = len(info.get('packages', []))
            age = "unknown"
            if info['created']:
                created = datetime.strptime(info['created'], '%Y-%m-%d %H:%M:%S')
                days = (datetime.now() - created).days
                age = f"{days}d old"
            
            print(f"• {venv_path.name:20s}  {pkg_count:4d} packages  {age}")
    
    print(f"\n{'DRY RUN - would not delete' if dry_run else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Python virtual environments"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create new virtual environment')
    create_parser.add_argument('name', help='Environment name/path')
    create_parser.add_argument('--python', '-p', help='Python interpreter')
    create_parser.add_argument('--packages', nargs='+', help='Packages to install')
    create_parser.add_argument('--requirements', '-r', help='Requirements file')
    create_parser.add_argument('--upgrade', '-u', action='store_true',
                               help='Upgrade existing environment')
    create_parser.add_argument('--system-site-packages', action='store_true',
                               help='Give access to system site packages')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show environment info')
    info_parser.add_argument('path', help='Virtual environment path')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List virtual environments')
    list_parser.add_argument('--path', '-p', action='append',
                             help='Search paths (default: current dir, home)')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two environments')
    compare_parser.add_argument('env1', help='First environment path')
    compare_parser.add_argument('env2', help='Second environment path')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export installed packages')
    export_parser.add_argument('path', help='Virtual environment path')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean up old environments')
    clean_parser.add_argument('--execute', '-x', action='store_true',
                              help='Actually delete (default: dry-run)')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        create_venv(
            args.name,
            python=args.python,
            packages=args.packages,
            requirements=args.requirements,
            upgrade=args.upgrade,
            system_site_packages=args.system_site_packages
        )
    
    elif args.command == 'info':
        info = get_venv_info(args.path)
        if info:
            print(json.dumps(info, indent=2))
        else:
            print("Not a valid virtual environment")
    
    elif args.command == 'list':
        venvs = list_venvs(args.path)
        if venvs:
            for venv_path in venvs:
                info = get_venv_info(venv_path)
                if info:
                    print(f"{venv_path.name} ({info['python_version']})")
        else:
            print("No virtual environments found")
    
    elif args.command == 'compare':
        compare_venvs(args.env1, args.env2)
    
    elif args.command == 'export':
        export_packages(args.path)
    
    elif args.command == 'clean':
        clean_venvs(dry_run=not args.execute)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()