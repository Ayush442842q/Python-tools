#!/usr/bin/env python3
"""
Markdown Resume Compiler

A standalone CLI tool to compile standard Markdown resume/CV files into beautiful,
responsive, and print-ready HTML files. It includes multiple responsive CSS templates
(Modern, Serif, Minimalist) with built-in print media queries for clean PDF generation.

Usage:
    python markdown_resume_compiler.py my_resume.md --theme modern
"""

import sys
import os
import argparse
import re
from typing import Dict

# Embedded CSS Themes
THEMES: Dict[str, str] = {
    "modern": """
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --text: #1f2937;
            --text-muted: #4b5563;
            --bg: #f9fafb;
            --container-bg: #ffffff;
            --border: #e5e7eb;
        }
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            margin: 0;
            padding: 2rem 1rem;
        }
        .container {
            max-width: 850px;
            margin: 0 auto;
            background: var(--container-bg);
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid var(--border);
        }
        h1 {
            color: var(--primary);
            font-size: 2.5rem;
            margin-top: 0;
            margin-bottom: 0.5rem;
            font-weight: 800;
        }
        h2 {
            color: var(--primary-dark);
            font-size: 1.5rem;
            border-bottom: 2px solid var(--primary);
            padding-bottom: 0.3rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        h3 {
            font-size: 1.2rem;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            color: var(--text);
        }
        a {
            color: var(--primary);
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        ul {
            padding-left: 1.5rem;
        }
        li {
            margin-bottom: 0.4rem;
        }
        .contact-info {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.95rem;
            color: var(--text-muted);
            margin-bottom: 2rem;
        }
        .contact-info span:not(:last-child)::after {
            content: " |";
            margin-left: 1rem;
            color: var(--border);
        }
        @media print {
            body {
                background: none;
                color: #000;
                padding: 0;
            }
            .container {
                box-shadow: none;
                border: none;
                padding: 0;
                max-width: 100%;
            }
            h2 {
                border-bottom-color: #000;
            }
        }
    """,
    "serif": """
        :root {
            --text: #111111;
            --text-muted: #555555;
            --border: #cccccc;
        }
        body {
            font-family: 'Playfair Display', Georgia, Cambria, serif;
            color: var(--text);
            line-height: 1.5;
            margin: 0;
            padding: 3rem 1rem;
            background: #fff;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 0 1rem;
        }
        h1 {
            font-size: 3rem;
            text-align: center;
            margin-top: 0;
            margin-bottom: 0.5rem;
            font-weight: normal;
        }
        h2 {
            font-size: 1.3rem;
            text-align: center;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            padding: 0.4rem 0;
            margin-top: 2rem;
            margin-bottom: 1.2rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        h3 {
            font-size: 1.1rem;
            margin-top: 1.2rem;
            margin-bottom: 0.3rem;
            display: flex;
            justify-content: space-between;
        }
        .contact-info {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 2rem;
            font-style: italic;
        }
        ul {
            padding-left: 1.2rem;
        }
        li {
            margin-bottom: 0.3rem;
        }
        @media print {
            body {
                padding: 0;
            }
            .container {
                max-width: 100%;
            }
        }
    """,
    "minimalist": """
        :root {
            --text: #222222;
            --text-muted: #666666;
            --border: #e0e0e0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: var(--text);
            line-height: 1.5;
            padding: 2rem 1rem;
            background: #fff;
        }
        .container {
            max-width: 780px;
            margin: 0 auto;
        }
        h1 {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
            letter-spacing: -0.02em;
        }
        h2 {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-top: 1.8rem;
            margin-bottom: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.2rem;
        }
        h3 {
            font-size: 1rem;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 0.2rem;
        }
        .contact-info {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
        }
        .contact-info a {
            color: inherit;
        }
        ul {
            padding-left: 1.1rem;
            margin-top: 0.4rem;
        }
        li {
            margin-bottom: 0.25rem;
            font-size: 0.95rem;
        }
        @media print {
            body {
                padding: 0;
            }
            .container {
                max-width: 100%;
            }
        }
    """
}

