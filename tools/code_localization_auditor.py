#!/usr/bin/env python3
"""
Code Localization Auditor
Scans codebase source files (Python, JS, TS, JSX, TSX, HTML) to detect hardcoded
user-facing strings that are not wrapped in internationalization (i18n) or
translation functions (e.g., _(), gettext(), t()).
"""

import os
import sys
import re
import ast
import argparse
import json
from typing import Dict, List, Set, Tuple

# Common regex patterns to filter out non-user-facing strings
URL_RE = re.compile(r'^https?://|^/[a-zA-Z0-9_.-]+')
PATH_RE = re.compile(r'^(\.{0,2}/)+[a-zA-Z0-9_.-]+|/usr/bin/|/dev/null|\.txt$|\.json$|\.csv$|\.py$|\.js$|\.html$|\.png$|\.jpg$')
VAR_OR_KEY_RE = re.compile(r'^[a-z0-9_]+$|^[A-Z0-9_]+$')
BASE64_RE = re.compile(r'^[a-zA-Z0-9+/=]{20,}$')
ENV_RE = re.compile(r'^ENV_|^[A-Z_]+_ENV$')
DATE_TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}')
HEX_COLOR_RE = re.compile(r'^#[a-fA-F0-9]{3,8}$')
SQL_RE = re.compile(r'\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bCREATE\b|\bDROP\b|\bFROM\b|\bWHERE\b', re.IGNORECASE)

# File patterns to exclude
DEFAULT_EXCLUDES = {
    '.git', '__pycache__', 'node_modules', 'venv', '.venv', 'dist', 'build',
    'locale', 'locales', 'translations', 'test', 'tests', 'setup.py'
}


def is_user_facing_string(s: str) -> bool:
    """Determine if a string is likely user-facing and needs translation."""
    s = s.strip()
    if not s:
        return False
    
    # Needs to contain letters
    if not any(c.isalpha() for c in s):
        return False
    
    # Exclude technical strings
    if URL_RE.match(s) or PATH_RE.match(s):
        return False
    if VAR_OR_KEY_RE.match(s):
        return False
    if BASE64_RE.match(s):
        return False
    if ENV_RE.match(s) or DATE_TIME_RE.match(s) or HEX_COLOR_RE.match(s):
        return False
    if SQL_RE.search(s):
        return False
        
    # Strings with spaces, punctuation, or multiple words are likely user-facing
    words = s.split()
    if len(words) > 1:
        return True
    
    # Single words that are capitalized/mixed case but not pure uppercase variables
    if s[0].isupper() and not s.isupper():
        return True
        
    return False


class PythonStringVisitor(ast.NodeVisitor):
    """AST visitor to find strings in Python files that are not wrapped in translation."""
    
    def __init__(self, content: str):
        self.content_lines = content.splitlines()
        self.findings: List[Tuple[int, str, str]] = []
        self.current_call_funcs: List[str] = []
        
    def visit_Call(self, node: ast.Call):
        # Track function calls to see if they are translation wrappers like _ or gettext
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            
        self.current_call_funcs.append(func_name)
        self.generic_visit(node)
        self.current_call_funcs.pop()
        
    def visit_Constant(self, node: ast.Constant):
        # For Python 3.8+
        if isinstance(node.value, str):
            self._check_string(node.value, node.lineno)
            
    # For Python < 3.8
    if sys.version_info < (3, 8):
        def visit_Str(self, node: ast.Str):
            self._check_string(node.s, node.lineno)

    def _check_string(self, s: str, lineno: int):
        if not is_user_facing_string(s):
            return
            
        # If the string is inside a translation call (like _("hello") or t("hello")), ignore it
        if any(f in {'_', 'gettext', 'ngettext', 't', 'translate', 'ugettext'} for f in self.current_call_funcs):
            return
            
        # Get line content for context
        line_content = self.content_lines[lineno - 1].strip() if 0 < lineno <= len(self.content_lines) else ""
        self.findings.append((lineno, s, line_content))


