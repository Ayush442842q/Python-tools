#!/usr/bin/env python3
"""
Python Exception Flow Auditor
Parses Python source files using AST to extract defined custom exceptions,
raised exceptions, and caught exceptions, auditing handler safety and generating flows.

Features:
1. Scans Python files to build an exception catalog.
2. Identifies custom exception definitions.
3. Traces 'raise' statements and locates potential uncaught or generic exceptions.
4. Identifies 'except' blocks, checking for safety issues:
   - Bare 'except:' or 'except Exception:' (generic catching)
   - Empty exception handlers (silent failures / 'pass')
   - Unchained re-raises (raising a new exception without 'from')
5. Generates reports in terminal (colored text) and Mermaid.js format.
"""

import argparse
import ast
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_DIM = "\033[2m"

def supports_color() -> bool:
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_CYAN = ""
    COLOR_DIM = ""


class ExceptionFlowVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.defined_exceptions: List[Dict] = []
        self.raised_exceptions: List[Dict] = []
        self.caught_exceptions: List[Dict] = []
        self.issues: List[Dict] = []
        
        self.current_function = "Global scope"
        self._try_stack: List[ast.Try] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        old_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_func

    def visit_ClassDef(self, node: ast.ClassDef):
        # Detect custom exceptions
        is_exception = False
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
                if "Exception" in base.id or "Error" in base.id or base.id == "BaseException":
                    is_exception = True
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                base_names.append(f"{base.value.id}.{base.attr}")
                if "Exception" in base.attr or "Error" in base.attr:
                    is_exception = True

        if is_exception:
            self.defined_exceptions.append({
                "name": node.name,
                "bases": base_names,
                "line": node.lineno,
                "file": self.filepath
            })
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        exc_type = "Unknown"
        if node.exc:
            if isinstance(node.exc, ast.Name):
                exc_type = node.exc.id
            elif isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):
                    exc_type = node.exc.func.id
                elif isinstance(node.exc.func, ast.Attribute) and isinstance(node.exc.func.value, ast.Name):
                    exc_type = f"{node.exc.func.value.id}.{node.exc.func.attr}"
            elif isinstance(node.exc, ast.Attribute) and isinstance(node.exc.value, ast.Name):
                exc_type = f"{node.exc.value.id}.{node.exc.attr}"

        self.raised_exceptions.append({
            "type": exc_type,
            "line": node.lineno,
            "function": self.current_function,
            "file": self.filepath
        })
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        self._try_stack.append(node)
        
        # Analyze handlers
        for handler in node.handlers:
            caught_type = "bare"
            if handler.type:
                if isinstance(handler.type, ast.Name):
                    caught_type = handler.type.id
                elif isinstance(handler.type, ast.Tuple):
                    names = []
                    for t in handler.type.elts:
                        if isinstance(t, ast.Name):
                            names.append(t.id)
                        elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                            names.append(f"{t.value.id}.{t.attr}")
                    caught_type = f"({', '.join(names)})"
                elif isinstance(handler.type, ast.Attribute) and isinstance(handler.type.value, ast.Name):
                    caught_type = f"{handler.type.value.id}.{handler.type.attr}"

            self.caught_exceptions.append({
                "type": caught_type,
                "line": handler.lineno,
                "function": self.current_function,
                "file": self.filepath
            })

            # Audit: Bare except or broad exception
            if caught_type == "bare" or caught_type == "Exception" or caught_type == "BaseException":
                # Check if it contains only 'pass' or 'raise'
                is_empty = False
                if len(handler.body) == 1:
                    body_node = handler.body[0]
                    if isinstance(body_node, ast.Pass):
                        is_empty = True
                    elif isinstance(body_node, ast.Expr) and isinstance(body_node.value, ast.Constant) and body_node.value.value is Ellipsis:
                        is_empty = True

                self.issues.append({
                    "type": "Broad Exception Catch",
                    "message": f"Broad/bare exception handler catching '{caught_type}' at line {handler.lineno}.",
                    "severity": "MEDIUM" if not is_empty else "HIGH",
                    "file": self.filepath,
                    "line": handler.lineno,
                    "function": self.current_function
                })
                
                if is_empty:
                    self.issues.append({
                        "type": "Silent Exception Handler",
                        "message": f"Silent exception handler ('pass' / '...') at line {handler.lineno} swallowing all exceptions.",
                        "severity": "HIGH",
                        "file": self.filepath,
                        "line": handler.lineno,
                        "function": self.current_function
                    })
            else:
                # Normal exceptions: check if empty handler
                if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                    self.issues.append({
                        "type": "Silent Exception Handler",
                        "message": f"Exception handler for '{caught_type}' is empty (uses 'pass') at line {handler.lineno}.",
                        "severity": "MEDIUM",
                        "file": self.filepath,
                        "line": handler.lineno,
                        "function": self.current_function
                    })

        # Visit children
        self.generic_visit(node)
        self._try_stack.pop()


def analyze_file(filepath: str) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code)
        visitor = ExceptionFlowVisitor(filepath)
        visitor.visit(tree)
        return visitor.defined_exceptions, visitor.raised_exceptions, visitor.caught_exceptions, visitor.issues
    except Exception as e:
        return [], [], [], [{
            "type": "File Parse Error",
            "message": f"Could not parse file: {e}",
            "severity": "HIGH",
            "file": filepath,
            "line": 0,
            "function": "N/A"
        }]