def parse_markdown_to_html(md_content: str) -> str:
    """A lightweight Markdown parser converting basic elements to HTML tags."""
    html = []
    lines = md_content.split("\n")
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # Unordered lists
        if stripped.startswith(("- ", "* ", "+ ")):
            if not in_list:
                html.append("<ul>")
                in_list = True
            content = stripped[2:]
            # Parse inline formatting
            content = parse_inline_elements(content)
            html.append(f"<li>{content}</li>")
            continue
        elif in_list and stripped == "":
            # Keep list open if we just have blank line but list isn't terminated
            pass
        elif in_list and not stripped.startswith(("- ", "* ", "+ ")):
            html.append("</ul>")
            in_list = False
            
        if stripped == "":
            html.append("<br/>")
            continue
            
        # Headers
        if stripped.startswith("# "):
            html.append(f"<h1>{parse_inline_elements(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            html.append(f"<h2>{parse_inline_elements(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            html.append(f"<h3>{parse_inline_elements(stripped[4:])}</h3>")
        elif stripped.startswith("#### "):
            html.append(f"<h4>{parse_inline_elements(stripped[5:])}</h4>")
        # Blockquotes
        elif stripped.startswith("> "):
            html.append(f"<blockquote>{parse_inline_elements(stripped[2:])}</blockquote>")
        # Horizontal rules
        elif stripped in ("---", "***", "___"):
            html.append("<hr/>")
        else:
            # Paragraph
            html.append(f"<p>{parse_inline_elements(stripped)}</p>")
            
    if in_list:
        html.append("</ul>")
        
    return "\n".join(html)

def parse_inline_elements(text: str) -> str:
    """Helper to convert bold, italic, and links in lines."""
    # Bold
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.*?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.*?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    # Links: [text](url)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', text)
    return text

def compile_resume(md_path: str, theme_name: str, output_path: str):
    """Read markdown file, inject into HTML wrapper with CSS theme, and write out."""
    if not os.path.exists(md_path):
        print(f"Error: Markdown file not found at {md_path}")
        sys.exit(1)
        
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    # Extract Title (often the first # header)
    title_match = re.search(r"^#\s+(.*)", md_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Resume"
    
    # Parse Markdown blocks
    body_html = parse_markdown_to_html(md_content)
    
    # Wrap in contact-info container helper if there's a contact header/block
    # We look for a line of text containing links or pipe signs right below h1
    # Example: email@email.com | github.com/username
    # This is easily handled in CSS via .contact-info styling. We can wrap the first p tags
    # that follow the h1 title.
    body_html = re.sub(
        r"(<h1>.*?</h1>\s*)<p>(.*?\|.*?)</p>",
        r'\1<div class="contact-info"><span>\2</span></div>',
        body_html,
        flags=re.DOTALL
    )
    # Split contact line elements by pipeline and wrap in spans
    def format_contact_spans(match):
        h1 = match.group(1)
        contacts = match.group(2).split("|")
        span_str = "".join(f"<span>{c.strip()}</span>" for c in contacts)
        return f'{h1}<div class="contact-info">{span_str}</div>'
        
    body_html = re.sub(r"(<h1>.*?</h1>\s*)<p>(.*?\|.*?)</p>", format_contact_spans, body_html, flags=re.DOTALL)
    
    css_content = THEMES.get(theme_name.lower(), THEMES["modern"])
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        {css_content}
    </style>
</head>
<body>
    <div class="container">
        {body_html}
    </div>
</body>
</html>
"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    print(f"\033[92m[+] Successfully compiled resume to: {output_path} (Theme: {theme_name})\033[0m")
    print(f"[*] Open this file in your browser to view and print to PDF!")

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Resume Compiler: Compile plain Markdown resumes to beautiful print-ready HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input",
        help="Path to the input Markdown resume file."
    )
    parser.add_argument(
        "--theme", "-t",
        choices=["modern", "serif", "minimalist"],
        default="modern",
        help="CSS theme template to apply (default: modern)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output HTML path (default: input_filename.html)"
    )
    
    args = parser.parse_args()
    
    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.input)
        output_path = f"{base}.html"
        
    compile_resume(args.input, args.theme, output_path)

if __name__ == "__main__":
    main()
