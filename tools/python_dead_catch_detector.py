#!/usr/bin/env python3
import os
import ast
import argparse
import sys

# Simple ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

# Build Python's built-in exception hierarchy statically
# Format: exception_name -> list of ancestor exception names
BUILTIN_EXCEPTIONS_ANCESTORS = {
    "BaseException": [],
    
    # Direct subclasses of BaseException
    "Exception": ["BaseException"],
    "GeneratorExit": ["BaseException"],
    "KeyboardInterrupt": ["BaseException"],
    "SystemExit": ["BaseException"],
    
    # Subclasses of Exception
    "ArithmeticError": ["Exception", "BaseException"],
    "AssertionError": ["Exception", "BaseException"],
    "AttributeError": ["Exception", "BaseException"],
    "BufferError": ["Exception", "BaseException"],
    "EOFError": ["Exception", "BaseException"],
    "ImportError": ["Exception", "BaseException"],
    "LookupError": ["Exception", "BaseException"],
    "MemoryError": ["Exception", "BaseException"],
    "NameError": ["Exception", "BaseException"],
    "OSError": ["Exception", "BaseException"],
    "ReferenceError": ["Exception", "BaseException"],
    "RuntimeError": ["Exception", "BaseException"],
    "StopIteration": ["Exception", "BaseException"],
    "StopAsyncIteration": ["Exception", "BaseException"],
    "SyntaxError": ["Exception", "BaseException"],
    "SystemError": ["Exception", "BaseException"],
    "TypeError": ["Exception", "BaseException"],
    "ValueError": ["Exception", "BaseException"],
    "Warning": ["Exception", "BaseException"],
    
    # Subclasses of ArithmeticError
    "FloatingPointError": ["ArithmeticError", "Exception", "BaseException"],
    "OverflowError": ["ArithmeticError", "Exception", "BaseException"],
    "ZeroDivisionError": ["ArithmeticError", "Exception", "BaseException"],
    
    # Subclasses of ImportError
    "ModuleNotFoundError": ["ImportError", "Exception", "BaseException"],
    
    # Subclasses of LookupError
    "IndexError": ["LookupError", "Exception", "BaseException"],
    "KeyError": ["LookupError", "Exception", "BaseException"],
    
    # Subclasses of NameError
    "UnboundLocalError": ["NameError", "Exception", "BaseException"],
    
    # Subclasses of OSError
    "BlockingIOError": ["OSError", "Exception", "BaseException"],
    "ChildProcessError": ["OSError", "Exception", "BaseException"],
    "ConnectionError": ["OSError", "Exception", "BaseException"],
    "FileExistsError": ["OSError", "Exception", "BaseException"],
    "FileNotFoundError": ["OSError", "Exception", "BaseException"],
    "InterruptedError": ["OSError", "Exception", "BaseException"],
    "IsADirectoryError": ["OSError", "Exception", "BaseException"],
    "NotADirectoryError": ["OSError", "Exception", "BaseException"],
    "PermissionError": ["OSError", "Exception", "BaseException"],
    "ProcessLookupError": ["OSError", "Exception", "BaseException"],
    "TimeoutError": ["OSError", "Exception", "BaseException"],
    
    # Subclasses of ConnectionError
    "BrokenPipeError": ["ConnectionError", "OSError", "Exception", "BaseException"],
    "ConnectionAbortedError": ["ConnectionError", "OSError", "Exception", "BaseException"],
    "ConnectionRefusedError": ["ConnectionError", "OSError", "Exception", "BaseException"],
    "ConnectionResetError": ["ConnectionError", "OSError", "Exception", "BaseException"],
    
    # Subclasses of RuntimeError
    "NotImplementedError": ["RuntimeError", "Exception", "BaseException"],
    "RecursionError": ["RuntimeError", "Exception", "BaseException"],
    
    # Subclasses of SyntaxError
    "IndentationError": ["SyntaxError", "Exception", "BaseException"],
    
    # Subclasses of IndentationError
    "TabError": ["IndentationError", "SyntaxError", "Exception", "BaseException"],
    
    # Subclasses of ValueError
    "UnicodeError": ["ValueError", "Exception", "BaseException"],
    
    # Subclasses of UnicodeError
    "UnicodeDecodeError": ["UnicodeError", "ValueError", "Exception", "BaseException"],
    "UnicodeEncodeError": ["UnicodeError", "ValueError", "Exception", "BaseException"],
    "UnicodeTranslateError": ["UnicodeError", "ValueError", "Exception", "BaseException"],
}

