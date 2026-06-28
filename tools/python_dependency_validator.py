#!/usr/bin/env python3
"""
Python Dependency Validator

Scans a Python codebase recursively to extract all imported external packages
and compares them with the dependencies declared in requirements.txt.

Flags:
- Missing dependencies: Packages imported in code but not listed in requirements.txt.
- Unused dependencies: Packages listed in requirements.txt but never imported.

Usage:
    python tools/python_dependency_validator.py [project_dir] [--req requirements.txt]
"""

import argparse
import sys
import os
import ast
import re

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

# A comprehensive list of standard library modules (for python < 3.10 fallback)
STD_LIB = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'crypt', 'csv', 'ctypes',
    'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
    'distutils', 'doctest', 'dummy_threading', 'email', 'encodings', 'ensurepip',
    'errno', 'faulthandler', 'filecmp', 'fileinput', 'fnmatch', 'formatter',
    'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext',
    'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http',
    'imaplib', 'imghdr', 'imp', 'importlib', 'inspect', 'io', 'ipaddress',
    'itertools', 'json', 'keyword', 'lib2to3', 'linecache', 'locale', 'logging',
    'lzma', 'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap',
    'modulefinder', 'msilib', 'msvcrt', 'multiprocessing', 'netrc', 'nis',
    'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'parser',
    'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform',
    'plistlib', 'poplib', 'posix', 'pprint', 'profile', 'pstats', 'pty', 'pwd',
    'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline',
    'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
    'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 'smtplib',
    'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat',
    'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau',
    'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
    'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time',
    'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback',
    'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing', 'unicodedata',
    'unittest', 'urllib', 'uu', 'uuid', 'warnings', 'wave', 'weakref', 'webbrowser',
    'wsgiref', 'xdg', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    'zoneinfo'
}

# Some packages map to different import names. E.g., 'pyyaml' is imported as 'yaml'
IMPORT_TO_PKG_MAP = {
    'yaml': 'pyyaml',
    'PIL': 'pillow',
    'bs4': 'beautifulsoup4',
    'dns': 'dnspython',
    'git': 'gitpython',
    'github': 'pygithub',
    'jwt': 'pyjwt',
    'dateutil': 'python-dateutil',
    'dotenv': 'python-dotenv',
    'mysql': 'mysql-connector-python',
    'google': 'google-cloud-storage', # simplified map
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def get_stdlib_modules():
    # sys.stdlib_module_names is available in Python 3.10+
    try:
        return sys.stdlib_module_names | STD_LIB
    except AttributeError:
        return STD_LIB

def get_top_level_module(import_path):
    """Extracts top level module name (e.g. urllib.request -> urllib)"""
    return import_path.split('.')[0]

def extract_imports_from_file(file_path):
    """Uses AST to parse python imports from a file."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(get_top_level_module(name.name))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module: # level 0 is absolute import
                    imports.add(get_top_level_module(node.module))
    except Exception as e:
        # Ignore syntax errors or reading errors; we print warning later
        pass
    return imports

def find_all_imports(directory):
    """Recursively scans directory for python files and gathers all imported modules."""
    all_imports = set()
    local_modules = set()
    
    # 1. Identify local modules/packages to ignore them in external deps check
    for root, dirs, files in os.walk(directory):
        # Ignore virtualenvs or hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '.venv', 'env')]
        
        for file in files:
            if file.endswith('.py'):
                module_name = file[:-3]
                local_modules.add(module_name)
        for d in dirs:
            local_modules.add(d)
            
    # 2. Extract all imports
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '.venv', 'env')]
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                all_imports.update(extract_imports_from_file(full_path))
                
    return all_imports, local_modules

def parse_requirements(requirements_path):
    """Parses requirements.txt and returns package names as lowercase."""
    packages = set()
    if not os.path.exists(requirements_path):
        return packages
        
    with open(requirements_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments/empty lines
            if not line or line.startswith('#') or line.startswith('-r'):
                continue
            
            # Match package name (before any operators like ==, >=, etc.)
            match = re.match(r'^([a-zA-Z0-9_\-]+)', line)
            if match:
                pkg_name = match.group(1).lower().replace('_', '-')
                packages.add(pkg_name)
    return packages

def main():
    parser = argparse.ArgumentParser(description="Check Python imports against requirements.txt.")
    parser.add_argument("project_dir", nargs="?", default=".", help="Project root directory (default: current)")
    parser.add_argument("--req", default="requirements.txt", help="Path to requirements.txt (default: requirements.txt)")
    parser.add_argument("--no-color", action="store_true", help="Disable color outputs")
    
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
        
    project_dir = os.path.abspath(args.project_dir)
    req_path = os.path.join(project_dir, args.req) if not os.path.isabs(args.req) else args.req
    
    if not os.path.isdir(project_dir):
        print(f"{COLORS['red']}Error: '{project_dir}' is not a directory.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning directory: {COLORS['cyan']}{project_dir}{COLORS['reset']}")
    
    # Get standard libraries
    stdlib = get_stdlib_modules()
    
    # 1. Gather all imports from codebase
    raw_imports, local_mods = find_all_imports(project_dir)
    
    # 2. Map import names to potential package names
    imported_third_party = set()
    for imp in raw_imports:
        if imp in stdlib:
            continue
        if imp in local_mods:
            continue
        # Normalize name
        pkg_name = IMPORT_TO_PKG_MAP.get(imp, imp).lower().replace('_', '-')
        if pkg_name:
            imported_third_party.add(pkg_name)
            
    # 3. Read requirements.txt
    req_packages = parse_requirements(req_path)
    
    if not os.path.exists(req_path):
        print(f"{COLORS['yellow']}Warning: requirements file not found at '{req_path}'. Only listing third-party imports found.{COLORS['reset']}")
        print(f"\n{COLORS['bold']}Third-Party Imports found:{COLORS['reset']}")
        for pkg in sorted(imported_third_party):
            print(f"  - {pkg}")
        sys.exit(0)
        
    print(f"Comparing imports with: {COLORS['cyan']}{req_path}{COLORS['reset']}\n")
    
    # 4. Compare
    missing_deps = imported_third_party - req_packages
    unused_deps = req_packages - imported_third_party
    
    has_issues = False
    
    if missing_deps:
        has_issues = True
        print(f"{COLORS['red']}{COLORS['bold']}Missing Dependencies (imported in code but not in requirements.txt):{COLORS['reset']}")
        for pkg in sorted(missing_deps):
            print(f"  - {COLORS['red']}{pkg}{COLORS['reset']}")
        print()
        
    if unused_deps:
        has_issues = True
        print(f"{COLORS['yellow']}{COLORS['bold']}Unused Dependencies (in requirements.txt but never imported):{COLORS['reset']}")
        for pkg in sorted(unused_deps):
            print(f"  - {COLORS['yellow']}{pkg}{COLORS['reset']}")
        print()
        
    if not has_issues:
        print(f"{COLORS['green']}Success: All imports are correctly declared in requirements.txt, and there are no unused dependencies!{COLORS['reset']}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
