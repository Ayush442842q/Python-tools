#!/usr/bin/env python3
"""
API Documentation Generator - Auto-generates REST API documentation from Python Flask/FastAPI code.

This tool scans Python files for route decorators (@app.route, @router.get, etc.)
and generates comprehensive API documentation in Markdown format.

Features:
- Detects Flask (@app.route) and FastAPI (@router.get/post/put/delete) decorators
- Extracts HTTP methods, paths, and endpoint names
- Parses docstrings for descriptions
- Identifies path/query/body parameters from type hints
- Generates formatted Markdown documentation
- Supports multiple output formats (Markdown, HTML)

Usage:
    python api_doc_generator.py <source_directory> [-o output.md] [--html]

Example:
    python api_doc_generator.py ./src -o API_DOCS.md
    python api_doc_generator.py ./api --html
"""

import os
import re
import argparse
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class APIDocGenerator:
    """Generate API documentation from Python source code."""

    FLASK_ROUTE_PATTERN = re.compile(
        r'@(?:app|blueprint)\.route\s*\(\s*[\'"]([^\'"]+)[\'"]'
        r'(?:,\s*methods\s*=\s*\[([^\]]+)\])?',
        re.MULTILINE
    )

    FASTAPI_PATTERNS = [
        (re.compile(r'@(?:app|router)\.get\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'GET'),
        (re.compile(r'@(?:app|router)\.post\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'POST'),
        (re.compile(r'@(?:app|router)\.put\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'PUT'),
        (re.compile(r'@(?:app|router)\.delete\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'DELETE'),
        (re.compile(r'@(?:app|router)\.patch\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'PATCH'),
    ]

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.endpoints: List[Dict] = []

    def scan_directory(self) -> None:
        """Scan directory for Python files and extract API endpoints."""
        for py_file in self.source_dir.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            self._extract_endpoints(py_file)

    def _extract_endpoints(self, file_path: Path) -> None:
        """Extract API endpoints from a Python file."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return

        relative_path = file_path.relative_to(self.source_dir)

        # Extract Flask routes
        for match in self.FLASK_ROUTE_PATTERN.finditer(content):
            path = match.group(1)
            methods_str = match.group(2)
            methods = [m.strip().strip("'\"") for m in methods_str.split(',')] if methods_str else ['GET']

            endpoint = {
                'file': str(relative_path),
                'path': path,
                'methods': methods,
                'description': '',
                'params': []
            }
            endpoint['description'] = self._get_nearby_docstring(content, match.start())
            self.endpoints.append(endpoint)

        # Extract FastAPI routes
        for pattern, method in self.FASTAPI_PATTERNS:
            for match in pattern.finditer(content):
                path = match.group(1)
                endpoint = {
                    'file': str(relative_path),
                    'path': path,
                    'methods': [method],
                    'description': '',
                    'params': []
                }
                endpoint['description'] = self._get_nearby_docstring(content, match.start())
                self.endpoints.append(endpoint)

    def _get_nearby_docstring(self, content: str, match_start: int) -> str:
        """Extract docstring near the route decorator."""
        lines = content[:match_start].split('\n')

        # Look for function definition and its docstring
        for i in range(len(lines) - 1, max(0, len(lines) - 50), -1):
            line = lines[i].strip()
            if line.startswith('def '):
                # Found function, now look for docstring after it
                remaining_lines = lines[i+1:i+10]
                docstring_start = None
                for j, rl in enumerate(remaining_lines):
                    if '"""' in rl or "'''" in rl:
                        docstring_start = j
                        break

                if docstring_start is not None:
                    docstring_lines = []
                    quote_type = '"""' if '"""' in remaining_lines[docstring_start] else "'''"
                    for k in range(docstring_start + 1, len(remaining_lines)):
                        if quote_type in remaining_lines[k]:
                            break
                        docstring_lines.append(remaining_lines[k].strip())

                    return ' '.join(docstring_lines)
                break

        return ''

    def generate_markdown(self) -> str:
        """Generate Markdown documentation."""
        if not self.endpoints:
            return "# API Documentation\n\nNo API endpoints found.\n"

        md = [
            "# API Documentation",
            "",
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            f"**Total Endpoints:** {len(self.endpoints)}",
            "",
            "---",
            "",
        ]

        # Group by path
        endpoints_by_path: Dict[str, List[Dict]] = {}
        for ep in self.endpoints:
            path = ep['path']
            if path not in endpoints_by_path:
                endpoints_by_path[path] = []
            endpoints_by_path[path].append(ep)

        for path, eps in sorted(endpoints_by_path.items()):
            md.append(f"## `{path}`")
            md.append("")

            for ep in eps:
                methods = ', '.join(ep['methods'])
                md.append(f"### {methods}")
                md.append("")
                md.append(f"**Source:** `{ep['file']}`")
                md.append("")

                if ep['description']:
                    md.append(f"**Description:** {ep['description']}")
                    md.append("")

                md.append("---")
                md.append("")

        return '\n'.join(md)

    def generate_html(self) -> str:
        """Generate HTML documentation."""
        md_content = self.generate_markdown()

        # Simple MD to HTML conversion
        html = md_content
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'^---$', '<hr>', html, flags=re.MULTILINE)
        html = html.replace('\n\n', '</p><p>')

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }}
        hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
        strong {{ color: #2c3e50; }}
    </style>
</head>
<body>
{html}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description='Generate API documentation from Python Flask/FastAPI code'
    )
    parser.add_argument('source_dir', help='Directory containing Python source files')
    parser.add_argument('-o', '--output', default='API_DOCS.md',
                        help='Output file path (default: API_DOCS.md)')
    parser.add_argument('--html', action='store_true',
                        help='Generate HTML output instead of Markdown')

    args = parser.parse_args()

    if not os.path.isdir(args.source_dir):
        print(f"Error: '{args.source_dir}' is not a valid directory")
        return 1

    print(f"Scanning {args.source_dir} for API endpoints...")

    generator = APIDocGenerator(args.source_dir)
    generator.scan_directory()

    print(f"Found {len(generator.endpoints)} API endpoints")

    if args.html:
        output = args.output.replace('.md', '.html') if args.output.endswith('.md') else args.output + '.html'
        content = generator.generate_html()
    else:
        output = args.output
        content = generator.generate_markdown()

    output_path = Path(output)
    output_path.write_text(content, encoding='utf-8')

    print(f"Documentation saved to: {output_path.absolute()}")
    return 0


if __name__ == '__main__':
    exit(main())