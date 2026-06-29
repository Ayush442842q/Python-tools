#!/usr/bin/env python3
"""
SQL Injection Detector
Statically analyzes Python code using Abstract Syntax Trees (AST) to identify
potential SQL injection vulnerabilities. Detects dynamic string formatting,
interpolations (f-strings), or string concatenations passed to database execute calls.
"""

import argparse
import ast
import os
import sys
from typing import List, Dict, Any, Tuple

# ANSI color codes for clean reporting
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"

# Common database execution methods to monitor
DB_EXECUTE_METHODS = {
    "execute", 
    "executemany", 
    "execute_query", 
    "raw", 
    "execute_sql"
}

# Simple SQL keyword matching to confirm if a string/operation represents a query
SQL_KEYWORDS = {
    "select", "insert", "update", "delete", "from", 
    "where", "join", "into", "values", "drop", "alter"
}

class SQLInjectionVisitor(ast.NodeVisitor):
    """AST visitor that audits code for dynamic SQL statements inside execute calls."""
    
    def __init__(self, filename: str, lines: List[str]):
        self.filename = filename
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []

    def _is_sql_query(self, text: str) -> bool:
        """Determines if a string contains typical SQL syntax keywords."""
        words = text.lower().split()
        # Check if at least two sql keywords exist in the text to minimize false positives
        matches = [w for w in words if any(kw in w for kw in SQL_KEYWORDS)]
        return len(matches) >= 1

    def _analyze_expression(self, node: ast.AST) -> Tuple[bool, str, str]:
        """Analyzes an AST node to detect if it involves dynamic string manipulation.
        Returns (is_dynamic, explanation, sql_substring_if_found)"""
        
        # 1. f-strings (JoinedStr in AST)
        if isinstance(node, ast.JoinedStr):
            # Check if there's any text element that looks like SQL
            sql_found = False
            full_text = ""
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    full_text += val.value
                elif isinstance(val, ast.Str): # Support for older Python versions
                    full_text += val.s
                else:
                    full_text += "{expr}"
            
            if self._is_sql_query(full_text):
                return True, f"f-string interpolation (JoinedStr)", full_text
            return False, "", ""

        # 2. String formatting call: "select * from ...".format(...)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                # Check if the string base is sql
                base = node.func.value
                if isinstance(base, (ast.Constant, ast.Str)):
                    val = base.value if isinstance(base, ast.Constant) else base.s
                    if self._is_sql_query(val):
                        return True, "String format() method call", val

        # 3. Binary operations: string additions ("SELECT ... " + var) or modulo formatting ("SELECT ... %s" % var)
        if isinstance(node, ast.BinOp):
            # Concatenation (+)
            if isinstance(node.op, ast.Add):
                # Traverse left and right to check if any side is a string containing SQL
                left_dyn, left_explain, left_val = self._analyze_expression(node.left)
                right_dyn, right_explain, right_val = self._analyze_expression(node.right)
                
                # Check if either side is a constant string containing SQL keywords
                left_is_str = isinstance(node.left, (ast.Constant, ast.Str))
                right_is_str = isinstance(node.right, (ast.Constant, ast.Str))
                
                left_txt = (node.left.value if isinstance(node.left, ast.Constant) else node.left.s) if left_is_str else ""
                right_txt = (node.right.value if isinstance(node.right, ast.Constant) else node.right.s) if right_is_str else ""
                
                if (left_is_str and self._is_sql_query(left_txt)) or (right_is_str and self._is_sql_query(right_txt)):
                    return True, "String concatenation (+ operator)", left_txt or right_txt
                
                if left_dyn or right_dyn:
                    return True, "Cascaded string concatenation (+)", left_val or right_val
            
            # Modulo formatting (%)
            elif isinstance(node.op, ast.Mod):
                if isinstance(node.left, (ast.Constant, ast.Str)):
                    val = node.left.value if isinstance(node.left, ast.Constant) else node.left.s
                    if self._is_sql_query(val):
                        # SQL Injection is highly likely if % formatting is used with string inputs directly
                        return True, "Modulo string formatting (%% operator)", val

        # 4. Standard Constants / Str (safe unless built dynamically earlier)
        if isinstance(node, (ast.Constant, ast.Str)):
            return False, "", ""

        # 5. Name variables (might be dynamic, but we can't do full dataflow analysis simply)
        return False, "", ""

    def visit_Call(self, node: ast.Call):
        """Overrides visit_Call to inspect database execute statements."""
        # Check if call is method attribute (e.g. cursor.execute)
        method_name = ""
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            method_name = node.func.id

        if method_name in DB_EXECUTE_METHODS:
            # Audit the first argument (usually the SQL query string)
            if node.args:
                sql_arg = node.args[0]
                is_vuln, reason, query_sample = self._analyze_expression(sql_arg)
                
                if is_vuln:
                    # Get lines of context
                    line_no = node.lineno
                    context_line = self.lines[line_no - 1].strip() if line_no <= len(self.lines) else "N/A"
                    
                    self.findings.append({
                        "line": line_no,
                        "context": context_line,
                        "reason": reason,
                        "query_sample": query_sample,
                        "severity": "HIGH" if "f-string" in reason or "%" in reason or "format" in reason else "MEDIUM"
                    })
                    
        # Continue traversing
        self.generic_visit(node)

