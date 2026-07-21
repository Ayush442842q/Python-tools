#!/usr/bin/env python3
"""
Markdown to HTML Converter - Compiles Markdown files into highly stylized, standalone HTML files.
Built-in CSS themes for quick, aesthetic document sharing.
"""

import argparse
import os
import re
import sys

# HTML templates with embedded CSS stylesheets
THEMES = {
    'github': """
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            padding: 45px;
            max-width: 850px;
            margin: 0 auto;
        }
        h1, h2, h3, h4, h5, h6 {
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }
        h1 { font-size: 2em; }
        h2 { font-size: 1.5em; }
        h3 { font-size: 1.25em; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        code {
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
        }
        pre {
            padding: 16px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            background-color: #f6f8fa;
            border-radius: 6px;
            margin-bottom: 16px;
        }
        pre code {
            background-color: transparent;
            padding: 0;
            font-size: 100%;
        }
        blockquote {
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
            margin: 0 0 16px 0;
        }
        table {
            border-spacing: 0;
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }
        table th, table td {
            padding: 6px 13px;
            border: 1px solid #dfe2e5;
        }
        table tr:nth-child(even) { background-color: #f6f8fa; }
        hr {
            height: 0.25em;
            padding: 0;
            margin: 24px 0;
            background-color: #e1e4e6;
            border: 0;
        }
    """,
    'dark': """
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px;
            line-height: 1.7;
            color: #e2e8f0;
            background-color: #0f172a;
            padding: 40px 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #f8fafc;
            margin-top: 1.8em;
            margin-bottom: 0.8em;
            font-weight: 700;
            letter-spacing: -0.025em;
        }
        h1 { font-size: 2.25em; border-bottom: 1px solid #334155; padding-bottom: 0.4em; }
        h2 { font-size: 1.75em; border-bottom: 1px solid #1e293b; padding-bottom: 0.3em; }
        h3 { font-size: 1.4em; }
        a { color: #38bdf8; text-decoration: none; transition: color 0.2s; }
        a:hover { color: #7dd3fc; }
        code {
            padding: 0.2em 0.4em;
            font-size: 90%;
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            color: #f472b6;
        }
        pre {
            padding: 20px;
            overflow: auto;
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        pre code {
            background-color: transparent;
            border: none;
            padding: 0;
            color: #e2e8f0;
            font-size: 90%;
        }
        blockquote {
            padding-left: 20px;
            color: #94a3b8;
            border-left: 4px solid #38bdf8;
            margin: 0 0 20px 0;
            font-style: italic;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 24px;
        }
        table th, table td {
            padding: 10px 14px;
            border: 1px solid #334155;
            text-align: left;
        }
        table th { background-color: #1e293b; color: #f8fafc; }
        table tr:nth-child(even) { background-color: #0f172a; }
        table tr:nth-child(odd) { background-color: #1e293b; }
        hr {
            height: 1px;
            background-color: #334155;
            border: 0;
            margin: 32px 0;
        }
    """,
    'slate': """
        body {
            font-family: 'Georgia', serif;
            font-size: 18px;
            line-height: 1.8;
            color: #333333;
            background-color: #f4f4f4;
            padding: 50px 30px;
            max-width: 750px;
            margin: 0 auto;
        }
        h1, h2, h3, h4 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            color: #111111;
            margin-top: 1.5em;
        }
        h1 { font-size: 2.2em; border-bottom: 2px solid #333; padding-bottom: 10px; }
        h2 { font-size: 1.6em; }
        a { color: #800000; text-decoration: underline; }
        a:hover { color: #b22222; }
        code {
            font-family: monospace;
            background-color: #e0e0e0;
            padding: 2px 4px;
            border-radius: 2px;
            font-size: 85%;
        }
        pre {
            background-color: #2d3748;
            color: #f7fafc;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            color: inherit;
        }
        blockquote {
            border-left: 3px double #800000;
            padding-left: 15px;
            margin: 0 0 15px 15px;
            color: #555;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        table th, table td {
            border-bottom: 1px solid #ccc;
            padding: 8px;
            text-align: left;
        }
        table th { border-bottom: 2px solid #333; }
    """
}

