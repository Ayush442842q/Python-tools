#!/usr/bin/env python3
"""
Python AST Security Linter
A lightweight static analysis tool that parses Python files using the standard 'ast' module.
Scans for common security risks, insecure API usage, and hardcoded secrets.
"""

import os
import sys
import ast
import re
import argparse

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"

SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Regex for common secret/key patterns in variable assignments
SECRET_KEY_RE = re.compile(
    r'.*(key|secret|password|passwd|token|credential|auth|api_key|private_key).*',
    re.IGNORECASE
)

# Common high-entropy string matcher
ENTROPY_RE = re.compile(r'^[a-zA-Z0-9+/=_-]{16,128}$')

class SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.issues = []
        self.raw_lines = []
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                self.raw_lines = f.readlines()
        except Exception:
            pass

    def add_issue(self, node, severity, code, message, advice):
        line_num = getattr(node, 'lineno', 0)
        col_offset = getattr(node, 'col_offset', 0)
        code_snippet = ""
        if 0 < line_num <= len(self.raw_lines):
            code_snippet = self.raw_lines[line_num - 1].strip()

        self.issues.append({
            "filename": self.filename,
            "line": line_num,
            "col": col_offset,
            "severity": severity,
            "code": code,
            "message": message,
            "snippet": code_snippet,
            "advice": advice
        })

    def visit_Call(self, node):
        # 1. Check for eval() and exec()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('eval', 'exec'):
                self.add_issue(
                    node,
                    SEVERITY_HIGH,
                    "SEC100",
                    f"Use of insecure built-in function '{func_name}'",
                    "Avoid dynamic code execution with user-controlled input."
                )
            
            # Check tempfile.mktemp
            elif func_name == 'mktemp':
                self.add_issue(
                    node,
                    SEVERITY_MEDIUM,
                    "SEC101",
                    "Use of deprecated and insecure tempfile.mktemp()",
                    "Use tempfile.TemporaryFile or tempfile.mkstemp instead."
                )

        # 2. Check for subprocess with shell=True
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            # Check full path or module
            module_name = ""
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
            
            if module_name == 'subprocess' or func_name in ('Popen', 'call', 'run', 'check_output', 'check_call'):
                # Look for shell=True kwarg
                for keyword in node.keywords:
                    if keyword.arg == 'shell':
                        if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            self.add_issue(
                                node,
                                SEVERITY_HIGH,
                                "SEC200",
                                "Subprocess execution with shell=True",
                                "Set shell=False and pass arguments as a list to prevent shell injection."
                            )
                        elif isinstance(keyword.value, ast.Name) and keyword.value.id == 'True': # compatibility
                            self.add_issue(
                                node,
                                SEVERITY_HIGH,
                                "SEC200",
                                "Subprocess execution with shell=True",
                                "Set shell=False and pass arguments as a list to prevent shell injection."
                            )

            # 3. Check for insecure deserialization
            elif (module_name == 'pickle' and func_name in ('load', 'loads')) or \
                 (module_name == 'marshal' and func_name in ('load', 'loads')) or \
                 (module_name == 'shelve' and func_name == 'open'):
                self.add_issue(
                    node,
                    SEVERITY_HIGH,
                    "SEC300",
                    f"Insecure deserialization using '{module_name}.{func_name}'",
                    "Never deserialize untrusted data. Use safer formats like JSON or Protocol Buffers."
                )

            # 4. Check for unsafe PyYAML load
            elif module_name == 'yaml' and func_name == 'load':
                has_safe_loader = False
                for keyword in node.keywords:
                    if keyword.arg == 'Loader':
                        # Check if Loader is yaml.SafeLoader
                        if isinstance(keyword.value, ast.Attribute) and keyword.value.attr in ('SafeLoader', 'CSafeLoader'):
                            has_safe_loader = True
                        elif isinstance(keyword.value, ast.Name) and keyword.value.id in ('SafeLoader', 'CSafeLoader'):
                            has_safe_loader = True
                
                if not has_safe_loader:
                    self.add_issue(
                        node,
                        SEVERITY_HIGH,
                        "SEC301",
                        "Unsafe yaml.load() call",
                        "Use yaml.safe_load() or specify Loader=yaml.SafeLoader."
                    )

            # 5. Check XML parsing (insecure against Entity Expansion / XXE)
            elif module_name in ('xml', 'ElementTree', 'minidom') or func_name in ('parse', 'parseString', 'fromstring'):
                if module_name in ('ElementTree', 'minidom', 'etree') or (isinstance(node.func.value, ast.Attribute) and getattr(node.func.value.value, 'id', '') == 'xml'):
                    self.add_issue(
                        node,
                        SEVERITY_MEDIUM,
                        "SEC400",
                        "Standard XML parser used, vulnerable to XML external entity (XXE) attacks",
                        "Use defusedxml package to parse untrusted XML documents safely."
                    )

            # 6. Check insecure HTTP/SSL options
            elif module_name == 'ssl' and func_name == 'wrap_socket':
                self.add_issue(
                    node,
                    SEVERITY_MEDIUM,
                    "SEC500",
                    "Legacy ssl.wrap_socket() invoked",
                    "Use ssl.SSLContext to manage SSL connections instead."
                )
            
            # Check urllib context suppression
            elif module_name == 'urllib' or func_name == 'urlopen':
                for keyword in node.keywords:
                    if keyword.arg == 'context':
                        # If context is ssl._create_unverified_context
                        if isinstance(keyword.value, ast.Call) and isinstance(keyword.value.func, ast.Attribute):
                            if keyword.value.func.attr == '_create_unverified_context':
                                self.add_issue(
                                    node,
                                    SEVERITY_HIGH,
                                    "SEC501",
                                    "Certificate validation explicitly bypassed in urlopen",
                                    "Do not bypass SSL certificate verification in production environments."
                                )

        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self._check_import_name(node, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self._check_import_name(node, node.module)
        self.generic_visit(node)

    def _check_import_name(self, node, name):
        # Check for obsolete or insecure modules
        insecure_modules = {
            "telnetlib": "Telnet protocols do not encrypt traffic. Use paramiko or subprocess to SSH.",
            "ftplib": "FTP protocols do not encrypt credentials or files. Use SFTP via paramiko or urllib.",
            "cgi": "The cgi module is legacy and contains obsolete utilities.",
            "smtplib": "Make sure SMTP connections utilize STARTTLS or SSL/TLS.",
            "crypt": "The crypt module is deprecated and has weak cryptographic algorithms."
        }
        if name in insecure_modules:
            self.add_issue(
                node,
                SEVERITY_LOW,
                "SEC600",
                f"Import of insecure or deprecated module '{name}'",
                insecure_modules[name]
            )

    def visit_Assign(self, node):
        # Check for hardcoded credentials / keys
        # We look for variables like api_key = "..." or PASSWORD = "..."
        for target in node.targets:
            var_name = ""
            if isinstance(target, ast.Name):
                var_name = target.id
            elif isinstance(target, ast.Attribute):
                var_name = target.attr

            if var_name and SECRET_KEY_RE.match(var_name):
                # Verify if assigned value is a non-empty string constant
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    val = node.value.value.strip()
                    # Skip empty strings or typical placeholders
                    if val and len(val) > 5 and not any(p in val.lower() for p in ('place', 'your', 'todo', 'change', 'env', '<', '{')):
                        # Raise issue
                        self.add_issue(
                            node,
                            SEVERITY_HIGH,
                            "SEC700",
                            f"Potential hardcoded credentials detected in variable '{var_name}'",
                            "Move sensitive keys and secrets to environment variables or config files."
                        )
        self.generic_visit(node)


def scan_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content, filepath)
        visitor = SecurityVisitor(filepath)
        visitor.visit(tree)
        return visitor.issues
    except SyntaxError as se:
        return [{
            "filename": filepath,
            "line": se.lineno or 0,
            "col": se.offset or 0,
            "severity": SEVERITY_LOW,
            "code": "SYNTAX",
            "message": f"Syntax error preventing security scan: {se.msg}",
            "snippet": se.text or "",
            "advice": "Fix syntax errors to enable full AST-based security analysis."
        }]
    except Exception as e:
        return [{
            "filename": filepath,
            "line": 0,
            "col": 0,
            "severity": SEVERITY_LOW,
            "code": "ERR",
            "message": f"Error scanning file: {str(e)}",
            "snippet": "",
            "advice": "Check file permissions and format."
        }]