def audit_python_file(filepath: str) -> List[Dict]:
    """Parse and audit a Python file using AST."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filepath)
        visitor = PythonStringVisitor(content)
        visitor.visit(tree)
        
        results = []
        for lineno, val, context in visitor.findings:
            results.append({
                'line': lineno,
                'string': val,
                'context': context,
                'type': 'Python literal'
            })
        return results
    except Exception as e:
        return [{'line': 0, 'string': f'Error parsing file: {str(e)}', 'context': '', 'type': 'Error'}]


def audit_html_file(filepath: str) -> List[Dict]:
    """Scan HTML file for text content outside tags and translation structures."""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Look for text between tags: >Text<
        # We can extract text nodes and check if they contain hardcoded strings
        tag_text_re = re.compile(r'>\s*([^<>\n\t{}]*?)\s*<')
        
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            # Skip comments or script/style blocks
            if line_str.startswith('<!--') or line_str.startswith('<script') or line_str.startswith('<style'):
                continue
                
            matches = tag_text_re.findall(line)
            for match in matches:
                match_clean = match.strip()
                # Ensure it's not empty, doesn't look like template expressions (e.g. {{ var }})
                if match_clean and not (match_clean.startswith('{{') or match_clean.startswith('{%')) and is_user_facing_string(match_clean):
                    results.append({
                        'line': idx,
                        'string': match_clean,
                        'context': line_str,
                        'type': 'HTML text node'
                    })
    except Exception as e:
        results.append({'line': 0, 'string': f'Error reading HTML: {str(e)}', 'context': '', 'type': 'Error'})
    return results


def audit_js_file(filepath: str) -> List[Dict]:
    """Scan JS/TS/JSX/TSX file for hardcoded strings using regular expressions."""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Match single-quoted, double-quoted, and backtick string literals
        # Avoid matching comments or imports
        string_literal_re = re.compile(r'(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|`([^`\\]*(?:\\.[^`\\]*)*)`)')
        
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            # Skip comments or imports
            if line_str.startswith('//') or line_str.startswith('/*') or line_str.startswith('*') or line_str.startswith('import ') or line_str.startswith('require('):
                continue
                
            for match in string_literal_re.finditer(line):
                # The regex has three capture groups, one for each quote type
                val = match.group(1) or match.group(2) or match.group(3)
                if val and is_user_facing_string(val):
                    # Check if wrapped in i18n functions like t('string') or i18n.t('string')
                    # Look back from the match start
                    start_idx = match.start()
                    before_str = line[:start_idx].strip()
                    # Check if the string is immediately preceded by t(, _(, translate(, etc.
                    is_wrapped = False
                    for wrapper in [r'\b_t\s*\(', r'\bt\s*\(', r'\b_\s*\(', r'\bi18n\.t\s*\(', r'\btranslate\s*\(']:
                        if re.search(wrapper + r'$', before_str):
                            is_wrapped = True
                            break
                            
                    if not is_wrapped:
                        results.append({
                            'line': idx,
                            'string': val,
                            'context': line_str,
                            'type': 'JS string literal'
                        })
                        
    except Exception as e:
        results.append({'line': 0, 'string': f'Error reading JS/TS: {str(e)}', 'context': '', 'type': 'Error'})
    return results


def main():
    parser = argparse.ArgumentParser(description='Audit codebase for hardcoded user-facing strings requiring translation.')
    parser.add_argument('path', nargs='?', default='.', help='Directory or file path to scan')
    parser.add_argument('--exclude', nargs='*', default=[], help='Directories or files to exclude')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--output', help='Save output to file')
    
    args = parser.parse_args()
    
    scan_path = os.path.abspath(args.path)
    excludes = DEFAULT_EXCLUDES.union(set(args.exclude))
    
    all_findings = {}
    total_files_scanned = 0
    total_strings_found = 0
    
    if os.path.isfile(scan_path):
        files_to_scan = [scan_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(scan_path):
            # Prune directories in-place
            dirs[:] = [d for d in dirs if d not in excludes and not d.startswith('.')]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm'}:
                    files_to_scan.append(os.path.join(root, file))

    for filepath in files_to_scan:
        rel_path = os.path.relpath(filepath, scan_path)
        ext = os.path.splitext(filepath)[1].lower()
        
        findings = []
        if ext == '.py':
            findings = audit_python_file(filepath)
        elif ext in {'.html', '.htm'}:
            findings = audit_html_file(filepath)
        elif ext in {'.js', '.ts', '.jsx', '.tsx'}:
            findings = audit_js_file(filepath)
            
        if findings:
            all_findings[rel_path] = findings
            total_strings_found += len(findings)
            
        total_files_scanned += 1

    summary = {
        'total_files_scanned': total_files_scanned,
        'total_strings_found': total_strings_found,
        'findings': all_findings
    }
    
    # Output formatting
    output_str = ""
    if args.format == 'json':
        output_str = json.dumps(summary, indent=2)
    else:
        output_str += "========================================\n"
        output_str += "       CODE LOCALIZATION AUDIT          \n"
        output_str += "========================================\n"
        output_str += f"Scanned: {total_files_scanned} files\n"
        output_str += f"Found: {total_strings_found} hardcoded strings requiring translation\n"
        output_str += "----------------------------------------\n\n"
        
        for file, findings in all_findings.items():
            output_str += f"File: {file}\n"
            output_str += "=" * (len(file) + 6) + "\n"
            for f in findings:
                output_str += f"  Line {f['line']} [{f['type']}]:\n"
                output_str += f"    String:  \"{f['string']}\"\n"
                output_str += f"    Context: {f['context']}\n"
                output_str += "\n"
            output_str += "-" * 40 + "\n\n"
            
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as out_f:
            out_f.write(output_str)
        print(f"Results saved to {args.output}")
    else:
        print(output_str)


if __name__ == '__main__':
    main()
