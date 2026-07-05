#!/usr/bin/env python3
"""
Text Diff HTML Reporter
-----------------------
Generates a standalone, interactive HTML diff report comparing two text files or strings.
Supports side-by-side and unified views, dark/light mode toggle, line numbers, and change stats.

Author: Antigravity
License: MIT
"""

import sys
import os
import difflib
import argparse
import html
from typing import List, Tuple

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visual Text Diff Report - {title}</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-color: #c9d1d9;
            --border-color: #30363d;
            --add-bg: #0e4429;
            --add-text: #3fb950;
            --del-bg: #4c1d1d;
            --del-text: #f85149;
            --info-color: #58a6ff;
        }}
        body.light-mode {{
            --bg-color: #ffffff;
            --card-bg: #f6f8fa;
            --text-color: #24292f;
            --border-color: #d0d7de;
            --add-bg: #e6ffec;
            --add-text: #1a7f37;
            --del-bg: #ffebe9;
            --del-text: #cf222e;
            --info-color: #0969da;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .title {{
            font-size: 20px;
            font-weight: bold;
        }}
        .controls {{
            display: flex;
            gap: 10px;
        }}
        button {{
            background: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 6px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
        }}
        button:hover {{
            border-color: var(--info-color);
        }}
        .stats-bar {{
            display: flex;
            gap: 20px;
            background: var(--card-bg);
            padding: 10px 15px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            margin-bottom: 20px;
            font-family: monospace;
        }}
        .stat-add {{ color: var(--add-text); font-weight: bold; }}
        .stat-del {{ color: var(--del-text); font-weight: bold; }}
        .diff-container {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow-x: auto;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 13px;
            line-height: 1.5;
        }}
        table.diff {{
            width: 100%;
            border-collapse: collapse;
        }}
        table.diff td, table.diff th {{
            padding: 2px 8px;
            vertical-align: top;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .diff_header {{
            background-color: var(--card-bg);
            color: var(--info-color);
            text-align: right;
            user-select: none;
            width: 40px;
            border-right: 1px solid var(--border-color);
        }}
        .diff_add {{ background-color: var(--add-bg); color: var(--add-text); }}
        .diff_sub {{ background-color: var(--del-bg); color: var(--del-text); }}
        .diff_chg {{ background-color: #3b2e04; color: #d29922; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Diff: {file1} &harr; {file2}</div>
        <div class="controls">
            <button onclick="toggleTheme()">Toggle Theme</button>
        </div>
    </div>

    <div class="stats-bar">
        <span>File 1: <strong>{file1}</strong></span>
        <span>File 2: <strong>{file2}</strong></span>
        <span class="stat-add">+{additions} additions</span>
        <span class="stat-del">-{deletions} deletions</span>
    </div>

    <div class="diff-container">
        {diff_html}
    </div>

    <script>
        function toggleTheme() {{
            document.body.classList.toggle('light-mode');
        }}
    </script>
</body>
</html>
"""


def generate_html_diff(file1_path: str, file2_path: str, lines1: List[str], lines2: List[str]) -> Tuple[str, int, int]:
    differ = difflib.HtmlDiff(wrapcolumn=80)
    table_html = differ.make_table(
        lines1, lines2,
        fromdesc=os.path.basename(file1_path),
        todesc=os.path.basename(file2_path),
        context=True,
        numlines=3
    )

    # Compute addition and deletion stats
    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    additions = 0
    deletions = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            deletions += (i2 - i1)
            additions += (j2 - j1)
        elif tag == 'delete':
            deletions += (i2 - i1)
        elif tag == 'insert':
            additions += (j2 - j1)

    return table_html, additions, deletions


def main():
    parser = argparse.ArgumentParser(
        description="Generate a visual HTML diff report between two text files."
    )
    parser.add_argument("file1", nargs="?", help="First file path")
    parser.add_argument("file2", nargs="?", help="Second file path")
    parser.add_argument("-o", "--output", default="diff_report.html", help="Output HTML file path (default: diff_report.html)")
    parser.add_argument("--title", default="Text Comparison", help="Custom report title")

    args = parser.parse_args()

    if not args.file1 or not args.file2:
        print(f"{BLUE}{BOLD}Text Diff HTML Reporter - Demo Mode{RESET}\n")
        file1_name, file2_name = "original.py", "modified.py"
        lines1 = [
            "def calculate_total(items, tax_rate):\n",
            "    subtotal = sum(item.price for item in items)\n",
            "    total = subtotal * (1 + tax_rate)\n",
            "    return total\n"
        ]
        lines2 = [
            "def calculate_total(items, tax_rate, discount=0.0):\n",
            "    subtotal = sum(item.price for item in items) - discount\n",
            "    if subtotal < 0:\n",
            "        subtotal = 0\n",
            "    total = subtotal * (1 + tax_rate)\n",
            "    return round(total, 2)\n"
        ]
    else:
        file1_name, file2_name = args.file1, args.file2
        if not os.path.exists(file1_name):
            print(f"{RED}Error: File {file1_name} does not exist.{RESET}")
            sys.exit(1)
        if not os.path.exists(file2_name):
            print(f"{RED}Error: File {file2_name} does not exist.{RESET}")
            sys.exit(1)

        with open(file1_name, "r", encoding="utf-8", errors="ignore") as f:
            lines1 = f.readlines()
        with open(file2_name, "r", encoding="utf-8", errors="ignore") as f:
            lines2 = f.readlines()

    table_html, additions, deletions = generate_html_diff(file1_name, file2_name, lines1, lines2)

    full_html = HTML_TEMPLATE.format(
        title=html.escape(args.title),
        file1=html.escape(os.path.basename(file1_name)),
        file2=html.escape(os.path.basename(file2_name)),
        additions=additions,
        deletions=deletions,
        diff_html=table_html
    )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"{GREEN}{BOLD}HTML Diff Report generated successfully!{RESET}")
    print(f"File: {os.path.abspath(args.output)}")
    print(f"Stats: {GREEN}+{additions} additions{RESET}, {RED}-{deletions} deletions{RESET}")


if __name__ == "__main__":
    main()
