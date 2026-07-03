#!/usr/bin/env python3
"""
Scans a Python codebase to dynamically analyze imports, find script entry points,
infer packaging metadata, and auto-generate a standard PEP 621 pyproject.toml configuration.
"""

import sys
import os
import re
import ast
import argparse

# Comprehensive list of standard library module names to filter them out of dependencies
STD_LIB_MODULES = {
    'string', 're', 'difflib', 'textwrap', 'unicodedata', 'stringprep', 'readline',
    'rlcompleter', 'struct', 'codecs', 'datetime', 'zoneinfo', 'calendar', 'collections',
    'abc', 'bisect', 'heapq', 'copy', 'pprint', 'reprlib', 'enum', 'numbers',
    'math', 'cmath', 'decimal', 'fractions', 'random', 'statistics', 'itertools',
    'functools', 'operator', 'pathlib', 'os', 'posixpath', 'ntpath', 'stat', 'genericpath',
    'fnmatch', 'linecache', 'shutil', 'macpath', 'pickle', 'copyreg', 'shelve',
    'marshal', 'dbm', 'sqlite3', 'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',
    'csv', 'configparser', 'tomllib', 'netrc', 'plistlib', 'hashlib', 'hmac', 'secrets',
    'os.path', 'sys', 'time', 'argparse', 'logging', 'warnings', 'contextlib', 'typing',
    'json', 'urllib', 'http', 'ftplib', 'poplib', 'imaplib', 'smtplib', 'uuid', 'socket',
    'select', 'selectors', 'signal', 'threading', 'subprocess', 'multiprocessing',
    'asyncio', 'socketserver', 'xml', 'email', 'html', 'code', 'unittest', 'mock',
    'traceback', 'inspect', 'pydoc', 'gc', 'weakref', 'inspect', 'platform', 'ctypes',
    'distutils', 'venv', 'pip', 'pkgutil', 'modulefinder', 'runpy', 'pdb', 'profile',
    'cProfile', 'timeit', 'trace', 'tracemalloc', 'getopt'
}

# Mapping of common import names to their PyPI package names
IMPORT_TO_PYPI = {
    'PIL': 'Pillow',
    'bs4': 'beautifulsoup4',
    'yaml': 'pyyaml',
    'dateutil': 'python-dateutil',
    'jwt': 'PyJWT',
    'dotenv': 'python-dotenv',
    'mysql': 'mysql-connector-python',
    'pg': 'postgresql',
    'fitz': 'PyMuPDF',
    'cv2': 'opencv-python',
    'docx': 'python-docx',
    'pptx': 'python-pptx',
    'openpyxl': 'openpyxl',
    'xlsxwriter': 'XlsxWriter',
    'pandas': 'pandas',
    'numpy': 'numpy',
    'scipy': 'scipy',
    'matplotlib': 'matplotlib',
    'sqlalchemy': 'SQLAlchemy',
    'requests': 'requests',
    'fastapi': 'fastapi',
    'flask': 'Flask',
    'django': 'Django',
    'pytest': 'pytest',
    'click': 'click',
    'rich': 'rich',
    'tqdm': 'tqdm',
    'jinja2': 'Jinja2',
    'pydantic': 'pydantic',
    'black': 'black',
    'flake8': 'flake8',
    'ruamel': 'ruamel.yaml',
    'websocket': 'websocket-client',
    'gunicorn': 'gunicorn',
    'redis': 'redis',
    'pymongo': 'pymongo',
    'boto3': 'boto3'
}