class ExceptionShadowVisitor(ast.NodeVisitor):
    def __init__(self, file_path):
        self.file_path = file_path
        self.findings = [] # list of dicts: {line, message, type}

    def visit_Try(self, node):
        # Walk into nested try statements first
        self.generic_visit(node)
        
        seen_exceptions = [] # stores list of exceptions caught in previous blocks of this Try

        for handler in node.handlers:
            line_no = handler.lineno
            
            # 1. Broad catch validation
            if handler.type is None:
                # An empty "except:" is equivalent to "except BaseException:" (pre-3.x) or "except Exception:" (usually).
                # Technically it catches BaseException. If it is not the last handler, it syntax errors in Python,
                # but if we see it, we treat it as catching BaseException.
                for seen in seen_exceptions:
                    if seen == "BaseException" or seen == "Exception":
                        self.findings.append({
                            "line": line_no,
                            "type": "shadowed",
                            "message": f"Broad catch-all 'except:' is shadowed by an earlier handler for '{seen}'."
                        })
                seen_exceptions.append("BaseException")
                continue

            # 2. Extract exception names caught by this handler
            caught_here = []
            if isinstance(handler.type, ast.Tuple):
                for element in handler.type.elts:
                    name = self._get_exception_name(element)
                    if name:
                        caught_here.append(name)
            else:
                name = self._get_exception_name(handler.type)
                if name:
                    caught_here.append(name)

            for name in caught_here:
                # Check for shadowing
                for seen in seen_exceptions:
                    # Case A: Exact duplicate
                    if name == seen:
                        self.findings.append({
                            "line": line_no,
                            "type": "duplicate",
                            "message": f"Duplicate catch block: exception '{name}' was already caught in an earlier handler of this try block."
                        })
                    
                    # Case B: Parent exception was caught earlier, shadowing this subclass
                    elif name in BUILTIN_EXCEPTIONS_ANCESTORS and seen in BUILTIN_EXCEPTIONS_ANCESTORS[name]:
                        self.findings.append({
                            "line": line_no,
                            "type": "shadowed",
                            "message": f"Shadowed/Dead catch block: exception '{name}' is a subclass of '{seen}', which was already caught on a preceding line."
                        })
                
                seen_exceptions.append(name)

    def _get_exception_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Handles things like os.error, sys.exit, etc.
            return node.attr
        return None

def analyze_python_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
        return []

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as se:
        print(f"{COLOR_YELLOW}Warning: Syntax error parsing AST for {file_path}: {se}{COLOR_RESET}")
        return []

    visitor = ExceptionShadowVisitor(file_path)
    visitor.visit(tree)
    return visitor.findings

def main():
    parser = argparse.ArgumentParser(
        description="Statically audit Python code for exception shadowing and dead catch blocks."
    )
    parser.add_argument("path", help="Path to a Python file or directory to scan")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting Python Exception Shadowing Auditor...{COLOR_RESET}")
    print("-" * 65)

    total_files_scanned = 0
    total_findings_count = 0

    files_to_scan = []
    if os.path.isfile(args.path):
        if args.path.endswith(".py"):
            files_to_scan.append(args.path)
    else:
        for root, _, files in os.walk(args.path):
            if "node_modules" in root or ".git" in root or "venv" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    files_to_scan.append(os.path.join(root, file))

    for file_path in files_to_scan:
        total_files_scanned += 1
        findings = analyze_python_file(file_path)
        if findings:
            total_findings_count += len(findings)
            print(f"\n{COLOR_CYAN}{COLOR_BOLD}File: {file_path}{COLOR_RESET}")
            for f in findings:
                color = COLOR_RED if f["type"] == "shadowed" else COLOR_YELLOW
                print(f"  Line {f['line']}: [{color}{f['type'].upper()}{COLOR_RESET}] {f['message']}")

    print("-" * 65)
    print(f"{COLOR_BOLD}Summary:{COLOR_RESET}")
    print(f"  Files scanned: {total_files_scanned}")
    print(f"  Total issues found: {total_findings_count}")
    
    if total_findings_count > 0:
        sys.exit(1)
    else:
        print(f"  {COLOR_GREEN}Result: No dead or shadowed catch blocks found!{COLOR_RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
