#!/usr/bin/env python3
r"""
CSS Design System & Style Guide Generator - Parses CSS files to build a visual style guide.
Generates an interactive, beautiful HTML design system overview with live component previews and color copy triggers.

Usage:
    python tools/css_style_guide_generator.py [DIRECTORY_OR_FILE] [--output GUIDE_PATH]

Example:
    python tools/css_style_guide_generator.py h:\my_project\css\
    python tools/css_style_guide_generator.py tools/ -o my_style_guide.html
"""

import argparse
import os
import re
import sys

# Regex Patterns for CSS parsing
HEX_COLOR_PATTERN = re.compile(r'#(?:[0-9a-fA-F]{3,4}){1,2}\b')
RGB_COLOR_PATTERN = re.compile(r'rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[0-9.]+\s*)?\)')
HSL_COLOR_PATTERN = re.compile(r'hsla?\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*[0-9.]+\s*)?\)')
CSS_VAR_PATTERN = re.compile(r'(--[a-zA-Z0-9_-]+)\s*:\s*([^;}\n]+);?')
FONT_FAMILY_PATTERN = re.compile(r'font-family\s*:\s*([^;}\n]+);?')
MEDIA_QUERY_PATTERN = re.compile(r'@media\s+([^{]+)\{')

def parse_css_content(content):
    tokens = {
        'colors': set(),
        'variables': {},
        'fonts': set(),
        'media_queries': set()
    }
    
    # 1. Find standard colors
    for match in HEX_COLOR_PATTERN.findall(content):
        tokens['colors'].add(match)
    for match in RGB_COLOR_PATTERN.findall(content):
        tokens['colors'].add(match)
    for match in HSL_COLOR_PATTERN.findall(content):
        tokens['colors'].add(match)
        
    # 2. Find CSS custom variables
    for var_name, var_val in CSS_VAR_PATTERN.findall(content):
        val = var_val.strip()
        tokens['variables'][var_name] = val
        # Check if variable itself is a color
        if HEX_COLOR_PATTERN.match(val) or RGB_COLOR_PATTERN.match(val) or HSL_COLOR_PATTERN.match(val):
            tokens['colors'].add(val)
            
    # 3. Find font families
    for match in FONT_FAMILY_PATTERN.findall(content):
        fonts_list = [f.strip(' "\'') for f in match.split(',')]
        for f in fonts_list:
            if f:
                tokens['fonts'].add(f)
                
    # 4. Find media queries
    for match in MEDIA_QUERY_PATTERN.findall(content):
        tokens['media_queries'].add(match.strip())
        
    return tokens


