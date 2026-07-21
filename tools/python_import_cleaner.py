#!/usr/bin/env python3
"""
Python Import Cleaner & Sorter
Parses Python files using the built-in 'ast' module to:
1. Detect unused imports (both 'import x' and 'from x import y').
2. Sort and group remaining imports according to PEP 8:
   - Group 1: Standard library imports
   - Group 2: Third-party imports
   - Group 3: Local application/relative imports
3. Preview changes (diff) or modify files in-place.

Usage:
    python tools/python_import_cleaner.py my_script.py
    python tools/python_import_cleaner.py my_script.py --check-only
    python tools/python_import_cleaner.py my_script.py --inplace
"""

import argparse
import ast
import difflib
import os
import sys

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Common Python Standard Library module names (fallback for Python < 3.10)
STD_LIBS = {
    'abc', 'argparse', 'array', 'ast', 'asyncio', 'atexit', 'base64', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs', 'collections',
    'colorsys', 'compileall', 'concurrent', 'configparser', 'contextlib', 'contextvars',
    'copy', 'copyreg', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm',
    'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email', 'encodings', 'ensurepip',
    'enum', 'errno', 'faulthandler', 'filecmp', 'fileinput', 'fnmatch', 'fractions', 'ftplib',
    'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp', 'gzip',
    'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'importlib', 'inspect',
    'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache', 'locale',
    'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap',
    'modulefinder', 'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator',
    'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
    'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'pprint', 'profile', 'pstats',
    'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're',
    'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
    'selectors', 'shelve', 'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket',
    'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep',
    'struct', 'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny',
    'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time',
    'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback', 'tracemalloc',
    'tty', 'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'warnings',
    'wave', 'weakref', 'webbrowser', 'wsgiref', 'xdgurl', 'xml', 'xmlrpc', 'zipapp', 'zipfile',
    'zlib'
}