class CodebaseScanner(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.defines_main = False
        
    def visit_Import(self, node):
        for alias in node.names:
            # Get the top-level module name
            top_level = alias.name.split('.')[0]
            self.imports.add(top_level)
            
    def visit_ImportFrom(self, node):
        if node.level == 0 and node.module:  # Absolute import
            top_level = node.module.split('.')[0]
            self.imports.add(top_level)
            
    def visit_If(self, node):
        # Check if code block contains `if __name__ == '__main__':`
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == '__name__':
                for op in node.test.ops:
                    if isinstance(op, ast.Eq):
                        for comparator in node.test.comparators:
                            if isinstance(comparator, ast.Constant) and comparator.value == '__main__':
                                self.defines_main = True
                            elif isinstance(comparator, ast.Str) and comparator.s == '__main__':
                                # Compatibility with older Python versions where strings are ast.Str
                                self.defines_main = True
        self.generic_visit(node)

def scan_file(filepath):
    """Parses a Python file using AST and extracts imports and entry points."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=filepath)
        scanner = CodebaseScanner()
        scanner.visit(tree)
        return scanner.imports, scanner.defines_main
    except Exception as e:
        # Ignore parse/read errors gracefully
        return set(), False

def analyze_codebase(directory):
    """Scans the directory recursively and returns all imports and potential entry points."""
    all_imports = set()
    entry_points = {}
    local_packages = set()
    
    # First, list all directory names to find local packages/modules
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
            local_packages.add(item)
        elif item.endswith(".py"):
            local_packages.add(item[:-3])

    # Scan python files
    for root, _, files in os.walk(directory):
        # Skip common directories
        if any(d in root for d in [".git", "venv", ".venv", "__pycache__", "build", "dist", ".egg-info"]):
            continue
            
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                imports, defines_main = scan_file(filepath)
                all_imports.update(imports)
                
                if defines_main:
                    rel_path = os.path.relpath(filepath, directory)
                    mod_name = os.path.splitext(rel_path)[0].replace(os.sep, ".")
                    entry_points[file] = mod_name

    # Filter out local modules and standard libraries
    filtered_imports = set()
    for imp in all_imports:
        if imp not in local_packages and imp not in STD_LIB_MODULES:
            # Map import name to PyPI name
            pypi_name = IMPORT_TO_PYPI.get(imp, imp.lower().replace("_", "-"))
            filtered_imports.add(pypi_name)
            
    return filtered_imports, entry_points

def main():
    parser = argparse.ArgumentParser(
        description="Scan Python source files, analyze dependencies, and generate a pyproject.toml configuration."
    )
    parser.add_argument(
        "directory", 
        nargs="?", 
        default=".", 
        help="Root directory of the Python project to scan (default: current directory)."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Path to save the generated pyproject.toml. If omitted, writes to stdout."
    )
    parser.add_argument(
        "--name", 
        help="Override the automatically inferred project name."
    )
    parser.add_argument(
        "--version", 
        default="0.1.0", 
        help="Default project version (default: 0.1.0)."
    )
    parser.add_argument(
        "--description", 
        default="A python project package.", 
        help="Project description."
    )
    parser.add_argument(
        "--python-version", 
        default=">=3.8", 
        help="Inferred Python version requirement (default: >=3.8)."
    )
    
    args = parser.parse_args()
    
    scan_dir = os.path.abspath(args.directory)
    if not os.path.isdir(scan_dir):
        print(f"Error: Directory '{args.directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning codebase under {scan_dir}...", file=sys.stderr)
    dependencies, entry_points = analyze_codebase(scan_dir)
    
    # Inferred project name
    proj_name = args.name or os.path.basename(scan_dir).lower().replace("_", "-").replace(" ", "-")
    if proj_name == "." or proj_name == "":
        proj_name = "mypackage"
        
    # Check for Readme file
    readme_file = ""
    for r_file in ["README.md", "README.txt", "README"]:
        if os.path.exists(os.path.join(scan_dir, r_file)):
            readme_file = r_file
            break
            
    # Construct TOML
    toml = []
    toml.append('[build-system]')
    toml.append('requires = ["hatchling"]')
    toml.append('build-backend = "hatchling.build"')
    toml.append('')
    toml.append('[project]')
    toml.append(f'name = "{proj_name}"')
    toml.append(f'version = "{args.version}"')
    toml.append(f'description = "{args.description}"')
    
    if readme_file:
        toml.append(f'readme = "{readme_file}"')
        
    toml.append(f'requires-python = "{args.python_version}"')
    
    # Authors placeholder
    toml.append('authors = [')
    toml.append('    { name = "Developer Name", email = "developer@example.com" }')
    toml.append(']')
    
    toml.append('classifiers = [')
    toml.append('    "Programming Language :: Python :: 3",')
    toml.append('    "License :: OSI Approved :: MIT License",')
    toml.append('    "Operating System :: OS Independent",')
    toml.append(']')
    toml.append('')
    
    # Dependencies
    toml.append('dependencies = [')
    for dep in sorted(dependencies):
        toml.append(f'    "{dep}",')
    toml.append(']')
    toml.append('')
    
    # Scripts / Entry Points
    if entry_points:
        toml.append('[project.scripts]')
        for filename, module_path in sorted(entry_points.items()):
            script_name = os.path.splitext(filename)[0].replace("_", "-")
            # Assumes standard main() entry point exists in target file
            toml.append(f'{script_name} = "{module_path}:main"')
        toml.append('')
        
    toml_str = "\n".join(toml)
    
    output_path = args.output
    if not output_path and args.output is not None:
        output_path = "pyproject.toml"
        
    if output_path:
        # Resolve path
        if not os.path.isabs(output_path):
            output_path = os.path.join(scan_dir, output_path)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(toml_str)
            print(f"Successfully generated and wrote {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(toml_str)

if __name__ == "__main__":
    main()