def scan_file(filepath: str) -> List[Dict[str, Any]]:
    """Reads a Python file, parses it to AST, and audits for SQL Injection."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            lines = code.splitlines()
            
        tree = ast.parse(code, filename=filepath)
        visitor = SQLInjectionVisitor(filepath, lines)
        visitor.visit(tree)
        return visitor.findings
    except SyntaxError as se:
        # Return error as warning/skipped file
        return [{"error": f"SyntaxError during parsing: {se}"}]
    except Exception as e:
        return [{"error": f"Failed to parse file: {e}"}]

def run_detector(path: str, verbose: bool) -> Tuple[int, int]:
    """Scans all Python files in the given directory path."""
    python_files = []
    
    if os.path.isfile(path):
        if path.endswith(".py"):
            python_files.append(path)
    else:
        for root, _, files in os.walk(path):
            # Skip hidden folders and virtual environments
            if any(part.startswith(".") or part in {"venv", "env", "node_modules", "__pycache__"} for part in root.split(os.sep)):
                continue
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))

    total_vulns = 0
    scanned_count = 0
    
    print(f"\n[*] SQL Injection Static Security Detector")
    print(f"[*] Scanning {len(python_files)} Python files in: {path}...\n")
    
    for filepath in python_files:
        scanned_count += 1
        rel_path = os.path.relpath(filepath, path)
        findings = scan_file(filepath)
        
        # Separate errors and actual findings
        errors = [f for f in findings if "error" in f]
        vulns = [f for f in findings if "error" not in f]
        
        if errors and verbose:
            print(f"{COLOR_YELLOW}[WARNING]{COLOR_RESET} Skipped {rel_path} - {errors[0]['error']}")
            
        if vulns:
            total_vulns += len(vulns)
            print(f"{COLOR_RED}[VULNERABILITY FOUND]{COLOR_RESET} in file: {COLOR_CYAN}{rel_path}{COLOR_RESET}")
            for v in vulns:
                sev_color = COLOR_RED if v["severity"] == "HIGH" else COLOR_YELLOW
                print(f"  ├─ Line {v['line']}: {sev_color}{v['severity']}{COLOR_RESET} Severity")
                print(f"  ├─ Reason: {v['reason']}")
                print(f"  ├─ Code Snippet: `{v['context']}`")
                print(f"  └─ Remediation: Use parameterized queries instead of dynamic string building.")
                print(f"     Example: cursor.execute(\"SELECT * FROM users WHERE name = ?\", (username,))")
                print()
                
    return scanned_count, total_vulns

def main():
    parser = argparse.ArgumentParser(
        description="Static security scanner to detect SQL injection vulnerabilities in Python codebases."
    )
    parser.add_argument(
        "path", 
        nargs="?", 
        default=".", 
        help="Path to Python file or folder to scan (default: current directory)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Show warnings and parsing errors for skipped files"
    )
    args = parser.parse_args()
    
    # Enable colors on Windows cmd if supported
    if sys.platform == "win32":
        os.system("color")

    try:
        scanned_count, total_vulns = run_detector(args.path, args.verbose)
        
        print("=" * 60)
        print(f" SCAN COMPLETED")
        print("=" * 60)
        print(f" Files Scanned: {scanned_count}")
        
        if total_vulns > 0:
            print(f" Vulnerabilities Detected: {COLOR_RED}{total_vulns}{COLOR_RESET}")
            print(f" Status: {COLOR_RED}FAIL - Security vulnerabilities identified.{COLOR_RESET}")
            sys.exit(1)
        else:
            print(f" Vulnerabilities Detected: {COLOR_GREEN}0{COLOR_RESET}")
            print(f" Status: {COLOR_GREEN}PASS - No direct SQL injection patterns found.{COLOR_RESET}")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n[-] Scan cancelled by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()