def run_linter(path, recursive=True):
    all_issues = []
    file_count = 0

    if os.path.isfile(path):
        if path.endswith('.py'):
            all_issues.extend(scan_file(path))
            file_count = 1
    else:
        for root, _, files in os.walk(path):
            if not recursive and root != path:
                continue
            for file in files:
                if file.endswith('.py'):
                    # Skip build/venv directories
                    if any(p in root.replace('\\', '/').split('/') for p in ('venv', '.venv', 'build', 'dist', '__pycache__', '.git')):
                        continue
                    file_count += 1
                    filepath = os.path.join(root, file)
                    all_issues.extend(scan_file(filepath))

    # Print results
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== Python Code Security Report ==={COLOR_RESET}\n")
    print(f"Scanned {file_count} file(s).")
    
    if not all_issues:
        print(f"\n{COLOR_BOLD}{COLOR_GREEN}[+] No security vulnerabilities or static analysis issues identified!{COLOR_RESET}")
        return 0

    # Sort issues: High -> Medium -> Low
    severity_order = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}
    all_issues.sort(key=lambda i: (severity_order.get(i['severity'], 3), i['filename'], i['line']))

    high_count = sum(1 for i in all_issues if i['severity'] == SEVERITY_HIGH)
    med_count = sum(1 for i in all_issues if i['severity'] == SEVERITY_MEDIUM)
    low_count = sum(1 for i in all_issues if i['severity'] == SEVERITY_LOW)

    print(f"Found {len(all_issues)} issues: ", end="")
    print(f"{COLOR_RED}{high_count} High{COLOR_RESET}, ", end="")
    print(f"{COLOR_YELLOW}{med_count} Medium{COLOR_RESET}, ", end="")
    print(f"{COLOR_CYAN}{low_count} Low{COLOR_RESET}\n")

    current_file = ""
    for issue in all_issues:
        if issue['filename'] != current_file:
            current_file = issue['filename']
            print(f"\n{COLOR_BOLD}{COLOR_CYAN}File: {current_file}{COLOR_RESET}")
            print("-" * len(f"File: {current_file}"))

        color = COLOR_CYAN
        if issue['severity'] == SEVERITY_HIGH:
            color = COLOR_RED
        elif issue['severity'] == SEVERITY_MEDIUM:
            color = COLOR_YELLOW

        print(f"  [{color}{issue['severity']}{COLOR_RESET}] {COLOR_BOLD}{issue['code']}{COLOR_RESET}: {issue['message']} (Line {issue['line']})")
        if issue['snippet']:
            print(f"    {COLOR_BOLD}Code:{COLOR_RESET} {issue['snippet']}")
        print(f"    {COLOR_BOLD}Advice:{COLOR_RESET} {issue['advice']}\n")

    return len(all_issues)


def main():
    parser = argparse.ArgumentParser(description="AST-based Python Code Security Linter")
    parser.add_argument("target", nargs="?", default=".", help="File or folder to scan (default: current directory)")
    parser.add_argument("--no-recursive", action="store_false", dest="recursive", help="Do not scan subfolders recursively")

    args = parser.parse_args()

    sys.exit(run_linter(args.target, args.recursive))


if __name__ == "__main__":
    main()