class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imported_names = {}  # alias -> (module, original_name, node)
        self.used_names = set()
        self.import_nodes = []

    def visit_Import(self, node):
        self.import_nodes.append(node)
        for alias in node.names:
            name = alias.name
            asname = alias.asname or name
            self.imported_names[asname] = (name, name, node)

    def visit_ImportFrom(self, node):
        self.import_nodes.append(node)
        module = node.module or ''
        # Keep relative level dot prefixes
        if node.level > 0:
            module = '.' * node.level + module
        for alias in node.names:
            name = alias.name
            asname = alias.asname or name
            self.imported_names[asname] = (module, name, node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Captures cases where module is used as an attribute base (e.g. os.path)
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

def classify_module(module_name, project_dir):
    """Classifies a module into standard, local, or third-party."""
    if not module_name:
        return 'local'
        
    root_module = module_name.lstrip('.').split('.')[0]
    
    if root_module in STD_LIBS or root_module in sys.builtin_module_names:
        return 'standard'
        
    # Check if it resides in the current project directory as a folder/file
    if project_dir:
        local_path_dir = os.path.join(project_dir, root_module)
        local_path_file = os.path.join(project_dir, root_module + ".py")
        if os.path.isdir(local_path_dir) or os.path.isfile(local_path_file) or module_name.startswith('.'):
            return 'local'
            
    return 'thirdparty'

def format_import_node(module, name, asname):
    """Helper to stringify an import."""
    # Detect if it was a plain import or import-from
    if module == name:
        if asname != name:
            return f"import {name} as {asname}"
        return f"import {name}"
    else:
        if asname != name:
            return f"from {module} import {name} as {asname}"
        return f"from {module} import {name}"

def organize_imports(active_imports, project_dir):
    """Sorts and formats imports into PEP-8 groups."""
    standard = []
    thirdparty = []
    local = []

    for name, (module, orig, _) in active_imports.items():
        classification = classify_module(module, project_dir)
        stmt = format_import_node(module, orig, name)
        
        if classification == 'standard':
            standard.append(stmt)
        elif classification == 'thirdparty':
            thirdparty.append(stmt)
        else:
            local.append(stmt)

    # Sort each group alphabetically
    standard.sort()
    thirdparty.sort()
    local.sort()

    blocks = []
    if standard:
        blocks.append("\n".join(standard))
    if thirdparty:
        blocks.append("\n".join(thirdparty))
    if local:
        blocks.append("\n".join(local))

    return "\n\n".join(blocks)

def clean_file(file_path, check_only=False, inplace=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        print(f"{RED}[ERROR] Could not read file {file_path}: {e}{RESET}")
        return False

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"{RED}[ERROR] Syntax error in {file_path} (Line {e.lineno}): {e.msg}{RESET}")
        return False

    visitor = ASTVisitor()
    visitor.visit(tree)

    # Detect unused imports
    unused = []
    active_imports = {}

    for asname, info in visitor.imported_names.items():
        module, orig, node = info
        # Special exclusion: __init__.py files often import modules to expose them
        is_init = os.path.basename(file_path) == '__init__.py'
        
        # Unused detection: not in loaded names and not an init export
        if asname not in visitor.used_names and not is_init:
            unused.append((asname, module, orig, node.lineno))
        else:
            active_imports[asname] = info

    if not visitor.import_nodes:
        print(f"{GREEN}[PASS] No imports found in {file_path}.{RESET}")
        return True

    # Report unused imports
    if unused:
        print(f"{YELLOW}[WARN] Found {len(unused)} unused import(s) in {file_path}:{RESET}")
        for asname, module, orig, line in unused:
            stmt = format_import_node(module, orig, asname)
            print(f"  Line {line}: {RED}{stmt}{RESET}")
    else:
        print(f"{GREEN}[PASS] No unused imports found in {file_path}.{RESET}")

    # Reconstruct script without the old import lines
    # We locate the range of lines occupied by imports
    lines = source.splitlines()
    import_lines_indices = set()
    
    for node in visitor.import_nodes:
        # ast nodes contain end_lineno in 3.8+
        end_line = getattr(node, 'end_lineno', node.lineno)
        for i in range(node.lineno - 1, end_line):
            if i < len(lines):
                import_lines_indices.add(i)

    # Generate new import block
    project_dir = os.path.dirname(os.path.abspath(file_path))
    new_import_block = organize_imports(active_imports, project_dir)

    # Rebuild script
    # We want to replace the first import statement with the new import block,
    # and remove all other old import lines.
    cleaned_lines = []
    first_import_idx = min(node.lineno - 1 for node in visitor.import_nodes)
    
    # Check if there are leading comments (shebang, docstrings) we should preserve
    for idx, line in enumerate(lines):
        if idx in import_lines_indices:
            if idx == first_import_idx:
                cleaned_lines.append(new_import_block)
            continue
        cleaned_lines.append(line)

    new_source = "\n".join(cleaned_lines)
    # Match trailing newline of original file
    if source.endswith('\n'):
        new_source += '\n'

    # Print diff
    diff = list(difflib.unified_diff(
        source.splitlines(keepends=True),
        new_source.splitlines(keepends=True),
        fromfile=file_path,
        tofile=file_path + " (optimized)"
    ))

    if diff:
        print(f"\n{BOLD}Proposed changes for {file_path}:{RESET}")
        print("-" * 60)
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                sys.stdout.write(f"{GREEN}{line}{RESET}")
            elif line.startswith('-') and not line.startswith('---'):
                sys.stdout.write(f"{RED}{line}{RESET}")
            elif line.startswith('@@'):
                sys.stdout.write(f"{CYAN}{line}{RESET}")
            else:
                sys.stdout.write(line)
        print("-" * 60)
        
        if check_only:
            print(f"{YELLOW}[INFO] Checked {file_path}. File was not modified.{RESET}")
            return False
        
        if inplace:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_source)
                print(f"{GREEN}[PASS] In-place optimization complete for {file_path}.{RESET}")
            except Exception as e:
                print(f"{RED}[ERROR] Could not write to file {file_path}: {e}{RESET}")
                return False
        else:
            print(f"{YELLOW}[INFO] Run with --inplace to apply these changes.{RESET}")
    else:
        print(f"{GREEN}[PASS] Imports in {file_path} are already clean and optimized.{RESET}")

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Clean and sort Python imports in a file using AST analysis."
    )
    parser.add_argument("file", help="Python source file to optimize.")
    parser.add_argument("--check-only", action="store_true", help="Only check and report, do not apply changes.")
    parser.add_argument("--inplace", action="store_true", help="Modify the file in-place with changes.")

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"{RED}[ERROR] File '{args.file}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    success = clean_file(args.file, check_only=args.check_only, inplace=args.inplace)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(1)
