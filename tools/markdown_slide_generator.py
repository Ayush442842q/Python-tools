#!/usr/bin/env python3
"""
Markdown to HTML Slide Generator

Compiles structured Markdown documents (separated by `---` horizontal rules)
into responsive, standalone, and interactive HTML presentations with smooth 
transitions, multiple styling themes, and built-in keyboard controls.

Usage:
    python tools/markdown_slide_generator.py <markdown_file> --output <html_file> [options]

Example:
    python tools/markdown_slide_generator.py presentations/pitch.md --output pitch.html --theme dark
"""

import argparse
import os
import re
import sys
from typing import List, Dict

# Standard embedded CSS styles for slideshow
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --font-main: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --transition-speed: 0.5s;
        }}

        /* Themes definitions */
        .theme-dark {{
            --bg-color: #0f172a;
            --text-color: #f8fafc;
            --primary-color: #38bdf8;
            --accent-color: #ec4899;
            --card-bg: #1e293b;
            --border-color: #334155;
            --code-bg: #020617;
        }}

        .theme-light {{
            --bg-color: #f8fafc;
            --text-color: #0f172a;
            --primary-color: #0284c7;
            --accent-color: #db2777;
            --card-bg: #ffffff;
            --border-color: #e2e8f0;
            --code-bg: #f1f5f9;
        }}

        .theme-warm {{
            --bg-color: #fafaf9;
            --text-color: #1c1917;
            --primary-color: #ea580c;
            --accent-color: #0f766e;
            --card-bg: #f5f5f4;
            --border-color: #e7e5e4;
            --code-bg: #ede9fe;
        }}

        .theme-glass {{
            --bg-color: #0b0f19;
            --text-color: #e2e8f0;
            --primary-color: #818cf8;
            --accent-color: #f472b6;
            --card-bg: rgba(30, 41, 59, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --code-bg: rgba(15, 23, 42, 0.6);
            background-image: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(236, 72, 153, 0.15) 0%, transparent 40%);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: var(--font-main);
            background-color: var(--bg-color);
            color: var(--text-color);
            overflow: hidden;
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: background-color 0.4s ease, color 0.4s ease;
        }}

        /* Presentation Wrapper */
        #presentation-container {{
            width: 100%;
            height: 100%;
            position: relative;
            perspective: 1500px;
        }}

        /* Slide Styles */
        .slide {{
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 4rem;
            opacity: 0;
            visibility: hidden;
            transform: scale(0.9) translateZ(-100px);
            transition: opacity var(--transition-speed) ease,
                        visibility var(--transition-speed) ease,
                        transform var(--transition-speed) cubic-bezier(0.25, 1, 0.5, 1);
            z-index: 1;
            text-align: center;
        }}

        .slide.active {{
            opacity: 1;
            visibility: visible;
            transform: scale(1) translateZ(0);
            z-index: 10;
        }}

        /* Slide transitions */
        .slide.past {{
            opacity: 0;
            visibility: hidden;
            transform: scale(0.9) translateZ(-100px) translateX(-100%);
        }}

        .slide.future {{
            opacity: 0;
            visibility: hidden;
            transform: scale(0.9) translateZ(-100px) translateX(100%);
        }}

        /* Slide Content Formatting */
        .slide-content {{
            max-width: 900px;
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            text-align: left;
        }}

        /* Typography */
        h1 {{
            font-size: 4rem;
            font-weight: 800;
            line-height: 1.1;
            color: var(--primary-color);
            letter-spacing: -0.02em;
            text-align: center;
            margin-bottom: 1rem;
        }}

        h2 {{
            font-size: 2.8rem;
            font-weight: 700;
            color: var(--primary-color);
            border-bottom: 3px solid var(--border-color);
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
        }}

        h3 {{
            font-size: 2rem;
            font-weight: 600;
            color: var(--accent-color);
        }}

        p {{
            font-size: 1.5rem;
            line-height: 1.6;
            color: var(--text-color);
            opacity: 0.9;
        }}

        /* Lists */
        ul, ol {{
            margin-left: 2.5rem;
            font-size: 1.4rem;
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }}

        li strong {{
            color: var(--accent-color);
        }}

        /* Code Blocks */
        pre {{
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: left;
            overflow-x: auto;
            max-width: 100%;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}

        code {{
            font-family: var(--font-mono);
            font-size: 1.1rem;
            color: var(--text-color);
        }}

        :not(pre) > code {{
            background-color: var(--code-bg);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            font-size: 1.2rem;
            color: var(--accent-color);
        }}

        /* Blockquotes */
        blockquote {{
            border-left: 6px solid var(--primary-color);
            background-color: var(--card-bg);
            padding: 1.5rem 2rem;
            border-radius: 0 12px 12px 0;
            font-style: italic;
            font-size: 1.4rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}

        /* Links */
        a {{
            color: var(--primary-color);
            text-decoration: none;
            border-bottom: 2px dashed var(--primary-color);
            transition: color 0.2s, border-color 0.2s;
        }}

        a:hover {{
            color: var(--accent-color);
            border-bottom-color: var(--accent-color);
        }}

        /* Layout elements */
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 2rem;
            margin-top: 1rem;
        }}

        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }}

        .card:hover {{
            transform: translateY(-5px);
        }}

        /* Footer Navigation controls */
        #nav-controls {{
            position: absolute;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 1.5rem;
            z-index: 100;
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 0.6rem 1.5rem;
            border-radius: 30px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }}

        .nav-btn {{
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 1.5rem;
            cursor: pointer;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: background-color 0.2s, color 0.2s;
        }}

        .nav-btn:hover {{
            background-color: var(--border-color);
            color: var(--primary-color);
        }}

        #progress-indicator {{
            font-size: 1.1rem;
            font-weight: 600;
            min-width: 60px;
            text-align: center;
        }}

        /* ProgressBar */
        #progress-bar-container {{
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background-color: var(--border-color);
            z-index: 100;
        }}

        #progress-bar {{
            height: 100%;
            width: 0%;
            background-image: linear-gradient(to right, var(--primary-color), var(--accent-color));
            transition: width 0.3s ease;
        }}

        /* Touch Swipe hints */
        .instruction-hint {{
            position: absolute;
            bottom: 1rem;
            right: 2rem;
            font-size: 0.9rem;
            opacity: 0.5;
            pointer-events: none;
            font-family: var(--font-mono);
        }}
    </style>
