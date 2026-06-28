#!/usr/bin/env python3
"""
Virtual Environment Dependency Auditor
Scans the current project codebase for imports, lists all installed packages in the
virtual environment, maps package names to imports (using a built-in mapping dictionary),
and reports: active dependencies, orphaned/unused dependencies, and missing packages.
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_RED = ""
    COLOR_CYAN = ""

# Common PyPI Package Name to Top-level Import Name mapping
PYPI_TO_IMPORT_MAP = {
    "beautifulsoup4": "bs4",
    "pillow": "PIL",
    "pyyaml": "yaml",
    "python-dotenv": "dotenv",
    "scikit-learn": "sklearn",
    "pypdf2": "PyPDF2",
    "pymongo": "bson", # can import pymongo or bson
    "apache-airflow": "airflow",
    "websocket-client": "websocket",
    "pyjwt": "jwt",
    "python-dateutil": "dateutil",
    "python-jose": "jose",
    "ruamel.yaml": "ruamel",
    "scikit-image": "skimage",
    "tb-nightly": "tensorboard",
    "authlib": "authlib",
    "django-rest-framework": "rest_framework",
    "google-api-python-client": "googleapiclient",
    "protobuf": "google.protobuf",
    "markupcontrol": "markup",
    "pydantic-core": "pydantic_core",
    "mysql-connector-python": "mysql"
}

# Reverse mapping for lookups
IMPORT_TO_PYPI_MAP = {v: k for k, v in PYPI_TO_IMPORT_MAP.items()}

# Set of standard library modules (Python 3.10 standard list, expanded)
STD_LIB_MODULES = {
    "string", "re", "difflib", "textwrap", "unicodedata", "stringprep", "readline",
    "rlcompleter", "struct", "codecs", "datetime", "zoneinfo", "calendar", "collections",
    "heapq", "bisect", "array", "weakref", "types", "copy", "pprint", "reprlib", "enum",
    "numbers", "math", "cmath", "decimal", "fractions", "random", "statistics", "itertools",
    "functools", "operator", "pathlib", "os", "fileinput", "stat", "filecmp", "tempfile",
    "glob", "fnmatch", "linecache", "shutil", "macpath", "pickle", "copyreg", "shelve",
    "marshal", "dbm", "sqlite3", "zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile",
    "csv", "configparser", "tomllib", "netrc", "plistlib", "hashlib", "hmac", "secrets",
    "signaling", "curses", "platform", "errno", "ctypes", "select", "selectors",
    "signal", "threads", "threading", "queue", "multiprocessing", "subprocess", "sched",
    "sys", "sysconfig", "builtins", "warnings", "dataclasses", "contextlib", "abc",
    "atexit", "traceback", "gc", "inspect", "site", "ssl", "socket", "socketserver",
    "http", "urllib", "xmlrpc", "ftplib", "poplib", "imaplib", "smtplib", "uuid",
    "webbrowser", "hash", "json", "xml", "email", "mailbox", "mimetypes", "base64",
    "binhex", "binascii", "quopri", "uu", "html", "xml", "ast", "symtable", "token",
    "keyword", "tokenize", "tabnanny", "pyclbr", "pydoc", "doctest", "unittest",
    "test", "mock", "typing", "trace", "tracemalloc", "time", "argparse", "logging",
    "getpass", "getopt", "importlib", "pkgutil", "zipimport", "runpy", "asyncio",
    "concurrent", "wsgiref", "ipaddress", "selectors", "faulthandler", "distutils",
    "venv", "pwd", "grp", "posix", "crypt"
}

def find_venv_site_packages(venv_root: Path) -> Optional[Path]:
    """Finds the site-packages directory inside a virtual environment root."""
    if os.name == 'nt':
        # Windows structure: venv_root/Lib/site-packages
        path = venv_root / "Lib" / "site-packages"
        if path.exists():
            return path
    else:
        # Unix structure: venv_root/lib/pythonX.Y/site-packages
        lib_path = venv_root / "lib"
        if lib_path.exists():
            for sub in lib_path.iterdir():
                if sub.is_dir() and sub.name.startswith("python"):
                    site_pack = sub / "site-packages"
                    if site_pack.exists():
                        return site_pack
    return None

def get_installed_packages(site_packages: Path) -> Dict[str, str]:
    """Retrieves installed package names and versions from site-packages metadata."""
    packages = {}
    
    # 1. Try modern importlib.metadata
    try:
        from importlib.metadata import distributions
        dists = distributions(paths=[str(site_packages)])
        for d in dists:
            # Normalize package name to lowercase
            packages[d.metadata["Name"].lower()] = d.version
        if packages:
            return packages
    except Exception:
        pass

    # 2. Fallback: manual scan of .dist-info and .egg-info directories
    try:
        for item in site_packages.iterdir():
            if item.is_dir() and (item.name.endswith(".dist-info") or item.name.endswith(".egg-info")):
                # E.g. requests-2.28.1.dist-info
                parts = item.name[:-10].split("-")
                if len(parts) >= 2:
                    name = parts[0].replace("_", "-").lower()
                    version = parts[1]
                    packages[name] = version
    except Exception:
        pass
        
    return packages

def extract_imports_from_file(filepath: Path) -> Set[str]:
    """Parses a Python file using AST and extracts all top-level module imports."""
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(filepath))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Get top level module name (e.g. requests.auth -> requests)
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module: # level 0 means absolute import
                    imports.add(node.module.split('.')[0])
    except Exception:
        pass
    return imports

def scan_project_imports(project_dir: Path, excludes: List[str]) -> Set[str]:
    """Scans the codebase recursively to compile all imported module names."""
    all_imports = set()
    for root, dirs, files in os.walk(project_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if not any(ex in os.path.join(root, d) for ex in excludes)]
        
        for file in files:
            if file.endswith('.py'):
                full_path = Path(root) / file
                if any(ex in str(full_path) for ex in excludes):
                    continue
                all_imports.update(extract_imports_from_file(full_path))
    return all_imports

def find_venv_directory(start_dir: Path) -> Optional[Path]:
    """Tries to auto-detect a virtual environment directory in the start path."""
    common_names = [".venv", "venv", "env"]
    for name in common_names:
        candidate = start_dir / name
        if candidate.exists() and candidate.is_dir():
            # Check if it has a site-packages folder
            if find_venv_site_packages(candidate):
                return candidate
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Audit project codebase imports against virtual environment packages."
    )
    parser.add_argument(
        "--venv", help="Path to the virtual environment root directory"
    )
    parser.add_argument(
        "--dir", default=".", help="Project root directory to scan (default: current dir)"
    )
    parser.add_argument(
        "--exclude", action="append", default=[".git", "__pycache__", "venv", "env", ".venv"],
        help="Directories or files to exclude from code scan"
    )
    
    args = parser.parse_args()
    
    project_root = Path(args.dir).resolve()
    
    # Locate virtual environment
    venv_root = None
    if args.venv:
        venv_root = Path(args.venv).resolve()
    else:
        # Try to auto-detect in project root
        venv_root = find_venv_directory(project_root)
        if not venv_root:
            # Try to auto-detect in current directory
            venv_root = find_venv_directory(Path(".").resolve())
            
    if not venv_root or not venv_root.exists():
        print(f"{COLOR_RED}Error: Virtual environment directory could not be resolved or auto-detected.{COLOR_RESET}")
        print("Please specify your venv path using: --venv /path/to/venv")
        sys.exit(1)
        
    site_packages = find_venv_site_packages(venv_root)
    if not site_packages:
        print(f"{COLOR_RED}Error: Could not locate site-packages folder in virtual environment {venv_root}{COLOR_RESET}")
        sys.exit(1)
        
    print(f"{COLOR_CYAN}Found virtual environment at: {venv_root}{COLOR_RESET}")
    print(f"{COLOR_CYAN}Site-packages folder: {site_packages}{COLOR_RESET}")
    
    # Get installed packages in venv
    installed = get_installed_packages(site_packages)
    print(f"{COLOR_CYAN}Detected {len(installed)} installed packages in venv.{COLOR_RESET}")
    
    # Scan project code for imports
    print(f"{COLOR_CYAN}Scanning project codebase for imports in {project_root}...{COLOR_RESET}")
    raw_imports = scan_project_imports(project_root, args.exclude)
    print(f"Detected {len(raw_imports)} unique import modules.")
    
    # Filter out standard library imports
    external_imports = sorted(list(raw_imports - STD_LIB_MODULES))
    
    # Classify imports
    used_packages: Dict[str, str] = {}
    missing_packages: List[str] = []
    
    for imp in external_imports:
        # Check standard mapping or normalize name
        pypi_name = IMPORT_TO_PYPI_MAP.get(imp, imp).lower().replace("_", "-")
        
        # Check if installed
        if pypi_name in installed:
            used_packages[pypi_name] = installed[pypi_name]
        elif imp.lower().replace("_", "-") in installed:
            used_packages[imp.lower().replace("_", "-")] = installed[imp.lower().replace("_", "-")]
        else:
            missing_packages.append(imp)
            
    # Find unused/orphaned packages (installed but not imported)
    orphaned_packages = {}
    for pkg_name, ver in installed.items():
        # Map pypi package name to import name
        import_name = PYPI_TO_IMPORT_MAP.get(pkg_name, pkg_name).lower().replace("-", "_")
        
        # If neither PyPI name nor import name is in external imports, it's orphaned
        if import_name not in [i.lower() for i in external_imports] and pkg_name not in [IMPORT_TO_PYPI_MAP.get(i, i).lower() for i in external_imports]:
            # Also exclude pip, setuptools, wheel, which are system/standard packages
            if pkg_name not in ["pip", "setuptools", "wheel"]:
                orphaned_packages[pkg_name] = ver
                
    # Display results
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}====================================================")
    print("           DEPENDENCY AUDIT RESULTS                 ")
    print(f"===================================================={COLOR_RESET}")
    
    print(f"\n{COLOR_BOLD}{COLOR_GREEN}✔ USED DEPENDENCIES ({len(used_packages)}){COLOR_RESET}")
    print("Installed packages that are imported in your code:")
    if used_packages:
        for pkg, ver in sorted(used_packages.items()):
            print(f"  - {pkg} ({ver})")
    else:
        print("  None")
        
    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}⚠ ORPHANED DEPENDENCIES ({len(orphaned_packages)}){COLOR_RESET}")
    print("Packages installed in venv but NOT imported in code (or transitive dependencies):")
    if orphaned_packages:
        for pkg, ver in sorted(orphaned_packages.items()):
            print(f"  - {pkg} ({ver})")
    else:
        print("  None")
        
    print(f"\n{COLOR_BOLD}{COLOR_RED}✘ MISSING PACKAGES ({len(missing_packages)}){COLOR_RESET}")
    print("Modules imported in code but NOT installed in venv:")
    if missing_packages:
        for imp in sorted(missing_packages):
            print(f"  - {imp}")
    else:
        print("  None")
        
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}===================================================={COLOR_RESET}\n")

if __name__ == "__main__":
    main()