def scan_and_parse(path):
    css_files = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith('.css'):
                    css_files.append(os.path.join(root, file))
    elif os.path.isfile(path) and path.lower().endswith('.css'):
        css_files.append(path)
        
    aggregated = {
        'colors': set(),
        'variables': {},
        'fonts': set(),
        'media_queries': set()
    }
    
    for css_file in css_files:
        try:
            with open(css_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tokens = parse_css_content(content)
            aggregated['colors'].update(tokens['colors'])
            aggregated['variables'].update(tokens['variables'])
            aggregated['fonts'].update(tokens['fonts'])
            aggregated['media_queries'].update(tokens['media_queries'])
        except Exception as e:
            print(f"[!] Error reading '{css_file}': {e}", file=sys.stderr)
            
    # Remove variables from simple colors list to keep it neat
    for val in list(aggregated['colors']):
        if val.startswith('var('):
            aggregated['colors'].remove(val)
            
    return aggregated, len(css_files)


def build_style_guide_html(tokens, source_path, output_path):
    # Prepare color cards
    colors_html = ""
    for color in sorted(list(tokens['colors'])):
        # Make a simple safety checks for values
        if len(color) < 20: # skip overly long computed colors
            colors_html += f"""
            <div class="color-card">
                <div class="color-preview" style="background-color: {color};"></div>
                <div class="color-info">
                    <span class="color-value">{color}</span>
                    <button class="copy-btn" onclick="copyToClipboard('{color}')">Copy</button>
                </div>
            </div>
            """

    # Prepare variables table
    vars_html = ""
    for var, val in sorted(tokens['variables'].items()):
        vars_html += f"""
        <tr>
            <td><code>{var}</code></td>
            <td><code>{val}</code></td>
            <td>
                <div class="var-preview-box" style="background-color: {val}; border: 1px solid rgba(255,255,255,0.1);"></div>
            </td>
        </tr>
        """

    # Prepare typography font list
    fonts_html = "".join(f"<span class='font-badge'>{font}</span>" for font in sorted(list(tokens['fonts'])))

    # Prepare media queries list
    mq_html = "".join(f"<div class='mq-item'><code>{mq}</code></div>" for mq in sorted(list(tokens['media_queries'])))

    # Inline CSS Variables to style preview components!
    preview_style = ""
    if tokens['variables']:
        preview_style = ":root {\n"
        for var, val in tokens['variables'].items():
            preview_style += f"  {var}: {val};\n"
        preview_style += "}"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Design System & Style Guide - {source_path}</title>
    <style>
        {preview_style}
        
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 30, 49, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #6366f1;
        }}
        body {{
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at top right, rgba(99, 102, 241, 0.1) 0%, transparent 60%);
            color: var(--text-color);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 1000px;
            width: 100%;
        }}
        header {{
            margin-bottom: 40px;
            padding: 30px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(12px);
            border-radius: 20px;
        }}
        h1 {{
            margin: 0 0 10px 0;
            font-size: 2.2rem;
            letter-spacing: -0.025em;
        }}
        .sub-header {{
            color: var(--text-muted);
            font-size: 0.95rem;
        }}
        
        h2 {{
            font-size: 1.5rem;
            margin: 40px 0 20px 0;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 8px;
            letter-spacing: -0.01em;
        }}
        
        .colors-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 20px;
        }}
        .color-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s;
        }}
        .color-card:hover {{
            transform: translateY(-2px);
        }}
        .color-preview {{
            height: 100px;
            width: 100%;
            background-color: #ccc;
        }}
        .color-info {{
            padding: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .color-value {{
            font-size: 0.85rem;
            font-family: monospace;
            color: #cbd5e1;
        }}
        .copy-btn {{
            background: rgba(255,255,255,0.08);
            border: none;
            color: #fff;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            cursor: pointer;
        }}
        .copy-btn:hover {{
            background: var(--accent);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: rgba(0,0,0,0.2);
            font-size: 0.9rem;
            font-weight: 600;
        }}
        td {{
            font-size: 0.9rem;
        }}
        .var-preview-box {{
            width: 24px;
            height: 24px;
            border-radius: 6px;
        }}
        
        .font-badge {{
            display: inline-block;
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 6px 12px;
            border-radius: 8px;
            margin-right: 10px;
            margin-bottom: 10px;
            font-size: 0.9rem;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }}
        
        .mq-item {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }}
        
        /* Interactive Live Previews section */
        .preview-box {{
            background: rgba(30, 41, 59, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 30px;
            margin-top: 20px;
        }}
        .preview-group {{
            margin-bottom: 30px;
        }}
        .preview-group:last-child {{
            margin-bottom: 0;
        }}
        .preview-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 15px;
            letter-spacing: 0.05em;
        }}
        
        /* Demo components styling using fallback variable bindings */
        .demo-btn {{
            background-color: var(--primary, var(--accent));
            color: var(--primary-foreground, #fff);
            padding: 10px 20px;
            border: none;
            border-radius: var(--radius, 8px);
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
            margin-right: 10px;
        }}
        .demo-btn:hover {{
            opacity: 0.9;
        }}
        .demo-btn-secondary {{
            background: transparent;
            border: 2px solid var(--border, var(--border-color));
            color: var(--foreground, #fff);
            padding: 8px 18px;
            border-radius: var(--radius, 8px);
            cursor: pointer;
            margin-right: 10px;
        }}
        .demo-badge {{
            display: inline-block;
            background-color: var(--muted, rgba(255,255,255,0.1));
            color: var(--muted-foreground, #cbd5e1);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        .toast-notification {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #10b981;
            color: #fff;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transform: translateY(100px);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            font-size: 0.9rem;
            z-index: 1000;
        }}
        .toast-show {{
            transform: translateY(0);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Design System & Style Guide</h1>
            <div class="sub-header">Parsed Source: <code>{source_path}</code></div>
        </header>

        <h2>Theme Custom Properties (CSS Variables)</h2>
        <table>
            <thead>
                <tr>
                    <th>Variable Name</th>
                    <th>Extracted Value</th>
                    <th>Visual Preview</th>
                </tr>
            </thead>
            <tbody>
                {vars_html or "<tr><td colspan='3'>No variables detected.</td></tr>"}
            </tbody>
        </table>

        <h2>Color Palette</h2>
        <div class="colors-grid">
            {colors_html or "<p>No explicit colors extracted.</p>"}
        </div>

        <h2>Typography Fonts</h2>
        <div>
            {fonts_html or "<p>No specific font families detected.</p>"}
        </div>

        <h2>Responsive Media Queries</h2>
        <div>
            {mq_html or "<p>No media queries detected.</p>"}
        </div>

        <h2>Interactive Component Playgrounds</h2>
        <div class="preview-box">
            <div class="preview-group">
                <div class="preview-label">Buttons (Styled with extracted vars)</div>
                <button class="demo-btn">Primary Action</button>
                <button class="demo-btn-secondary">Secondary Action</button>
            </div>
            
            <div class="preview-group">
                <div class="preview-label">Status Badges</div>
                <span class="demo-badge">Design Token System</span>
            </div>
        </div>
    </div>

    <div id="toast" class="toast-notification">Color copied to clipboard!</div>

    <script>
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                var toast = document.getElementById("toast");
                toast.classList.add("toast-show");
                setTimeout(function() {{
                    toast.classList.remove("toast-show");
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>
"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        print(f"[+] Style Guide successfully saved to: {output_path}")
    except Exception as e:
        print(f"[!] Error saving Style Guide: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="CSS Design System & Style Guide Generator")
    parser.add_argument("target", nargs="?", default=".", help="CSS file or directory to scan (default: current directory)")
    parser.add_argument("-o", "--output", help="HTML report output destination (default: css_style_guide.html)")
    args = parser.parse_args()

    target = args.target
    output_path = args.output or "css_style_guide.html"

    print(f"[*] Scanning '{target}' for CSS stylesheet declarations...")
    tokens, files_count = scan_and_parse(target)
    
    if files_count == 0:
        print(f"[!] No CSS files found matching the target path: {target}")
        return 1
        
    print(f"[+] Processed {files_count} stylesheet(s).")
    print(f"[+] Extracted: {len(tokens['colors'])} colors, {len(tokens['variables'])} variables, {len(tokens['fonts'])} fonts, {len(tokens['media_queries'])} media queries.")

    build_style_guide_html(tokens, target, output_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