</head>
<body class="theme-{theme}">

    <div id="presentation-container">
        {slides_html}
        
        <!-- Controls -->
        <div id="nav-controls">
            <button id="prev-btn" class="nav-btn" aria-label="Previous slide">←</button>
            <div id="progress-indicator">1 / 1</div>
            <button id="next-btn" class="nav-btn" aria-label="Next slide">→</button>
        </div>
    </div>
    
    <div id="progress-bar-container">
        <div id="progress-bar"></div>
    </div>

    <div class="instruction-hint">Use Left/Right arrows or Spacebar</div>

    <script>
        const slides = Array.from(document.querySelectorAll('.slide'));
        const totalSlides = slides.length;
        let currentIdx = 0;

        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const indicator = document.getElementById('progress-indicator');
        const progressBar = document.getElementById('progress-bar');

        function updateSlides() {{
            slides.forEach((slide, idx) => {{
                slide.classList.remove('active', 'past', 'future');
                if (idx === currentIdx) {{
                    slide.classList.add('active');
                }} else if (idx < currentIdx) {{
                    slide.classList.add('past');
                }} else {{
                    slide.classList.add('future');
                }}
            }});

            // Update footer
            indicator.innerText = `${{currentIdx + 1}} / ${{totalSlides}}`;
            
            // Update progress bar
            const percent = ((currentIdx + 1) / totalSlides) * 100;
            progressBar.style.width = `${{percent}}%`;
        }}

        function nextSlide() {{
            if (currentIdx < totalSlides - 1) {{
                currentIdx++;
                updateSlides();
            }}
        }}

        function prevSlide() {{
            if (currentIdx > 0) {{
                currentIdx--;
                updateSlides();
            }}
        }}

        // Event Listeners
        prevBtn.addEventListener('click', prevSlide);
        nextBtn.addEventListener('click', nextSlide);

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'Enter') {{
                e.preventDefault();
                nextSlide();
            }} else if (e.key === 'ArrowLeft') {{
                e.preventDefault();
                prevSlide();
            }}
        }});

        // Touch Navigation support
        let startX = 0;
        document.addEventListener('touchstart', (e) => {{
            startX = e.touches[0].clientX;
        }}, false);

        document.addEventListener('touchend', (e) => {{
            const endX = e.changedTouches[0].clientX;
            const diffX = startX - endX;
            if (Math.abs(diffX) > 50) {{
                if (diffX > 0) {{
                    nextSlide();
                }} else {{
                    prevSlide();
                }}
            }}
        }}, false);

        // Init
        updateSlides();
    </script>
