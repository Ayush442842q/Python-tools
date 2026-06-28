#!/usr/bin/env python3
"""
Python Requirement Optimizer

Scans Python files in a directory recursively, extracts external module imports,
resolves their PyPI package names, fetches current installed versions or queries 
PyPI for versions, and generates a clean, optimized requirements.txt.

Usage:
    python tools/python_requirement_optimizer.py /path/to/project -o requirements.txt
"""

import os
import sys
import re
import ast
import json
import urllib.request
import argparse
from typing import Set, Dict, List, Optional

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Standard libraries mapping (built-in modules in Python 3)
STD_LIBS = {
    "abc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore", "atexit", 
    "base64", "bdb", "binascii", "bisect", "builtins", "bz2", "calendar", "cgi", 
    "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections", 
    "colorsys", "compileall", "concurrent", "configparser", "contextlib", "contextvars", 
    "copy", "copyreg", "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime", 
    "dbm", "decimal", "difflib", "dis", "distutils", "doctest", "email", "encodings", 
    "ensurepip", "errno", "faulthandler", "filecmp", "fileinput", "fnmatch", "formatter", 
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", 
    "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http", "imaplib", 
    "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json", 
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap", 
    "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing", 
    "netrc", "nis", "nntplib", "ntpath", "numbers", "operator", "optparse", "os", 
    "ossaudiodev", "pathlib", "pdb", "pickle", "pickleshare", "pickletools", "pipes", 
    "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", 
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", 
    "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter", 
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shimport", 
    "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", 
    "socketserver", "spwd", "sqlite3", "sre_compile", "sre_constants", "sre_parse", 
    "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess", 
    "sunau", "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny", 
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap", "threading", 
    "time", "timeit", "tkinter", "token", "tokenize", "trace", "traceback", 
    "tracemalloc", "tty", "types", "typing", "unicodedata", "unittest", "urllib", 
    "uu", "uuid", "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", 
    "wsgiref", "xdg", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", 
    "zoneinfo"
}

# Module import name to PyPI package name mapping
MODULE_MAPPING = {
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "jinja2": "Jinja2",
    "git": "GitPython",
    "google": "google-api-python-client",
    "dateutil": "python-dateutil",
    "jwt": "PyJWT",
    "mysql": "mysql-connector-python",
    "pg": "pg8000",
    "psycopg2": "psycopg2-binary",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "docker": "docker",
    "websocket": "websocket-client",
    "dns": "dnspython",
    "OpenSSL": "pyOpenSSL",
    "mpl_toolkits": "matplotlib",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "requests": "requests",
    "urllib3": "urllib3",
    "dotenv": "python-dotenv",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "flask": "Flask",
    "django": "Django",
    "sqlalchemy": "SQLAlchemy",
    "redis": "redis",
    "pydantic": "pydantic",
    "yaml": "PyYAML",
    "toml": "toml",
    "pygments": "Pygments",
    "rich": "rich",
    "prompt_toolkit": "prompt-toolkit"
}

def print_colored(text: str, color: str):
    """Prints text in color if it's a TUI."""
    if sys.stderr.isatty():
        sys.stderr.write(f"{color}{text}{RESET}\n")
    else:
        sys.stderr.write(f"{text}\n")

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            # Extract top-level module name: e.g. 'foo.bar' -> 'foo'
            top_level = alias.name.split('.')[0]
            self.imports.add(top_level)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level == 0 and node.module:  # Exclude relative imports e.g., 'from . import foo'
            top_level = node.module.split('.')[0]
            self.imports.add(top_level)
        self.generic_visit(node)

