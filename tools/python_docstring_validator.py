#!/usr/bin/env python3
"""
Python Docstring Signature Matcher & Linter - Validate docstring arguments against actual function signatures.

Scans Python files and checks if existing docstrings match the actual function signatures:
  - Detects undocumented parameters (defined in signature but not in docstring)
  - Detects extraneous parameters (documented in docstring but missing in signature)
  - Supports Google, Sphinx (reStructuredText), and NumPy docstring conventions
  - Reports return statement inconsistencies (e.g. has return statements but no documented return value)
"""

import os
import ast
import re
import sys
import argparse

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

# Severity tags
SEV_ERROR = f"{COLOR_RED}[ERROR]{COLOR_RESET}"
SEV_WARNING = f"{COLOR_YELLOW}[WARNING]{COLOR_RESET}"
SEV_INFO = f"{COLOR_CYAN}[INFO]{COLOR_RESET}"

class DocstringValidator(ast.NodeVisitor):
    def __init__(self, filepath, style="auto"):
        self.filepath = filepath
        self.style = style
        self.issues = []
        self.current_class = None

    def visit_ClassDef(self, node):
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        self.check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.check_function(node)
        self.generic_visit(node)

    def parse_google_args(self, docstring):
        """Extract documented arguments from Google style docstring."""
        # Find 'Args:' or 'Arguments:' section
        pattern = r'(?:Args|Arguments):\s*\n(.*?)(?:\n\s*\n|\n\S|\Z)'
        match = re.search(pattern, docstring, re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        
        args_block = match.group(1)
        # Match lines like: "name (type): description" or "name: description"
        # Bullet points are optional, but usually indented
        arg_lines = re.findall(r'^\s*\*?\*?([a-zA-Z0-9_]+)\s*(?:\([^)]+\))?\s*:\s', args_block, re.MULTILINE)
        return arg_lines

    def parse_sphinx_args(self, docstring):
        """Extract documented arguments from Sphinx/reST style docstring."""
        # Match lines like: ":param name: description" or ":parameter name: description"
        arg_lines = re.findall(r':param(?:eter)?\s+([a-zA-Z0-9_]+)\s*:', docstring)
        return arg_lines

    def parse_numpy_args(self, docstring):
        """Extract documented arguments from NumPy style docstring."""
        # Find 'Parameters' section followed by line of hyphens
        pattern = r'Parameters\s*\n-+\s*\n(.*?)(?:\n\s*\n|\n[A-Z][a-z]+|\Z)'
        match = re.search(pattern, docstring, re.DOTALL)
        if not match:
            return []
        
        params_block = match.group(1)
        # Look for lines starting at the base indent level of the block, containing: "name : type" or "name"
        # NumPy args are declared at the beginning of the line inside the block
        arg_lines = re.findall(r'^\s*([a-zA-Z0-9_]+)\s*(?::\s*.*)?$', params_block, re.MULTILINE)
        # Filter empty matches
        return [a.strip() for a in arg_lines if a.strip()]

    def detect_style(self, docstring):
        if ":param" in docstring or ":type" in docstring:
            return "sphinx"
        if re.search(r'Parameters\s*\n-+\s*\n', docstring):
            return "numpy"
        if re.search(r'(?:Args|Arguments):\s*\n', docstring, re.IGNORECASE):
            return "google"
        return "unknown"

    def has_return_documentation(self, docstring, style):
        if style == "sphinx":
            return ":return" in docstring or ":rtype" in docstring
        if style == "numpy":
            return re.search(r'Returns\s*\n-+\s*\n', docstring) is not None
        if style == "google":
            return re.search(r'Returns?:\s*\n', docstring, re.IGNORECASE) is not None
        # Default fallback
        return any(term in docstring.lower() for term in ("returns:", "return:", ":return"))

    def check_function(self, node):
        docstring = ast.get_docstring(node)
        if not docstring:
            return # Skip functions with no docstring (handled by docstring coverage analyzers)

        # Build signature args list
        # Skip self and cls for methods
        all_args = [arg.arg for arg in node.args.args]
        if self.current_class and all_args:
            # Simple heuristic: if it's the first arg of a class function, it's self/cls
            if all_args[0] in ("self", "cls"):
                all_args.pop(0)

        # Detect/resolve docstring format style
        style = self.style
        if style == "auto":
            style = self.detect_style(docstring)
            if style == "unknown":
                # Default fallback to google if ambiguous
                style = "google"

        # Parse documented arguments based on style
        doc_args = []
        if style == "google":
            doc_args = self.parse_google_args(docstring)
        elif style == "sphinx":
            doc_args = self.parse_sphinx_args(docstring)
        elif style == "numpy":
            doc_args = self.parse_numpy_args(docstring)

        # If they didn't document any arguments, but the function takes arguments,
        # it might just be a brief one-line docstring. We only flag if they started
        # an Args/Parameters block but missed some, or if it's strict.
        has_args_section = False
        if style == "google" and "Args:" in docstring: has_args_section = True
        elif style == "numpy" and "Parameters" in docstring: has_args_section = True
        elif style == "sphinx" and ":param" in docstring: has_args_section = True

        # Check for discrepancies
        missing_in_doc = set(all_args) - set(doc_args)
        extraneous_in_doc = set(doc_args) - set(all_args)

        func_display_name = f"{self.current_class}.{node.name}" if self.current_class else node.name

        # Report missing args
        if missing_in_doc:
            # If there's an args section or if it has complex arguments
            if has_args_section or len(all_args) > 1:
                self.issues.append({
                    "line": node.lineno,
                    "severity": SEV_WARNING,
                    "function": func_display_name,
                    "message": f"Undocumented parameter(s) in docstring ({style} style): {', '.join(missing_in_doc)}",
                    "code": f"def {node.name}(...)"
                })

        # Report extraneous args
        if extraneous_in_doc:
            self.issues.append({
                "line": node.lineno,
                "severity": SEV_ERROR,
                "function": func_display_name,
                "message": f"Extraneous parameter(s) documented but not in signature: {', '.join(extraneous_in_doc)}",
                "code": f"def {node.name}(...)"
            })

        # Check returns statement
        # Check if function physically returns anything other than None/implicit
        has_return_val = False
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Return):
                if sub_node.value is not None:
                    # Ignore returning None directly: "return" or "return None"
                    if isinstance(sub_node.value, ast.Constant) and sub_node.value.value is None:
                        continue
                    if isinstance(sub_node.value, ast.Name) and sub_node.value.id == "None":
                        continue
                    has_return_val = True
                    break

        if has_return_val and not self.has_return_documentation(docstring, style):
            # Only warn if they have an args section or it's a long docstring (not a simple one-liner)
            if has_args_section or len(docstring.strip().splitlines()) > 1:
                self.issues.append({
                    "line": node.lineno,
                    "severity": SEV_INFO,
                    "function": func_display_name,
                    "message": f"Function returns a value but lacks documented return details in docstring ({style} style).",
                    "code": f"def {node.name}(...)"
                })