</body>
</html>
"""

def parse_markdown_to_html(md_text: str) -> str:
    """A lightweight state-machine parser that converts basic Markdown structures to HTML."""
    html_lines = []
    in_list = False
    in_code_block = False
    
    lines = md_text.split('\n')
    for line in lines:
        stripped = line.strip()
        
        # Code block handling
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
                html_lines.append('</code></pre>')
            else:
                in_code_block = True
                lang = stripped[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">')
            continue
            
        if in_code_block:
            # Escape HTML characters inside code blocks
            escaped_code = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_lines.append(escaped_code)
            continue
            
        # Unordered lists
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                in_list = True
                html_lines.append('<ul>')
            item_text = line.replace('- ', '', 1).replace('* ', '', 1).strip()
            # Parse bold, italic, code inside list item
            item_text = parse_inline_elements(item_text)
            html_lines.append(f'<li>{item_text}</li>')
            continue
        else:
            if in_list:
                in_list = False
                html_lines.append('</ul>')
                
        # Headers
        if stripped.startswith('#'):
            h_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if h_match:
                level = len(h_match.group(1))
                h_text = parse_inline_elements(h_match.group(2))
                html_lines.append(f'<h{level}>{h_text}</h{level}>')
                continue
                
        # Blockquotes
        if stripped.startswith('>'):
            bq_text = parse_inline_elements(stripped[1:].strip())
            html_lines.append(f'<blockquote>{bq_text}</blockquote>')
            continue
            
        # Grid Cards shorthand e.g. [card] Content [/card]
        if stripped.startswith('[card]') and stripped.endswith('[/card]'):
            card_content = parse_inline_elements(stripped[6:-7].strip())
            html_lines.append(f'<div class="card">{card_content}</div>')
            continue
            
        # Grid layout container tags
        if stripped == '[grid]':
            html_lines.append('<div class="grid">')
            continue
        if stripped == '[/grid]':
            html_lines.append('</div>')
            continue
            
        # Empty lines
        if not stripped:
            continue
            
        # Default paragraph
        p_text = parse_inline_elements(stripped)
        html_lines.append(f'<p>{p_text}</p>')
        
    if in_list:
        html_lines.append('</ul>')
        
    return '\n'.join(html_lines)

def parse_inline_elements(text: str) -> str:
    """Parses inline elements like links, bold, italics, and inline code."""
    # 1. Escape HTML entities first to avoid parsing problems
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # 2. Bold: **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # 3. Italics: *text* or _text_
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)
    
    # 4. Inline code: `code`
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # 5. Markdown Links: [label](url)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank">\1</a>', text)
    
    # Put back escaped quotes inside HTML tags if generated by regexes
    # We didn't escape double quotes, so it is fine.
    return text

def build_slides(md_content: str) -> List[str]:
    """Splits markdown into slides based on horizontal rule delimiter '---'."""
    # Split slides. A slide starts/ends with a horizontal rule '---' on its own line
    raw_slides = re.split(r'^---+\s*$', md_content, flags=re.MULTILINE)
    
    slides_html = []
    for idx, slide_md in enumerate(raw_slides):
        slide_md = slide_md.strip()
        if not slide_md:
            continue
            
        # Convert this slide's markdown
        inner_html = parse_markdown_to_html(slide_md)
        
        # Build container
        slide_class = "slide"
        if idx == 0:
            slide_class += " active"
            
        slides_html.append(f'<div class="{slide_class}">\n<div class="slide-content">\n{inner_html}\n</div>\n</div>')
        
    return slides_html

def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Markdown slides into a standalone premium HTML slideshow.")
    parser.add_argument("markdown_file", help="Path to input Markdown (.md) file")
    parser.add_argument("-o", "--output", required=True, help="Path to write the output HTML (.html) file")
    parser.add_argument("-t", "--theme", choices=["dark", "light", "warm", "glass"], default="dark", help="Slide deck style theme (default: 'dark')")
    parser.add_argument("--title", default="Interactive Presentation", help="Title for the HTML document")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.markdown_file):
        print(f"Error: Input file '{args.markdown_file}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(args.markdown_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except Exception as e:
        print(f"Error reading markdown file: {e}", file=sys.stderr)
        return 1
        
    # Build list of slides
    slides_html_list = build_slides(md_content)
    if not slides_html_list:
        print("Warning: No slides detected. Slides must be separated by '---' on a line.", file=sys.stderr)
        
    slides_joined = '\n'.join(slides_html_list)
    
    # Generate final HTML
    html_output = HTML_TEMPLATE.format(
        title=args.title,
        theme=args.theme,
        slides_html=slides_joined
    )
    
    try:
        # Create output directory if it doesn't exist
        out_dir = os.path.dirname(args.output)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_output)
        print(f"Slideshow built successfully! Output written to {args.output}")
        print("Open the HTML file in any browser to play presentation.")
    except Exception as e:
        print(f"Error writing HTML output: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