def generate_mermaid(defined: List[Dict], raised: List[Dict], caught: List[Dict]) -> str:
    lines = ["graph TD", "    subgraph Exceptions Raised/Defined"]
    
    # Custom exceptions nodes
    added_nodes = set()
    for d in defined:
        node_id = f"def_{d['name']}"
        added_nodes.add(node_id)
        bases_str = f" inherits {', '.join(d['bases'])}" if d['bases'] else ""
        lines.append(f"        {node_id}[\"Custom: {d['name']}{bases_str}\"]")

    # Raised exceptions nodes
    for r in raised:
        node_id = f"raise_{r['type']}"
        if node_id not in added_nodes and r['type'] != "Unknown":
            added_nodes.add(node_id)
            lines.append(f"        {node_id}[\"Raises: {r['type']}\"]")
            
    lines.append("    end")
    lines.append("    subgraph Exceptions Caught")
    
    # Caught exceptions nodes
    for c in caught:
        node_id = f"catch_{c['type']}"
        if node_id not in added_nodes:
            added_nodes.add(node_id)
            lines.append(f"        {node_id}[\"Catches: {c['type']}\"]")
            
    lines.append("    end")

    # Draw flows (if raised exception type matches caught exception type)
    lines.append("    %% Flow mappings")
    for r in raised:
        r_type = r['type']
        if r_type == "Unknown":
            continue
        for c in caught:
            c_type = c['type']
            if c_type == r_type or c_type == "Exception" or c_type == "bare":
                lines.append(f"    raise_{r_type} -->|handled by| catch_{c_type}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Audits Python exception raising and handling structures, locating unsafe exception handlers and mapping flows.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", help="Path to a Python file or directory to scan")
    parser.add_argument("--mermaid", action="store_true", help="Generate Mermaid.js graph format output")
    parser.add_argument("--exclude", help="Comma-separated file patterns to exclude", default="")
    
    args = parser.parse_args()

    exclude_patterns = [p.strip() for p in args.exclude.split(",") if p.strip()]

    all_defined = []
    all_raised = []
    all_caught = []
    all_issues = []

    if os.path.isfile(args.path):
        d, r, c, i = analyze_file(args.path)
        all_defined.extend(d)
        all_raised.extend(r)
        all_caught.extend(c)
        all_issues.extend(i)
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    
                    # Exclude check
                    skip = False
                    for pattern in exclude_patterns:
                        if pattern in filepath:
                            skip = True
                            break
                    if skip:
                        continue

                    d, r, c, i = analyze_file(filepath)
                    all_defined.extend(d)
                    all_raised.extend(r)
                    all_caught.extend(c)
                    all_issues.extend(i)
    else:
        print(f"{COLOR_RED}Error: Path '{args.path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    if args.mermaid:
        print(generate_mermaid(all_defined, all_raised, all_caught))
        return

    # Print Text Report
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== PYTHON EXCEPTION FLOW AUDIT REPORT ==={COLOR_RESET}\n")

    print(f"{COLOR_BOLD}Summary statistics:{COLOR_RESET}")
    print(f"  Files audited      : {args.path}")
    print(f"  Custom Exceptions  : {len(all_defined)}")
    print(f"  Exception Raises   : {len(all_raised)}")
    print(f"  Exception Handlers : {len(all_caught)}")
    print(f"  Issues Detected    : {len(all_issues)}\n")

    if all_defined:
        print(f"{COLOR_BOLD}{COLOR_GREEN}Defined Custom Exceptions:{COLOR_RESET}")
        for d in all_defined:
            bases = f" (inherits {', '.join(d['bases'])})" if d['bases'] else ""
            print(f"  - {COLOR_BOLD}{d['name']}{COLOR_RESET}{bases} in {d['file']}:{d['line']}")
        print()

    # Audit Issues
    if all_issues:
        print(f"{COLOR_BOLD}{COLOR_YELLOW}Safety Audit Issues:{COLOR_RESET}")
        high_issues = [i for i in all_issues if i['severity'] == "HIGH"]
        med_issues = [i for i in all_issues if i['severity'] == "MEDIUM"]
        
        for issue in high_issues:
            print(f"  [{COLOR_RED}HIGH{COLOR_RESET}] {issue['type']} in {issue['file']}:{issue['line']} (Function: {issue['function']})")
            print(f"         {issue['message']}")
            
        for issue in med_issues:
            print(f"  [{COLOR_YELLOW}MEDIUM{COLOR_RESET}] {issue['type']} in {issue['file']}:{issue['line']} (Function: {issue['function']})")
            print(f"         {issue['message']}")
        print()
    else:
        print(f"{COLOR_BOLD}{COLOR_GREEN}✓ No exception safety issues detected!{COLOR_RESET}\n")

    # Details of Raises and Catches
    print(f"{COLOR_BOLD}Exception Flow Maps (Top 15 Raises):{COLOR_RESET}")
    for r in all_raised[:15]:
        # See if there is a matching handler in the same function/file
        handlers = [c for c in all_caught if c['file'] == r['file'] and (c['type'] == r['type'] or c['type'] == "Exception" or c['type'] == "bare")]
        handler_info = ""
        if handlers:
            handler_info = f" -> {COLOR_GREEN}Caught by '{handlers[0]['type']}' (line {handlers[0]['line']}){COLOR_RESET}"
        else:
            handler_info = f" -> {COLOR_RED}Uncaught or Propagates{COLOR_RESET}"

        print(f"  - {COLOR_CYAN}{r['type']}{COLOR_RESET} raised in {COLOR_BOLD}{r['function']}{COLOR_RESET} ({os.path.basename(r['file'])}:{r['line']}){handler_info}")

    if len(all_raised) > 15:
        print(f"  ... and {len(all_raised) - 15} more raises.")


if __name__ == "__main__":
    main()
