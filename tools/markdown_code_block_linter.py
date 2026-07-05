#!/usr/bin/env python3
"""
Markdown Embedded Code Block Syntax Linter

Scans Markdown (.md) files for code blocks (fenced with ``` or ~~~), extracts
snippets (Python, JSON, HTML, XML), validates their syntax, and reports line numbers
for any syntax errors.

Usage:
    python tools/markdown_code_block_linter.py README.md
    python tools/markdown_code_block_linter.py docs/ --json
    python tools/markdown_code_block_linter.py . --lang python --lang json
"""

import ast
import sys
import os
import re
import json
import argparse
from pathlib import Path
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def is_color_enabled() -> bool:
    return sys.stdout.isatty() and os.name != 'nt' or os.getenv('COLORTERM') is not None or os.name == 'nt'


def colorize(text: str, color_code: str) -> str:
    if is_color_enabled():
        return f"{color_code}{text}{COLOR_RESET}"
    return text


class HTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

    def error(self, message):
        self.errors.append(message)


def validate_snippet(code: str, lang: str) -> Tuple[bool, str]:
    lang = lang.lower().strip()

    if lang in ("python", "py"):
        try:
            ast.parse(code)
            return True, "Valid Python syntax"
        except SyntaxError as se:
            return False, f"Python SyntaxError at line {se.lineno}: {se.msg}"
        except Exception as ex:
            return False, f"Python error: {str(ex)}"

    elif lang in ("json", "json5", "geojson"):
        try:
            json.loads(code)
            return True, "Valid JSON syntax"
        except json.JSONDecodeError as jde:
            return False, f"JSON Error at line {jde.lineno}, col {jde.colno}: {jde.msg}"
        except Exception as ex:
            return False, f"JSON error: {str(ex)}"

    elif lang in ("html", "htm"):
        parser = HTMLValidator()
        try:
            parser.feed(code)
            if parser.errors:
                return False, f"HTML Error: {parser.errors[0]}"
            return True, "Valid HTML structure"
        except Exception as ex:
            return False, f"HTML parse error: {str(ex)}"

    elif lang in ("xml", "svg"):
        try:
            ET.fromstring(f"<root>{code}</root>")
            return True, "Valid XML"
        except ET.ParseError as pe:
            return False, f"XML ParseError: {str(pe)}"
        except Exception as ex:
            return False, f"XML error: {str(ex)}"

    elif lang in ("yaml", "yml"):
        # Basic YAML syntax heuristic (indentation check)
        lines = code.splitlines()
        for idx, line in enumerate(lines, start=1):
            if "\t" in line:
                return False, f"YAML Error at line {idx}: YAML forbids tab characters for indentation"
        return True, "YAML indentation check passed"

    # Unsupported or plain text language - skip linting
    return True, "Skipped (no validator registered for language)"


def extract_code_blocks(content: str) -> List[Dict[str, Any]]:
    """Extract code blocks with line numbers from Markdown content."""
    blocks = []
    lines = content.splitlines()
    in_block = False
    fence_char = ""
    current_lang = ""
    start_line = 0
    block_lines = []

    fence_pattern = re.compile(r"^(`{3,}|~{3,})\s*([a-zA-Z0-9_-]*)")

    for i, line in enumerate(lines, start=1):
        match = fence_pattern.match(line)
        if match:
            fence = match.group(1)
            lang = match.group(2)
            if not in_block:
                in_block = True
                fence_char = fence[0]
                current_lang = lang
                start_line = i
                block_lines = []
            elif line.strip().startswith(fence_char * 3):
                in_block = False
                blocks.append({
                    "start_line": start_line,
                    "end_line": i,
                    "language": current_lang or "text",
                    "code": "\n".join(block_lines)
                })
                block_lines = []
        elif in_block:
            block_lines.append(line)

    return blocks


def lint_markdown_file(filepath: str, allowed_langs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as ex:
        return [{
            "filepath": filepath,
            "start_line": 0,
            "language": "file",
            "valid": False,
            "message": f"Could not read file: {str(ex)}"
        }]

    blocks = extract_code_blocks(content)
    results = []

    for blk in blocks:
        lang = blk["language"].lower()
        if allowed_langs and lang not in allowed_langs:
            continue

        valid, msg = validate_snippet(blk["code"], lang)
        if not valid:
            results.append({
                "filepath": filepath,
                "start_line": blk["start_line"],
                "end_line": blk["end_line"],
                "language": blk["language"],
                "snippet_preview": blk["code"].splitlines()[0] if blk["code"] else "",
                "valid": False,
                "message": msg
            })

    return results


def lint_directory(
    target_path: str,
    allowed_langs: Optional[List[str]] = None
) -> Dict[str, Any]:
    path = Path(target_path)
    all_issues = []
    files_scanned = 0
    total_blocks_checked = 0

    if path.is_file():
        if path.suffix == ".md":
            files_scanned += 1
            all_issues.extend(lint_markdown_file(str(path), allowed_langs))
    else:
        for md_file in path.glob("**/*.md"):
            files_scanned += 1
            all_issues.extend(lint_markdown_file(str(md_file), allowed_langs))

    return {
        "target_path": str(path.resolve()),
        "files_scanned": files_scanned,
        "total_issues": len(all_issues),
        "issues": all_issues
    }


def print_report(results: Dict[str, Any]):
    print("=" * 72)
    print(colorize("  Markdown Code Block Syntax Linter Report", COLOR_BOLD + COLOR_HEADER))
    print("=" * 72)
    print(f"  Target Path:   {results['target_path']}")
    print(f"  Files Scanned: {results['files_scanned']}")
    print(f"  Syntax Errors: {results['total_issues']}")
    print("-" * 72)

    if not results["issues"]:
        print(colorize("\n  ✓ All code blocks in Markdown files passed syntax linting!\n", COLOR_GREEN + COLOR_BOLD))
        print("=" * 72)
        return

    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in results["issues"]:
        by_file.setdefault(issue["filepath"], []).append(issue)

    for fname, issues in by_file.items():
        rel_fname = os.path.relpath(fname)
        print(f"\n[{colorize('FILE', COLOR_CYAN)}] {colorize(rel_fname, COLOR_BOLD)} ({len(issues)} issue{'s' if len(issues)>1 else ''}):")
        for iss in issues:
            line_str = f"Line {iss['start_line']}-{iss['end_line']}"
            lang_str = colorize(iss['language'], COLOR_YELLOW)
            print(f"  └─ {colorize(line_str, COLOR_YELLOW)} [{lang_str}]:")
            print(f"     Error:   {colorize(iss['message'], COLOR_RED)}")
            if iss.get("snippet_preview"):
                print(f"     Preview: {colorize(iss['snippet_preview'], COLOR_RESET)}")

    print("\n" + "=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Extract and lint embedded code blocks (Python, JSON, HTML, XML, YAML) in Markdown files."
    )
    parser.add_argument("target", nargs="?", default=".", help="Markdown file or directory to scan (default: current directory)")
    parser.add_argument("--lang", action="append", help="Specific language to lint (e.g. python, json). Can be specified multiple times.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    allowed_langs = [l.lower() for l in args.lang] if args.lang else None
    results = lint_directory(args.target, allowed_langs)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["total_issues"] == 0 else 1)


if __name__ == "__main__":
    main()
