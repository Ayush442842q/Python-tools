#!/usr/bin/env python3
"""
Python Import Shadowing & Namespace Conflict Auditor

Scans a directory/codebase to identify local Python files or folders that shadow
standard library modules or built-ins. For example, naming a local file `csv.py`
or `json.py` shadows the standard library, leading to mysterious `ImportError` or
`AttributeError` exceptions when other modules try to import the standard library.

Features:
- Dynamically retrieves standard library module names (using sys.stdlib_module_names in 3.10+ or fallback)
- Detects local files (e.g., re.py, email.py) or directories (e.g., json/) shadowing stdlib modules
- Checks for shadow conflicts in specified search paths
- Outputs clean, colored terminal reports
- Exit code reflecting conflicts found (useful for CI/CD checks)
"""

import os
import sys
import argparse
import sysconfig

# Fallback stdlib modules list for Python versions < 3.10
FALLBACK_STDLIB = {
    "abc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore", "atexit",
    "base64", "bdb", "binascii", "bisect", "builtins", "bz2", "calendar", "cgi",
    "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib", "contextvars",
    "copy", "copyreg", "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime",
    "dbm", "decimal", "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "ensurepip", "errno", "faulthandler", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib",
    "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http", "imaplib", "imghdr",
    "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap", "marshal",
    "math", "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "pprint", "profile", "pstats", "pty", "pwd", "py_compile",
    "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "select", "selectors", "shelve",
    "shily", "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr",
    "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat", "statistics",
    "string", "stringprep", "struct", "subprocess", "sunau", "symtable", "sys",
    "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "test", "textwrap", "threading", "time", "timeit", "tkinter", "token", "tokenize",
    "tomllib", "trace", "traceback", "tracemalloc", "tty", "types", "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "warnings", "wave", "weakref",
    "webbrowser", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
    "zlib"
}

def get_stdlib_modules():
    """Returns the set of standard library module names."""
    # sys.stdlib_module_names is available in Python 3.10+
    if hasattr(sys, 'stdlib_module_names'):
        return set(sys.stdlib_module_names)
    
    # Fallback compilation
    modules = set(sys.builtin_module_names)
    modules.update(FALLBACK_STDLIB)
    
    # Add files from the standard library directory
    try:
        stdlib_path = sysconfig.get_path('stdlib')
        if stdlib_path and os.path.exists(stdlib_path):
            for item in os.listdir(stdlib_path):
                if item.endswith('.py'):
                    modules.add(item[:-3])
                elif os.path.isdir(os.path.join(stdlib_path, item)) and not item.startswith('_'):
                    if os.path.exists(os.path.join(stdlib_path, item, '__init__.py')):
                        modules.add(item)
    except Exception:
        pass
        
    return modules

def scan_directory(path, exclude_dirs=None):
    """
    Recursively scans the directory and yields files/directories shadowing stdlib.
    """
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', 'venv', '.venv', 'env', '.agents', '.gemini'}
    
    stdlib_modules = get_stdlib_modules()
    conflicts = []

    for root, dirs, files in os.walk(path):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # Check folders/directories shadowing stdlib (packages)
        for d in dirs:
            if d in stdlib_modules:
                dir_path = os.path.join(root, d)
                # Check if it's a python package directory or contains .py files
                has_py = any(f.endswith('.py') for f in os.listdir(dir_path))
                if has_py or os.path.exists(os.path.join(dir_path, '__init__.py')):
                    conflicts.append({
                        "type": "directory",
                        "name": d,
                        "path": dir_path,
                        "reason": f"Directory '{d}/' shadows standard library module '{d}' and contains Python files."
                    })
                    
        # Check files shadowing stdlib
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                module_name = f[:-3]
                if module_name in stdlib_modules:
                    conflicts.append({
                        "type": "file",
                        "name": module_name,
                        "path": os.path.join(root, f),
                        "reason": f"File '{f}' shadows standard library module '{module_name}'."
                    })
                    
    return conflicts

def main():
    parser = argparse.ArgumentParser(
        description="Audit directory for Python files/packages that shadow standard library modules."
    )
    parser.add_argument(
        'paths', nargs='*', default=['.'],
        help="Directories to scan (default: current directory)"
    )
    parser.add_argument(
        '--exclude', nargs='*', default=[],
        help="Extra directory names to exclude from scanning"
    )
    parser.add_argument(
        '--no-color', action='store_true',
        help="Disable ANSI color output"
    )
    args = parser.parse_args()

    # ANSI Colors
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt'
    COLOR_RED = "\033[91m" if use_color else ""
    COLOR_YELLOW = "\033[93m" if use_color else ""
    COLOR_GREEN = "\033[92m" if use_color else ""
    COLOR_CYAN = "\033[96m" if use_color else ""
    COLOR_RESET = "\033[0m" if use_color else ""
    
    exclude_dirs = {'.git', '__pycache__', 'venv', '.venv', 'env', '.agents', '.gemini'}
    exclude_dirs.update(args.exclude)
    
    print(f"{COLOR_CYAN}=== Python Import Shadowing Auditor ==={COLOR_RESET}")
    print(f"Loaded {len(get_stdlib_modules())} standard library modules for collision auditing.\n")
    
    total_conflicts = 0
    all_conflicts = []
    
    for path in args.paths:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            print(f"{COLOR_RED}Error: Path '{path}' does not exist.{COLOR_RESET}", file=sys.stderr)
            continue
            
        print(f"Scanning: {abs_path}...")
        conflicts = scan_directory(abs_path, exclude_dirs)
        all_conflicts.extend(conflicts)
        
    print(f"\n{COLOR_CYAN}--- Audit Report ---{COLOR_RESET}")
    if not all_conflicts:
        print(f"{COLOR_GREEN}✔ Clean! No import shadowing namespace conflicts detected.{COLOR_RESET}")
        sys.exit(0)
        
    # Group conflicts by module name for easier readability
    conflicts_by_name = {}
    for conflict in all_conflicts:
        conflicts_by_name.setdefault(conflict['name'], []).append(conflict)
        
    for name, items in sorted(conflicts_by_name.items()):
        print(f"\n{COLOR_RED}⚠ Conflict: Shadowing standard module '{name}'{COLOR_RESET}")
        for item in items:
            type_label = f"[{item['type'].upper()}]"
            print(f"  {COLOR_YELLOW}{type_label:<13}{COLOR_RESET} {item['path']}")
            print(f"  Details:      {item['reason']}")
            print(f"  Risks:        Imports of 'import {name}' from within the same package directory tree")
            print(f"                will resolve to this local file rather than the standard library.")
            print(f"                This can cause cryptic 'AttributeError' or 'ImportError' in dependencies.")
            
    print(f"\nTotal import shadowing issues found: {COLOR_RED}{len(all_conflicts)}{COLOR_RESET}")
    print(f"{COLOR_YELLOW}Recommendation: Rename the conflicting local files/directories to avoid namespaces clashes.{COLOR_RESET}")
    sys.exit(1)

if __name__ == '__main__':
    main()