def audit_file(filepath, style="auto"):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        return []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
    except Exception as e:
        print(f"Error parsing file '{filepath}': {e}", file=sys.stderr)
        return []

    validator = DocstringValidator(filepath, style)
    validator.visit(tree)
    return validator.issues

def main():
    parser = argparse.ArgumentParser(description="Python Docstring Signature Matcher & Linter.")
    parser.add_argument("path", nargs="?", default=".", help="Path to Python file or directory to scan (default: current directory)")
    parser.add_argument("-s", "--style", choices=["google", "sphinx", "numpy", "auto"], default="auto", 
                        help="Expected docstring convention style (default: auto-detect)")
    parser.add_argument("--strict", action="store_true", help="Return non-zero exit code if warnings/errors are found")

    args = parser.parse_args()

    # Find python files
    files = []
    if os.path.isfile(args.path):
        if args.path.endswith(".py"):
            files.append(args.path)
    else:
        for root, _, filenames in os.walk(args.path):
            # Skip virtualenvs or common hidden folders
            if any(part in root.split(os.sep) for part in (".venv", "venv", ".git", "__pycache__", ".agents", "build", "dist")):
                continue
            for f in filenames:
                if f.endswith(".py"):
                    files.append(os.path.join(root, f))

    if not files:
        print("No Python files found to audit.")
        sys.exit(0)

    print(f"Auditing docstrings in {len(files)} Python files...\n")
    
    total_issues = 0
    errors_count = 0
    
    for file in sorted(files):
        issues = audit_file(file, args.style)
        if issues:
            print(f"File: {COLOR_CYAN}{file}{COLOR_RESET}")
            for iss in issues:
                print(f"  Line {iss['line']}: {iss['severity']} in function {COLOR_BOLD}{iss['function']}{COLOR_RESET}")
                print(f"    {iss['message']}")
                total_issues += 1
                if SEV_ERROR in iss["severity"] or SEV_WARNING in iss["severity"]:
                    errors_count += 1
            print()

    if total_issues == 0:
        print(f"{COLOR_GREEN}✓ All docstrings are perfectly aligned with function signatures!{COLOR_RESET}")
        sys.exit(0)
    else:
        print(f"Found a total of {COLOR_BOLD}{total_issues}{COLOR_RESET} issues.")
        if args.strict and errors_count > 0:
            print(f"{COLOR_RED}Strict mode: Exiting with error status.{COLOR_RESET}")
            sys.exit(1)
        sys.exit(0)

if __name__ == "__main__":
    main()