def extract_imports_from_file(filepath: str) -> Set[str]:
    """Parses a Python file and returns all top-level module import names."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        visitor = ImportVisitor()
        visitor.visit(tree)
        return visitor.imports
    except SyntaxError:
        # Fall back to regex parsing if AST fails
        imports = set()
        for line in content.splitlines():
            # simple import matching
            match_imp = re.match(r"^\s*import\s+([\w\.]+)", line)
            if match_imp:
                imports.add(match_imp.group(1).split('.')[0])
            match_from = re.match(r"^\s*from\s+([\w\.]+)\s+import", line)
            if match_from:
                imports.add(match_from.group(1).split('.')[0])
        return imports
    except Exception as e:
        print_colored(f"[!] Warning: Could not parse '{filepath}': {e}", YELLOW)
        return set()

def scan_directory(path: str) -> Set[str]:
    """Recursively scans a directory for Python files and returns unique top-level imports."""
    all_imports: Set[str] = set()
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".py"):
                file_path = os.path.join(root, f)
                all_imports.update(extract_imports_from_file(file_path))
    return all_imports

def get_installed_version(package_name: str) -> Optional[str]:
    """Attempts to find the installed version of a package in current environment."""
    try:
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except Exception:
        try:
            # older version fallback
            import pkg_resources
            return pkg_resources.get_distribution(package_name).version
        except Exception:
            return None

def fetch_latest_pypi_version(package_name: str) -> Optional[str]:
    """Fetches the latest version of a package from PyPI JSON endpoint."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Requirement-Optimizer"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("info", {}).get("version")
    except Exception:
        return None

def optimize_requirements(project_path: str, output_path: Optional[str], fetch_pypi: bool):
    """Scans codebase, filters standard libs, maps to PyPI and writes output."""
    if not os.path.exists(project_path):
        print_colored(f"[-] Error: Path not found: {project_path}", RED)
        sys.exit(1)

    print_colored(f"[*] Scanning '{project_path}' for imports...", BLUE)
    raw_imports = scan_directory(project_path)
    
    # Filter out standard libraries and local files/folders
    external_modules = sorted(list(raw_imports - STD_LIBS))
    
    # Filter out local directory names (e.g. if importing from a local package)
    local_dirs = {d for d in os.listdir(project_path) if os.path.isdir(os.path.join(project_path, d))}
    external_modules = [m for m in external_modules if m not in local_dirs]

    print_colored(f"[*] Found {len(external_modules)} external module imports.", BLUE)

    requirements: List[str] = []
    
    for mod in external_modules:
        # Resolve PyPI package name
        pypi_name = MODULE_MAPPING.get(mod, mod)
        
        # Determine version
        version = get_installed_version(pypi_name)
        version_source = "local environment"
        
        if not version and fetch_pypi:
            # Query PyPI
            version = fetch_latest_pypi_version(pypi_name)
            version_source = "PyPI registry"
            
        if version:
            spec = f"{pypi_name}=={version}"
            print(f"    - Found: {spec} (from {version_source})")
        else:
            spec = pypi_name
            print(f"    - Found: {spec} (version not found)")
            
        requirements.append(spec)

    requirements.sort(key=str.lower)

    if not requirements:
        print_colored("[*] No external requirements detected.", YELLOW)
        return

    # Write output
    output_content = "\n".join(requirements) + "\n"
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_content)
            print_colored(f"[+] Saved optimized requirements to '{output_path}'!", GREEN)
        except Exception as e:
            print_colored(f"[-] Error writing requirements file: {e}", RED)
            sys.exit(1)
    else:
        print_colored("\n--- Optimized requirements.txt ---", CYAN)
        print(output_content, end="")

def main():
    parser = argparse.ArgumentParser(description="Optimize project imports into a requirements.txt file.")
    parser.add_argument("project_path", nargs="?", default=".", help="Root path of the project to scan (default: .)")
    parser.add_argument("-o", "--output", help="Optional output path for requirements.txt")
    parser.add_argument("--fetch-pypi", action="store_true", help="Fetch version from PyPI if not installed locally")

    args = parser.parse_args()
    optimize_requirements(args.project_path, args.output, args.fetch_pypi)

if __name__ == "__main__":
    main()
