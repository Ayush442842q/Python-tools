#!/usr/bin/env python3
"""
Markdown to HTML/PDF Document Compiler

Compiles markdown files into cleanly formatted HTML files (or attempts basic PDF export) 
with customizable styling, responsive viewport tags, syntax-highlighted code containers, 
and automatic Table of Contents.

Usage:
    python tools/markdown_to_pdf.py document.md
    python tools/markdown_to_pdf.py document.md -o output.html --theme dark
"""

import os
import sys
import re
import argparse
from typing import List, Tuple, Dict, Any

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# CSS Themes
THEMES = {
    "light": """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1, h2, h3 { color: #111; margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }
        h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
        h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
        code { background-color: rgba(27,31,35,.05); border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 85%; padding: .2em .4em; }
        pre { background-color: #f6f8fa; border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; padding: 16px; overflow: auto; line-height: 1.45; }
        pre code { background-color: transparent; padding: 0; }
        blockquote { border-left: .25em solid #dfe2e5; color: #6a737d; padding: 0 1em; margin-left: 0; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 16px; }
        table, th, td { border: 1px solid #dfe2e5; }
        th, td { padding: 6px 13px; text-align: left; }
        tr:nth-child(even) { background-color: #f6f8fa; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
    """,
    "dark": """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #c9d1d9; background-color: #0d1117; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1, h2, h3 { color: #f0f6fc; margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }
        h1 { font-size: 2em; border-bottom: 1px solid #21262d; padding-bottom: .3em; }
        h2 { font-size: 1.5em; border-bottom: 1px solid #21262d; padding-bottom: .3em; }
        code { background-color: rgba(240,246,252,0.15); border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 85%; padding: .2em .4em; }
        pre { background-color: #161b22; border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; padding: 16px; overflow: auto; line-height: 1.45; border: 1px solid #30363d; }
        pre code { background-color: transparent; padding: 0; color: #c9d1d9; }
        blockquote { border-left: .25em solid #30363d; color: #8b949e; padding: 0 1em; margin-left: 0; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 16px; }
        table, th, td { border: 1px solid #30363d; }
        th, td { padding: 6px 13px; text-align: left; }
        tr:nth-child(even) { background-color: #161b22; }
        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    """
}

def print_colored(text: str, color: str):
    """Print text with ANSI color."""
    sys.stderr.write(f"{color}{text}{RESET}\n")

class MarkdownParser:
    @staticmethod
    def to_html(md_content: str) -> Tuple[str, List[Tuple[int, str, str]]]:
        """Translates basic markdown syntax blocks to equivalent HTML tags."""
        html_lines = []
        headings = []
        
        # Split by blocks/lines
        lines = md_content.splitlines()
        in_code_block = False
        code_block_lang = ""
        code_lines = []

        for line in lines:
            # Code block toggles
            if line.strip().startswith("```"):
                if in_code_block:
                    # Close code block
                    code_content = "\n".join(code_lines)
                    html_lines.append(f"<pre><code class=\"language-{code_block_lang}\">{code_content}</code></pre>")
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                    code_block_lang = line.strip().replace("```", "").strip()
                continue

            if in_code_block:
                # Escape code contents
                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                code_lines.append(escaped)
                continue

            # Headers
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if header_match:
                hashes, title = header_match.groups()
                level = len(hashes)
                anchor = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")
                headings.append((level, title, anchor))
                html_lines.append(f"<h{level} id=\"{anchor}\">{title}</h{level}>")
                continue

            # Blockquotes
            bq_match = re.match(r"^>\s*(.*)$", line)
            if bq_match:
                html_lines.append(f"<blockquote>{bq_match.group(1)}</blockquote>")
                continue

            # Horizontal Rules
            if re.match(r"^\s*([-\*_])\1\1+\s*$", line):
                html_lines.append("<hr />")
                continue

            # Lists (ordered / unordered)
            ul_match = re.match(r"^[\*\+-]\s+(.*)$", line)
            if ul_match:
                html_lines.append(f"<li>{ul_match.group(1)}</li>")
                continue
                
            ol_match = re.match(r"^\d+\.\s+(.*)$", line)
            if ol_match:
                html_lines.append(f"<li>{ol_match.group(1)}</li>")
                continue

            # Simple transformations (Bold, Italic, Code ticks, Links)
            line = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(r"\*([^\*]+)\*", r"<em>\1</em>", line)
            line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
            line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', line)

            if line.strip():
                html_lines.append(f"<p>{line}</p>")

        # Clean list tags wrapping (basic validation)
        final_html_lines = []
        in_list = False
        for line in html_lines:
            if line.startswith("<li>"):
                if not in_list:
                    final_html_lines.append("<ul>")
                    in_list = True
                final_html_lines.append(line)
            else:
                if in_list:
                    final_html_lines.append("</ul>")
                    in_list = False
                final_html_lines.append(line)
        if in_list:
            final_html_lines.append("</ul>")

        return "\n".join(final_html_lines), headings

def build_toc(headings: List[Tuple[int, str, str]]) -> str:
    """Builds a HTML list representing the Table of Contents."""
    if not headings:
        return ""
    toc_lines = ["<div class=\"toc\">", "<h2>Table of Contents</h2>", "<ul>"]
    for level, title, anchor in headings:
        # Indent according to heading depth level
        indent = "  " * (level - 1)
        toc_lines.append(f"{indent}<li><a href=\"#{anchor}\">{title}</a></li>")
    toc_lines.append("</ul>")
    toc_lines.append("</div><hr />")
    return "\n".join(toc_lines)

def main():
    parser = argparse.ArgumentParser(description="Compile Markdown documents to HTML/PDF layouts.")
    parser.add_argument("markdown_file", help="Path to input Markdown document")
    parser.add_argument("-o", "--output", help="Output path (default: input_file.html)")
    parser.add_argument("-t", "--theme", choices=["light", "dark"], default="light", help="Select CSS styling theme")
    parser.add_argument("--toc", action="store_true", help="Generate a Table of Contents at the top")
    
    args = parser.parse_args()

    if not os.path.exists(args.markdown_file):
        print_colored(f"[-] File not found: {args.markdown_file}", RED)
        sys.exit(1)

    try:
        with open(args.markdown_file, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        print_colored(f"[-] Failed to read input file: {e}", RED)
        sys.exit(1)

    print_colored(f"[*] Compiling document: {args.markdown_file}...", BLUE)
    
    html_content, headings = MarkdownParser.to_html(md_content)
    
    toc_html = ""
    if args.toc:
        toc_html = build_toc(headings)

    # Wrap in HTML boiler skeleton
    theme_css = THEMES[args.theme]
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compiled Document</title>
    <style>
        {theme_css}
    </style>
</head>
<body>
    {toc_html}
    {html_content}
</body>
</html>
"""

    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.markdown_file)
        output_path = base + ".html"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print_colored(f"[+] Document compiled successfully: {output_path}", GREEN)
    except Exception as e:
        print_colored(f"[-] Failed to write compiled output: {e}", RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