def parse_markdown(md_text):
    """Converts a Markdown string to basic HTML using regular expressions."""
    # Escape HTML tags first to prevent security issues / tag injection
    html = md_text
    html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Preformatted code blocks
    code_blocks = []
    def save_code_block(match):
        code = match.group(2)
        code_blocks.append(code)
        return f"<!--CODEBLOCK_{len(code_blocks)-1}-->"

    # Match triple backtick code blocks
    html = re.sub(r'```(\w*)\n(.*?)\n```', save_code_block, html, flags=re.DOTALL)
    
    # Inline code snippets
    inline_codes = []
    def save_inline_code(match):
        code = match.group(1)
        inline_codes.append(code)
        return f"<!--INLINECODE_{len(inline_codes)-1}-->"
    
    html = re.sub(r'`([^`\n]+)`', save_inline_code, html)

    # Headers
    html = re.sub(r'^###### (.*?)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
    html = re.sub(r'^##### (.*?)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Horizontal Rules
    html = re.sub(r'^---+$', r'<hr/>', html, flags=re.MULTILINE)

    # Blockquotes
    html = re.sub(r'^&gt;\s?(.*?)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # Links and Images
    html = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1" />', html)
    html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html)

    # Bold and Italic
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__(.*?)__', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    html = re.sub(r'_(.*?)_', r'<em>\1</em>', html)

    # Lists
    # Simple strategy: handle list items line by line, wrapping them later
    in_ul = False
    in_ol = False
    lines = html.split('\n')
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Unordered list item
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_ul:
                if in_ol:
                    new_lines.append('</ol>')
                    in_ol = False
                new_lines.append('<ul>')
                in_ul = True
            new_lines.append(f'<li>{stripped[2:]}</li>')
        # Ordered list item
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped)
            if not in_ol:
                if in_ul:
                    new_lines.append('</ul>')
                    in_ul = False
                new_lines.append('<ol>')
                in_ol = True
            new_lines.append(f'<li>{content}</li>')
        else:
            if in_ul:
                new_lines.append('</ul>')
                in_ul = False
            if in_ol:
                new_lines.append('</ol>')
                in_ol = False
            new_lines.append(line)
            
    if in_ul: new_lines.append('</ul>')
    if in_ol: new_lines.append('</ol>')
    html = '\n'.join(new_lines)

    # Tables parser
    # Match blocks of table syntax: lines containing '|'
    table_lines = []
    lines = html.split('\n')
    new_lines = []
    in_table = False
    
    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if not in_table:
                in_table = True
                table_lines = [line]
            else:
                table_lines.append(line)
        else:
            if in_table:
                # Compile table block
                new_lines.append(compile_table(table_lines))
                in_table = False
                table_lines = []
            new_lines.append(line)
    if in_table:
        new_lines.append(compile_table(table_lines))
    html = '\n'.join(new_lines)

    # Paragraph wrapper: Wrap blocks that aren't tags already in <p>
    blocks = html.split('\n\n')
    new_blocks = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        # If it doesn't start with block level HTML tags, wrap it in <p>
        block_tags = ('<h', '<ul', '<ol', '<li', '<blockquote', '<table', '<pre', '<hr', '<!--', '<img')
        if not any(stripped.startswith(tag) for tag in block_tags):
            # Also handle single-line break replacement
            para_content = stripped.replace('\n', '<br/>')
            new_blocks.append(f'<p>{para_content}</p>')
        else:
            new_blocks.append(block)
    html = '\n\n'.join(new_blocks)

    # Restore inline code and code blocks (in reverse order to avoid index confusion)
    for idx, code in enumerate(inline_codes):
        html = html.replace(f"<!--INLINECODE_{idx}-->", f"<code>{code}</code>")
        
    for idx, code in enumerate(code_blocks):
        html = html.replace(f"<!--CODEBLOCK_{idx}-->", f"<pre><code>{code}</code></pre>")

    return html

def compile_table(table_lines):
    """Compiles a block of lines containing piping into a HTML table."""
    if len(table_lines) < 2:
        return "\n".join(table_lines)
    
    rows = []
    for line in table_lines:
        # Strip outer pipes and split by pipes
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
        
    # Check if second row is divider (e.g. --- | ---)
    is_divider = all(re.match(r'^:?-+:?$', c) for c in rows[1]) if len(rows) > 1 else False
    
    html = ["<table>"]
    
    # Headers
    headers = rows[0]
    html.append("  <thead>")
    html.append("    <tr>")
    for cell in headers:
        html.append(f"      <th>{cell}</th>")
    html.append("    </tr>")
    html.append("  </thead>")
    
    # Body rows
    start_idx = 2 if is_divider else 1
    if start_idx < len(rows):
        html.append("  <tbody>")
        for r in rows[start_idx:]:
            html.append("    <tr>")
            for cell in r:
                html.append(f"      <td>{cell}</td>")
            html.append("    </tr>")
        html.append("  </tbody>")
        
    html.append("</table>")
    return "\n".join(html)

def main():
    parser = argparse.ArgumentParser(
        description="Markdown to HTML: Compile Markdown documents into beautiful standalone HTML pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", help="Path to input Markdown file")
    parser.add_argument("-o", "--output", help="Path to output HTML file (defaults to input_name.html)")
    parser.add_argument("-t", "--theme", choices=list(THEMES.keys()), default="github", help="CSS layout theme (default: github)")
    parser.add_argument("--title", help="Custom HTML page title (defaults to Markdown filename)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"[!] Error: File not found '{args.input}'", file=sys.stderr)
        sys.exit(1)
        
    with open(args.input, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Base details
    title = args.title or os.path.splitext(os.path.basename(args.input))[0].replace('_', ' ').replace('-', ' ').title()
    output_path = args.output or os.path.splitext(args.input)[0] + ".html"
    
    # Parse to HTML
    body_content = parse_markdown(md_content)
    theme_css = THEMES[args.theme]
    
    # Standalone HTML structure
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        /* Base styles */
        * {{ box-sizing: border-box; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 1.5em auto; border-radius: 4px; }}
        {theme_css}
    </style>
</head>
<body>
    {body_content}
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_template)
        
    print(f"[+] Output compiled successfully: {output_path}")

if __name__ == "__main__":
    main()
